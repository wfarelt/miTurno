from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AdminDashboardAccessTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.superadmin = user_model.objects.create_user(
			email="superadmin@example.com",
			username="superadmin",
			password="testpass123",
			is_staff=True,
			is_superuser=True,
		)
		self.staff_user = user_model.objects.create_user(
			email="staff@example.com",
			username="staff",
			password="testpass123",
			is_staff=True,
			is_superuser=False,
		)

	def test_superadmin_can_access_platform_dashboard(self):
		self.client.force_login(self.superadmin)
		url = reverse("admin-dashboard")
		response = self.client.get(url)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Dashboard de Plataforma")

	def test_staff_non_superadmin_cannot_access_platform_dashboard(self):
		self.client.force_login(self.staff_user)
		url = reverse("admin-dashboard")
		response = self.client.get(url)

		self.assertEqual(response.status_code, 403)
