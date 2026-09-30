"""The entitlement of a pot, month by month over its leave year: under a
daily policy the day-by-day integral of (weeks + tier) × weekly amount ÷
days in the year; under a monthly one (Policy.accrual) a twelfth of the
year's figure for each calendar month the person is employed with a
contract, a part month counting in full. Pure: reads people rows and
policies, writes nothing.

The months are calendar months clipped to the leave year, so a year that
starts on the 1st has twelve and one that starts mid-month has thirteen
(its first and last are part months, each a whole twelfth). A month's
basis, figure and weekly amount are those of its last active day, so a
contract change, a tier reached or a policy switching basis part way
through a month counts for that whole month.

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

ZERO = Decimal("0")
DAYS_PER_WEEK = Decimal("5")          # a bank holiday is one working day of a five-day week


def _days(pot):
    d = pot.year_start
    while d <= pot.year_end:
        yield d
        d += timedelta(days=1)


def _months(pot):
    """The pot's days, grouped by calendar month (clipped to the year)."""
    out, month = [], None
    for day in _days(pot):
        if (day.year, day.month) != month:
            month = (day.year, day.month)
            out.append([])
        out[-1].append(day)
    return out


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


def _rates(pot, rows):
    employment = rows.employment
    days_in_year = (pot.year_end - pot.year_start).days + 1
    out = []
    for month in _months(pot):
        rates, last = [], None
        for day in month:
            if not employment.is_active_on(day):
                rates.append((day, ZERO))
                continue
            active = rows.active(day)
            weekly = rows.weekly(active)
            if not weekly:
                rates.append((day, ZERO))
                continue
            rows.check_unit(active, day)
            policy = rows.policy(active, day)
            weeks = policy.weeks_per_year + policies.tier_extra_weeks(policy, employment, day)
            rates.append((day, weeks * weekly / days_in_year))
            last = (day, policy, weeks * weekly)
        if last is not None and last[1].accrual == Policy.Accrual.MONTHLY:
            sampled, _, yearly = last
            rates = [(day, yearly / 12 if day == sampled else ZERO) for day, _ in rates]
        out.extend(rates)
    return out


def daily_rates(pot):
    """[(day, unrounded units accrued that day)]. Under a monthly policy a
    month's twelfth falls on its last active day and its other days are 0.
    Raises ValidationError when a day's contract is in another unit than
    the pot, or no policy covers a day the person is contracted."""
    return _rates(pot, _Rows(pot))


def _step(rows, pot):
    """The rounding step: the policy's on the first contracted day of the year."""
    for day in _days(pot):
        if not rows.employment.is_active_on(day):
            continue
        active = rows.active(day)
        if rows.weekly(active):
            return rows.policy(active, day).rounding
    return None


def entitlement(pot):
    rows = _Rows(pot)
    total = sum((r for _, r in _rates(pot, rows)), ZERO)
    step = _step(rows, pot)
    return ZERO if step is None else rounding.round_to(total, step)


def bank_holidays_between(start, end):
    """The England and Wales bank holidays from `start` to `end`: the only
    ones the pot and the automatic absences count."""
    return BankHoliday.objects.filter(date__range=(start, end), nation="EW")


def bank_holiday_entitlement(pot):
    """The bank-holiday pot, from the calendar: one working day (the weekly
    amount on the day ÷ 5, whatever the working pattern) for each bank
    holiday in the pot's year on which the person is employed with a
    contract, rounded to the policy's step. The policy's weeks, tiers and
    accrual basis do not apply. Every contracted day of the year is still
    checked for its unit and its policy, as entitlement does."""
    rows = _Rows(pot)
    holidays = set(bank_holidays_between(pot.year_start, pot.year_end).values_list("date", flat=True))
    total = ZERO
    for day in _days(pot):
        if not rows.employment.is_active_on(day):
            continue
        active = rows.active(day)
        weekly = rows.weekly(active)
        if not weekly:
            continue
        rows.check_unit(active, day)
        rows.policy(active, day)
        if day in holidays:
            total += weekly / DAYS_PER_WEEK
    step = _step(rows, pot)
    return ZERO if step is None else rounding.round_to(total, step)
