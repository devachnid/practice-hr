from django.core.management.base import BaseCommand
from django.utils import timezone

from absence.services import nightly as absence_nightly
from people.services import nightly as people_nightly


class Command(BaseCommand):
    help = "Nightly housekeeping. Each app's services.nightly.run(today) is called in turn."

    def handle(self, *args, **options):
        # The practice's day (TIME_ZONE), not the server's: the timer runs at
        # 01:30 London time, which is still yesterday in UTC for half the year.
        today = timezone.localdate()
        results = {"people": people_nightly.run(today), "absence": absence_nightly.run(today)}
        for app, result in results.items():
            self.stdout.write(f"{app}: {result}")
