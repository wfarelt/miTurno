from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
	list_display = (
		"id",
		"email",
		"username",
		"first_name",
		"last_name",
		"is_staff",
		"is_active",
		"is_phone_verified",
	)
	list_filter = ("is_staff", "is_superuser", "is_active", "is_phone_verified", "groups")
	search_fields = ("email", "username", "first_name", "last_name", "phone")
	ordering = ("id",)
