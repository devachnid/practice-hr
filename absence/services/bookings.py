"""Every change of an Absence's status, and the ledger line it implies."""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from absence.models import Absence, KitDay, LedgerEntry
from absence.services import costing, leave_year, ledger, policies, pots
from people.services import audit, contracts

LIVE = (Absence.Status.REQUESTED, Absence.Status.APPROVED)
SELF_CERT_DAYS = 7


def overlaps(employment, start, end, exclude_pk=None, auto=False):
    """A live absence of the same kind over these dates. Ordinary bookings
    clash with each other; automatic bank-holiday rows clash only with each
    other, so a week off and the bank holiday inside it coexist (the booking
    skips the bank holiday; the automatic row charges it)."""
    qs = Absence.objects.filter(employment=employment, status__in=LIVE, auto_bank_holiday=auto,
                                start_date__lte=end, end_date__gte=start)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


def _check_leave_year(absence):
    if not absence.absence_type.uses_pot:
        return
    policy = policies.policy_for(absence.employment, absence.absence_type, absence.start_date)
    _, end = leave_year.bounds(policy, absence.employment, absence.start_date)
    if absence.end_date > end:
        raise ValidationError("This crosses the end of the leave year. Book the two leave years separately.")


def _lock(absence):
    """Re-read the row under a lock, so a stale in-memory copy cannot pass a status guard."""
    return Absence.objects.select_for_update().get(pk=absence.pk)


def _booked_pot(absence, actor):
    """The pot this absence's own lines are on. Cancelling and re-costing
    never re-resolve it from today's contracts and policy: a leaver has no
    contract on the day, and a changed leave year would pick another pot.
    Only an absence with no line yet (approved at zero, re-costed upwards)
    falls back to the pot for its start date."""
    line = absence.ledger_entries.select_related("pot").order_by("id").first()
    if line is not None:
        return line.pot
    return pots.for_day(absence.employment, absence.absence_type, absence.start_date, actor=actor)


def _copy_back(fresh, absence):
    for field in fresh._meta.concrete_fields:
        setattr(absence, field.attname, getattr(fresh, field.attname))
    return absence


def check_family_dates(absence_type, expected_start=None, actual_start=None, expected_return=None):
    """Only family leave has these dates, and the return comes after a start."""
    if not absence_type.is_family:
        if expected_start or actual_start or expected_return:
            raise ValidationError("Only family leave has expected and actual dates.")
        return
    for label, start in (("expected start", expected_start), ("actual start", actual_start)):
        if start and expected_return and expected_return <= start:
            raise ValidationError(f"The expected return must be after the {label}.")


def preview(employment, absence_type, start_date, end_date=None, start_half="", end_half="",
            start_time=None, end_time=None, hours=None, category="", requested_by=None,
            expected_start=None, expected_return=None):
    """The absence request() would write, unsaved and costed, after every
    check request() makes. Writes nothing: the request page shows it before
    the requester confirms."""
    a = Absence(employment=employment, absence_type=absence_type, start_date=start_date,
                end_date=end_date or start_date, start_half=start_half, end_half=end_half,
                start_time=start_time, end_time=end_time, hours=hours, category=category,
                requested_by=requested_by, expected_start=expected_start,
                expected_return=expected_return)
    a.full_clean(exclude=["employment", "absence_type", "requested_by"])
    if a.is_partial and contracts.unit(employment, start_date) != "hours":
        raise ValidationError({"hours": "Partial days are only for people whose allowance is in hours."})
    check_family_dates(absence_type, expected_start=expected_start, expected_return=expected_return)
    if overlaps(employment, a.start_date, a.end_date):
        raise ValidationError("There is already an absence on those dates.")
    _check_leave_year(a)
    if absence_type.code == "SICK":
        a.self_certified = (a.end_date - a.start_date) < timedelta(days=SELF_CERT_DAYS)
    a.cost_units = costing.cost(a)
    return a


@transaction.atomic
def request(actor, employment, absence_type, start_date, end_date=None, start_half="", end_half="",
            start_time=None, end_time=None, hours=None, category="", requested_by=None,
            expected_start=None, expected_return=None):
    a = preview(employment, absence_type, start_date, end_date, start_half, end_half, start_time,
                end_time, hours, category, requested_by=requested_by or actor,
                expected_start=expected_start, expected_return=expected_return)
    a.save()
    changes = {"requested": ("", str(a))}
    for field in ("expected_start", "expected_return"):
        if getattr(a, field):
            changes[field] = ("", getattr(a, field))
    audit.record(actor, a, changes)
    if not absence_type.needs_approval:
        return approve(actor, a)
    return a


@transaction.atomic
def approve(actor, absence, comment=""):
    caller, absence = absence, _lock(absence)
    if absence.status != Absence.Status.REQUESTED:
        raise ValidationError("Only a requested absence can be approved.")
    if overlaps(absence.employment, absence.start_date, absence.end_date, exclude_pk=absence.pk,
                auto=absence.auto_bank_holiday):
        raise ValidationError("Another absence now overlaps these dates.")
    absence.cost_units = costing.cost(absence)
    absence.status = Absence.Status.APPROVED
    absence.decided_at = timezone.now()
    absence.decided_by = actor
    absence.decision_comment = comment
    absence.save()
    if absence.absence_type.uses_pot and absence.cost_units:
        pot = pots.for_day(absence.employment, absence.absence_type, absence.start_date, actor=actor)
        kind = LedgerEntry.Kind.TOIL_TAKEN if absence.absence_type.code == "TOIL" else LedgerEntry.Kind.BOOKING
        ledger.write(pot, kind, -absence.cost_units, actor, absence=absence,
                     note=f"{absence.start_date:%d %b}–{absence.end_date:%d %b %Y}", date=absence.start_date)
    audit.record(actor, absence, {"status": ("requested", "approved")})
    return _copy_back(absence, caller)


@transaction.atomic
def decline(actor, absence, comment=""):
    caller, absence = absence, _lock(absence)
    if absence.status != Absence.Status.REQUESTED:
        raise ValidationError("Only a requested absence can be declined.")
    absence.status = Absence.Status.DECLINED
    absence.decided_at = timezone.now()
    absence.decided_by = actor
    absence.decision_comment = comment
    absence.save()
    audit.record(actor, absence, {"status": ("requested", "declined")})
    return _copy_back(absence, caller)


@transaction.atomic
def cancel(actor, absence):
    caller, absence = absence, _lock(absence)
    if absence.status not in LIVE:
        raise ValidationError("Only a requested or approved absence can be cancelled.")
    was = absence.status
    absence.status = Absence.Status.CANCELLED
    absence.cancelled_at = timezone.now()
    absence.cancelled_by = actor
    absence.save()
    if was == Absence.Status.APPROVED and absence.absence_type.uses_pot and absence.cost_units:
        pot = _booked_pot(absence, actor)
        ledger.write(pot, LedgerEntry.Kind.CANCELLATION, absence.cost_units, actor, absence=absence,
                     note="cancelled", date=absence.start_date)
    audit.record(actor, absence, {"status": (was, "cancelled")})
    return _copy_back(absence, caller)


@transaction.atomic
def recost(actor, absence, note):
    """An HR admin re-prices an approved absence after a pattern change.
    Writes an adjustment for the difference, or nothing."""
    caller, absence = absence, _lock(absence)
    if absence.status != Absence.Status.APPROVED or not absence.absence_type.uses_pot:
        raise ValidationError("Only an approved, pot-backed absence can be re-costed.")
    new = costing.cost(absence)
    delta = absence.cost_units - new
    if delta == 0:
        return None
    old = absence.cost_units
    absence.cost_units = new
    absence.save()
    _copy_back(absence, caller)
    pot = _booked_pot(absence, actor)
    line = ledger.write(pot, LedgerEntry.Kind.ADJUSTMENT, delta, actor, absence=absence, note=note)
    audit.record(actor, absence, {"cost_units": (str(old), str(new))}, note=note)
    return line


FAMILY_DATES = ("expected_start", "actual_start", "expected_return")


@transaction.atomic
def set_family_dates(actor, absence, expected_start=None, actual_start=None, expected_return=None):
    """An HR admin sets a family-leave absence's three dates. All three are
    set to the values given: None clears one, so pass every date the
    absence should keep."""
    caller, absence = absence, _lock(absence)
    if absence.status not in LIVE:
        raise ValidationError("Only a requested or approved absence can be changed.")
    new = {"expected_start": expected_start, "actual_start": actual_start, "expected_return": expected_return}
    check_family_dates(absence.absence_type, **new)
    changes = {f: (getattr(absence, f) or "", new[f] or "") for f in FAMILY_DATES}
    for f in FAMILY_DATES:
        setattr(absence, f, new[f])
    absence.save(update_fields=list(FAMILY_DATES))
    audit.record(actor, absence, changes)
    return _copy_back(absence, caller)


@transaction.atomic
def add_kit_day(actor, absence, day):
    """A keeping-in-touch day within a live family-leave absence. Adding the
    same day twice is a no-op."""
    absence = _lock(absence)
    if not absence.absence_type.is_family:
        raise ValidationError("Keeping-in-touch days are for family leave only.")
    if absence.status not in LIVE:
        raise ValidationError("Only a requested or approved absence can take a keeping-in-touch day.")
    if not absence.start_date <= day <= absence.end_date:
        raise ValidationError("A keeping-in-touch day falls within the leave.")
    kit, created = KitDay.objects.get_or_create(absence=absence, date=day)
    if created:
        audit.record(actor, absence, {"kit_day": ("", day)})
    return kit
