"""Bank holidays are charged automatically under the two pot handlings."""

from contextvars import ContextVar

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from absence.models import Absence, AbsenceType, BankHoliday, Policy
from absence.services import bookings, costing, policies, pots
from people.services import audit, patterns


def _target_type(handling):
    if handling == Policy.BankHolidays.PRO_RATA_POT:
        return AbsenceType.objects.get(code="BH")
    if handling == Policy.BankHolidays.INCLUDED_IN_ANNUAL:
        return AbsenceType.objects.get(code="AL")
    return None


# The reason on an automatic row cancelled because the pattern or policy no
# longer implies it (or the employment has ended before it). A row cancelled
# for any other reason was cancelled on purpose: the sync leaves that day
# alone, and it is charged again only by recording it.
NOT_IMPLIED = "no longer implied by the pattern or policy"

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
    skipped the bank holiday (costing), so this row is what charges it. A
    day whose latest automatic row was cancelled other than by the sync
    (NOT_IMPLIED) is not charged again ("kept_cancelled")."""
    token = _running.set(True)
    try:
        return _sync(employment, year_start, year_end, actor, today or timezone.localdate())
    finally:
        _running.reset(token)


def _sync(employment, year_start, year_end, actor, today):
    created = removed = recosted = kept_cancelled = 0
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
            bookings.cancel(actor, absence, reason=NOT_IMPLIED)
            removed += 1
            del existing[day]
    cancelled = {a.start_date: a for a in Absence.objects.filter(      # the latest per day wins
        employment=employment, auto_bank_holiday=True, status=Absence.Status.CANCELLED,
        start_date__range=(year_start, year_end)).order_by("cancelled_at", "pk")}
    for day, target in wanted.items():
        if day not in existing and day in cancelled and cancelled[day].cancel_reason != NOT_IMPLIED:
            kept_cancelled += 1
            continue
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
    return {"created": created, "removed": removed, "recosted": recosted, "kept_cancelled": kept_cancelled}


@transaction.atomic
def charge_again(actor, absence):
    """HR undoes an opt-out: the cancelled automatic row's day is charged
    again. Its cancel reason (and that of any other cancelled automatic row
    of the same person and day, so the latest cannot still hold the day) is
    set to NOT_IMPLIED, audited, and the row's leave year is synced at once
    as `actor`: the day comes back as a new automatic row if the pattern and
    policy still imply it, and stays uncharged if they do not. Returns the
    sync's counts."""
    if not (absence.auto_bank_holiday and absence.status == Absence.Status.CANCELLED):
        raise ValidationError("Only a cancelled automatic bank-holiday row can be charged again.")
    employment, day = absence.employment, absence.start_date
    rows = (Absence.objects.select_for_update()
            .filter(employment=employment, auto_bank_holiday=True, status=Absence.Status.CANCELLED, start_date=day)
            .exclude(cancel_reason=NOT_IMPLIED))
    for row in rows:
        audit.record(actor, row, {"cancel_reason": (row.cancel_reason, NOT_IMPLIED)}, note="charged again")
        row.cancel_reason = NOT_IMPLIED
        row.save(update_fields=["cancel_reason"])
    absence.refresh_from_db(fields=["cancel_reason"])
    year_start, year_end = pots.bounds(employment, AbsenceType.objects.get(code="AL"), day)
    return sync_auto_absences(employment, year_start, year_end, actor=actor)
