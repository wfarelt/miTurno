from rest_framework import serializers

from tenants.models import Business


class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ("id", "name", "slug", "subdomain", "timezone", "is_active")
        read_only_fields = ("id", "slug", "subdomain")