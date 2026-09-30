from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Sum

from absence.models import Absence, AbsenceType, LedgerEntry, Policy
from absence.services import ledger, policies, pots
from people.services import contracts

K = LedgerEntry.Kind
ZERO = Decimal("0")


def _sum(qs):
    return qs.aggregate(t=Sum("units"))["t"] or ZERO


def summary(pot, today):
    entries = pot.entries
    booked_lines = entries.filter(kind__in=(K.BOOKING, K.TOIL_TAKEN, K.CANCELLATION))
    taken = -_sum(booked_lines.filter(absence__end_date__lt=today))
    booked = -_sum(booked_lines.filter(absence__end_date__gte=today))
    pending = Absence.objects.filter(
        employment=pot.employment, absence_type=pot.absence_type, status=Absence.Status.REQUESTED,
        start_date__range=(pot.year_start, pot.year_end)).aggregate(t=Sum("cost_units"))["t"] or Decimal("0")
    return {
        "entitlement": ledger.entitlement_lines_total(pot),
        "carried_in": _sum(entries.filter(kind=K.CARRY_IN)),
        "taken": taken,
        "booked": booked,
        "pending": pending,
        "expired": -_sum(entries.filter(kind=K.EXPIRY)),
        "adjustments": _sum(entries.filter(kind__in=(K.ADJUSTMENT, K.TOIL_EARNED))),
        "remaining": ledger.balance(pot),
    }


def _nothing_yet(employment, absence_type, start, end):
    """The summary of a pot not opened yet for a type that does not accrue
    (TOIL): nothing earned, so every figure is 0 but the requests waiting in
    the year, when the year is known."""
    out = {k: ZERO for k in ("entitlement", "carried_in", "taken", "booked", "pending", "expired",
                             "adjustments", "remaining")}
    if start is not None:
        out["pending"] = Absence.objects.filter(
            employment=employment, absence_type=absence_type, status=Absence.Status.REQUESTED,
            start_date__range=(start, end)).aggregate(t=Sum("cost_units"))["t"] or ZERO
    return out


def _year(employment, absence_type, day, today):
    """(pot, summary) for the leave year containing `day`: (None, None) when
    the pot is not open yet, except for a type that does not accrue, whose
    pot starts at zero: (None, _nothing_yet). Raises as pots.lookup."""
    pot = pots.lookup(employment, absence_type, day)
    if pot is not None:
        return pot, summary(pot, today)
    if absence_type.accrues:
        return None, None
    start, end = pots.bounds(employment, absence_type, day)
    return None, _nothing_yet(employment, absence_type, start, end)


def bank_holiday_pot_used(employment, day):
    """Only "pot" handling on the annual-leave policy charges a bank-holiday
    pot; otherwise there is none to show (nor to open overnight)."""
    try:
        al = policies.policy_for(employment, AbsenceType.objects.get(code="AL"), day)
    except ValidationError:
        return False
    return al.bank_holiday_handling == Policy.BankHolidays.PRO_RATA_POT


def rows(employment, today, include_bh=False, with_next=False, show_setup_gaps=False):
    """One row per active pot-backed type for the leave year containing
    `today`: {"type", "pot", "summary", "unit", "error"}. Reads only: a pot
    not yet opened has pot and summary None. A missing contract carries the
    service's message in "error"; a type with no policy for the contract
    type is left out, unless `show_setup_gaps` (an HR admin, who can add the
    policy) asks for its message too.

    A type that does not accrue (TOIL) always has a row for a person with a
    contract, and never the "no policy" gap: it needs none, and until its
    pot opens (when TOIL is first earned or booked) its summary is all 0
    (_nothing_yet), with pot None.

    The bank-holiday row (`include_bh`) is there only where the annual
    policy's handling is "pot". A pot not opened yet is one the nightly
    opens (nightly._open_pots opens this year's and next year's).

    `with_next` adds the following leave year as "next_pot"/"next_summary"
    (None when it is not open yet), found by lookup on the day after this
    year ends, so nothing is opened or synced. "next_unavailable" says why
    there is none to open: the employment ends before it, or no contract or
    policy covers it."""
    types = AbsenceType.objects.filter(active=True, uses_pot=True)
    if not include_bh or not bank_holiday_pot_used(employment, today):
        types = types.exclude(code="BH")
    unit = contracts.unit(employment, today)
    out = []
    for t in types:
        row = {"type": t, "pot": None, "summary": None, "unit": unit, "error": ""}
        this_end = None
        try:
            row["pot"], row["summary"] = _year(employment, t, today, today)
            if row["pot"] is not None:
                row["unit"], this_end = row["pot"].unit, row["pot"].year_end
            elif not t.accrues:
                this_end = pots.bounds(employment, t, today)[1]
        except policies.NoPolicy as e:
            if not t.accrues:
                row["summary"] = _nothing_yet(employment, t, None, None)   # no year to earn in: nothing earned
            elif not show_setup_gaps:
                continue
            else:
                row["error"] = " ".join(e.messages)
        except ValidationError as e:
            row["error"] = " ".join(e.messages)
        if with_next:
            row.update(next_pot=None, next_summary=None, next_unavailable="")
            if this_end is not None:
                next_start = this_end + timedelta(days=1)
                if not employment.is_active_on(next_start):
                    row["next_unavailable"] = "Not employed then."
                else:
                    try:
                        row["next_pot"], row["next_summary"] = _year(employment, t, next_start, today)
                    except ValidationError:
                        row["next_unavailable"] = "Nothing is set up for this year."
            elif row["pot"] is None and row["summary"] is not None:
                row["next_unavailable"] = "Nothing is set up for this year."
        out.append(row)
    return out


def after(employment, absence_type, day, cost, today):
    """What the pot a `cost` absence starting on `day` would draw on has
    left, and after it, in the pot's "unit". None for a pot-less type;
    {"pot": None} when the pot is not open yet, but for a type that does
    not accrue (TOIL), which starts from 0 until its pot opens. Reads only;
    raises ValidationError as pots.lookup does."""
    if not absence_type.uses_pot:
        return None
    pot, s = _year(employment, absence_type, day, today)
    if s is None:
        return {"pot": None}
    cost = cost or ZERO
    left = s["remaining"] - cost
    return {"pot": pot, "unit": pot.unit if pot is not None else contracts.unit(employment, day),
            "remaining": s["remaining"], "pending": s["pending"], "cost": cost, "after": left, "over": left < 0}
