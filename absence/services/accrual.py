"""The entitlement of a pot, month by month over its leave year: under a
daily policy the day-by-day integral of (weeks + tier) × weekly amount ÷
days in the year; under a monthly one (Policy.accrual) a twelfth of the
year's figure for each month of the leave year in which the person is
employed with a contract, a part month counting in full. Pure: reads
people rows and policies, writes nothing.

The twelve months are counted from the leave year's start, on the same day
of the month (clipped at a short month's end): a 1 January year gives the
calendar months, a 15 March one 15 Mar-14 Apr … 15 Feb-14 Mar. A month's
basis, figure and weekly amount are those of its last active day, so a
contract change, a tier reached or a policy switching basis part way
through a month counts for that whole month.

A day counts towards a pot only when the policy in force that day puts it
in the pot's own leave year (leave_year.bounds). Ordinarily every day of
the year does; when a type moves from an April to a January year (the
April policy ending on 31 December, a January one from 1 January), January
to March count in the new year's pots and not in the April pots as well.

The rows are read once per pot (the employment's contracts, the policies
and tiers for their contract types, the year's bank holidays) and every day
is computed in memory, so an entitlement is a handful of queries, not
several per day.

A pot whose type does not accrue (TOIL: earned, not accrued) is 0 on every
day and reads nothing: no policy, contract or bank holiday."""

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError

from absence.models import BankHoliday, Policy
from absence.services import leave_year, policies, rounding
from people.models import Contract

ZERO = Decimal("0")
DAYS_PER_WEEK = Decimal("5")          # a bank holiday is one working day of a five-day week


def _days(pot):
    d = pot.year_start
    while d <= pot.year_end:
        yield d
        d += timedelta(days=1)


def _month_start(start, k):
    """`start` plus k months, on the same day of the month or the month's last day."""
    year, month = divmod(start.month - 1 + k, 12)
    year, month = start.year + year, month + 1
    return date(year, month, min(start.day, monthrange(year, month)[1]))


def _months(pot):
    """The pot's days in its twelve months from year_start: month k is
    [start + k months, start + k+1 months), the twelfth running to year_end.
    Exactly twelve, even where a clipped start (a 29 February anniversary
    kept on 28 February) would fit a thirteenth before year_end."""
    out = []
    for k in range(12):
        first = _month_start(pot.year_start, k)
        last = pot.year_end if k == 11 else min(_month_start(pot.year_start, k + 1) - timedelta(days=1),
                                                pot.year_end)
        out.append([first + timedelta(days=i) for i in range((last - first).days + 1)])
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

    def counted(self, day):
        """(active contracts, weekly amount, policy) for a day that counts
        towards this pot, else None: the person employed with a contracted
        amount, and the day's policy putting the day in the pot's own leave
        year. A day a later policy moves into another year (a type moved
        from an April to a January year) belongs to that year's pot, not to
        this one too. Raises for a day in another unit or with no policy."""
        if not self.employment.is_active_on(day):
            return None
        active = self.active(day)
        weekly = self.weekly(active)
        if not weekly:
            return None
        self.check_unit(active, day)
        policy = self.policy(active, day)
        if leave_year.bounds(policy, self.employment, day)[0] != self.pot.year_start:
            return None
        return active, weekly, policy

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
            found = rows.counted(day)
            if found is None:
                rates.append((day, ZERO))
                continue
            _, weekly, policy = found
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
    A day whose policy puts it in another leave year is 0 (_Rows.counted).
    Raises ValidationError when a day's contract is in another unit than
    the pot, or no policy covers a day the person is contracted. All 0 for a
    type that does not accrue."""
    if not pot.absence_type.accrues:
        return [(day, ZERO) for day in _days(pot)]
    return _rates(pot, _Rows(pot))


def _step(rows, pot):
    """The rounding step: the policy's on the first day that counts towards the pot."""
    for day in _days(pot):
        found = rows.counted(day)
        if found is not None:
            return found[2].rounding
    return None


def entitlement(pot):
    if not pot.absence_type.accrues:
        return ZERO
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
    contract and which that day's policy puts in the pot's year, rounded to
    the policy's step. The policy's weeks, tiers and accrual basis do not
    apply. Every contracted day of the year is still checked for its unit
    and its policy, as entitlement does. 0 for a type that does not accrue."""
    if not pot.absence_type.accrues:
        return ZERO
    rows = _Rows(pot)
    holidays = set(bank_holidays_between(pot.year_start, pot.year_end).values_list("date", flat=True))
    total = ZERO
    for day in _days(pot):
        found = rows.counted(day)                  # checks every day, holiday or not
        if found is not None and day in holidays:
            total += found[1] / DAYS_PER_WEEK
    step = _step(rows, pot)
    return ZERO if step is None else rounding.round_to(total, step)
