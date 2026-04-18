from django.db import models

from appointments.models import Appointment
from tenants.models import Business, TimeStampedModel


class Notification(TimeStampedModel):
	class Channel(models.TextChoices):
		EMAIL = "EMAIL", "Email"
		WHATSAPP = "WHATSAPP", "WhatsApp"

	class EventType(models.TextChoices):
		BOOKING_CREATED = "BOOKING_CREATED", "Booking Created"
		APPOINTMENT_CONFIRMED = "APPOINTMENT_CONFIRMED", "Appointment Confirmed"
		REMINDER_24H = "REMINDER_24H", "Reminder 24h"
		REMINDER_1H = "REMINDER_1H", "Reminder 1h"

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
	event_type = models.CharField(max_length=32, choices=EventType.choices)
	scheduled_for = models.DateTimeField()
	sent_at = models.DateTimeField(null=True, blank=True)
	payload = models.JSONField(default=dict, blank=True)
	retry_count = models.PositiveSmallIntegerField(default=0)
	error_message = models.TextField(blank=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=["appointment", "channel", "event_type"],
				name="uq_notification_appointment_channel_event",
			)
		]


class NotificationOutbox(TimeStampedModel):
	class Status(models.TextChoices):
		PENDING = "PENDING", "Pending"
		PROCESSING = "PROCESSING", "Processing"
		DELIVERED = "DELIVERED", "Delivered"
		FAILED = "FAILED", "Failed"

	business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="notification_outbox")
	notification = models.OneToOneField(
		Notification,
		on_delete=models.CASCADE,
		related_name="outbox_entry",
	)
	status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
	attempts = models.PositiveSmallIntegerField(default=0)
	next_attempt_at = models.DateTimeField()
	locked_at = models.DateTimeField(null=True, blank=True)
	delivered_at = models.DateTimeField(null=True, blank=True)
	last_error = models.TextField(blank=True)
	provider_message_id = models.CharField(max_length=128, unique=True, null=True, blank=True)
	provider_status = models.CharField(max_length=64, blank=True)
	provider_payload = models.JSONField(default=dict, blank=True)

	class Meta:
		indexes = [
			models.Index(fields=["status", "next_attempt_at"]),
		]

# Create your models here.
