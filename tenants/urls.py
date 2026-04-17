from django.urls import path

from tenants.views import MyBusinessView

urlpatterns = [
    path("me/", MyBusinessView.as_view(), name="my-business"),
]
