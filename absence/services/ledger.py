from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from absence.models import LedgerEntry


@transaction.atomic
def write(pot, kind, units, actor=None, absence=None, note="", date=None):
    return LedgerEntry.objects.create(
        pot=pot, date=date or timezone.localdate(), kind=kind, units=Decimal(units),
        absence=absence, note=note[:200], actor=actor)


def balance(pot):
    return pot.entries.aggregate(t=Sum("units"))["t"] or Decimal("0")
