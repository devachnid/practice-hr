from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from absence.services import year_end


class Command(BaseCommand):
    help = "Close pots whose leave year has ended and run the date-based expiries."

    def add_arguments(self, parser):
        parser.add_argument("--today", default=None, help="YYYY-MM-DD; defaults to the practice's today")

    def handle(self, *args, **options):
        today = date.fromisoformat(options["today"]) if options["today"] else timezone.localdate()
        self.stdout.write(str(year_end.run(today)))
