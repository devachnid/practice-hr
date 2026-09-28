from decimal import Decimal

from django.db import transaction

from people.models import PatternDay, WorkingPattern
from people.services import audit, contracts


def _fmt(amount):
    """Decimal.normalize() drops to scientific notation for round tens
    (Decimal("20.00") -> Decimal('2E+1')); keep plain decimal form instead."""
    normalized = amount.normalize()
    if normalized == normalized.to_integral_value():
        return normalized.quantize(Decimal(1))
    return normalized


def pattern_on(employment, day):
    return (WorkingPattern.objects.filter(employment=employment, effective_from__lte=day)
            .order_by("-effective_from").prefetch_related("days").first())


def units_on(employment, day, half):
    pattern = pattern_on(employment, day)
    if pattern is None:
        return Decimal("0")
    for d in pattern.days.all():
        if d.weekday == day.weekday():
            return d.units(half)
    return Decimal("0")


def weekly_total(pattern):
    return sum((d.am_units + d.pm_units for d in pattern.days.all()), Decimal("0"))


@transaction.atomic
def set_pattern(actor, employment, effective_from, days):
    """Create or replace the version dated effective_from. Returns the
    pattern and a warning string when its total differs from the
    contracted amount that day, which is allowed."""
    pattern, created = WorkingPattern.objects.get_or_create(
        employment=employment, effective_from=effective_from)
    before = "" if created else ", ".join(
        f"{d.weekday}:{d.am_units}/{d.pm_units}" for d in pattern.days.all())
    pattern.days.all().delete()
    for weekday in range(7):
        am, pm = days.get(weekday, (Decimal("0"), Decimal("0")))
        PatternDay.objects.create(pattern=pattern, weekday=weekday, am_units=am, pm_units=pm)
    after = ", ".join(f"{d.weekday}:{d.am_units}/{d.pm_units}" for d in pattern.days.all())
    audit.record(actor, pattern, {"days": (before, after)})
    total = weekly_total(pattern)
    contracted = contracts.contracted_amount(employment, effective_from)
    warning = None
    if contracted and total != contracted:
        warning = f"Pattern totals {_fmt(total)} a week; contracts total {_fmt(contracted)}."
    return pattern, warning
