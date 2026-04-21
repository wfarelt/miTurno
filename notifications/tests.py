from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from appointments.models import Appointment
from notifications.channels import ChannelResult, WhatsAppChannel
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

	def test_dispatch_due_notifications_marks_permanent_failures_without_retry(self):
		appointment = self._appointment()
		notification = Notification.objects.create(
			business=self.business,
			appointment=appointment,
			channel=Notification.Channel.WHATSAPP,
			event_type=Notification.EventType.APPOINTMENT_CONFIRMED,
			scheduled_for=timezone.now() - timedelta(minutes=1),
			payload={"body": "Body"},
		)
		outbox = NotificationOutbox.objects.create(
			business=self.business,
			notification=notification,
			next_attempt_at=timezone.now() - timedelta(minutes=1),
		)

		with patch(
			"notifications.channels.WhatsAppChannel.send",
			return_value=ChannelResult(
				ok=False,
				error="WhatsApp API error (400): invalid payload",
				error_kind="http_400",
			),
		):
			dispatch_due_notifications(limit=10, max_retries=5)

		notification.refresh_from_db()
		outbox.refresh_from_db()

		self.assertEqual(outbox.status, NotificationOutbox.Status.FAILED)
		self.assertEqual(notification.status, Notification.Status.FAILED)
		self.assertEqual(outbox.attempts, 1)

	@override_settings(
		TELEGRAM_PROVIDER_ENABLED=True,
		TELEGRAM_BOT_TOKEN="telegram-token",
		TELEGRAM_DEFAULT_CHAT_ID="123456",
	)
	@patch("notifications.channels.requests.post")
	def test_dispatch_due_notifications_sends_telegram(self, post_mock):
		response_mock = post_mock.return_value
		response_mock.status_code = 200
		response_mock.json.return_value = {"ok": True, "result": {"message_id": 77}}

		appointment = self._appointment()
		notification = Notification.objects.create(
			business=self.business,
			appointment=appointment,
			channel=Notification.Channel.TELEGRAM,
			event_type=Notification.EventType.APPOINTMENT_CONFIRMED,
			scheduled_for=timezone.now() - timedelta(minutes=1),
			payload={"body": "Body"},
		)
		outbox = NotificationOutbox.objects.create(
			business=self.business,
			notification=notification,
			next_attempt_at=timezone.now() - timedelta(minutes=1),
		)

		result = dispatch_due_notifications(limit=10)
		notification.refresh_from_db()
		outbox.refresh_from_db()

		self.assertEqual(result["sent"], 1)
		self.assertEqual(notification.status, Notification.Status.SENT)
		self.assertEqual(outbox.status, NotificationOutbox.Status.DELIVERED)
		self.assertEqual(outbox.provider_message_id, "77")

	@override_settings(
		TELEGRAM_PROVIDER_ENABLED=True,
		TELEGRAM_BOT_TOKEN="telegram-token",
		TELEGRAM_DEFAULT_CHAT_ID="123456",
	)
	@patch("notifications.channels.requests.post")
	def test_dispatch_due_notifications_telegram_400_is_permanent_failure(self, post_mock):
		response_mock = post_mock.return_value
		response_mock.status_code = 400
		response_mock.text = "chat not found"

		appointment = self._appointment()
		notification = Notification.objects.create(
			business=self.business,
			appointment=appointment,
			channel=Notification.Channel.TELEGRAM,
			event_type=Notification.EventType.APPOINTMENT_CONFIRMED,
			scheduled_for=timezone.now() - timedelta(minutes=1),
			payload={"body": "Body"},
		)
		outbox = NotificationOutbox.objects.create(
			business=self.business,
			notification=notification,
			next_attempt_at=timezone.now() - timedelta(minutes=1),
		)

		dispatch_due_notifications(limit=10, max_retries=5)
		notification.refresh_from_db()
		outbox.refresh_from_db()

		self.assertEqual(outbox.status, NotificationOutbox.Status.FAILED)
		self.assertEqual(notification.status, Notification.Status.FAILED)


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

	def test_manager_can_get_notification_dashboard(self):
		self.client.force_authenticate(self.manager_user)
		url = reverse("notification-dashboard")
		response = self.client.get(url, HTTP_X_BUSINESS_SLUG=self.business.slug)

		self.assertEqual(response.status_code, 200)
		self.assertIn("totals", response.data)
		self.assertEqual(response.data["totals"]["total"], 1)
		self.assertIn("by_channel", response.data)

	def test_dashboard_rejects_invalid_date_filter(self):
		self.client.force_authenticate(self.manager_user)
		url = reverse("notification-dashboard")
		response = self.client.get(
			url,
			{"start_at": "not-a-date"},
			HTTP_X_BUSINESS_SLUG=self.business.slug,
		)

		self.assertEqual(response.status_code, 400)


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


@override_settings(
	WHATSAPP_PROVIDER_ENABLED=True,
	WHATSAPP_ACCESS_TOKEN="token",
	WHATSAPP_PHONE_NUMBER_ID="123456",
	WHATSAPP_CIRCUIT_BREAKER_ENABLED=True,
	WHATSAPP_CIRCUIT_FAILURE_THRESHOLD=2,
	WHATSAPP_CIRCUIT_RECOVERY_SECONDS=300,
)
class WhatsAppCircuitBreakerTests(TestCase):
	def setUp(self):
		cache.clear()

	@patch("notifications.channels.requests.post")
	def test_circuit_breaker_opens_after_threshold(self, post_mock):
		response_mock = post_mock.return_value
		response_mock.status_code = 503
		response_mock.text = "service unavailable"

		channel = WhatsAppChannel()
		first = channel.send(to_phone="573001234567", body="msg-1")
		second = channel.send(to_phone="573001234567", body="msg-2")
		third = channel.send(to_phone="573001234567", body="msg-3")

		self.assertFalse(first.ok)
		self.assertFalse(second.ok)
		self.assertFalse(third.ok)
		self.assertEqual(third.error_kind, "circuit_open")
		self.assertEqual(post_mock.call_count, 2)


@override_settings(TELEGRAM_WEBHOOK_SECRET_TOKEN="telegram-secret")
class TelegramWebhookTests(APITestCase):
	def setUp(self):
		self.user_model = get_user_model()
		self.business = Business.objects.create(name="Telegram Salon", slug="telegram-salon")
		self.employee = Employee.objects.create(
			business=self.business,
			first_name="Tina",
			last_name="Stylist",
			telegram_username="barber_tina",
		)
		self.service = Service.objects.create(
			business=self.business,
			name="Corte clasico",
			duration_minutes=30,
			price="25.00",
		)

	def test_webhook_updates_employee_chat_id(self):
		url = reverse("telegram-webhook")
		payload = {
			"update_id": 100001,
			"message": {
				"message_id": 5,
				"from": {
					"id": 555,
					"is_bot": False,
					"username": "barber_tina",
				},
				"chat": {
					"id": 99887766,
					"type": "private",
				},
				"date": 1713600000,
				"text": "/start",
			},
		}

		response = self.client.post(
			url,
			data=payload,
			format="json",
			HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="telegram-secret",
		)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["updated"], 1)

		self.employee.refresh_from_db()
		self.assertEqual(self.employee.telegram_chat_id, "99887766")

	def test_webhook_rejects_invalid_secret(self):
		url = reverse("telegram-webhook")
		response = self.client.post(
			url,
			data={"update_id": 1},
			format="json",
			HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="wrong",
		)
		self.assertEqual(response.status_code, 403)

	@override_settings(TELEGRAM_PROVIDER_ENABLED=True, TELEGRAM_BOT_TOKEN="telegram-token")
	@patch("notifications.channels.requests.post")
	def test_webhook_replies_to_citas_command_with_upcoming_appointments(self, post_mock):
		post_response = post_mock.return_value
		post_response.status_code = 200
		post_response.json.return_value = {"ok": True, "result": {"message_id": 321}}

		client_user = self.user_model.objects.create_user(
			email="client-telegram@example.com",
			username="client-telegram",
			password="testpass123",
		)
		TenantMembership.objects.create(
			user=client_user,
			business=self.business,
			role=TenantMembership.Role.CLIENT,
		)
		starts_at = timezone.now() + timedelta(hours=2)
		Appointment.objects.create(
			business=self.business,
			client=client_user,
			employee=self.employee,
			service=self.service,
			starts_at=starts_at,
			ends_at=starts_at + timedelta(minutes=30),
			status=Appointment.Status.CONFIRMED,
		)

		url = reverse("telegram-webhook")
		payload = {
			"update_id": 200002,
			"message": {
				"message_id": 8,
				"from": {
					"id": 555,
					"is_bot": False,
					"username": "barber_tina",
				},
				"chat": {
					"id": 99887766,
					"type": "private",
				},
				"date": 1713600000,
				"text": "/citas",
			},
		}

		response = self.client.post(
			url,
			data=payload,
			format="json",
			HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="telegram-secret",
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["command_replies"], 1)
		self.assertEqual(post_mock.call_count, 1)
		sent_body = post_mock.call_args.kwargs["json"]["text"]
		self.assertIn("Tus proximas citas:", sent_body)
		self.assertIn("Corte clasico", sent_body)

	@override_settings(TELEGRAM_PROVIDER_ENABLED=True, TELEGRAM_BOT_TOKEN="telegram-token")
	@patch("notifications.channels.requests.post")
	def test_webhook_replies_to_citas_command_when_no_upcoming(self, post_mock):
		post_response = post_mock.return_value
		post_response.status_code = 200
		post_response.json.return_value = {"ok": True, "result": {"message_id": 322}}

		url = reverse("telegram-webhook")
		payload = {
			"update_id": 200003,
			"message": {
				"message_id": 9,
				"from": {
					"id": 555,
					"is_bot": False,
					"username": "barber_tina",
				},
				"chat": {
					"id": 99887766,
					"type": "private",
				},
				"date": 1713600000,
				"text": "/citas",
			},
		}

		response = self.client.post(
			url,
			data=payload,
			format="json",
			HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="telegram-secret",
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["command_replies"], 1)
		sent_body = post_mock.call_args.kwargs["json"]["text"]
		self.assertEqual(sent_body, "No tienes citas programadas.")

	@override_settings(TELEGRAM_PROVIDER_ENABLED=True, TELEGRAM_BOT_TOKEN="telegram-token")
	@patch("notifications.channels.requests.post")
	def test_webhook_replies_to_hoy_command_only_with_today_appointments(self, post_mock):
		post_response = post_mock.return_value
		post_response.status_code = 200
		post_response.json.return_value = {"ok": True, "result": {"message_id": 323}}

		client_today = self.user_model.objects.create_user(
			email="client-hoy@example.com",
			username="client-hoy",
			password="testpass123",
		)
		TenantMembership.objects.create(
			user=client_today,
			business=self.business,
			role=TenantMembership.Role.CLIENT,
		)
		client_tomorrow = self.user_model.objects.create_user(
			email="client-manana@example.com",
			username="client-manana",
			password="testpass123",
		)
		TenantMembership.objects.create(
			user=client_tomorrow,
			business=self.business,
			role=TenantMembership.Role.CLIENT,
		)

		now_local = timezone.localtime(timezone.now())
		today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
		today_10am = today_start + timedelta(hours=10)
		tomorrow_10am = today_10am + timedelta(days=1)

		Appointment.objects.create(
			business=self.business,
			client=client_today,
			employee=self.employee,
			service=self.service,
			starts_at=today_10am,
			ends_at=today_10am + timedelta(minutes=30),
			status=Appointment.Status.CONFIRMED,
		)
		Appointment.objects.create(
			business=self.business,
			client=client_tomorrow,
			employee=self.employee,
			service=self.service,
			starts_at=tomorrow_10am,
			ends_at=tomorrow_10am + timedelta(minutes=30),
			status=Appointment.Status.CONFIRMED,
		)

		url = reverse("telegram-webhook")
		payload = {
			"update_id": 200004,
			"message": {
				"message_id": 10,
				"from": {
					"id": 555,
					"is_bot": False,
					"username": "barber_tina",
				},
				"chat": {
					"id": 99887766,
					"type": "private",
				},
				"date": 1713600000,
				"text": "/hoy",
			},
		}

		response = self.client.post(
			url,
			data=payload,
			format="json",
			HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="telegram-secret",
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["command_replies"], 1)
		sent_body = post_mock.call_args.kwargs["json"]["text"]
		self.assertIn("Tus citas de hoy:", sent_body)
		self.assertIn("client-hoy", sent_body)
		self.assertNotIn("client-manana", sent_body)
