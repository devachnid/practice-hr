from decimal import ROUND_DOWN, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from people.models import Employment
from people.services import audit


def active_on(day):
    return Employment.objects.filter(
        Q(start_date__lte=day) & (Q(end_date__isnull=True) | Q(end_date__gte=day)))


def current(employee, day):
    return active_on(day).filter(employee=employee).first()


def _overlaps(employee, start, end, exclude_pk=None):
    qs = Employment.objects.filter(employee=employee)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    qs = qs.filter(Q(end_date__isnull=True) | Q(end_date__gte=start))
    if end is not None:
        qs = qs.filter(start_date__lte=end)
    return qs.exists()


@transaction.atomic
def start(actor, employee, start_date, continuous_service_date=None):
    if _overlaps(employee, start_date, None):
        raise ValidationError("This person already has an employment covering that date.")
    emp = Employment(employee=employee, start_date=start_date,
                     continuous_service_date=continuous_service_date or start_date)
    emp.full_clean()
    emp.save()
    audit.record(actor, emp, {"start_date": ("", start_date),
                              "continuous_service_date": ("", emp.continuous_service_date)})
    return emp


@transaction.atomic
def end(actor, employment, end_date, leaving_reason):
    before = (employment.end_date, employment.leaving_reason)
    employment.end_date = end_date
    employment.leaving_reason = leaving_reason
    employment.full_clean()
    employment.save()
    audit.record(actor, employment, {"end_date": (before[0], end_date),
                                     "leaving_reason": (before[1], leaving_reason)})
    return employment


@transaction.atomic
def amend(actor, employment, start_date=None, continuous_service_date=None):
    """Change the dates of an existing spell. Re-runs the overlap check."""
    new_start = start_date or employment.start_date
    if _overlaps(employment.employee, new_start, employment.end_date, exclude_pk=employment.pk):
        raise ValidationError("Another employment covers those dates.")
    changes = {}
    if start_date and start_date != employment.start_date:
        changes["start_date"] = (employment.start_date, start_date)
        employment.start_date = start_date
    if continuous_service_date and continuous_service_date != employment.continuous_service_date:
        changes["continuous_service_date"] = (employment.continuous_service_date, continuous_service_date)
        employment.continuous_service_date = continuous_service_date
    employment.full_clean()
    employment.save()
    audit.record(actor, employment, changes)
    return employment


def _anniversary(start, year):
    try:
        return start.replace(year=year)
    except ValueError:            # 29 February in a common year
        return start.replace(year=year, day=28)


def service_years(employment, day):
    """Continuous service on `day`: whole years by calendar anniversary,
    plus the fraction of the current anniversary year, rounded down to two
    places so a tier is never reached a day early. The anniversary itself
    reads exactly N.00."""
    start = employment.continuous_service_date
    years = day.year - start.year
    if _anniversary(start, start.year + years) > day:
        years -= 1
    last = _anniversary(start, start.year + years)
    nxt = _anniversary(start, start.year + years + 1)
    fraction = Decimal((day - last).days) / Decimal((nxt - last).days)
    return (Decimal(years) + fraction).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
