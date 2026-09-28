from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from absence.services import payroll


class Command(BaseCommand):
    help = "Generate the payroll changes report for a month and print where it was saved."

    def add_arguments(self, parser):
        parser.add_argument("--period", required=True, help="YYYY-MM")

    def handle(self, *args, **options):
        try:
            start, end = payroll.month(options["period"])
        except ValueError:
            raise CommandError("--period is a month, YYYY-MM.")
        run = payroll.run(None, start, end)
        self.stdout.write(str(Path(settings.MEDIA_ROOT) / run.path))
