from datetime import timedelta
import re

from django.conf import settings
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

from notifications.channels import EmailChannel, TelegramChannel, WhatsAppChannel
from notifications.models import Notification, NotificationOutbox
from staffs.models import Employee


def _event_message(event_type: str, appointment):
    starts_local = timezone.localtime(appointment.starts_at)
    when_text = starts_local.strftime("%Y-%m-%d %H:%M")

    if event_type == Notification.EventType.BOOKING_CREATED:
        return (
            "Cita registrada",
            f"Tu cita fue registrada para {when_text}. Estado: {appointment.status}.",
        )
    if event_type == Notification.EventType.APPOINTMENT_CONFIRMED:
        return (
            "Cita confirmada",
            f"Tu cita fue confirmada para {when_text}.",
        )
    if event_type == Notification.EventType.REMINDER_24H:
        return (
            "Recordatorio de cita (24h)",
            f"Recordatorio: tienes una cita en 24 horas ({when_text}).",
        )
    return (
        "Recordatorio de cita (1h)",
        f"Recordatorio: tienes una cita en 1 hora ({when_text}).",
    )


def _configured_channels(appointment):
    raw_channels = getattr(settings, "NOTIFICATION_CHANNELS", [Notification.Channel.EMAIL])
    channels = []
    for channel in raw_channels:
        if channel == Notification.Channel.WHATSAPP and not appointment.client.phone:
            continue
        if channel == Notification.Channel.TELEGRAM:
            employee_chat_id = str(getattr(appointment.employee, "telegram_chat_id", "") or "").strip()
            default_chat_id = str(getattr(settings, "TELEGRAM_DEFAULT_CHAT_ID", "") or "").strip()
            if not employee_chat_id and not default_chat_id:
                continue
        channels.append(channel)

    if not channels:
        channels = [Notification.Channel.EMAIL]
    return channels


def schedule_notification(appointment, channel: str, event_type: str, scheduled_for):
    now = timezone.now()
    if scheduled_for < now:
        scheduled_for = now

    subject, body = _event_message(event_type, appointment)
    notification, _ = Notification.objects.get_or_create(
        appointment=appointment,
        channel=channel,
        event_type=event_type,
        defaults={
            "business": appointment.business,
            "scheduled_for": scheduled_for,
            "payload": {
                "subject": subject,
                "body": body,
            },
        },
    )
    NotificationOutbox.objects.get_or_create(
        notification=notification,
        defaults={
            "business": appointment.business,
            "next_attempt_at": scheduled_for,
        },
    )
    return notification


def schedule_booking_notifications(appointment):
    for channel in _configured_channels(appointment):
        schedule_notification(
            appointment=appointment,
            channel=channel,
            event_type=Notification.EventType.BOOKING_CREATED,
            scheduled_for=timezone.now(),
        )


def schedule_confirmation_and_reminders(appointment):
    start = appointment.starts_at
    for channel in _configured_channels(appointment):
        schedule_notification(
            appointment=appointment,
            channel=channel,
            event_type=Notification.EventType.APPOINTMENT_CONFIRMED,
            scheduled_for=timezone.now(),
        )
        schedule_notification(
            appointment=appointment,
            channel=channel,
            event_type=Notification.EventType.REMINDER_24H,
            scheduled_for=start - timedelta(hours=24),
        )
        schedule_notification(
            appointment=appointment,
            channel=channel,
            event_type=Notification.EventType.REMINDER_1H,
            scheduled_for=start - timedelta(hours=1),
        )


def backfill_confirmed_reminders(lookahead_hours: int = 48):
    now = timezone.now()
    window_end = now + timedelta(hours=lookahead_hours)
    from appointments.models import Appointment

    appointments = Appointment.objects.filter(
        status=Appointment.Status.CONFIRMED,
        starts_at__gte=now,
        starts_at__lte=window_end,
    )
    created = 0
    for appointment in appointments:
        before = Notification.objects.filter(appointment=appointment).count()
        schedule_confirmation_and_reminders(appointment)
        after = Notification.objects.filter(appointment=appointment).count()
        created += max(after - before, 0)
    return created


def build_notification_dashboard(business, start_at=None, end_at=None):
    base_queryset = Notification.objects.filter(business=business)
    outbox_queryset = NotificationOutbox.objects.filter(business=business)

    if start_at is not None:
        base_queryset = base_queryset.filter(created_at__gte=start_at)
        outbox_queryset = outbox_queryset.filter(created_at__gte=start_at)
    if end_at is not None:
        base_queryset = base_queryset.filter(created_at__lte=end_at)
        outbox_queryset = outbox_queryset.filter(created_at__lte=end_at)

    total = base_queryset.count()
    sent = base_queryset.filter(status=Notification.Status.SENT).count()
    failed = base_queryset.filter(status=Notification.Status.FAILED).count()
    pending = base_queryset.filter(status=Notification.Status.PENDING).count()
    avg_retry_count = base_queryset.aggregate(value=Avg("retry_count")).get("value") or 0
    delivery_rate = round((sent / total) * 100, 2) if total else 0.0

    by_channel_rows = (
        base_queryset.values("channel")
        .annotate(
            total=Count("id"),
            sent=Count("id", filter=Q(status=Notification.Status.SENT)),
            failed=Count("id", filter=Q(status=Notification.Status.FAILED)),
            pending=Count("id", filter=Q(status=Notification.Status.PENDING)),
        )
        .order_by("channel")
    )
    by_channel = []
    for row in by_channel_rows:
        channel_total = row["total"]
        by_channel.append(
            {
                "channel": row["channel"],
                "total": channel_total,
                "sent": row["sent"],
                "failed": row["failed"],
                "pending": row["pending"],
                "delivery_rate": round((row["sent"] / channel_total) * 100, 2)
                if channel_total
                else 0.0,
            }
        )

    by_event_rows = (
        base_queryset.values("event_type")
        .annotate(
            total=Count("id"),
            sent=Count("id", filter=Q(status=Notification.Status.SENT)),
            failed=Count("id", filter=Q(status=Notification.Status.FAILED)),
            pending=Count("id", filter=Q(status=Notification.Status.PENDING)),
        )
        .order_by("event_type")
    )
    by_event_type = []
    for row in by_event_rows:
        event_total = row["total"]
        by_event_type.append(
            {
                "event_type": row["event_type"],
                "total": event_total,
                "sent": row["sent"],
                "failed": row["failed"],
                "pending": row["pending"],
                "delivery_rate": round((row["sent"] / event_total) * 100, 2)
                if event_total
                else 0.0,
            }
        )

    outbox_by_status_rows = outbox_queryset.values("status").annotate(total=Count("id"))
    outbox_by_status = {row["status"]: row["total"] for row in outbox_by_status_rows}

    provider_status_rows = (
        outbox_queryset.exclude(provider_status="")
        .values("provider_status")
        .annotate(total=Count("id"))
        .order_by("provider_status")
    )
    provider_statuses = [
        {"provider_status": row["provider_status"], "total": row["total"]}
        for row in provider_status_rows
    ]

    return {
        "range": {
            "start_at": start_at,
            "end_at": end_at,
        },
        "totals": {
            "total": total,
            "sent": sent,
            "failed": failed,
            "pending": pending,
            "delivery_rate": delivery_rate,
            "avg_retry_count": round(float(avg_retry_count), 2),
        },
        "outbox": {
            "pending": outbox_by_status.get(NotificationOutbox.Status.PENDING, 0),
            "processing": outbox_by_status.get(NotificationOutbox.Status.PROCESSING, 0),
            "delivered": outbox_by_status.get(NotificationOutbox.Status.DELIVERED, 0),
            "failed": outbox_by_status.get(NotificationOutbox.Status.FAILED, 0),
        },
        "by_channel": by_channel,
        "by_event_type": by_event_type,
        "provider_statuses": provider_statuses,
    }


def _extract_http_status(error_message: str) -> int | None:
    match = re.search(r"\((\d{3})\)", error_message or "")
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _is_permanent_failure(channel: str, error_message: str, error_kind: str = "") -> bool:
    text = (error_message or "").lower()
    kind = (error_kind or "").lower()

    permanent_kinds = {"validation", "configuration", "circuit_open"}
    if kind in permanent_kinds:
        return True

    if channel == Notification.Channel.WHATSAPP:
        http_status = _extract_http_status(error_message)
        if http_status is not None:
            # Retry only timeout/throttling/server responses.
            if 400 <= http_status < 500 and http_status not in {408, 429}:
                return True
            return False
        if "recipient phone is required" in text:
            return True
        if "credentials are missing" in text or "not configured" in text:
            return True

    if channel == Notification.Channel.EMAIL and "recipient email is required" in text:
        return True

    if channel == Notification.Channel.TELEGRAM:
        http_status = _extract_http_status(error_message)
        if http_status is not None:
            if 400 <= http_status < 500 and http_status not in {408, 429}:
                return True
            return False
        if "chat_id is required" in text:
            return True
        if "credentials are missing" in text or "not configured" in text:
            return True

    return False


def dispatch_due_notifications(limit: int = 100, max_retries: int = 3):
    now = timezone.now()
    queryset = (
        NotificationOutbox.objects.select_related(
            "notification",
            "notification__appointment",
            "notification__appointment__client",
        )
        .filter(
            status__in=[NotificationOutbox.Status.PENDING, NotificationOutbox.Status.FAILED],
            next_attempt_at__lte=now,
            attempts__lt=max_retries,
        )
        .order_by("next_attempt_at")[:limit]
    )

    email_channel = EmailChannel()
    whatsapp_channel = WhatsAppChannel()
    telegram_channel = TelegramChannel()

    sent = 0
    failed = 0
    for outbox in queryset:
        notification = outbox.notification
        appointment = notification.appointment
        payload = notification.payload or {}
        subject = payload.get("subject", "CitaPro")
        body = payload.get("body", "Tienes una notificacion de cita.")

        if notification.channel == Notification.Channel.EMAIL:
            result = email_channel.send(
                to_address=appointment.client.email,
                subject=subject,
                body=body,
            )
        elif notification.channel == Notification.Channel.WHATSAPP:
            result = whatsapp_channel.send(
                to_phone=appointment.client.phone,
                body=body,
            )
        else:
            telegram_chat_id = str(
                payload.get("telegram_chat_id")
                or getattr(appointment.employee, "telegram_chat_id", "")
                or getattr(settings, "TELEGRAM_DEFAULT_CHAT_ID", "")
            ).strip()
            result = telegram_channel.send(
                chat_id=telegram_chat_id,
                body=body,
            )

        with transaction.atomic():
            fresh_outbox = NotificationOutbox.objects.select_for_update().get(pk=outbox.pk)
            fresh_notification = Notification.objects.select_for_update().get(pk=notification.pk)

            fresh_outbox.attempts += 1
            fresh_outbox.locked_at = timezone.now()
            if result.ok:
                if notification.channel == Notification.Channel.WHATSAPP:
                    fresh_outbox.status = NotificationOutbox.Status.PROCESSING
                    fresh_outbox.provider_message_id = result.external_message_id or None
                    fresh_outbox.provider_payload = result.raw_response or {}
                    fresh_outbox.provider_status = "accepted"
                else:
                    fresh_outbox.status = NotificationOutbox.Status.DELIVERED
                    fresh_outbox.delivered_at = timezone.now()
                    fresh_outbox.provider_message_id = result.external_message_id or None
                    fresh_outbox.provider_payload = result.raw_response or {}
                    fresh_outbox.provider_status = "delivered"
                fresh_outbox.last_error = ""

                fresh_notification.status = Notification.Status.SENT
                fresh_notification.sent_at = timezone.now()
                fresh_notification.error_message = ""
                sent += 1
            else:
                fresh_outbox.last_error = result.error
                is_permanent_failure = _is_permanent_failure(
                    channel=notification.channel,
                    error_message=result.error,
                    error_kind=getattr(result, "error_kind", ""),
                )
                if is_permanent_failure:
                    fresh_outbox.status = NotificationOutbox.Status.FAILED
                elif fresh_outbox.attempts >= max_retries:
                    fresh_outbox.status = NotificationOutbox.Status.FAILED
                else:
                    # Exponential backoff in minutes: 2, 4, 8...
                    backoff_minutes = 2 ** fresh_outbox.attempts
                    fresh_outbox.next_attempt_at = timezone.now() + timedelta(minutes=backoff_minutes)

                fresh_notification.retry_count = fresh_outbox.attempts
                fresh_notification.error_message = result.error
                if fresh_outbox.status == NotificationOutbox.Status.FAILED:
                    fresh_notification.status = Notification.Status.FAILED
                failed += 1

            fresh_outbox.save(
                update_fields=[
                    "status",
                    "attempts",
                    "next_attempt_at",
                    "locked_at",
                    "delivered_at",
                    "last_error",
                    "provider_message_id",
                    "provider_status",
                    "provider_payload",
                    "updated_at",
                ]
            )
            fresh_notification.save(
                update_fields=[
                    "status",
                    "sent_at",
                    "retry_count",
                    "error_message",
                    "updated_at",
                ]
            )

    return {"sent": sent, "failed": failed, "processed": sent + failed}


def process_whatsapp_webhook(payload: dict):
    statuses = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            statuses.extend(value.get("statuses", []))

    updated = 0
    ignored = 0
    for status_event in statuses:
        message_id = str(status_event.get("id", "")).strip()
        status_value = str(status_event.get("status", "")).strip().lower()
        if not message_id:
            ignored += 1
            continue

        outbox = NotificationOutbox.objects.select_related("notification").filter(
            provider_message_id=message_id,
            notification__channel=Notification.Channel.WHATSAPP,
        ).first()
        if outbox is None:
            ignored += 1
            continue

        with transaction.atomic():
            fresh_outbox = NotificationOutbox.objects.select_for_update().get(pk=outbox.pk)
            fresh_notification = Notification.objects.select_for_update().get(
                pk=fresh_outbox.notification_id
            )

            fresh_outbox.provider_status = status_value
            fresh_outbox.provider_payload = status_event

            if status_value in {"sent", "accepted"}:
                fresh_outbox.status = NotificationOutbox.Status.PROCESSING
            elif status_value in {"delivered", "read"}:
                fresh_outbox.status = NotificationOutbox.Status.DELIVERED
                fresh_outbox.delivered_at = timezone.now()
            elif status_value in {"failed", "undelivered"}:
                errors = status_event.get("errors", [])
                error_message = "WhatsApp delivery failed."
                if errors and isinstance(errors, list):
                    first = errors[0]
                    error_message = str(first.get("title") or first.get("message") or error_message)
                fresh_outbox.status = NotificationOutbox.Status.FAILED
                fresh_outbox.last_error = error_message

                fresh_notification.status = Notification.Status.FAILED
                fresh_notification.error_message = error_message
                fresh_notification.save(update_fields=["status", "error_message", "updated_at"])

            fresh_outbox.save(
                update_fields=[
                    "status",
                    "delivered_at",
                    "last_error",
                    "provider_status",
                    "provider_payload",
                    "updated_at",
                ]
            )
            updated += 1

    return {"updated": updated, "ignored": ignored, "events": len(statuses)}


def process_telegram_webhook(payload: dict):
    updates = []
    if isinstance(payload, dict):
        updates.append(payload)

    updated = 0
    ignored = 0
    ambiguous = 0

    for update in updates:
        message = update.get("message") or update.get("edited_message") or {}
        if not isinstance(message, dict):
            ignored += 1
            continue

        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        chat_id = str(chat.get("id", "")).strip()
        username = str(sender.get("username", "")).strip().lstrip("@").lower()

        if not chat_id:
            ignored += 1
            continue
        if not username:
            ignored += 1
            continue

        matches = Employee.objects.filter(
            telegram_username__iexact=username,
            is_active=True,
        )
        count = matches.count()
        if count == 0:
            ignored += 1
            continue
        if count > 1:
            ambiguous += 1
            continue

        employee = matches.first()
        if employee is None:
            ignored += 1
            continue

        employee.telegram_chat_id = chat_id
        if not employee.telegram_username:
            employee.telegram_username = username
        employee.save(update_fields=["telegram_chat_id", "telegram_username", "updated_at"])
        updated += 1

    return {
        "updated": updated,
        "ignored": ignored,
        "ambiguous": ambiguous,
        "events": len(updates),
    }