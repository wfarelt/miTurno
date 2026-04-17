from django.db import models

from appointments.models import Appointment
from tenants.models import Business, TimeStampedModel


class Notification(TimeStampedModel):
	class Channel(models.TextChoices):
		EMAIL = "EMAIL", "Email"
		WHATSAPP = "WHATSAPP", "WhatsApp"

	class Status(models.TextChoices):
		PENDING = "PENDING", "Pending"
		SENT = "SENT", "Sent"
		FAILED = "FAILED", "Failed"

	business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="notifications")
	appointment = models.ForeignKey(
		Appointment,
		on_delete=models.CASCADE,
		related_name="notifications",
	)
	channel = models.CharField(max_length=16, choices=Channel.choices)
	status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
	scheduled_for = models.DateTimeField()
	sent_at = models.DateTimeField(null=True, blank=True)
	payload = models.JSONField(default=dict, blank=True)

# Create your models here.
