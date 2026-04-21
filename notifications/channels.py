from dataclasses import dataclass

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail


@dataclass
class ChannelResult:
    ok: bool
    error: str = ""
    external_message_id: str = ""
    raw_response: dict | None = None
    error_kind: str = ""


class EmailChannel:
    def send(self, to_address: str, subject: str, body: str) -> ChannelResult:
        if not to_address:
            return ChannelResult(ok=False, error="Recipient email is required.")

        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@citapro.local"),
            recipient_list=[to_address],
            fail_silently=False,
        )
        return ChannelResult(ok=True)


class WhatsAppChannel:
    """Meta WhatsApp Cloud API adapter."""

    _CB_FAIL_COUNT_KEY = "notifications:whatsapp:circuit:fail_count"
    _CB_OPEN_UNTIL_KEY = "notifications:whatsapp:circuit:open_until"

    def _circuit_enabled(self) -> bool:
        return bool(getattr(settings, "WHATSAPP_CIRCUIT_BREAKER_ENABLED", True))

    def _failure_threshold(self) -> int:
        return int(getattr(settings, "WHATSAPP_CIRCUIT_FAILURE_THRESHOLD", 5))

    def _recovery_seconds(self) -> int:
        return int(getattr(settings, "WHATSAPP_CIRCUIT_RECOVERY_SECONDS", 120))

    def _is_circuit_open(self) -> bool:
        if not self._circuit_enabled():
            return False
        open_until = cache.get(self._CB_OPEN_UNTIL_KEY)
        if open_until is None:
            return False
        from django.utils import timezone

        return timezone.now().timestamp() < float(open_until)

    def _record_failure(self):
        if not self._circuit_enabled():
            return
        from django.utils import timezone

        failures = int(cache.get(self._CB_FAIL_COUNT_KEY, 0)) + 1
        cache.set(self._CB_FAIL_COUNT_KEY, failures, timeout=self._recovery_seconds())
        if failures >= self._failure_threshold():
            open_until = timezone.now().timestamp() + self._recovery_seconds()
            cache.set(self._CB_OPEN_UNTIL_KEY, open_until, timeout=self._recovery_seconds())

    def _record_success(self):
        if not self._circuit_enabled():
            return
        cache.delete(self._CB_FAIL_COUNT_KEY)
        cache.delete(self._CB_OPEN_UNTIL_KEY)

    def send(self, to_phone: str, body: str) -> ChannelResult:
        if self._is_circuit_open():
            return ChannelResult(
                ok=False,
                error="WhatsApp circuit breaker open: provider temporarily disabled.",
                error_kind="circuit_open",
            )

        enabled = getattr(settings, "WHATSAPP_PROVIDER_ENABLED", False)
        if not enabled:
            return ChannelResult(
                ok=False,
                error="WhatsApp provider is not configured yet.",
                error_kind="configuration",
            )

        if not to_phone:
            return ChannelResult(ok=False, error="Recipient phone is required.", error_kind="validation")

        access_token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "")
        phone_number_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "")
        api_base_url = getattr(
            settings,
            "WHATSAPP_API_URL",
            "https://graph.facebook.com/v22.0",
        )

        if not access_token or not phone_number_id:
            return ChannelResult(
                ok=False,
                error="WhatsApp credentials are missing (token or phone number ID).",
                error_kind="configuration",
            )

        url = f"{api_base_url.rstrip('/')}/{phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "text",
            "text": {"body": body},
        }
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
        except requests.RequestException as exc:
            self._record_failure()
            return ChannelResult(ok=False, error=f"WhatsApp request failed: {exc}", error_kind="network")

        if response.status_code >= 300:
            self._record_failure()
            return ChannelResult(
                ok=False,
                error=f"WhatsApp API error ({response.status_code}): {response.text[:300]}",
                error_kind=f"http_{response.status_code}",
            )

        response_json = {}
        try:
            response_json = response.json()
        except ValueError:
            response_json = {}

        message_id = ""
        messages = response_json.get("messages", [])
        if messages and isinstance(messages, list):
            message_id = str(messages[0].get("id", ""))

        self._record_success()
        return ChannelResult(
            ok=True,
            external_message_id=message_id,
            raw_response=response_json,
        )