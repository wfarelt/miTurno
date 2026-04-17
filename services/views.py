from rest_framework import viewsets

from services.models import Service
from services.serializers import ServiceSerializer
from tenants.permissions import IsBusinessAdmin


class ServiceViewSet(viewsets.ModelViewSet):
	serializer_class = ServiceSerializer
	permission_classes = [IsBusinessAdmin]

	def get_queryset(self):
		return Service.objects.filter(business=self.request.tenant)

	def perform_create(self, serializer):
		serializer.save(business=self.request.tenant)

# Create your views here.
