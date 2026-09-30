"""Closing a pot at the end of its leave year, and the expiries that run
from dates: carried-in leave after the policy's deadline, TOIL after the
type's own (AbsenceType.earned_expires_after_days: TOIL has no policy).

Every line goes through ledger.write, so each is an ordinary ledger line an
HR admin reverses with an adjustment. Each function looks for its own
earlier line (by kind and note) before writing, so a re-run writes nothing,
and a reversed line is never written again."""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q, Sum
from django.utils import timezone

from absence.models import Absence, LedgerEntry, Pot
from absence.services import ledger, policies, pots, rounding
from people.services import contracts

K = LedgerEntry.Kind
ZERO = Decimal("0")
CLOSE = "year end close"             # the closing line's note starts with this: the pot is closed
CARRY_IN_EXPIRED = "carry-in expired"
TOIL_EXPIRED = "toil expired"


def _sum(qs):
    return qs.aggregate(t=Sum("units"))["t"] or ZERO


def _closing_lines():
    return LedgerEntry.objects.filter(kind=K.EXPIRY, note__startswith=CLOSE)


def is_closed(pot):
    """Closed iff the pot itself has its closing expiry line. The next pot's
    carry-in is not looked at: that pot is not closed by being carried into."""
    return _closing_lines().filter(pot=pot).exists()


def check_open(pot):
    """Refuse a write to a closed pot: its balance was carried or expired at
    the close, so a line written after it would be stranded there. HR
    corrects the current year's pot instead, by an adjustment."""
    if is_closed(pot):
        raise ValidationError(
            f"{pot} is closed: its leave year has ended and its balance has been carried forward or expired. "
            f"Nothing more is written to it; adjust the current year's pot instead.")


def waiting(pot):
    """The requests still to be decided that would draw on the pot: its
    type, starting in its year."""
    return Absence.objects.filter(employment=pot.employment, absence_type=pot.absence_type,
                                  status=Absence.Status.REQUESTED,
                                  start_date__range=(pot.year_start, pot.year_end))


def _lock(pot):
    """Hold the pot's row for the transaction, so two runs at once (the
    nightly and the command) cannot both find no earlier line and write."""
    Pot.objects.select_for_update().get(pk=pot.pk)


def _stays(employment, day):
    return employment.is_active_on(day) and contracts.active_on(employment, day).exists()


def _cap(pot, day):
    """The most that carries into the year starting `day`: the policy in
    force that day, times the contracted amount that day, rounded."""
    policy = policies.policy_for(pot.employment, pot.absence_type, day)
    if policy.carry_over_max_weeks is None:
        return ZERO
    return rounding.round_to(policy.carry_over_max_weeks * contracts.contracted_amount(pot.employment, day),
                             policy.rounding)


def _bookings(pot):
    """What each absence drawing on the pot uses, in the order it was
    booked: [(booked_on, units used, order key)]. An absence is booked on the
    local date it was requested (the Absence is the booking, whatever its
    status; spec §4), so a slow approver never costs the employee; only an
    approved one has lines here. Its use is the net of all its lines on the
    pot (the booking, a cancellation, a re-costing), so a cancellation
    reverses its own booking's use."""
    booked, used = {}, {}
    for line in pot.entries.filter(absence__isnull=False).select_related("absence").order_by("created_at", "id"):
        if line.kind in (K.BOOKING, K.TOIL_TAKEN) and line.absence_id not in booked:
            requested = line.absence.requested_at
            booked[line.absence_id] = (timezone.localdate(requested), (requested, line.absence_id))
        used[line.absence_id] = used.get(line.absence_id, ZERO) - line.units
    return [(day, used[absence], key) for absence, (day, key) in booked.items()]


def _undecided_by(pot, day):
    """A request drawing on the pot, made on or before `day`, still waiting:
    once decided it may count as booked by then, so an expiry with that
    deadline waits for it (and runs the next night after)."""
    return waiting(pot).filter(requested_at__date__lte=day).exists()


def _toil_marker(earned):
    return f"{TOIL_EXPIRED}: earned {earned.date:%d %b %Y} (entry {earned.pk})"


def _toil_lots(pot):
    """The pot's TOIL-earned lines as lots, oldest first, each with its
    deadline (the day it was earned plus the type's
    earned_expires_after_days; None for no expiry), what of it is left
    after its own expiry, and what bookings have used of it.

    Lots are the TOIL-earned lines (a claim approved, toil.approve) and the
    positive adjustments not tied to an absence (an HR admin adding TOIL,
    or reversing a TOIL expiry): each is dated its line's date, expires
    earned_expires_after_days from it, and
    carries forward at year end like an earned line.

    The rule, shared with expire_carry_in: leave counts as using TOIL only
    if it was booked on or before the lot's deadline. Bookings (see
    _bookings), and the negative adjustments not tied to an absence (dated
    the day they were written), are taken in the order they were made, and
    each is used up first in, first out: from the oldest lot still within
    its deadline on that day and with something left."""
    already = {e.note: ZERO - e.units
               for e in pot.entries.filter(kind=K.EXPIRY, note__startswith=TOIL_EXPIRED)}
    lots = []
    days = pot.absence_type.earned_expires_after_days
    manual = pot.entries.filter(kind=K.ADJUSTMENT, absence__isnull=True)
    earned = pot.entries.filter(Q(kind=K.TOIL_EARNED) | Q(pk__in=manual.filter(units__gt=0)))
    for line in earned.order_by("date", "id"):
        marker = _toil_marker(line)
        lots.append({"line": line, "marker": marker, "expired": marker in already,
                     "deadline": line.date + timedelta(days=days) if days else None,
                     "left": line.units - already.get(marker, ZERO), "used": ZERO})
    taken = _bookings(pot) + [(timezone.localdate(line.created_at), ZERO - line.units, (line.created_at, line.pk))
                              for line in manual.filter(units__lt=0)]
    for booked_on, units, _ in sorted(taken, key=lambda t: t[2]):
        for lot in lots:
            if units <= 0:
                break
            if lot["deadline"] is not None and booked_on > lot["deadline"]:
                continue
            take = min(units, lot["left"] - lot["used"])
            if take > 0:
                lot["used"] += take
                units -= take
    return lots


def _close_toil(pot, remaining, new_start, actor):
    """A TOIL pot's positive balance carries forward uncapped, as each
    earned line's unused remainder: a TOIL-earned line on the next pot dated
    the day it was originally earned, so expire_toil runs its deadline on
    unchanged. A line whose deadline has passed by the new year expires
    instead. Lots are as _toil_lots has them, so an adjustment adding TOIL
    carries too. Never more than the balance carries: a shortfall (TOIL
    booked beyond what was earned) is taken from the oldest lines first. Returns the amount carried."""
    carry = [(lot["line"], lot["left"] - lot["used"]) for lot in _toil_lots(pot)
             if not lot["expired"] and lot["left"] - lot["used"] > 0
             and (lot["deadline"] is None or lot["deadline"] >= new_start)]
    short = sum((units for _, units in carry), ZERO) - remaining
    trimmed = []
    for line, units in carry:
        cut = min(units, max(short, ZERO))
        short -= cut
        if units - cut > 0:
            trimmed.append((line, units - cut))
    if not trimmed:
        return ZERO
    nxt = _next_pot(pot, new_start, actor)
    for line, units in trimmed:
        ledger.write(nxt, K.TOIL_EARNED, units, actor, date=line.date,
                     note=f"carried from {pot.year_start:%d %b %Y}–{pot.year_end:%d %b %Y}")
    return sum((units for _, units in trimmed), ZERO)


def _next_pot(pot, new_start, actor):
    # A pot that cannot open (no policy next year) or is in another unit
    # fails the whole close, and the caller's atomic block rolls it back.
    nxt = pots.for_day(pot.employment, pot.absence_type, new_start, actor=actor)
    if nxt.unit != pot.unit:
        raise ValidationError(
            f"{pot} is in {pot.unit}, but {nxt} is in {nxt.unit}. "
            f"Settle the balance by adjustment and the year end will close it at zero.")
    return nxt


@transaction.atomic
def close(pot, actor=None):
    """Close a pot whose leave year has ended.

    The pot's entitlement is re-synced first, so a contract change or
    leaving date recorded after the year ended still reaches it. Then one
    expiry line on the pot takes its whole remaining balance, so a closed
    pot stands at exactly zero; the part within the carry cap (the policy
    on the new year's first day) is written as a carry-in on the next year's
    pot, opened synced if need be. A negative balance carries in full. A
    zero balance still writes a zero line, which marks the closure. A TOIL
    pot carries its unused earned lines instead, uncapped (_close_toil).

    A leaver (no employment or contract on the new year's first day) has a
    positive balance expired; a negative one is left on the pot untouched
    and returned as `leaver_debt`, for payroll, and the pot stays open to a
    later run until it is settled. Idempotent: a closed pot is skipped.

    Refused (ValidationError, so run() lists it and retries it the next
    night) while a request that would draw on the pot is still waiting: its
    approval could no longer be written once the pot is closed."""
    _lock(pot)
    if is_closed(pot):
        return {"carried": ZERO, "expired": ZERO, "skipped": True}
    n = waiting(pot).count()
    if n:
        raise ValidationError(f"{n} request(s) waiting — decide them first")
    ledger.sync_entitlement(pot, actor, cause="year end")
    remaining = ledger.balance(pot)
    new_start = pot.year_end + timedelta(days=1)
    if not _stays(pot.employment, new_start):
        if remaining < 0:
            return {"carried": ZERO, "expired": ZERO, "leaver_debt": remaining}
        ledger.write(pot, K.EXPIRY, ZERO - remaining, actor,
                     note=f"{CLOSE}: leaver, {remaining:.2f} expired", date=pot.year_end)
        return {"carried": ZERO, "expired": remaining}
    toil = pot.absence_type.code == "TOIL"
    if toil and remaining > 0:
        carried = _close_toil(pot, remaining, new_start, actor)
    else:
        carried = min(remaining, _cap(pot, new_start)) if remaining > 0 else remaining
        if carried:
            nxt = _next_pot(pot, new_start, actor)
            ledger.write(nxt, K.CARRY_IN, carried, actor, date=nxt.year_start,
                         note=f"year end: carried in from {pot.year_start:%Y}/{pot.year_end:%y}")
    expired = remaining - carried
    what = "TOIL carried forward" if toil and remaining > 0 else f"carried to {new_start:%Y-%m-%d}"
    ledger.write(pot, K.EXPIRY, ZERO - remaining, actor,
                 note=f"{CLOSE}: {carried:.2f} {what}, {expired:.2f} expired", date=pot.year_end)
    return {"carried": carried, "expired": expired}


@transaction.atomic
def expire_carry_in(pot, today, actor=None):
    """Expire carried-in leave unused by the policy's deadline (year start
    plus carry_over_expires_after_days; usable through that day).

    The rule, shared with expire_toil: leave counts as using the carry-in
    only if it was booked on or before the deadline (requested by then and
    approved, whatever the date of the leave or of the approval; a
    cancellation reverses its booking; see _bookings), and it is taken from
    the carry-in first. While a request made by the deadline is still
    waiting nothing is written (None), and the next run tries again. What is
    left of the carry-in expires, never more than the pot's balance. A
    negative carry-in never expires. One line at most, noted "carry-in
    expired"; returns it, or None."""
    _lock(pot)
    carried = _sum(pot.entries.filter(kind=K.CARRY_IN))
    if carried <= 0 or pot.entries.filter(kind=K.EXPIRY, note=CARRY_IN_EXPIRED).exists():
        return None
    days = policies.policy_for(pot.employment, pot.absence_type, pot.year_start).carry_over_expires_after_days
    if not days:
        return None
    deadline = pot.year_start + timedelta(days=days)
    if today <= deadline or _undecided_by(pot, deadline):
        return None
    used = sum((units for booked_on, units, _ in _bookings(pot) if booked_on <= deadline and units > 0), ZERO)
    unused = min(carried - used, max(ledger.balance(pot), ZERO))
    if unused <= 0:
        return None
    return ledger.write(pot, K.EXPIRY, ZERO - unused, actor, note=CARRY_IN_EXPIRED,
                        date=deadline + timedelta(days=1))


@transaction.atomic
def expire_toil(pot, today, actor=None):
    """Expire each TOIL lot (an earned line, or an adjustment adding TOIL;
    see _toil_lots) unused by its deadline: the day it was earned plus the
    type's earned_expires_after_days; usable through that day. A line carried from last year keeps its earned date,
    so its deadline runs on.

    Used means booked on or before the deadline, first in, first out, in
    the order the bookings were made (see _toil_lots; the same rule as
    expire_carry_in). A line past its deadline with no expiry of its own
    yet expires what of it is unused, never more than the pot's balance,
    unless a request made by its deadline is still waiting: then it waits
    for the decision, and a later run expires it. One expiry per earned line
    at most; returns the lines written."""
    _lock(pot)
    out = []
    for lot in _toil_lots(pot):
        if lot["expired"] or lot["deadline"] is None or today <= lot["deadline"]:
            continue
        if _undecided_by(pot, lot["deadline"]):
            continue                    # a request made in time may use it: wait for the decision
        unused = min(lot["left"] - lot["used"], max(ledger.balance(pot), ZERO))
        if unused <= 0:
            continue
        out.append(ledger.write(pot, K.EXPIRY, ZERO - unused, actor, note=lot["marker"],
                                date=lot["deadline"] + timedelta(days=1)))
    return out


def _why(pot, e):
    return f"{pot}: {'; '.join(e.messages)}"


def run(today):
    """Close every pot whose year ended before `today` and is not closed
    (oldest first, so a late catch-up carries forward in order), then run
    the carry-in and TOIL expiries on the open pots that have such lines.
    Each pot is its own transaction; one that cannot be processed is listed
    in `failed`, so the rest still run. Idempotent."""
    failed, leaver_debts = [], []
    closed, carried_total, expired_total = 0, ZERO, ZERO
    ended = (Pot.objects.filter(year_end__lt=today)
             .exclude(Exists(_closing_lines().filter(pot=OuterRef("pk"))))
             .select_related("employment__employee", "absence_type").order_by("year_start", "id"))
    for pot in ended:
        try:
            r = close(pot)
        except ValidationError as e:
            failed.append(_why(pot, e))
            continue
        if "leaver_debt" in r:
            leaver_debts.append(f"{pot}: {r['leaver_debt']:.2f} owed")
            continue
        closed += 1
        carried_total += r["carried"]
        expired_total += r["expired"]
    carry_in_expired = toil_expired = 0
    for pot in pots.open_pots(today).filter(entries__kind=K.CARRY_IN).distinct():
        try:
            if expire_carry_in(pot, today) is not None:
                carry_in_expired += 1
        except ValidationError as e:
            failed.append(_why(pot, e))
    for pot in pots.open_pots(today).filter(entries__kind=K.TOIL_EARNED).distinct():
        try:
            toil_expired += len(expire_toil(pot, today))
        except ValidationError as e:
            failed.append(_why(pot, e))
    return {"closed": closed, "carried_total": carried_total, "expired_total": expired_total,
            "carry_in_expired": carry_in_expired, "toil_expired": toil_expired,
            "leaver_debts": leaver_debts, "failed": failed}
