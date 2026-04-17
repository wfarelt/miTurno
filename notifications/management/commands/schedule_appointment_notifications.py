from django.core.management.base import BaseCommand

from notifications.services import backfill_confirmed_reminders


class Command(BaseCommand):
    help = "Backfill confirmation/reminder notifications for upcoming confirmed appointments."

    def add_arguments(self, parser):
        parser.add_argument(
            "--lookahead-hours",
            type=int,
            default=48,
            help="Hours ahead to scan confirmed appointments.",
        )

    def handle(self, *args, **options):
        created = backfill_confirmed_reminders(
            lookahead_hours=options["lookahead_hours"],
        )
        self.stdout.write(
            self.style.SUCCESS(f"Created {created} notifications.")
        )
