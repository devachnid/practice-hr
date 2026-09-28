"""What a booking costs, in the employment's unit, from the working
pattern in force on each day. Pure."""

from datetime import time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError

from absence.models import BankHoliday, ClosedDay, Policy
from absence.services import policies, rounding
from people.services import patterns

MIDDAY = time(13, 0)


def halves_covered(absence):
    out = []
    day = absence.start_date
    while day <= absence.end_date:
        halves = ["AM", "PM"]
        if day == absence.start_date and absence.start_half == "PM":
            halves.remove("AM")
        if day == absence.end_date and absence.end_half == "AM":
            halves.remove("PM")
        out.extend((day, h) for h in halves)
        day += timedelta(days=1)
    return out


def _handling(absence):
    try:
        return policies.policy_for(absence.employment, absence.absence_type, absence.start_date)
    except ValidationError:
        return None


def _skip(day, policy):
    if ClosedDay.objects.filter(date=day).exists():
        return True
    handling = policy.bank_holiday_handling if policy else Policy.BankHolidays.CLOSED_NOT_CHARGED
    if handling == Policy.BankHolidays.CLOSED_NOT_CHARGED:
        return BankHoliday.objects.filter(date=day, nation="EW").exists()
    return False


def cost(absence):
    policy = _handling(absence)
    step = policy.rounding if policy else Decimal("0.25")
    emp = absence.employment
    if absence.is_partial:
        day = absence.start_date
        if _skip(day, policy):
            return Decimal("0.00")
        cap = Decimal("0")
        if absence.start_time < MIDDAY:
            cap += patterns.units_on(emp, day, "AM")
        if absence.end_time > MIDDAY:
            cap += patterns.units_on(emp, day, "PM")
        return rounding.round_to(min(absence.hours, cap), step)
    total = Decimal("0")
    for day, half in halves_covered(absence):
        if _skip(day, policy):
            continue
        total += patterns.units_on(emp, day, half)
    return rounding.round_to(total, step)
