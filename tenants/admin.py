from django.contrib import admin

from tenants.models import Business, TenantMembership


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
	list_display = ("id", "name", "slug", "subdomain", "timezone", "is_active", "created_at")
	list_filter = ("is_active", "timezone")
	search_fields = ("name", "slug", "subdomain")
	ordering = ("name",)


@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
	list_display = ("id", "user", "business", "role", "is_active", "created_at")
	list_filter = ("role", "is_active", "business")
	search_fields = ("user__email", "user__username", "business__name", "business__slug")
	raw_id_fields = ("user", "business")
	ordering = ("-created_at",)
