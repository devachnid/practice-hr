"""The registrations step of hr_nightly: sync each body's verified flag
from its adapter's fixtures, make any row that uses a number already held
(the Welsh list, for a title that came to need it), then run tonight's
lookups. Never raises out
of the command, which runs it before the morning digest: the digest still
goes, and the next night retries."""
import logging

from registers import adapters
from registers.models import RegisterBody
from registers.services import lookups, registrations

log = logging.getLogger("hr.registers")
UNREADABLE_AFTER_DAYS = 14


def sync_verified():
    n = 0
    for body in RegisterBody.objects.all():
        verified = body.code in adapters.CODES and adapters.verified(body.code)
        if body.verified != verified:
            body.verified = verified
            body.save(update_fields=["verified"])
        if not verified:                     # every night, so the journal says why nothing ran
            log.info("register body %s is not verified: no saved pages to test its parser", body.code)
        n += verified
    return n


def run(today):
    verified = sync_verified()
    filled = registrations.fill_all_shared(None, today)
    counts = lookups.scheduled(today)
    return {**counts, "verified": verified, "filled": filled}
