"""Time off in lieu: earned by a claim the person's approver decides, taken
as an ordinary TOIL booking (bookings.approve writes the toil_taken line),
expired by year_end.expire_toil.

A claim (ToilClaim) is for time already worked on one day, in quarter hours
(half sessions for a sessions contract). It is routed exactly as a leave
request is (people.services.access.route_for; HR admins decide any but
their own), and made by its approver or an HR admin it is approved at once,
as bookings.record does for leave. Approving writes one TOIL-earned line
through earn(), dated the day worked, so the type's
earned_expires_after_days runs from then; declining and cancelling write
nothing. An approved claim is never undone here: HR corrects the pot with
an adjustment (ledger.adjust).

Every writer is atomic and, like bookings, re-reads the claim under a lock
(_lock) before its status guard, and copies the fresh row back onto the
caller's instance (_copy_back). Emails are the caller's, after the
transaction (notify.claim_submitted / claim_decided)."""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from absence.models import AbsenceType, LedgerEntry, Pot, ToilClaim
from absence.services import ledger, pots, year_end
from people.services import access, audit, contracts

S = ToilClaim.Status
STEPS = {"hours": Decimal("0.25"), "sessions": Decimal("0.5")}
EXPIRING_WITHIN_DAYS = 60


def _toil():
    return AbsenceType.objects.get(code="TOIL")


@transaction.atomic
def earn(actor, employment, units, day, note):
    """Credit `units` of TOIL earned on `day` to the TOIL pot for that day,
    opening it if needed (it borrows the annual-leave policy's leave year:
    TOIL has no policy). Raises ValidationError for non-positive units, when
    there is no contract or annual-leave policy on the day, or when the
    pot's year has been closed (year_end.check_open)."""
    units = Decimal(units).quantize(Decimal("0.01"))
    if units <= 0:
        raise ValidationError("TOIL earned must be more than zero.")
    pot = pots.for_day(employment, _toil(), day, actor=actor)
    Pot.objects.select_for_update().get(pk=pot.pk)     # the year end holds the same lock while it closes
    year_end.check_open(pot)
    row = ledger.write(pot, LedgerEntry.Kind.TOIL_EARNED, units, actor, note=note, date=day)
    audit.record(actor, row, {"toil_earned": ("", units)}, note=note)
    return row


def step(employment, day):
    """The smallest amount a claim for `day` is made in: a quarter hour, or
    half a session, from the contract in force that day. None without one."""
    return STEPS.get(contracts.unit(employment, day))


def check(employment, day, units, reason, today=None):
    """claim()'s rules, without writing: returns (units, reason) cleaned."""
    today = today or timezone.localdate()
    if day > today:
        raise ValidationError("A claim is for time already worked: the day cannot be after today.")
    if not employment.is_active_on(day):
        raise ValidationError(f"{employment.employee} was not employed on {day:%d %b %Y}.")
    unit = contracts.unit(employment, day)
    if unit is None:
        raise ValidationError(f"{employment.employee} had no contract on {day:%d %b %Y}.")
    units = Decimal(units)
    if units <= 0:
        raise ValidationError("A claim is for more than zero.")
    if units % STEPS[unit]:
        raise ValidationError(f"Claim in steps of {STEPS[unit]:f} {unit}.")
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Say what the time was worked for.")
    pot = pots.lookup(employment, _toil(), day)
    if pot is not None:
        year_end.check_open(pot)
    return units.quantize(Decimal("0.01")), reason


def _own(actor, claim):
    me = access.employee_for(actor)
    return me is not None and me.pk == claim.employment.employee_id


def decides_at_once(actor, employment, today=None):
    """Whether a claim `actor` makes for `employment` is approved as it is
    made: the actor is the person it would be routed to, or an HR admin,
    and never for their own."""
    today = today or timezone.localdate()
    me = access.employee_for(actor)
    if me is not None and me.pk == employment.employee_id:
        return False
    return access.can_view_restricted(actor) or (me is not None and access.route_for(employment, today) == me)


@transaction.atomic
def claim(actor, employment, day, units, reason, requested_by=None):
    """A claim for `units` of time worked on `day`, `reason` saying what for.
    Refused (ValidationError) for a day after today, a day the person was
    not employed or had no contract, units that are not more than zero or
    not a whole number of steps (step()), no reason, or a day whose TOIL
    leave year has closed. Waits for the approver, unless `actor` is that
    approver or an HR admin (decides_at_once): then it is approved in the
    same transaction."""
    units, reason = check(employment, day, units, reason)
    c = ToilClaim.objects.create(employment=employment, day=day, units=units, reason=reason[:200],
                                 requested_by=requested_by or actor)
    audit.record(actor, c, {"claimed": ("", str(c))})
    if decides_at_once(actor, employment):
        return approve(actor, c)
    return c


def _lock(claim):
    """Re-read the row under a lock, so a stale in-memory copy cannot pass a status guard."""
    return ToilClaim.objects.select_for_update().select_related("employment__employee").get(pk=claim.pk)


def _copy_back(fresh, claim):
    for field in fresh._meta.concrete_fields:
        setattr(claim, field.attname, getattr(fresh, field.attname))
    return claim


def _decidable(actor, claim):
    if claim.status != S.REQUESTED:
        raise ValidationError("Only a claim still waiting can be decided.")
    if _own(actor, claim):
        raise ValidationError("You cannot decide your own claim.")


@transaction.atomic
def approve(actor, claim, comment=""):
    """Approve a waiting claim: one TOIL-earned line through earn(), dated
    the day worked and noted with the reason, linked as `earned`."""
    caller, claim = claim, _lock(claim)
    _decidable(actor, claim)
    claim.earned = earn(actor, claim.employment, claim.units, claim.day, note=f"TOIL claim: {claim.reason}")
    claim.status = S.APPROVED
    claim.decided_at = timezone.now()
    claim.decided_by = actor
    claim.decision_comment = comment
    claim.save()
    audit.record(actor, claim, {"status": ("requested", "approved")})
    return _copy_back(claim, caller)


@transaction.atomic
def decline(actor, claim, comment=""):
    """Decline a waiting claim. Nothing is written to the ledger."""
    caller, claim = claim, _lock(claim)
    _decidable(actor, claim)
    claim.status = S.DECLINED
    claim.decided_at = timezone.now()
    claim.decided_by = actor
    claim.decision_comment = comment
    claim.save()
    audit.record(actor, claim, {"status": ("requested", "declined")})
    return _copy_back(claim, caller)


def may_cancel(user, claim):
    """The claimant, or an HR admin, while the claim is waiting."""
    if claim.status != S.REQUESTED:
        return False
    return claim.employment.employee.user_id == user.pk or access.can_view_restricted(user)


@transaction.atomic
def cancel(actor, claim):
    """Withdraw a waiting claim: by the person it is for, or an HR admin.
    An approved claim is not cancelled; HR corrects the pot by adjustment."""
    caller, claim = claim, _lock(claim)
    if claim.status != S.REQUESTED:
        raise ValidationError("Only a claim still waiting can be cancelled; "
                              "an HR admin corrects an approved one with an adjustment.")
    if not may_cancel(actor, claim):
        raise ValidationError("Only the person claiming, or an HR admin, can cancel a claim.")
    claim.status = S.CANCELLED
    claim.cancelled_at = timezone.now()
    claim.cancelled_by = actor
    claim.save()
    audit.record(actor, claim, {"status": ("requested", "cancelled")})
    return _copy_back(claim, caller)


def position(employment, today):
    """What a person's TOIL stands at, for My absences and the decide page:
    remaining now, earned this leave year (claims and other TOIL-earned
    lines dated in it, not the lines carried in from last year), the lots
    with something left expiring in the next EXPIRING_WITHIN_DAYS days
    (year_end._toil_lots), and the claims waiting. Reads only: with no pot
    open yet everything is 0."""
    toil_type = _toil()
    try:
        pot = pots.lookup(employment, toil_type, today)
    except ValidationError:
        pot = None
    out = {"pot": pot, "unit": pot.unit if pot else contracts.unit(employment, today) or "",
           "remaining": Decimal("0"), "earned": Decimal("0"), "expiring": [],
           "waiting": list(ToilClaim.objects.filter(employment=employment, status=S.REQUESTED)
                           .order_by("day", "pk")),
           "window": EXPIRING_WITHIN_DAYS}
    if pot is None:
        return out
    out["remaining"] = ledger.balance(pot)
    out["earned"] = pot.entries.filter(kind=LedgerEntry.Kind.TOIL_EARNED, date__gte=pot.year_start).aggregate(
        t=Sum("units"))["t"] or Decimal("0")
    horizon = today + timedelta(days=EXPIRING_WITHIN_DAYS)
    for lot in year_end._toil_lots(pot):
        left = lot["left"] - lot["used"]
        if not lot["expired"] and left > 0 and lot["deadline"] is not None and today <= lot["deadline"] <= horizon:
            out["expiring"].append({"units": left, "earned_on": lot["line"].date, "deadline": lot["deadline"]})
    return out
