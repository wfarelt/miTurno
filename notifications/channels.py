from dataclasses import dataclass

from django.conf import settings
from django.core.mail import send_mail


@dataclass
class ChannelResult:
    ok: bool
    error: str = ""


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
    """Placeholder adapter for future WhatsApp Business API integration."""

    def send(self, to_phone: str, body: str) -> ChannelResult:
        enabled = getattr(settings, "WHATSAPP_PROVIDER_ENABLED", False)
        if not enabled:
            return ChannelResult(
                ok=False,
                error="WhatsApp provider is not configured yet.",
            )

        if not to_phone:
            return ChannelResult(ok=False, error="Recipient phone is required.")

        return ChannelResult(ok=True)