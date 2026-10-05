"""The registrations step of hr_nightly: sync each body's verified flag
from its adapter's fixtures, then run tonight's lookups. Never raises out
of the command: the digest has already gone; the next night retries."""
import logging

from registers import adapters
from registers.models import RegisterBody
from registers.services import lookups

log = logging.getLogger("hr.registers")
UNREADABLE_AFTER_DAYS = 14


def sync_verified():
    n = 0
    for body in RegisterBody.objects.all():
        verified = body.code in adapters.CODES and adapters.verified(body.code)
        if body.verified != verified:
            body.verified = verified
            body.save(update_fields=["verified"])
            if not verified:
                log.info("register body %s is not verified: no saved pages to test its parser", body.code)
        n += verified
    return n


def run(today):
    verified = sync_verified()
    counts = lookups.scheduled(today)
    return {**counts, "verified": verified}
