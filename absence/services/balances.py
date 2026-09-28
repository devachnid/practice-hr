from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Sum

from absence.models import Absence, AbsenceType, LedgerEntry
from absence.services import ledger, pots

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


def rows(employment, today, include_bh=False):
    """One row per active pot-backed type for the leave year containing
    `today`: {"type", "pot", "summary", "error"}. Reads only: a pot not yet
    opened has pot and summary None; a type with no policy or contract
    carries the service's message in "error"."""
    types = AbsenceType.objects.filter(active=True, uses_pot=True)
    if not include_bh:
        types = types.exclude(code="BH")
    out = []
    for t in types:
        row = {"type": t, "pot": None, "summary": None, "error": ""}
        try:
            row["pot"] = pots.lookup(employment, t, today)
        except ValidationError as e:
            row["error"] = " ".join(e.messages)
        if row["pot"] is not None:
            row["summary"] = summary(row["pot"], today)
        out.append(row)
    return out
