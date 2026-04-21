from django.urls import path

from panel.views import (
    BusinessSelectView,
    DashboardView,
    EmployeeCreateView,
    EmployeeListView,
    EmployeeTelegramTestView,
    EmployeeUpdateView,
    PanelLoginView,
    PanelLogoutView,
    ServiceCreateView,
    ServiceListView,
    ServiceUpdateView,
)

app_name = "panel"

urlpatterns = [
    path("login/", PanelLoginView.as_view(), name="login"),
    path("logout/", PanelLogoutView.as_view(), name="logout"),
    path("", DashboardView.as_view(), name="dashboard"),
    path("business/<slug:slug>/", BusinessSelectView.as_view(), name="business-select"),
    path("services/", ServiceListView.as_view(), name="services-list"),
    path("services/new/", ServiceCreateView.as_view(), name="services-create"),
    path("services/<int:pk>/edit/", ServiceUpdateView.as_view(), name="services-edit"),
    path("employees/", EmployeeListView.as_view(), name="employees-list"),
    path("employees/new/", EmployeeCreateView.as_view(), name="employees-create"),
    path("employees/<int:pk>/edit/", EmployeeUpdateView.as_view(), name="employees-edit"),
    path("employees/<int:pk>/telegram-test/", EmployeeTelegramTestView.as_view(), name="employees-telegram-test"),
]
