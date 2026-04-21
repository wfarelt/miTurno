from django.contrib import admin

from notifications.models import Notification, NotificationOutbox


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"business",
		"appointment",
		"channel",
		"event_type",
		"status",
		"scheduled_for",
		"sent_at",
		"retry_count",
	)
	list_filter = ("channel", "event_type", "status", "business")
	search_fields = ("appointment__id", "business__name", "error_message")
	raw_id_fields = ("business", "appointment")
	ordering = ("-created_at",)


@admin.register(NotificationOutbox)
class NotificationOutboxAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"business",
		"notification",
		"status",
		"attempts",
		"next_attempt_at",
		"delivered_at",
		"provider_status",
	)
	list_filter = ("status", "business", "provider_status")
	search_fields = ("provider_message_id", "last_error", "notification__id")
	raw_id_fields = ("business", "notification")
	ordering = ("next_attempt_at",)
