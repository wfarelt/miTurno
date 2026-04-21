from django.contrib import admin

from staffs.models import Employee, EmployeeAvailability, EmployeeTimeOff


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"first_name",
		"last_name",
		"business",
		"email",
		"phone",
		"is_active",
	)
	list_filter = ("is_active", "business")
	search_fields = ("first_name", "last_name", "email", "phone", "business__name")
	raw_id_fields = ("business",)
	ordering = ("first_name", "last_name")


@admin.register(EmployeeAvailability)
class EmployeeAvailabilityAdmin(admin.ModelAdmin):
	list_display = ("id", "employee", "day_of_week", "start_time", "end_time", "created_at")
	list_filter = ("day_of_week", "employee__business")
	search_fields = ("employee__first_name", "employee__last_name", "employee__business__name")
	raw_id_fields = ("employee",)
	ordering = ("employee", "day_of_week", "start_time")


@admin.register(EmployeeTimeOff)
class EmployeeTimeOffAdmin(admin.ModelAdmin):
	list_display = ("id", "employee", "date", "reason", "created_at")
	list_filter = ("date", "employee__business")
	search_fields = ("employee__first_name", "employee__last_name", "reason")
	raw_id_fields = ("employee",)
	ordering = ("-date",)
