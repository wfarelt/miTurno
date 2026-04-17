from datetime import datetime, timedelta
from secrets import token_urlsafe

from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from appointments.models import Appointment, SlotHold
from appointments.serializers import (
	AppointmentCreateSerializer,
	AppointmentSerializer,
	SlotHoldSerializer,
)
from staffs.models import Employee
from tenants.permissions import IsTenantMember


class ConflictError(APIException):
	status_code = 409
	default_detail = "Conflict while booking this appointment."
	default_code = "conflict"


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
		hold_token = serializer.validated_data.pop("hold_token")
		starts_at = serializer.validated_data["starts_at"]
		ends_at = serializer.validated_data["ends_at"]
		employee = serializer.validated_data["employee"]
		service = serializer.validated_data["service"]

		now = timezone.now()
		with transaction.atomic():
			locked_employee = Employee.objects.select_for_update().get(
				pk=employee.pk,
				business=self.request.tenant,
			)
			locked_hold = SlotHold.objects.select_for_update().filter(
				token=hold_token,
				business=self.request.tenant,
				client=self.request.user,
				employee=locked_employee,
				service=service,
				starts_at=starts_at,
				ends_at=ends_at,
				expires_at__gt=now,
			).first()
			if locked_hold is None:
				raise ConflictError(
					"Invalid or expired hold token for this slot."
				)

			has_conflict = Appointment.objects.select_for_update().filter(
				business=self.request.tenant,
				employee=locked_employee,
				starts_at__lt=ends_at,
				ends_at__gt=starts_at,
				status__in=[Appointment.Status.PENDING, Appointment.Status.CONFIRMED],
			).exists()
			if has_conflict:
				raise ConflictError("This slot is no longer available.")

			serializer.save(
				business=self.request.tenant,
				client=self.request.user,
				employee=locked_employee,
			)
			locked_hold.delete()

	@action(detail=False, methods=["post"], url_path="holds")
	def create_hold(self, request):
		serializer = SlotHoldSerializer(data=request.data, context={"request": request})
		serializer.is_valid(raise_exception=True)

		now = timezone.now()
		expires_at = now + timedelta(minutes=5)
		with transaction.atomic():
			employee = Employee.objects.select_for_update().get(
				pk=serializer.validated_data["employee"].pk,
				business=request.tenant,
			)

			starts_at = serializer.validated_data["starts_at"]
			ends_at = serializer.validated_data["ends_at"]

			conflicting_appointment = Appointment.objects.select_for_update().filter(
				business=request.tenant,
				employee=employee,
				starts_at__lt=ends_at,
				ends_at__gt=starts_at,
				status__in=[Appointment.Status.PENDING, Appointment.Status.CONFIRMED],
			).exists()
			if conflicting_appointment:
				return Response({"detail": "This slot is already booked."}, status=409)

			conflicting_hold = SlotHold.objects.select_for_update().filter(
				business=request.tenant,
				employee=employee,
				starts_at__lt=ends_at,
				ends_at__gt=starts_at,
				expires_at__gt=now,
			).exists()
			if conflicting_hold:
				return Response({"detail": "This slot is temporarily locked."}, status=409)

			hold = SlotHold.objects.create(
				business=request.tenant,
				client=request.user,
				employee=employee,
				service=serializer.validated_data["service"],
				starts_at=starts_at,
				ends_at=ends_at,
				expires_at=expires_at,
				token=token_urlsafe(24),
			)

		response = SlotHoldSerializer(hold)
		return Response(response.data, status=201)

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
