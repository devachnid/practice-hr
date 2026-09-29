from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Sum

from absence.models import Absence, AbsenceType, LedgerEntry, Policy
from absence.services import ledger, policies, pots

K = LedgerEntry.Kind


def _sum(qs):
    return qs.aggregate(t=Sum("units"))["t"] or Decimal("0")


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


def _year(employment, absence_type, day, today):
    pot = pots.lookup(employment, absence_type, day)
    return pot, summary(pot, today) if pot is not None else None


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
    `today`: {"type", "pot", "summary", "error"}. Reads only: a pot not yet
    opened has pot and summary None. A missing contract carries the service's
    message in "error"; a type with no policy for the contract type is left
    out, unless `show_setup_gaps` (an HR admin, who can add the policy) asks
    for its message too.

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
    out = []
    for t in types:
        row = {"type": t, "pot": None, "summary": None, "error": ""}
        try:
            row["pot"], row["summary"] = _year(employment, t, today, today)
        except policies.NoPolicy as e:
            if not show_setup_gaps:
                continue
            row["error"] = " ".join(e.messages)
        except ValidationError as e:
            row["error"] = " ".join(e.messages)
        if with_next:
            row.update(next_pot=None, next_summary=None, next_unavailable="")
            if row["pot"] is not None:
                next_start = row["pot"].year_end + timedelta(days=1)
                if not employment.is_active_on(next_start):
                    row["next_unavailable"] = "Not employed then."
                else:
                    try:
                        row["next_pot"], row["next_summary"] = _year(employment, t, next_start, today)
                    except ValidationError:
                        row["next_unavailable"] = "Nothing is set up for this year."
        out.append(row)
    return out


def after(employment, absence_type, day, cost, today):
    """What the pot a `cost` absence starting on `day` would draw on has
    left, and after it. None for a pot-less type; {"pot": None} when the pot
    is not open yet. Reads only; raises ValidationError as pots.lookup does."""
    if not absence_type.uses_pot:
        return None
    pot = pots.lookup(employment, absence_type, day)
    if pot is None:
        return {"pot": None}
    s = summary(pot, today)
    cost = cost or Decimal("0")
    left = s["remaining"] - cost
    return {"pot": pot, "remaining": s["remaining"], "pending": s["pending"], "cost": cost,
            "after": left, "over": left < 0}
