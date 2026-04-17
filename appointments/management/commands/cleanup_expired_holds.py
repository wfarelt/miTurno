from django.core.management.base import BaseCommand
from django.utils import timezone

from appointments.models import SlotHold


class Command(BaseCommand):
    help = "Delete expired slot holds."

    def add_arguments(self, parser):
        parser.add_argument(
            "--business-slug",
            type=str,
            default=None,
            help="Optional business slug filter.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print how many rows would be removed without deleting.",
        )

    def handle(self, *args, **options):
        queryset = SlotHold.objects.filter(expires_at__lte=timezone.now())
        business_slug = options.get("business_slug")
        if business_slug:
            queryset = queryset.filter(business__slug=business_slug)

        count = queryset.count()
        if options.get("dry_run"):
            self.stdout.write(self.style.WARNING(f"Dry run: {count} expired holds found."))
            return

        deleted, _ = queryset.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} expired holds."))
