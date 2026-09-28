from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from people.models import Contract
from people.services import audit


def active_on(employment, day):
    return Contract.objects.filter(
        employment=employment, from_date__lte=day
    ).filter(Q(to_date__isnull=True) | Q(to_date__gte=day)).select_related("contract_type")


def contracted_amount(employment, day):
    return sum((c.weekly_amount for c in active_on(employment, day)), Decimal("0"))


def unit(employment, day):
    c = active_on(employment, day).first()
    return c.contract_type.unit if c else None


def fte(employment, day):
    total = sum((r.weekly_amount / r.contract_type.full_time_weekly for r in active_on(employment, day)),
                Decimal("0"))
    return total.quantize(Decimal("0.01"))


def _unit_clash(employment, contract_type, from_date, to_date, exclude_pk=None):
    others = Contract.objects.filter(employment=employment).exclude(
        contract_type__unit=contract_type.unit
    ).filter(Q(to_date__isnull=True) | Q(to_date__gte=from_date))
    if to_date is not None:
        others = others.filter(from_date__lte=to_date)
    if exclude_pk is not None:
        others = others.exclude(pk=exclude_pk)
    return others.exists()


@transaction.atomic
def add(actor, employment, contract_type, weekly_amount, from_date, basis="permanent",
        to_date=None, notes=""):
    if _unit_clash(employment, contract_type, from_date, to_date):
        raise ValidationError({"contract_type": "Concurrent contracts must share a unit "
                                                "(sessions or hours)."})
    c = Contract(employment=employment, contract_type=contract_type, basis=basis,
                 from_date=from_date, to_date=to_date, weekly_amount=weekly_amount, notes=notes)
    c.full_clean()
    c.save()
    audit.record(actor, c, {"created": ("", str(c))})
    return c


@transaction.atomic
def end(actor, contract, to_date):
    if _unit_clash(contract.employment, contract.contract_type, contract.from_date, to_date,
                    exclude_pk=contract.pk):
        raise ValidationError({"contract_type": "Concurrent contracts must share a unit "
                                                "(sessions or hours)."})
    before = contract.to_date
    contract.to_date = to_date
    contract.full_clean()
    contract.save()
    audit.record(actor, contract, {"to_date": (before, to_date)})
    return contract
