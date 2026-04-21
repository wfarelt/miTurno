from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from notifications.channels import ChannelResult
from staffs.models import Employee
from tenants.models import Business, TenantMembership


class PanelAccessTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="manager-panel@example.com",
            username="manager-panel",
            password="testpass123",
        )
        self.no_membership_user = user_model.objects.create_user(
            email="plain-user@example.com",
            username="plain-user",
            password="testpass123",
        )
        self.superuser = user_model.objects.create_user(
            email="super-panel@example.com",
            username="super-panel",
            password="testpass123",
            is_staff=True,
            is_superuser=True,
        )
        self.business = Business.objects.create(name="Panel Salon", slug="panel-salon")
        TenantMembership.objects.create(
            user=self.user,
            business=self.business,
            role=TenantMembership.Role.MANAGER,
            is_active=True,
        )
        self.employee = Employee.objects.create(
            business=self.business,
            first_name="Ana",
            last_name="Barber",
            telegram_chat_id="99887766",
        )
        self.employee_without_chat = Employee.objects.create(
            business=self.business,
            first_name="Luis",
            last_name="NoChat",
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("panel:dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_manager_can_access_dashboard(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("panel:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")

    def test_user_without_membership_is_redirected_to_admin(self):
        self.client.force_login(self.no_membership_user)
        response = self.client.get(reverse("panel:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin:index"))

    def test_superuser_is_redirected_to_admin_dashboard(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("panel:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin-dashboard"))

    @patch(
        "panel.views.TelegramChannel.send",
        return_value=ChannelResult(ok=True, external_message_id="1", raw_response={"ok": True}),
    )
    def test_manager_can_send_telegram_test_message(self, send_mock):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("panel:employees-telegram-test", args=[self.employee.id]),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("panel:employees-list"))
        send_mock.assert_called_once()

    @patch("panel.views.TelegramChannel.send")
    def test_telegram_test_message_requires_employee_chat_id(self, send_mock):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("panel:employees-telegram-test", args=[self.employee_without_chat.id]),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("panel:employees-list"))
        send_mock.assert_not_called()
