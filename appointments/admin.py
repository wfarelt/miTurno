from django.contrib import admin

from appointments.models import Appointment, SlotHold


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"business",
		"client",
		"employee",
		"service",
		"starts_at",
		"ends_at",
		"status",
	)
	list_filter = ("status", "business", "employee")
	search_fields = (
		"client__email",
		"client__username",
		"employee__first_name",
		"employee__last_name",
		"service__name",
		"business__name",
	)
	raw_id_fields = ("business", "client", "employee", "service")
	ordering = ("-starts_at",)


@admin.register(SlotHold)
class SlotHoldAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"business",
		"client",
		"employee",
		"service",
		"starts_at",
		"expires_at",
	)
	list_filter = ("business", "employee")
	search_fields = ("token", "client__email", "business__name")
	raw_id_fields = ("business", "client", "employee", "service")
	ordering = ("-created_at",)
