"""Bank holidays are charged automatically under the two pot handlings."""

from contextvars import ContextVar

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from absence.models import Absence, AbsenceType, BankHoliday, Policy
from absence.services import bookings, costing, policies
from people.services import patterns


def _target_type(handling):
    if handling == Policy.BankHolidays.PRO_RATA_POT:
        return AbsenceType.objects.get(code="BH")
    if handling == Policy.BankHolidays.INCLUDED_IN_ANNUAL:
        return AbsenceType.objects.get(code="AL")
    return None


_running = ContextVar("bank_holiday_sync_running", default=False)


def running():
    """True inside sync_auto_absences: pots opened by its own approvals must
    not start a second sync of the same year (pots._open)."""
    return _running.get()


@transaction.atomic
def sync_auto_absences(employment, year_start, year_end, actor=None, today=None):
    """Create the approved bank-holiday absences the pattern and policy
    imply, cancel the ones they no longer imply, and re-cost the ones from
    `today` on whose pattern has changed (a past charge stands). Idempotent.
    A day the person has booked off still gets its row: their booking
    skipped the bank holiday (costing), so this row is what charges it."""
    token = _running.set(True)
    try:
        return _sync(employment, year_start, year_end, actor, today or timezone.localdate())
    finally:
        _running.reset(token)


def _sync(employment, year_start, year_end, actor, today):
    created = removed = recosted = 0
    al = AbsenceType.objects.get(code="AL")
    existing = {a.start_date: a for a in Absence.objects.filter(
        employment=employment, auto_bank_holiday=True, status=Absence.Status.APPROVED,
        start_date__range=(year_start, year_end))}
    wanted = {}
    for bh in BankHoliday.objects.filter(date__range=(year_start, year_end), nation="EW"):
        if not employment.is_active_on(bh.date):
            continue
        try:
            policy = policies.policy_for(employment, al, bh.date)
        except ValidationError:
            continue
        target = _target_type(policy.bank_holiday_handling)
        if target is None:
            continue
        units = patterns.units_on(employment, bh.date, "AM") + patterns.units_on(employment, bh.date, "PM")
        if units:
            if target.code == "BH":
                # the bank-holiday pot needs its own policy (leave year, rounding);
                # without one, say so rather than charge nothing
                policies.policy_for(employment, target, bh.date)
            wanted[bh.date] = target
    for day, absence in list(existing.items()):
        if wanted.get(day) != absence.absence_type:
            bookings.cancel(actor, absence)
            removed += 1
            del existing[day]
    for day, target in wanted.items():
        if day in existing:
            kept = existing[day]
            if day >= today and costing.cost(kept) != kept.cost_units:
                bookings.recost(actor, kept, "working pattern changed")
                recosted += 1
            continue
        a = Absence(employment=employment, absence_type=target, start_date=day, end_date=day,
                    auto_bank_holiday=True, requested_by=actor)
        a.full_clean(exclude=["employment", "absence_type", "requested_by"])
        a.save()
        bookings.approve(actor, a, comment="bank holiday")
        created += 1
    return {"created": created, "removed": removed, "recosted": recosted}
