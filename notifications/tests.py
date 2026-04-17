from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from appointments.models import Appointment
from notifications.models import Notification
from notifications.services import (
	dispatch_due_notifications,
	schedule_booking_notifications,
	schedule_confirmation_and_reminders,
)
from services.models import Service
from staffs.models import Employee
from tenants.models import Business, TenantMembership


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class NotificationFlowTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.business = Business.objects.create(name="Demo Salon", slug="demo-salon")
		self.client_user = user_model.objects.create_user(
			email="notify-client@example.com",
			username="notify-client",
			password="testpass123",
		)
		TenantMembership.objects.create(
			user=self.client_user,
			business=self.business,
			role=TenantMembership.Role.CLIENT,
		)
		self.employee = Employee.objects.create(
			business=self.business,
			first_name="Ana",
			last_name="Barber",
		)
		self.service = Service.objects.create(
			business=self.business,
			name="Corte premium",
			duration_minutes=30,
			price="25.00",
		)

	def _appointment(self, status=Appointment.Status.CONFIRMED, starts_in_hours=25):
		starts_at = timezone.now() + timedelta(hours=starts_in_hours)
		ends_at = starts_at + timedelta(minutes=30)
		return Appointment.objects.create(
			business=self.business,
			client=self.client_user,
			employee=self.employee,
			service=self.service,
			starts_at=starts_at,
			ends_at=ends_at,
			status=status,
		)

	def test_schedule_booking_notification(self):
		appointment = self._appointment(status=Appointment.Status.PENDING)
		schedule_booking_notifications(appointment)

		self.assertTrue(
			Notification.objects.filter(
				appointment=appointment,
				channel=Notification.Channel.EMAIL,
				event_type=Notification.EventType.BOOKING_CREATED,
			).exists()
		)

	def test_schedule_confirmation_and_reminders(self):
		appointment = self._appointment()
		schedule_confirmation_and_reminders(appointment)

		event_types = set(
			Notification.objects.filter(appointment=appointment).values_list(
				"event_type", flat=True
			)
		)
		self.assertEqual(
			event_types,
			{
				Notification.EventType.APPOINTMENT_CONFIRMED,
				Notification.EventType.REMINDER_24H,
				Notification.EventType.REMINDER_1H,
			},
		)

	def test_dispatch_due_notifications_sends_email(self):
		appointment = self._appointment()
		notification = Notification.objects.create(
			business=self.business,
			appointment=appointment,
			channel=Notification.Channel.EMAIL,
			event_type=Notification.EventType.APPOINTMENT_CONFIRMED,
			scheduled_for=timezone.now() - timedelta(minutes=1),
			payload={"subject": "Test", "body": "Body"},
		)

		result = dispatch_due_notifications(limit=10)
		notification.refresh_from_db()

		self.assertEqual(result["sent"], 1)
		self.assertEqual(notification.status, Notification.Status.SENT)
		self.assertEqual(len(mail.outbox), 1)
