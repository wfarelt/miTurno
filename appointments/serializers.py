from rest_framework import serializers

from appointments.models import Appointment
from services.models import Service
from staffs.models import Employee


class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = (
            "id",
            "client",
            "employee",
            "service",
            "starts_at",
            "ends_at",
            "status",
            "notes",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def validate(self, attrs):
        request = self.context["request"]
        tenant = request.tenant
        employee = attrs.get("employee", getattr(self.instance, "employee", None))
        service = attrs.get("service", getattr(self.instance, "service", None))

        if employee and employee.business_id != tenant.id:
            raise serializers.ValidationError("Employee does not belong to this business.")
        if service and service.business_id != tenant.id:
            raise serializers.ValidationError("Service does not belong to this business.")

        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))

        overlapping = Appointment.objects.filter(
            employee=employee,
            starts_at__lt=ends_at,
            ends_at__gt=starts_at,
        ).exclude(pk=getattr(self.instance, "pk", None))
        if overlapping.exists():
            raise serializers.ValidationError("This time slot is already booked for the employee.")

        return attrs


class AppointmentCreateSerializer(AppointmentSerializer):
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all())