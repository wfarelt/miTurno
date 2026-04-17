from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from notifications.channels import EmailChannel, WhatsAppChannel
from notifications.models import Notification


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
    return notification


def schedule_booking_notifications(appointment):
    schedule_notification(
        appointment=appointment,
        channel=Notification.Channel.EMAIL,
        event_type=Notification.EventType.BOOKING_CREATED,
        scheduled_for=timezone.now(),
    )


def schedule_confirmation_and_reminders(appointment):
    start = appointment.starts_at
    schedule_notification(
        appointment=appointment,
        channel=Notification.Channel.EMAIL,
        event_type=Notification.EventType.APPOINTMENT_CONFIRMED,
        scheduled_for=timezone.now(),
    )
    schedule_notification(
        appointment=appointment,
        channel=Notification.Channel.EMAIL,
        event_type=Notification.EventType.REMINDER_24H,
        scheduled_for=start - timedelta(hours=24),
    )
    schedule_notification(
        appointment=appointment,
        channel=Notification.Channel.EMAIL,
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
        Notification.objects.select_related("appointment", "appointment__client")
        .filter(
            status=Notification.Status.PENDING,
            scheduled_for__lte=now,
            retry_count__lt=max_retries,
        )
        .order_by("scheduled_for")[:limit]
    )

    email_channel = EmailChannel()
    whatsapp_channel = WhatsAppChannel()

    sent = 0
    failed = 0
    for notification in queryset:
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
            fresh = Notification.objects.select_for_update().get(pk=notification.pk)
            if result.ok:
                fresh.status = Notification.Status.SENT
                fresh.sent_at = timezone.now()
                fresh.error_message = ""
                sent += 1
            else:
                fresh.retry_count += 1
                fresh.error_message = result.error
                if fresh.retry_count >= max_retries:
                    fresh.status = Notification.Status.FAILED
                failed += 1
            fresh.save(
                update_fields=[
                    "status",
                    "sent_at",
                    "retry_count",
                    "error_message",
                    "updated_at",
                ]
            )

    return {"sent": sent, "failed": failed, "processed": sent + failed}