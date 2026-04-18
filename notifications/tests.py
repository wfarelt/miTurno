from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from appointments.models import Appointment
from notifications.models import Notification, NotificationOutbox
from notifications.services import (
	dispatch_due_notifications,
	schedule_booking_notifications,
	schedule_confirmation_and_reminders,
)
from services.models import Service
from staffs.models import Employee
from tenants.models import Business, TenantMembership


@override_settings(
	EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
	NOTIFICATION_CHANNELS=[Notification.Channel.EMAIL],
)
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

		notification = Notification.objects.get(
			appointment=appointment,
			channel=Notification.Channel.EMAIL,
			event_type=Notification.EventType.BOOKING_CREATED,
		)
		self.assertTrue(
			NotificationOutbox.objects.filter(
				notification=notification,
				status=NotificationOutbox.Status.PENDING,
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
		NotificationOutbox.objects.create(
			business=self.business,
			notification=notification,
			next_attempt_at=timezone.now() - timedelta(minutes=1),
		)

		result = dispatch_due_notifications(limit=10)
		notification.refresh_from_db()
		outbox = notification.outbox_entry
		outbox.refresh_from_db()

		self.assertEqual(result["sent"], 1)
		self.assertEqual(notification.status, Notification.Status.SENT)
		self.assertEqual(outbox.status, NotificationOutbox.Status.DELIVERED)
		self.assertEqual(len(mail.outbox), 1)


class NotificationAuditApiTests(APITestCase):
	def setUp(self):
		user_model = get_user_model()
		self.business = Business.objects.create(name="Demo Salon", slug="audit-salon")
		self.manager_user = user_model.objects.create_user(
			email="manager-audit@example.com",
			username="manager-audit",
			password="testpass123",
		)
		self.client_user = user_model.objects.create_user(
			email="client-audit@example.com",
			username="client-audit",
			password="testpass123",
		)
		TenantMembership.objects.create(
			user=self.manager_user,
			business=self.business,
			role=TenantMembership.Role.MANAGER,
		)
		TenantMembership.objects.create(
			user=self.client_user,
			business=self.business,
			role=TenantMembership.Role.CLIENT,
		)

		employee = Employee.objects.create(
			business=self.business,
			first_name="Mia",
			last_name="Stylist",
		)
		service = Service.objects.create(
			business=self.business,
			name="Color",
			duration_minutes=60,
			price="55.00",
		)
		appointment = Appointment.objects.create(
			business=self.business,
			client=self.client_user,
			employee=employee,
			service=service,
			starts_at=timezone.now() + timedelta(days=1),
			ends_at=timezone.now() + timedelta(days=1, hours=1),
			status=Appointment.Status.CONFIRMED,
		)
		self.notification = Notification.objects.create(
			business=self.business,
			appointment=appointment,
			channel=Notification.Channel.EMAIL,
			event_type=Notification.EventType.APPOINTMENT_CONFIRMED,
			scheduled_for=timezone.now(),
			status=Notification.Status.PENDING,
		)
		NotificationOutbox.objects.create(
			business=self.business,
			notification=self.notification,
			next_attempt_at=timezone.now(),
		)

	def test_manager_can_list_notification_audit(self):
		self.client.force_authenticate(self.manager_user)
		url = reverse("notification-audit-list")
		response = self.client.get(url, HTTP_X_BUSINESS_SLUG=self.business.slug)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.data), 1)

	def test_client_cannot_list_notification_audit(self):
		self.client.force_authenticate(self.client_user)
		url = reverse("notification-audit-list")
		response = self.client.get(url, HTTP_X_BUSINESS_SLUG=self.business.slug)

		self.assertEqual(response.status_code, 403)


@override_settings(
	WHATSAPP_WEBHOOK_VERIFY_TOKEN="verify-secret",
	WHATSAPP_APP_SECRET="app-secret",
)
class WhatsAppWebhookTests(APITestCase):
	def setUp(self):
		user_model = get_user_model()
		business = Business.objects.create(name="Webhook Salon", slug="webhook-salon")
		client_user = user_model.objects.create_user(
			email="webhook-client@example.com",
			username="webhook-client",
			password="testpass123",
			phone="573001112233",
		)
		TenantMembership.objects.create(
			user=client_user,
			business=business,
			role=TenantMembership.Role.CLIENT,
		)
		employee = Employee.objects.create(
			business=business,
			first_name="Nina",
			last_name="Barber",
		)
		service = Service.objects.create(
			business=business,
			name="Fade",
			duration_minutes=30,
			price="30.00",
		)
		appointment = Appointment.objects.create(
			business=business,
			client=client_user,
			employee=employee,
			service=service,
			starts_at=timezone.now() + timedelta(days=1),
			ends_at=timezone.now() + timedelta(days=1, minutes=30),
			status=Appointment.Status.CONFIRMED,
		)
		notification = Notification.objects.create(
			business=business,
			appointment=appointment,
			channel=Notification.Channel.WHATSAPP,
			event_type=Notification.EventType.APPOINTMENT_CONFIRMED,
			scheduled_for=timezone.now(),
			status=Notification.Status.SENT,
		)
		self.outbox = NotificationOutbox.objects.create(
			business=business,
			notification=notification,
			status=NotificationOutbox.Status.PROCESSING,
			next_attempt_at=timezone.now(),
			provider_message_id="wamid.HBgLMjM0NTY3ODkwABEA",
		)

	def test_webhook_verification_success(self):
		url = reverse("whatsapp-webhook")
		response = self.client.get(
			url,
			{
				"hub.mode": "subscribe",
				"hub.verify_token": "verify-secret",
				"hub.challenge": "12345",
			},
		)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.content.decode("utf-8"), "12345")

	@override_settings(WHATSAPP_APP_SECRET="")
	def test_webhook_post_updates_outbox_status(self):
		url = reverse("whatsapp-webhook")
		payload = {
			"entry": [
				{
					"changes": [
						{
							"value": {
								"statuses": [
									{
										"id": "wamid.HBgLMjM0NTY3ODkwABEA",
										"status": "delivered",
									}
								]
							}
						}
					]
				}
			]
		}
		response = self.client.post(
			url,
			data=payload,
			format="json",
		)
		self.assertEqual(response.status_code, 200)

		self.outbox.refresh_from_db()
		self.assertEqual(self.outbox.status, NotificationOutbox.Status.DELIVERED)
		self.assertEqual(self.outbox.provider_status, "delivered")
