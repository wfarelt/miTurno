from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from services.models import Service
from staffs.models import Employee
from tenants.models import Business, TenantMembership


class AppointmentBookingFlowTests(APITestCase):
	def setUp(self):
		user_model = get_user_model()
		self.business = Business.objects.create(name="Demo Barbers", slug="demo")
		self.client_user = user_model.objects.create_user(
			email="client@example.com",
			username="client",
			password="testpass123",
		)
		TenantMembership.objects.create(
			user=self.client_user,
			business=self.business,
			role=TenantMembership.Role.CLIENT,
		)

		self.other_client = user_model.objects.create_user(
			email="client2@example.com",
			username="client2",
			password="testpass123",
		)
		TenantMembership.objects.create(
			user=self.other_client,
			business=self.business,
			role=TenantMembership.Role.CLIENT,
		)

		self.employee = Employee.objects.create(
			business=self.business,
			first_name="Luis",
			last_name="Lopez",
		)
		self.service = Service.objects.create(
			business=self.business,
			name="Corte",
			duration_minutes=30,
			price="15.00",
		)

	def _hold_payload(self):
		starts_at = timezone.now() + timedelta(days=1)
		starts_at = starts_at.replace(minute=0, second=0, microsecond=0)
		ends_at = starts_at + timedelta(minutes=30)
		return {
			"employee": self.employee.id,
			"service": self.service.id,
			"starts_at": starts_at.isoformat(),
			"ends_at": ends_at.isoformat(),
		}

	def test_create_hold_then_book_appointment(self):
		hold_url = reverse("appointment-create-hold")
		appointment_url = reverse("appointment-list")
		headers = {"HTTP_X_BUSINESS_SLUG": self.business.slug}

		self.client.force_authenticate(self.client_user)
		hold_payload = self._hold_payload()
		hold_response = self.client.post(hold_url, hold_payload, format="json", **headers)
		self.assertEqual(hold_response.status_code, 201)

		book_payload = {
			**hold_payload,
			"hold_token": hold_response.data["token"],
		}
		book_response = self.client.post(appointment_url, book_payload, format="json", **headers)
		self.assertEqual(book_response.status_code, 201)
		self.assertEqual(book_response.data["status"], "PENDING")

	def test_second_hold_on_same_slot_returns_conflict(self):
		hold_url = reverse("appointment-create-hold")
		headers = {"HTTP_X_BUSINESS_SLUG": self.business.slug}
		payload = self._hold_payload()

		self.client.force_authenticate(self.client_user)
		first_response = self.client.post(hold_url, payload, format="json", **headers)
		self.assertEqual(first_response.status_code, 201)

		self.client.force_authenticate(self.other_client)
		second_response = self.client.post(hold_url, payload, format="json", **headers)
		self.assertEqual(second_response.status_code, 409)

	def test_client_can_only_cancel_own_appointment(self):
		headers = {"HTTP_X_BUSINESS_SLUG": self.business.slug}
		hold_url = reverse("appointment-create-hold")
		appointment_url = reverse("appointment-list")

		self.client.force_authenticate(self.client_user)
		hold_payload = self._hold_payload()
		hold_response = self.client.post(hold_url, hold_payload, format="json", **headers)
		self.assertEqual(hold_response.status_code, 201)

		create_payload = {
			**hold_payload,
			"hold_token": hold_response.data["token"],
		}
		create_response = self.client.post(appointment_url, create_payload, format="json", **headers)
		self.assertEqual(create_response.status_code, 201)

		appointment_detail_url = reverse("appointment-detail", args=[create_response.data["id"]])
		note_response = self.client.patch(
			appointment_detail_url,
			{"notes": "change"},
			format="json",
			**headers,
		)
		self.assertEqual(note_response.status_code, 403)

		confirm_response = self.client.patch(
			appointment_detail_url,
			{"status": "CONFIRMED"},
			format="json",
			**headers,
		)
		self.assertEqual(confirm_response.status_code, 403)

		cancel_response = self.client.patch(
			appointment_detail_url,
			{"status": "CANCELLED"},
			format="json",
			**headers,
		)
		self.assertEqual(cancel_response.status_code, 200)
		self.assertEqual(cancel_response.data["status"], "CANCELLED")

	def test_manager_can_reschedule_appointment(self):
		user_model = get_user_model()
		manager_user = user_model.objects.create_user(
			email="manager@example.com",
			username="manager",
			password="testpass123",
		)
		TenantMembership.objects.create(
			user=manager_user,
			business=self.business,
			role=TenantMembership.Role.MANAGER,
		)

		headers = {"HTTP_X_BUSINESS_SLUG": self.business.slug}
		hold_url = reverse("appointment-create-hold")
		appointment_url = reverse("appointment-list")

		self.client.force_authenticate(self.client_user)
		hold_payload = self._hold_payload()
		hold_response = self.client.post(hold_url, hold_payload, format="json", **headers)
		self.assertEqual(hold_response.status_code, 201)

		create_payload = {
			**hold_payload,
			"hold_token": hold_response.data["token"],
		}
		create_response = self.client.post(appointment_url, create_payload, format="json", **headers)
		self.assertEqual(create_response.status_code, 201)

		appointment_detail_url = reverse("appointment-detail", args=[create_response.data["id"]])
		new_starts_at = timezone.now() + timedelta(days=2)
		new_starts_at = new_starts_at.replace(minute=0, second=0, microsecond=0)
		new_ends_at = new_starts_at + timedelta(minutes=30)

		self.client.force_authenticate(manager_user)
		patch_response = self.client.patch(
			appointment_detail_url,
			{
				"starts_at": new_starts_at.isoformat(),
				"ends_at": new_ends_at.isoformat(),
			},
			format="json",
			**headers,
		)
		self.assertEqual(patch_response.status_code, 200)
