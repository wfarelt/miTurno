from rest_framework import serializers

from services.models import Service


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = (
            "id",
            "name",
            "description",
            "duration_minutes",
            "price",
            "is_active",
        )
        read_only_fields = ("id",)