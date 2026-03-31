from django.core.management.base import BaseCommand

from control_center.services import retry_due_sync_jobs


class Command(BaseCommand):
    help = "Retry due sync delivery jobs in a bounded batch."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=25,
            help="Maximum number of due jobs to process in one run.",
        )

    def handle(self, *args, **options):
        limit = max(1, int(options["limit"]))
        processed = retry_due_sync_jobs(limit=limit)
        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {processed} due sync job(s) with limit={limit}."
            )
        )
