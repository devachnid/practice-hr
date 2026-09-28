"""Bank holidays are charged automatically under the two pot handlings."""

from django.core.exceptions import ValidationError
from django.db import transaction

from absence.models import Absence, AbsenceType, BankHoliday, Policy
from absence.services import bookings, policies
from people.services import patterns


def _target_type(handling):
    if handling == Policy.BankHolidays.PRO_RATA_POT:
        return AbsenceType.objects.get(code="BH")
    if handling == Policy.BankHolidays.INCLUDED_IN_ANNUAL:
        return AbsenceType.objects.get(code="AL")
    return None


@transaction.atomic
def sync_auto_absences(employment, year_start, year_end, actor=None):
    """Create the approved bank-holiday absences the pattern and policy
    imply, cancel the ones they no longer imply. Idempotent. A day the
    person has booked off still gets its row: their booking skipped the bank
    holiday (costing), so this row is what charges it."""
    created = removed = 0
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
            wanted[bh.date] = target
    for day, absence in list(existing.items()):
        if wanted.get(day) != absence.absence_type:
            bookings.cancel(actor, absence)
            removed += 1
            del existing[day]
    for day, target in wanted.items():
        if day in existing:
            continue
        a = Absence(employment=employment, absence_type=target, start_date=day, end_date=day,
                    auto_bank_holiday=True, requested_by=actor)
        a.full_clean(exclude=["employment", "absence_type", "requested_by"])
        a.save()
        bookings.approve(actor, a, comment="bank holiday")
        created += 1
    return {"created": created, "removed": removed}
