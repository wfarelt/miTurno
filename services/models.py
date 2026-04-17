from django.db import models

from tenants.models import Business, TimeStampedModel


class Service(TimeStampedModel):
	business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="services")
	name = models.CharField(max_length=120)
	description = models.TextField(blank=True)
	duration_minutes = models.PositiveIntegerField()
	price = models.DecimalField(max_digits=10, decimal_places=2)
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ["name"]
		constraints = [
			models.UniqueConstraint(
				fields=["business", "name"],
				name="uq_service_business_name",
			)
		]

	def __str__(self) -> str:
		return f"{self.name} ({self.business_id})"

# Create your models here.
