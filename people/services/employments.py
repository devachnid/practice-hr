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


def check_start(employee, start_date, end_date=None):
    """start()'s rule, without writing: raises ValidationError if a spell
    over these dates would overlap one the employee already has. An
    employee not yet saved has none."""
    if employee.pk is not None and _overlaps(employee, start_date, end_date):
        raise ValidationError("This person already has an employment covering those dates.")


def check_end(employment, end_date):
    """end()'s rule, without writing. Only widening an already-bounded spell
    (extending it, or reopening it) can newly reach a later spell; a spell
    that was already open-ended could never have let one exist."""
    if employment.end_date is not None and (end_date is None or end_date > employment.end_date):
        if _overlaps(employment.employee, employment.start_date, end_date, exclude_pk=employment.pk):
            raise ValidationError("Another employment covers those dates.")


def check_amend(employment, start_date=None):
    """amend()'s rule, without writing."""
    new_start = start_date or employment.start_date
    if _overlaps(employment.employee, new_start, employment.end_date, exclude_pk=employment.pk):
        raise ValidationError("Another employment covers those dates.")


@transaction.atomic
def start(actor, employee, start_date, continuous_service_date=None, end_date=None,
          leaving_reason=""):
    """A new spell. Usually open-ended; a spell already over (a past one
    being entered after the fact) takes its end date and reason here, so
    the overlap check sees its real dates rather than an open end that
    would collide with every later spell."""
    check_start(employee, start_date, end_date)
    emp = Employment(employee=employee, start_date=start_date, end_date=end_date,
                     leaving_reason=leaving_reason,
                     continuous_service_date=continuous_service_date or start_date)
    emp.full_clean()
    emp.save()
    changes = {"start_date": ("", start_date),
               "continuous_service_date": ("", emp.continuous_service_date)}
    if end_date is not None:
        changes.update({"end_date": ("", end_date), "leaving_reason": ("", leaving_reason)})
    audit.record(actor, emp, changes)
    return emp


def _cancel_after(actor, employment, end_date):
    """Cancel, through the absence service, the employment's live absences
    (requested or approved) that start after its last day, so they leave the
    calendar, the rota's feed and the balances. One that cannot be cancelled
    (its pot's leave year has closed) is left as it is. Returns the audit
    note, the ones not cancelled first (the part HR must act on), then a count
    and list of those cancelled, or ""."""
    if end_date is None:
        return ""
    from absence.models import Absence
    from absence.services import bookings
    done, left = [], []
    live = (Absence.objects.filter(employment=employment, status__in=bookings.LIVE, start_date__gt=end_date)
            .select_related("employment__employee", "absence_type").order_by("start_date", "id"))
    for absence in live:
        try:
            bookings.cancel(actor, absence)       # its own savepoint: a refusal leaves the rest
        except ValidationError as e:
            left.append(f"{absence} ({'; '.join(e.messages)})")
        else:
            done.append(f"{absence.absence_type} {absence.start_date:%d %b %Y}")
    parts = []
    if left:
        parts.append(f"not cancelled: {'; '.join(left)}")
    if done:
        parts.append(f"cancelled {len(done)} absence(s) after the leaving date: {', '.join(done)}")
    note = "; ".join(parts)
    # AuditEntry.note holds 200 characters: show a cut, never drop the end silently
    return note if len(note) <= 200 else note[:199] + "…"


@transaction.atomic
def end(actor, employment, end_date, leaving_reason):
    """Set (or clear) the last day. Live absences starting after it are
    cancelled in the same transaction (_cancel_after), and the audit entry's
    note lists them."""
    check_end(employment, end_date)
    before = (employment.end_date, employment.leaving_reason)
    employment.end_date = end_date
    employment.leaving_reason = leaving_reason
    employment.full_clean()
    employment.save()
    note = _cancel_after(actor, employment, end_date)
    audit.record(actor, employment, {"end_date": (before[0], end_date),
                                     "leaving_reason": (before[1], leaving_reason)}, note=note)
    return employment


@transaction.atomic
def amend(actor, employment, start_date=None, continuous_service_date=None):
    """Change the dates of an existing spell. Re-runs the overlap check."""
    check_amend(employment, start_date)
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
