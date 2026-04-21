from django.urls import path
from rest_framework.routers import DefaultRouter

from notifications.views import (
	NotificationAuditViewSet,
	NotificationDashboardView,
	TelegramWebhookView,
	WhatsAppWebhookView,
)

router = DefaultRouter()
router.register("", NotificationAuditViewSet, basename="notification-audit")

urlpatterns = [
	path("dashboard/", NotificationDashboardView.as_view(), name="notification-dashboard"),
	path("webhooks/whatsapp/", WhatsAppWebhookView.as_view(), name="whatsapp-webhook"),
	path("webhooks/telegram/", TelegramWebhookView.as_view(), name="telegram-webhook"),
] + router.urls
