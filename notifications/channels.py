from dataclasses import dataclass

import requests
from django.conf import settings
from django.core.mail import send_mail


@dataclass
class ChannelResult:
    ok: bool
    error: str = ""
    external_message_id: str = ""
    raw_response: dict | None = None


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

    def send(self, to_phone: str, body: str) -> ChannelResult:
        enabled = getattr(settings, "WHATSAPP_PROVIDER_ENABLED", False)
        if not enabled:
            return ChannelResult(
                ok=False,
                error="WhatsApp provider is not configured yet.",
            )

        if not to_phone:
            return ChannelResult(ok=False, error="Recipient phone is required.")

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
            return ChannelResult(ok=False, error=f"WhatsApp request failed: {exc}")

        if response.status_code >= 300:
            return ChannelResult(
                ok=False,
                error=f"WhatsApp API error ({response.status_code}): {response.text[:300]}",
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

        return ChannelResult(
            ok=True,
            external_message_id=message_id,
            raw_response=response_json,
        )