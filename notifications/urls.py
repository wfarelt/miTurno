from django.urls import path
from rest_framework.routers import DefaultRouter

from notifications.views import NotificationAuditViewSet, NotificationDashboardView, WhatsAppWebhookView

router = DefaultRouter()
router.register("", NotificationAuditViewSet, basename="notification-audit")

urlpatterns = [
	path("dashboard/", NotificationDashboardView.as_view(), name="notification-dashboard"),
	path("webhooks/whatsapp/", WhatsAppWebhookView.as_view(), name="whatsapp-webhook"),
] + router.urls
