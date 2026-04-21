import hashlib
import hmac
from datetime import datetime, time

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.models import Notification
from notifications.serializers import NotificationAuditSerializer
from notifications.services import (
	build_notification_dashboard,
	process_telegram_webhook,
	process_whatsapp_webhook,
)
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


class NotificationDashboardView(APIView):
	permission_classes = [IsBusinessAdmin]

	def get(self, request):
		start_at = self._parse_datetime_param(request.query_params.get("start_at"), start_of_day=True)
		end_at = self._parse_datetime_param(request.query_params.get("end_at"), start_of_day=False)

		if request.query_params.get("start_at") and start_at is None:
			return Response(
				{"detail": "Invalid start_at. Use ISO datetime or YYYY-MM-DD."},
				status=400,
			)
		if request.query_params.get("end_at") and end_at is None:
			return Response(
				{"detail": "Invalid end_at. Use ISO datetime or YYYY-MM-DD."},
				status=400,
			)

		data = build_notification_dashboard(
			business=request.tenant,
			start_at=start_at,
			end_at=end_at,
		)
		return Response(data)

	def _parse_datetime_param(self, raw_value, start_of_day: bool):
		if not raw_value:
			return None
		dt = parse_datetime(raw_value)
		if dt is not None:
			if timezone.is_naive(dt):
				dt = timezone.make_aware(dt, timezone.get_current_timezone())
			return dt

		d = parse_date(raw_value)
		if d is None:
			return None

		if start_of_day:
			result = datetime.combine(d, time.min)
		else:
			result = datetime.combine(d, time.max)
		return timezone.make_aware(result, timezone.get_current_timezone())


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


class TelegramWebhookView(APIView):
	authentication_classes = []
	permission_classes = [AllowAny]

	def post(self, request):
		expected = getattr(settings, "TELEGRAM_WEBHOOK_SECRET_TOKEN", "")
		if expected:
			received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
			if received != expected:
				return Response({"detail": "Invalid Telegram webhook secret."}, status=403)

		result = process_telegram_webhook(request.data or {})
		return Response(result, status=200)
