from celery import shared_task
from django.utils import timezone

from appointments.models import SlotHold


@shared_task
def cleanup_expired_holds_task(business_slug=None, dry_run=False):
    queryset = SlotHold.objects.filter(expires_at__lte=timezone.now())
    if business_slug:
        queryset = queryset.filter(business__slug=business_slug)

    if dry_run:
        return queryset.count()

    deleted, _ = queryset.delete()
    return deleted
