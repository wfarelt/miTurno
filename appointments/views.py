from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from appointments.models import Appointment
from appointments.serializers import AppointmentCreateSerializer, AppointmentSerializer
from tenants.permissions import IsTenantMember


class AppointmentViewSet(viewsets.ModelViewSet):
	permission_classes = [permissions.IsAuthenticated, IsTenantMember]

	def get_queryset(self):
		queryset = Appointment.objects.filter(business=self.request.tenant).select_related(
			"client",
			"employee",
			"service",
		)
		role_values = set(
			self.request.user.tenant_memberships.filter(
				business=self.request.tenant,
				is_active=True,
			).values_list("role", flat=True)
		)
		if "CLIENT" in role_values:
			queryset = queryset.filter(client=self.request.user)
		return queryset

	def get_serializer_class(self):
		if self.action == "create":
			return AppointmentCreateSerializer
		return AppointmentSerializer

	def perform_create(self, serializer):
		serializer.save(business=self.request.tenant, client=self.request.user)

	@action(detail=False, methods=["get"], url_path="availability")
	def availability(self, request):
		employee_id = request.query_params.get("employee_id")
		service_duration = int(request.query_params.get("duration", 30))
		date_raw = request.query_params.get("date")
		if not date_raw or not employee_id:
			return Response(
				{"detail": "date and employee_id are required query params."},
				status=400,
			)

		date = datetime.fromisoformat(date_raw).date()
		start = timezone.make_aware(datetime.combine(date, datetime.min.time())).replace(hour=9)
		end = start.replace(hour=18)
		slot_delta = timedelta(minutes=30)
		duration_delta = timedelta(minutes=service_duration)

		appointments = Appointment.objects.filter(
			business=request.tenant,
			employee_id=employee_id,
			starts_at__date=date,
			status__in=[Appointment.Status.PENDING, Appointment.Status.CONFIRMED],
		)

		slots = []
		cursor = start
		while cursor + duration_delta <= end:
			candidate_end = cursor + duration_delta
			conflict = appointments.filter(
				starts_at__lt=candidate_end,
				ends_at__gt=cursor,
			).exists()
			if not conflict:
				slots.append(
					{
						"starts_at": cursor.isoformat(),
						"ends_at": candidate_end.isoformat(),
					}
				)
			cursor += slot_delta

		return Response(slots)

# Create your views here.
