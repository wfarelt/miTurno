from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from notifications.channels import EmailChannel, WhatsAppChannel
from notifications.models import Notification, NotificationOutbox


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
        else:
            result = whatsapp_channel.send(
                to_phone=appointment.client.phone,
                body=body,
            )

        with transaction.atomic():
            fresh_outbox = NotificationOutbox.objects.select_for_update().get(pk=outbox.pk)
            fresh_notification = Notification.objects.select_for_update().get(pk=notification.pk)

            fresh_outbox.attempts += 1
            fresh_outbox.locked_at = timezone.now()
            if result.ok:
                fresh_outbox.status = NotificationOutbox.Status.DELIVERED
                fresh_outbox.last_error = ""

                fresh_notification.status = Notification.Status.SENT
                fresh_notification.sent_at = timezone.now()
                fresh_notification.error_message = ""
                sent += 1
            else:
                fresh_outbox.last_error = result.error
                if fresh_outbox.attempts >= max_retries:
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
                    "last_error",
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