"""What a booking costs, in the employment's unit, from the working
pattern in force on each day. Pure."""

from datetime import time, timedelta
from decimal import Decimal

from absence.models import BankHoliday, ClosedDay
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


def _policy(absence):
    """The policy whose rounding step applies. A pot-backed type with no
    policy is an error naming the missing policy (spec §6: never a silent
    zero); a pot-less type has none and rounds to the quarter."""
    if not absence.absence_type.uses_pot:
        return None
    return policies.policy_for(absence.employment, absence.absence_type, absence.start_date)


def _skip(day, absence):
    """Closed days are never charged. Bank holidays are charged only by the
    automation (bank_holidays.sync_auto_absences), whatever the handling: an
    ordinary booking skips them, so a week off over a bank holiday costs four
    days and the automatic row costs the fifth, from the pot its policy names."""
    if ClosedDay.objects.filter(date=day).exists():
        return True
    if absence.auto_bank_holiday:
        return False
    return BankHoliday.objects.filter(date=day, nation="EW").exists()


def cost(absence):
    return cost_between(absence, None, None)


def cost_between(absence, start, end):
    """The cost of the part of the absence that falls on or between `start`
    and `end` (either may be None for unbounded): the same rules and
    rounding as cost(), applied to the days in the window. The payroll
    report costs a spanning absence one month at a time with it."""
    policy = _policy(absence)
    step = policy.rounding if policy else Decimal("0.25")
    emp = absence.employment
    if absence.is_partial:
        day = absence.start_date
        if (start and day < start) or (end and day > end) or _skip(day, absence):
            return Decimal("0.00")
        cap = Decimal("0")
        if absence.start_time < MIDDAY:
            cap += patterns.units_on(emp, day, "AM")
        if absence.end_time > MIDDAY:
            cap += patterns.units_on(emp, day, "PM")
        return rounding.round_to(min(absence.hours, cap), step)
    total = Decimal("0")
    for day, half in halves_covered(absence):
        if (start and day < start) or (end and day > end) or _skip(day, absence):
            continue
        total += patterns.units_on(emp, day, half)
    return rounding.round_to(total, step)
