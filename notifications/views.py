from rest_framework import viewsets

from notifications.models import Notification
from notifications.serializers import NotificationAuditSerializer
from tenants.permissions import IsBusinessAdmin


class NotificationAuditViewSet(viewsets.ReadOnlyModelViewSet):
	serializer_class = NotificationAuditSerializer
	permission_classes = [IsBusinessAdmin]

	def get_queryset(self):
		queryset = Notification.objects.filter(
			business=self.request.tenant,
		).select_related("appointment", "outbox_entry")

		status_value = self.request.query_params.get("status")
		channel_value = self.request.query_params.get("channel")
		event_type = self.request.query_params.get("event_type")
		if status_value:
			queryset = queryset.filter(status=status_value)
		if channel_value:
			queryset = queryset.filter(channel=channel_value)
		if event_type:
			queryset = queryset.filter(event_type=event_type)
		return queryset.order_by("-created_at")
