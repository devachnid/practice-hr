"""Closing a pot at the end of its leave year, and the expiries that run
from dates: carried-in leave after the policy's deadline, TOIL after its own.

Every line goes through ledger.write, so each is an ordinary ledger line an
HR admin reverses with an adjustment. Each function looks for its own
earlier line (by kind and note) before writing, so a re-run writes nothing,
and a reversed line is never written again."""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Sum

from absence.models import LedgerEntry, Pot
from absence.services import ledger, policies, pots, rounding
from people.services import contracts

K = LedgerEntry.Kind
ZERO = Decimal("0")
CLOSE = "year end close"             # the closing line's note starts with this: the pot is closed
CARRY_IN_EXPIRED = "carry-in expired"
TOIL_EXPIRED = "toil expired"
TAKEN = (K.BOOKING, K.TOIL_TAKEN, K.CANCELLATION)


def _sum(qs):
    return qs.aggregate(t=Sum("units"))["t"] or ZERO


def _closing_lines():
    return LedgerEntry.objects.filter(kind=K.EXPIRY, note__startswith=CLOSE)


def is_closed(pot):
    """Closed iff the pot itself has its closing expiry line. The next pot's
    carry-in is not looked at: that pot is not closed by being carried into."""
    return _closing_lines().filter(pot=pot).exists()


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


@transaction.atomic
def close(pot, actor=None):
    """Close a pot whose leave year has ended.

    One expiry line on the pot takes its whole remaining balance, so a
    closed pot stands at exactly zero; the part within the carry cap (the
    policy on the new year's first day) is written as a carry-in on the next
    year's pot, opened synced if need be. A negative balance carries in
    full. A zero balance still writes a zero line, which marks the closure.

    A leaver (no employment or contract on the new year's first day) has a
    positive balance expired; a negative one is left on the pot untouched
    and returned as `leaver_debt`, for payroll, and the pot stays open to a
    later run until it is settled. Idempotent: a closed pot is skipped."""
    _lock(pot)
    if is_closed(pot):
        return {"carried": ZERO, "expired": ZERO, "skipped": True}
    remaining = ledger.balance(pot)
    new_start = pot.year_end + timedelta(days=1)
    if not _stays(pot.employment, new_start):
        if remaining < 0:
            return {"carried": ZERO, "expired": ZERO, "leaver_debt": remaining}
        ledger.write(pot, K.EXPIRY, ZERO - remaining, actor,
                     note=f"{CLOSE}: leaver, {remaining:.2f} expired", date=pot.year_end)
        return {"carried": ZERO, "expired": remaining}
    if remaining > 0:
        carried = min(remaining, _cap(pot, new_start))
    else:
        carried = remaining
    expired = remaining - carried
    if carried:
        # A pot that cannot open (no policy next year) or is in another unit
        # fails the whole close, and the atomic block rolls it back.
        nxt = pots.for_day(pot.employment, pot.absence_type, new_start, actor=actor)
        if nxt.unit != pot.unit:
            raise ValidationError(
                f"{pot} is in {pot.unit}, but {nxt} is in {nxt.unit}. "
                f"Settle the balance by adjustment and the year end will close it at zero.")
        ledger.write(nxt, K.CARRY_IN, carried, actor,
                     note=f"year end: carried in from {pot.year_start:%Y}/{pot.year_end:%y}", date=nxt.year_start)
    ledger.write(pot, K.EXPIRY, ZERO - remaining, actor,
                 note=f"{CLOSE}: {carried:.2f} carried to {new_start:%Y-%m-%d}, {expired:.2f} expired",
                 date=pot.year_end)
    return {"carried": carried, "expired": expired}


@transaction.atomic
def expire_carry_in(pot, today, actor=None):
    """Expire carried-in leave unused by the policy's deadline (year start
    plus carry_over_expires_after_days; usable through that day).

    Leave taken on or before the deadline (bookings, TOIL taken, net of
    cancellations, by the date of the leave) is taken from the carry-in
    first; what is left of the carry-in expires, never more than the pot's
    balance. A negative carry-in never expires. One line at most, noted
    "carry-in expired"; returns it, or None."""
    _lock(pot)
    carried = _sum(pot.entries.filter(kind=K.CARRY_IN))
    if carried <= 0 or pot.entries.filter(kind=K.EXPIRY, note=CARRY_IN_EXPIRED).exists():
        return None
    days = policies.policy_for(pot.employment, pot.absence_type, pot.year_start).carry_over_expires_after_days
    if not days:
        return None
    deadline = pot.year_start + timedelta(days=days)
    if today <= deadline:
        return None
    taken = max(ZERO - _sum(pot.entries.filter(kind__in=TAKEN, date__lte=deadline)), ZERO)
    unused = min(carried - taken, max(ledger.balance(pot), ZERO))
    if unused <= 0:
        return None
    return ledger.write(pot, K.EXPIRY, ZERO - unused, actor, note=CARRY_IN_EXPIRED,
                        date=deadline + timedelta(days=1))


def _toil_marker(earned):
    return f"{TOIL_EXPIRED}: earned {earned.date:%d %b %Y} (entry {earned.pk})"


@transaction.atomic
def expire_toil(pot, today, actor=None):
    """Expire each TOIL-earned line unused toil_expires_after_days after it
    was earned (the policy in force on the day it was earned; usable
    through the deadline).

    Consumption is first in, first out: all the TOIL taken on the pot (net
    of cancellations, whatever its date) is used up from the oldest earned
    line first, skipping what of each has already expired. An earned line
    past its deadline with no expiry of its own yet expires what of it is
    unconsumed, never more than the pot's balance. One expiry per earned
    line at most; returns the lines written."""
    _lock(pot)
    earned = list(pot.entries.filter(kind=K.TOIL_EARNED).order_by("date", "id"))
    if not earned:
        return []
    already = {e.note: ZERO - e.units
               for e in pot.entries.filter(kind=K.EXPIRY, note__startswith=TOIL_EXPIRED)}
    to_consume = max(ZERO - _sum(pot.entries.filter(kind__in=(K.TOIL_TAKEN, K.CANCELLATION))), ZERO)
    out = []
    for line in earned:
        marker = _toil_marker(line)
        left = line.units - already.get(marker, ZERO)
        used = min(to_consume, max(left, ZERO))
        to_consume -= used
        if marker in already:
            continue
        days = policies.policy_for(pot.employment, pot.absence_type, line.date).toil_expires_after_days
        if not days:
            continue
        deadline = line.date + timedelta(days=days)
        if today <= deadline:
            continue
        unused = min(left - used, max(ledger.balance(pot), ZERO))
        if unused <= 0:
            continue
        out.append(ledger.write(pot, K.EXPIRY, ZERO - unused, actor, note=marker,
                                date=deadline + timedelta(days=1)))
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
