import logging

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from absence.services import nightly as absence_nightly
from compliance.services import nightly as compliance_nightly
from people.services import nightly as people_nightly
from registers.services import nightly as registers_nightly

log = logging.getLogger("hr.nightly")


class Command(BaseCommand):
    help = "Nightly housekeeping. Each app's services.nightly.run(today) is called in turn."

    def handle(self, *args, **options):
        # The practice's day (TIME_ZONE), not the server's: the timer runs at
        # 01:30 London time, which is still yesterday in UTC for half the year.
        today = timezone.localdate()
        # Each line is printed as its step finishes, so a later failure
        # cannot lose an earlier step's line from the journal.
        self.stdout.write(f"people: {people_nightly.run(today)}")
        self.stdout.write(f"absence: {absence_nightly.run(today)}")
        try:
            result = compliance_nightly.run(today)
        except Exception as exc:  # noqa: BLE001 - reported below; the class only, its message may name someone
            log.error("nightly compliance step failed: %s", exc.__class__.__name__)
            self.stdout.write("compliance: failed")
            raise CommandError(f"compliance step failed: {exc.__class__.__name__}") from None
        self.stdout.write(f"compliance: {result}")
        try:
            self.stdout.write(f"registrations: {registers_nightly.run(today)}")
        except Exception as exc:  # noqa: BLE001 - the class only; the next night retries
            log.error("nightly registrations step failed: %s", exc.__class__.__name__)
            self.stdout.write("registrations: failed")
