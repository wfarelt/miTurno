from rest_framework.routers import DefaultRouter

from services.views import ServiceViewSet

router = DefaultRouter()
router.register("", ServiceViewSet, basename="service")

urlpatterns = router.urls
