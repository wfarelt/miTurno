from datetime import timedelta

from rest_framework import serializers

from appointments.models import Appointment, SlotHold
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
        read_only_fields = ("id", "created_at", "client")

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
    hold_token = serializers.CharField(write_only=True)

    class Meta(AppointmentSerializer.Meta):
        fields = AppointmentSerializer.Meta.fields + ("hold_token",)


class SlotHoldSerializer(serializers.ModelSerializer):
    class Meta:
        model = SlotHold
        fields = (
            "token",
            "employee",
            "service",
            "starts_at",
            "ends_at",
            "expires_at",
        )
        read_only_fields = ("token", "expires_at")

    def validate(self, attrs):
        request = self.context["request"]
        tenant = request.tenant

        employee = attrs["employee"]
        service = attrs["service"]
        starts_at = attrs["starts_at"]
        ends_at = attrs["ends_at"]

        if employee.business_id != tenant.id:
            raise serializers.ValidationError("Employee does not belong to this business.")
        if service.business_id != tenant.id:
            raise serializers.ValidationError("Service does not belong to this business.")
        if ends_at <= starts_at:
            raise serializers.ValidationError("ends_at must be greater than starts_at.")

        expected_duration = timedelta(minutes=service.duration_minutes)
        if (ends_at - starts_at) != expected_duration:
            raise serializers.ValidationError(
                "Selected range does not match service duration."
            )

        overlapping_appointment = Appointment.objects.filter(
            business=tenant,
            employee=employee,
            starts_at__lt=ends_at,
            ends_at__gt=starts_at,
            status__in=[Appointment.Status.PENDING, Appointment.Status.CONFIRMED],
        ).exists()
        if overlapping_appointment:
            raise serializers.ValidationError("This time slot is already booked.")

        return attrs