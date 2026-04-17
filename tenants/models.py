from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		abstract = True


class Business(TimeStampedModel):
	name = models.CharField(max_length=200)
	slug = models.SlugField(unique=True)
	subdomain = models.SlugField(unique=True, blank=True, null=True)
	timezone = models.CharField(max_length=64, default="UTC")
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ["name"]

	def __str__(self) -> str:
		return self.name


class TenantMembership(TimeStampedModel):
	class Role(models.TextChoices):
		OWNER_ADMIN = "OWNER_ADMIN", "Owner Admin"
		MANAGER = "MANAGER", "Manager"
		EMPLOYEE = "EMPLOYEE", "Employee"
		CLIENT = "CLIENT", "Client"

	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="tenant_memberships",
	)
	business = models.ForeignKey(
		Business,
		on_delete=models.CASCADE,
		related_name="memberships",
	)
	role = models.CharField(max_length=20, choices=Role.choices)
	is_active = models.BooleanField(default=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=["user", "business"],
				name="uq_membership_user_business",
			)
		]

	def __str__(self) -> str:
		return f"{self.user_id}:{self.business_id}:{self.role}"

# Create your models here.
