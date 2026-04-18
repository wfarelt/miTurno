from celery import shared_task

from notifications.services import (
    backfill_confirmed_reminders,
    dispatch_due_notifications,
)


@shared_task
def schedule_appointment_notifications_task(lookahead_hours=48):
    return backfill_confirmed_reminders(lookahead_hours=lookahead_hours)


@shared_task
def dispatch_due_notifications_task(limit=100, max_retries=3):
    return dispatch_due_notifications(limit=limit, max_retries=max_retries)
