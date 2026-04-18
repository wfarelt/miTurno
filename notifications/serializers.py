from rest_framework import serializers

from notifications.models import Notification, NotificationOutbox


class NotificationOutboxSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationOutbox
        fields = (
            "status",
            "attempts",
            "next_attempt_at",
            "delivered_at",
            "last_error",
            "provider_message_id",
            "provider_status",
            "provider_payload",
        )


class NotificationAuditSerializer(serializers.ModelSerializer):
    outbox_entry = NotificationOutboxSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = (
            "id",
            "appointment",
            "channel",
            "event_type",
            "status",
            "scheduled_for",
            "sent_at",
            "retry_count",
            "error_message",
            "payload",
            "created_at",
            "outbox_entry",
        )
