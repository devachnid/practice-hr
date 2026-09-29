from django.db import transaction
from django.utils import timezone

from absence.models import Pot
from absence.services import leave_year, policies
from people.services import contracts


def _year(employment, absence_type, day):
    """(first day, last day) of the leave year containing `day`, from the
    policy in force. Raises ValidationError when there is no contract or no
    policy."""
    policy = policies.policy_for(employment, absence_type, day)
    return leave_year.bounds(policy, employment, day)


def lookup(employment, absence_type, day):
    """The pot for the leave year containing `day` if it is open, else None.
    Writes nothing, so a page can call it on GET; pots are opened by
    for_day (the nightly, an approval). Raises ValidationError as for_day."""
    start, _ = _year(employment, absence_type, day)
    return Pot.objects.filter(employment=employment, absence_type=absence_type, year_start=start).first()


@transaction.atomic
def for_day(employment, absence_type, day, actor=None, sync=True):
    """The pot for the leave year containing `day`, created if needed.
    Raises ValidationError when there is no contract or no policy.

    A pot is opened with its entitlement, so a first booking never shows a
    negative balance, and an annual-leave pot with its automatic bank
    holidays (spec §4: they run "when a pot is created"). Any failure
    rolls the new pot back with it. `sync=False` leaves that to the caller:
    the nightly opens pots that way and syncs them in its own loops, so it
    can count what it wrote."""
    start, end = _year(employment, absence_type, day)
    pot, created = Pot.objects.get_or_create(
        employment=employment, absence_type=absence_type, year_start=start,
        defaults={"year_end": end, "unit": contracts.unit(employment, day)})
    if created and sync:
        _open(pot, actor)
    return pot


def _open(pot, actor):
    from absence.services import bank_holidays, ledger
    ledger.sync_entitlement(pot, actor, cause="pot opened")
    # An automatic absence's approval opens its own pot through for_day; when
    # that happens inside the sync (the annual pot under "included in annual",
    # the bank-holiday pot), the sync already running covers the year.
    if pot.absence_type.code == "AL" and not bank_holidays.running():
        bank_holidays.sync_auto_absences(pot.employment, pot.year_start, pot.year_end, actor=actor)


def open_pots(today=None):
    today = today or timezone.localdate()
    return Pot.objects.filter(year_end__gte=today).select_related("employment__employee", "absence_type")
