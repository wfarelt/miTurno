from django.db import models

from tenants.models import Business, TimeStampedModel


class Employee(TimeStampedModel):
	business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="employees")
	first_name = models.CharField(max_length=100)
	last_name = models.CharField(max_length=100)
	email = models.EmailField(blank=True)
	phone = models.CharField(max_length=20, blank=True)
	telegram_username = models.CharField(max_length=64, blank=True)
	telegram_chat_id = models.CharField(max_length=64, blank=True)
	title = models.CharField(max_length=100, blank=True)
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ["first_name", "last_name"]

	def __str__(self) -> str:
		return f"{self.first_name} {self.last_name}".strip()


class EmployeeAvailability(TimeStampedModel):
	employee = models.ForeignKey(
		Employee,
		on_delete=models.CASCADE,
		related_name="availabilities",
	)
	day_of_week = models.PositiveSmallIntegerField()
	start_time = models.TimeField()
	end_time = models.TimeField()

	class Meta:
		constraints = [
			models.CheckConstraint(
				condition=models.Q(end_time__gt=models.F("start_time")),
				name="ck_employee_availability_time_order",
			),
			models.UniqueConstraint(
				fields=["employee", "day_of_week", "start_time", "end_time"],
				name="uq_employee_availability_block",
			),
		]


class EmployeeTimeOff(TimeStampedModel):
	employee = models.ForeignKey(
		Employee,
		on_delete=models.CASCADE,
		related_name="time_off_entries",
	)
	date = models.DateField()
	reason = models.CharField(max_length=255, blank=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=["employee", "date"],
				name="uq_employee_time_off_date",
			)
		]

# Create your models here.
