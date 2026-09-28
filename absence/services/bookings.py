"""Every change of an Absence's status, and the ledger line it implies."""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from absence.models import Absence, LedgerEntry
from absence.services import costing, leave_year, ledger, policies, pots
from people.services import audit, contracts

LIVE = (Absence.Status.REQUESTED, Absence.Status.APPROVED)
SELF_CERT_DAYS = 7


def overlaps(employment, start, end, exclude_pk=None):
    qs = Absence.objects.filter(employment=employment, status__in=LIVE,
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


@transaction.atomic
def request(actor, employment, absence_type, start_date, end_date=None, start_half="", end_half="",
            start_time=None, end_time=None, hours=None, category="", requested_by=None):
    a = Absence(employment=employment, absence_type=absence_type, start_date=start_date,
                end_date=end_date or start_date, start_half=start_half, end_half=end_half,
                start_time=start_time, end_time=end_time, hours=hours, category=category,
                requested_by=requested_by or actor)
    a.full_clean(exclude=["employment", "absence_type", "requested_by"])
    if a.is_partial and contracts.unit(employment, start_date) != "hours":
        raise ValidationError({"hours": "Partial days are only for people whose allowance is in hours."})
    if overlaps(employment, a.start_date, a.end_date):
        raise ValidationError("There is already an absence on those dates.")
    _check_leave_year(a)
    if absence_type.code == "SICK":
        a.self_certified = (a.end_date - a.start_date) < timedelta(days=SELF_CERT_DAYS)
    a.cost_units = costing.cost(a)
    a.save()
    audit.record(actor, a, {"requested": ("", str(a))})
    if not absence_type.needs_approval:
        return approve(actor, a)
    return a


@transaction.atomic
def approve(actor, absence, comment=""):
    if absence.status != Absence.Status.REQUESTED:
        raise ValidationError("Only a requested absence can be approved.")
    if overlaps(absence.employment, absence.start_date, absence.end_date, exclude_pk=absence.pk):
        raise ValidationError("Another absence now overlaps these dates.")
    absence.cost_units = costing.cost(absence)
    absence.status = Absence.Status.APPROVED
    absence.decided_at = timezone.now()
    absence.decided_by = actor
    absence.decision_comment = comment
    absence.save()
    if absence.absence_type.uses_pot and absence.cost_units:
        pot = pots.for_day(absence.employment, absence.absence_type, absence.start_date)
        kind = LedgerEntry.Kind.TOIL_TAKEN if absence.absence_type.code == "TOIL" else LedgerEntry.Kind.BOOKING
        ledger.write(pot, kind, -absence.cost_units, actor, absence=absence,
                     note=f"{absence.start_date:%d %b}–{absence.end_date:%d %b %Y}", date=absence.start_date)
    audit.record(actor, absence, {"status": ("requested", "approved")})
    return absence


@transaction.atomic
def decline(actor, absence, comment=""):
    if absence.status != Absence.Status.REQUESTED:
        raise ValidationError("Only a requested absence can be declined.")
    absence.status = Absence.Status.DECLINED
    absence.decided_at = timezone.now()
    absence.decided_by = actor
    absence.decision_comment = comment
    absence.save()
    audit.record(actor, absence, {"status": ("requested", "declined")})
    return absence


@transaction.atomic
def cancel(actor, absence):
    if absence.status not in LIVE:
        raise ValidationError("Only a requested or approved absence can be cancelled.")
    was = absence.status
    absence.status = Absence.Status.CANCELLED
    absence.cancelled_at = timezone.now()
    absence.cancelled_by = actor
    absence.save()
    if was == Absence.Status.APPROVED and absence.absence_type.uses_pot and absence.cost_units:
        pot = pots.for_day(absence.employment, absence.absence_type, absence.start_date)
        ledger.write(pot, LedgerEntry.Kind.CANCELLATION, absence.cost_units, actor, absence=absence,
                     note="cancelled", date=absence.start_date)
    audit.record(actor, absence, {"status": (was, "cancelled")})
    return absence


@transaction.atomic
def recost(actor, absence, note):
    """An HR admin re-prices an approved absence after a pattern change.
    Writes an adjustment for the difference, or nothing."""
    if absence.status != Absence.Status.APPROVED or not absence.absence_type.uses_pot:
        raise ValidationError("Only an approved, pot-backed absence can be re-costed.")
    new = costing.cost(absence)
    delta = absence.cost_units - new
    if delta == 0:
        return None
    absence.cost_units = new
    absence.save()
    pot = pots.for_day(absence.employment, absence.absence_type, absence.start_date)
    return ledger.write(pot, LedgerEntry.Kind.ADJUSTMENT, delta, actor, absence=absence, note=note)
