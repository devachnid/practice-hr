"""The entitlement of a pot, as a day-by-day integral over its leave year.
Pure: reads people rows and policies, writes nothing."""

from datetime import timedelta
from decimal import Decimal

from absence.models import BankHoliday
from absence.services import policies, rounding
from people.services import contracts


def _days(pot):
    d = pot.year_start
    while d <= pot.year_end:
        yield d
        d += timedelta(days=1)


def _policy(pot, day):
    return policies.policy_for(pot.employment, pot.absence_type, day)


def daily_rates(pot, weeks_for_day=None):
    """[(day, unrounded units accrued that day)]. weeks_for_day(policy, day)
    overrides the weeks figure; bank_holiday_entitlement uses that."""
    employment = pot.employment
    days_in_year = (pot.year_end - pot.year_start).days + 1
    out = []
    for day in _days(pot):
        if not employment.is_active_on(day):
            out.append((day, Decimal("0")))
            continue
        weekly = contracts.contracted_amount(employment, day)
        if not weekly:
            out.append((day, Decimal("0")))
            continue
        policy = _policy(pot, day)
        if weeks_for_day is not None:
            weeks = weeks_for_day(policy, day)
        else:
            weeks = policy.weeks_per_year + policies.tier_extra_weeks(policy, employment, day)
        out.append((day, weeks * weekly / days_in_year))
    return out


def _rounded_total(pot, rates):
    total = sum((r for _, r in rates), Decimal("0"))
    first_active = next((d for d in _days(pot) if pot.employment.is_active_on(d)
                         and contracts.contracted_amount(pot.employment, d)), None)
    if first_active is None:
        return Decimal("0")
    return rounding.round_to(total, _policy(pot, first_active).rounding)


def entitlement(pot):
    return _rounded_total(pot, daily_rates(pot))


def bank_holiday_entitlement(pot):
    """Under pro_rata_pot: the year's bank holidays divided by five, as weeks."""
    n = BankHoliday.objects.filter(date__range=(pot.year_start, pot.year_end), nation="EW").count()
    weeks = Decimal(n) / Decimal("5")
    return _rounded_total(pot, daily_rates(pot, weeks_for_day=lambda policy, day: weeks))
