from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, TemplateView, UpdateView, View

from appointments.models import Appointment
from notifications.channels import TelegramChannel
from panel.forms import EmployeeForm, ServiceForm
from services.models import Service
from staffs.models import Employee
from tenants.models import TenantMembership


class PanelLoginView(LoginView):
    template_name = "panel/login.html"
    redirect_authenticated_user = True
    next_page = reverse_lazy("panel:dashboard")


class PanelLogoutView(LogoutView):
    next_page = reverse_lazy("panel:login")


class PanelAccessMixin:
    admin_roles = (TenantMembership.Role.OWNER_ADMIN, TenantMembership.Role.MANAGER)

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("panel:login")

        if request.user.is_superuser:
            return redirect("admin-dashboard")

        self.memberships = list(
            TenantMembership.objects.select_related("business")
            .filter(
                user=request.user,
                is_active=True,
                role__in=self.admin_roles,
                business__is_active=True,
            )
            .order_by("business__name")
        )
        if not self.memberships:
            return redirect("admin:index")

        self.active_business = self._resolve_active_business(request)
        return super().dispatch(request, *args, **kwargs)

    def _resolve_active_business(self, request):
        requested_slug = request.GET.get("business") or request.session.get("panel_business_slug")
        membership_by_slug = {m.business.slug: m for m in self.memberships}

        if requested_slug and requested_slug in membership_by_slug:
            request.session["panel_business_slug"] = requested_slug
            return membership_by_slug[requested_slug].business

        default_business = self.memberships[0].business
        request.session["panel_business_slug"] = default_business.slug
        return default_business

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["memberships"] = self.memberships
        context["active_business"] = self.active_business
        return context


class DashboardView(PanelAccessMixin, TemplateView):
    template_name = "panel/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        business = self.active_business
        context["counts"] = {
            "services": Service.objects.filter(business=business).count(),
            "employees": Employee.objects.filter(business=business).count(),
            "appointments": Appointment.objects.filter(business=business).count(),
        }
        context["recent_appointments"] = Appointment.objects.filter(business=business).select_related(
            "employee", "service", "client"
        )[:10]
        return context


class BusinessSelectView(PanelAccessMixin, View):
    def get(self, request, slug):
        for membership in self.memberships:
            if membership.business.slug == slug:
                request.session["panel_business_slug"] = slug
                return redirect("panel:dashboard")
        raise Http404("Business not found")


class ServiceListView(PanelAccessMixin, ListView):
    model = Service
    template_name = "panel/services_list.html"
    context_object_name = "services"

    def get_queryset(self):
        return Service.objects.filter(business=self.active_business).order_by("name")


class ServiceCreateView(PanelAccessMixin, CreateView):
    model = Service
    form_class = ServiceForm
    template_name = "panel/service_form.html"
    success_url = reverse_lazy("panel:services-list")

    def form_valid(self, form):
        form.instance.business = self.active_business
        return super().form_valid(form)


class ServiceUpdateView(PanelAccessMixin, UpdateView):
    model = Service
    form_class = ServiceForm
    template_name = "panel/service_form.html"
    success_url = reverse_lazy("panel:services-list")

    def get_queryset(self):
        return Service.objects.filter(business=self.active_business)


class EmployeeListView(PanelAccessMixin, ListView):
    model = Employee
    template_name = "panel/employees_list.html"
    context_object_name = "employees"

    def get_queryset(self):
        return Employee.objects.filter(business=self.active_business).order_by("first_name", "last_name")


class EmployeeCreateView(PanelAccessMixin, CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "panel/employee_form.html"
    success_url = reverse_lazy("panel:employees-list")

    def form_valid(self, form):
        form.instance.business = self.active_business
        return super().form_valid(form)


class EmployeeUpdateView(PanelAccessMixin, UpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "panel/employee_form.html"
    success_url = reverse_lazy("panel:employees-list")

    def get_queryset(self):
        return Employee.objects.filter(business=self.active_business)


class EmployeeTelegramTestView(PanelAccessMixin, View):
    def post(self, request, pk):
        employee = get_object_or_404(Employee, pk=pk, business=self.active_business)

        chat_id = (employee.telegram_chat_id or "").strip()
        if not chat_id:
            messages.error(
                request,
                "Este peluquero no tiene telegram_chat_id. Vinculalo primero desde el bot.",
            )
            return redirect("panel:employees-list")

        channel = TelegramChannel()
        result = channel.send(
            chat_id=chat_id,
            body=(
                "Mensaje de prueba desde miTurno. "
                f"Hola {employee.first_name}, tu integracion de Telegram esta activa."
            ),
        )
        if result.ok:
            messages.success(request, "Mensaje de prueba enviado por Telegram.")
        else:
            messages.error(request, f"No se pudo enviar el mensaje de prueba: {result.error}")

        return redirect("panel:employees-list")
