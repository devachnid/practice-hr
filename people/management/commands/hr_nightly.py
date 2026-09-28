from datetime import date

from django.core.management.base import BaseCommand

from people.services import nightly as people_nightly


class Command(BaseCommand):
    help = "Nightly housekeeping. Each app's services.nightly.run(today) is called in turn."

    def handle(self, *args, **options):
        today = date.today()
        results = {"people": people_nightly.run(today)}
        for app, result in results.items():
            self.stdout.write(f"{app}: {result}")
