from django.conf import settings
from django.db import models

from services.models import Service
from staffs.models import Employee
from tenants.models import Business, TimeStampedModel


class SlotHold(TimeStampedModel):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="slot_holds")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="slot_holds")
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="slot_holds")
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="slot_holds")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    token = models.CharField(max_length=64, unique=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="ck_slot_hold_time_order",
            )
        ]


class Appointment(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        NO_SHOW = "NO_SHOW", "No Show"

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="appointments")
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="appointments")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="appointments")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="appointments")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-starts_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="ck_appointment_time_order",
            ),
            models.UniqueConstraint(
                fields=["employee", "starts_at", "ends_at"],
                name="uq_appointment_employee_slot",
            ),
        ]
