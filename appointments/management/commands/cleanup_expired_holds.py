from django.core.management.base import BaseCommand
from appointments.tasks import cleanup_expired_holds_task


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
        business_slug = options.get("business_slug")
        if options.get("dry_run"):
            count = cleanup_expired_holds_task(
                business_slug=business_slug,
                dry_run=True,
            )
            self.stdout.write(self.style.WARNING(f"Dry run: {count} expired holds found."))
            return

        deleted = cleanup_expired_holds_task(business_slug=business_slug)
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} expired holds."))
