from rest_framework.routers import DefaultRouter

from notifications.views import NotificationAuditViewSet

router = DefaultRouter()
router.register("", NotificationAuditViewSet, basename="notification-audit")

urlpatterns = router.urls
