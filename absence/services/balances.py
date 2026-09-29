from decimal import Decimal

from django.db.models import Sum

from absence.models import Absence, LedgerEntry
from absence.services import ledger

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
