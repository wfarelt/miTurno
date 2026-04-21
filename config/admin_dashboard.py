from datetime import timedelta

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.template.response import TemplateResponse
from django.utils import timezone

from accounts.models import User
from appointments.models import Appointment
from notifications.models import Notification, NotificationOutbox
from services.models import Service
from staffs.models import Employee
from tenants.models import Business, TenantMembership


def superadmin_dashboard(request):
    if not request.user.is_superuser:
        raise PermissionDenied("Superadmin access required.")

    now = timezone.now()
    last_7_days = now - timedelta(days=7)

    appointment_status = list(
        Appointment.objects.values("status").annotate(total=Count("id")).order_by("status")
    )
    notification_status = list(
        Notification.objects.values("status").annotate(total=Count("id")).order_by("status")
    )
    notification_channels = list(
        Notification.objects.values("channel").annotate(total=Count("id")).order_by("channel")
    )
    outbox_status = list(
        NotificationOutbox.objects.values("status").annotate(total=Count("id")).order_by("status")
    )

    appointments_per_day = list(
        Appointment.objects.filter(starts_at__gte=last_7_days)
        .annotate(day=TruncDate("starts_at"))
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )

    context = {
        **admin.site.each_context(request),
        "title": "Platform Dashboard",
        "kpis": {
            "users": User.objects.count(),
            "businesses": Business.objects.count(),
            "active_businesses": Business.objects.filter(is_active=True).count(),
            "memberships": TenantMembership.objects.count(),
            "services": Service.objects.count(),
            "employees": Employee.objects.count(),
            "appointments": Appointment.objects.count(),
            "notifications": Notification.objects.count(),
        },
        "appointment_status": appointment_status,
        "notification_status": notification_status,
        "notification_channels": notification_channels,
        "outbox_status": outbox_status,
        "appointments_per_day": appointments_per_day,
        "recent_businesses": Business.objects.order_by("-created_at")[:8],
        "dashboard_generated_at": now,
    }
    return TemplateResponse(request, "admin/platform_dashboard.html", context)