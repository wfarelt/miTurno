import hashlib
import hmac

from django.conf import settings
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.models import Notification
from notifications.serializers import NotificationAuditSerializer
from notifications.services import process_whatsapp_webhook
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


class WhatsAppWebhookView(APIView):
	authentication_classes = []
	permission_classes = [AllowAny]

	def get(self, request):
		verify_token = request.query_params.get("hub.verify_token")
		challenge = request.query_params.get("hub.challenge")
		mode = request.query_params.get("hub.mode")

		expected = getattr(settings, "WHATSAPP_WEBHOOK_VERIFY_TOKEN", "")
		if mode == "subscribe" and expected and verify_token == expected:
			return HttpResponse(challenge or "", status=200)
		return Response({"detail": "Webhook verification failed."}, status=403)

	def post(self, request):
		app_secret = getattr(settings, "WHATSAPP_APP_SECRET", "")
		if app_secret:
			signature = request.headers.get("X-Hub-Signature-256", "")
			expected = "sha256=" + hmac.new(
				app_secret.encode("utf-8"),
				msg=request.body,
				digestmod=hashlib.sha256,
			).hexdigest()
			if not signature or not hmac.compare_digest(signature, expected):
				return Response({"detail": "Invalid webhook signature."}, status=403)

		result = process_whatsapp_webhook(request.data or {})
		return Response(result, status=200)
