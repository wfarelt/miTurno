from rest_framework import viewsets

from staffs.models import Employee
from staffs.serializers import EmployeeSerializer
from tenants.permissions import IsBusinessAdmin


class EmployeeViewSet(viewsets.ModelViewSet):
	serializer_class = EmployeeSerializer
	permission_classes = [IsBusinessAdmin]

	def get_queryset(self):
		return Employee.objects.filter(business=self.request.tenant).prefetch_related(
			"availabilities",
			"time_off_entries",
		)

	def perform_create(self, serializer):
		serializer.save(business=self.request.tenant)

# Create your views here.
