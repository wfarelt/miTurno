from rest_framework import generics

from tenants.permissions import IsBusinessAdmin
from tenants.serializers import BusinessSerializer


class MyBusinessView(generics.RetrieveUpdateAPIView):
	serializer_class = BusinessSerializer
	permission_classes = [IsBusinessAdmin]

	def get_object(self):
		return self.request.tenant

# Create your views here.
