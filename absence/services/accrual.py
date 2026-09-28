"""The entitlement of a pot, as a day-by-day integral over its leave year.
Pure: reads people rows and policies, writes nothing.

The rows are read once per pot (the employment's contracts, the policies
and tiers for their contract types, the year's bank holidays) and every day
is computed in memory, so an entitlement is a handful of queries, not
several per day."""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError

from absence.models import BankHoliday, Policy
from absence.services import policies, rounding
from people.models import Contract


def _days(pot):
    d = pot.year_start
    while d <= pot.year_end:
        yield d
        d += timedelta(days=1)


class _Rows:
    """What one pot's year reads, loaded once. The lookups mirror
    contracts.active_on / contracted_amount / unit and policies.policy_for,
    including their errors."""

    def __init__(self, pot):
        self.pot = pot
        self.employment = pot.employment
        self.contracts = list(Contract.objects.filter(
            employment=self.employment, from_date__lte=pot.year_end)
            .select_related("contract_type").order_by("from_date", "id"))
        types = {c.contract_type_id for c in self.contracts}
        self.policies = list(Policy.objects.filter(contract_type_id__in=types, absence_type=pot.absence_type)
                             .select_related("contract_type", "absence_type")
                             .prefetch_related("tiers").order_by("-effective_from"))

    def active(self, day):
        return [c for c in self.contracts if c.is_active_on(day)]

    def weekly(self, active):
        return sum((c.weekly_amount for c in active), Decimal("0"))

    def policy(self, active, day):
        ct = active[0].contract_type
        for p in self.policies:          # newest first, as policy_for orders them
            if p.contract_type_id == ct.pk and p.is_active_on(day):
                return p
        raise ValidationError(f"No {self.pot.absence_type} policy for {ct} on {day:%d %b %Y}. "
                              f"Add one under Absence › Policies.")

    def check_unit(self, active, day):
        unit = active[0].contract_type.unit
        if unit != self.pot.unit:
            raise ValidationError(
                f"{self.pot} is in {self.pot.unit}, but the contract on {day:%d %b %Y} is in {unit}. "
                f"A change of unit needs a new pot; it cannot be mixed into this one.")


def _rates(pot, rows, weeks_for_day):
    employment = rows.employment
    days_in_year = (pot.year_end - pot.year_start).days + 1
    out = []
    for day in _days(pot):
        if not employment.is_active_on(day):
            out.append((day, Decimal("0")))
            continue
        active = rows.active(day)
        weekly = rows.weekly(active)
        if not weekly:
            out.append((day, Decimal("0")))
            continue
        rows.check_unit(active, day)
        policy = rows.policy(active, day)
        if weeks_for_day is not None:
            weeks = weeks_for_day(policy, day)
        else:
            weeks = policy.weeks_per_year + policies.tier_extra_weeks(policy, employment, day)
        out.append((day, weeks * weekly / days_in_year))
    return out


def daily_rates(pot, weeks_for_day=None):
    """[(day, unrounded units accrued that day)]. weeks_for_day(policy, day)
    overrides the weeks figure; bank_holiday_entitlement uses that. Raises
    ValidationError when a day's contract is in another unit than the pot."""
    return _rates(pot, _Rows(pot), weeks_for_day)


def _entitlement(pot, weeks_for_day=None):
    rows = _Rows(pot)
    rates = _rates(pot, rows, weeks_for_day)
    total = sum((r for _, r in rates), Decimal("0"))
    for day, _ in rates:
        if not rows.employment.is_active_on(day):
            continue
        active = rows.active(day)
        if rows.weekly(active):
            return rounding.round_to(total, rows.policy(active, day).rounding)
    return Decimal("0")


def entitlement(pot):
    return _entitlement(pot)


def bank_holiday_entitlement(pot):
    """Under pro_rata_pot: the year's bank holidays divided by five, as weeks."""
    n = BankHoliday.objects.filter(date__range=(pot.year_start, pot.year_end), nation="EW").count()
    weeks = Decimal(n) / Decimal("5")
    return _entitlement(pot, weeks_for_day=lambda policy, day: weeks)
