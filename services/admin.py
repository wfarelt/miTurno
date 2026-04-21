from django.contrib import admin

from services.models import Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"name",
		"business",
		"duration_minutes",
		"price",
		"is_active",
		"created_at",
	)
	list_filter = ("is_active", "business")
	search_fields = ("name", "business__name", "business__slug")
	raw_id_fields = ("business",)
	ordering = ("name",)
