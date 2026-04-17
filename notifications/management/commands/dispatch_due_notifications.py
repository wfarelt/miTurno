from django.core.management.base import BaseCommand

from notifications.services import dispatch_due_notifications


class Command(BaseCommand):
    help = "Dispatch due pending notifications via configured channels."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--max-retries", type=int, default=3)

    def handle(self, *args, **options):
        result = dispatch_due_notifications(
            limit=options["limit"],
            max_retries=options["max_retries"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Processed {processed} notifications (sent={sent}, failed={failed}).".format(
                    **result
                )
            )
        )
