from rest_framework.routers import DefaultRouter

from staffs.views import EmployeeViewSet

router = DefaultRouter()
router.register("", EmployeeViewSet, basename="employee")

urlpatterns = router.urls
