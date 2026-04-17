from rest_framework import serializers

from staffs.models import Employee, EmployeeAvailability, EmployeeTimeOff


class EmployeeAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeAvailability
        fields = ("id", "day_of_week", "start_time", "end_time")
        read_only_fields = ("id",)


class EmployeeTimeOffSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeTimeOff
        fields = ("id", "date", "reason")
        read_only_fields = ("id",)


class EmployeeSerializer(serializers.ModelSerializer):
    availabilities = EmployeeAvailabilitySerializer(many=True, required=False)
    time_off_entries = EmployeeTimeOffSerializer(many=True, required=False)

    class Meta:
        model = Employee
        fields = (
            "id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "title",
            "is_active",
            "availabilities",
            "time_off_entries",
        )
        read_only_fields = ("id",)

    def create(self, validated_data):
        availabilities = validated_data.pop("availabilities", [])
        time_off_entries = validated_data.pop("time_off_entries", [])
        employee = Employee.objects.create(**validated_data)

        EmployeeAvailability.objects.bulk_create(
            [EmployeeAvailability(employee=employee, **item) for item in availabilities]
        )
        EmployeeTimeOff.objects.bulk_create(
            [EmployeeTimeOff(employee=employee, **item) for item in time_off_entries]
        )
        return employee

    def update(self, instance, validated_data):
        availabilities = validated_data.pop("availabilities", None)
        time_off_entries = validated_data.pop("time_off_entries", None)

        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()

        if availabilities is not None:
            instance.availabilities.all().delete()
            EmployeeAvailability.objects.bulk_create(
                [EmployeeAvailability(employee=instance, **item) for item in availabilities]
            )
        if time_off_entries is not None:
            instance.time_off_entries.all().delete()
            EmployeeTimeOff.objects.bulk_create(
                [EmployeeTimeOff(employee=instance, **item) for item in time_off_entries]
            )
        return instance