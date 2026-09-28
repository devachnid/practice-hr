from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q, Sum
from django.utils import timezone

from absence.models import LedgerEntry


@transaction.atomic
def write(pot, kind, units, actor=None, absence=None, note="", date=None):
    return LedgerEntry.objects.create(
        pot=pot, date=date or timezone.localdate(), kind=kind, units=Decimal(units),
        absence=absence, note=note[:200], actor=actor)


def balance(pot):
    return pot.entries.aggregate(t=Sum("units"))["t"] or Decimal("0")


def entitlement_lines_total(pot):
    kinds = (LedgerEntry.Kind.ENTITLEMENT, LedgerEntry.Kind.REVISION)
    return pot.entries.filter(kind__in=kinds).aggregate(t=Sum("units"))["t"] or Decimal("0")


@transaction.atomic
def sync_entitlement(pot, actor=None, cause=""):
    """Bring the entitlement lines up to accrual.entitlement(pot). Writes
    one line for the difference, or nothing. Idempotent."""
    from absence.services import accrual
    if pot.absence_type.code == "BH":
        expected = accrual.bank_holiday_entitlement(pot)
    else:
        expected = accrual.entitlement(pot)
    existing = entitlement_lines_total(pot)
    delta = expected - existing
    if delta == 0:
        return None
    kind = LedgerEntry.Kind.ENTITLEMENT if existing == 0 and not pot.entries.filter(
        kind=LedgerEntry.Kind.ENTITLEMENT).exists() else LedgerEntry.Kind.REVISION
    return write(pot, kind, delta, actor, note=cause or "entitlement recalculated",
                 date=pot.year_start if kind == LedgerEntry.Kind.ENTITLEMENT else None)


def resync_contract_type(contract_type, absence_type, actor=None, cause="", today=None):
    """Re-sync the pots a policy for (contract_type, absence_type) can
    change: open pots of that type whose employment has a contract of that
    type overlapping the pot's year, found in one query. Each pot syncs in
    its own transaction; one that cannot (no policy covers a day) is listed
    in `failed`, not raised, so the rest are still revised."""
    from absence.services import pots
    from people.models import Contract
    overlapping = Contract.objects.filter(
        employment=OuterRef("employment"), contract_type=contract_type, from_date__lte=OuterRef("year_end"),
    ).filter(Q(to_date__isnull=True) | Q(to_date__gte=OuterRef("year_start")))
    revised, failed = 0, []
    for pot in pots.open_pots(today).filter(absence_type=absence_type).filter(Exists(overlapping)):
        try:
            if sync_entitlement(pot, actor, cause):
                revised += 1
        except ValidationError as e:
            failed.append(f"{pot}: {'; '.join(e.messages)}")
    return {"revised": revised, "failed": failed}
