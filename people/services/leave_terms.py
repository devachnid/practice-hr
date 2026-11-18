"""Annual leave terms, held on a contract type (the usual terms) and on a
contract (its own, when they differ). A base and each step's total are in
days for an hours contract and weeks for a sessions one. AMG Shift Central
reads the terms in force through the feed and works the allowances out;
nothing here turns terms into hours, and Practice HR's own leave policies
do not read them."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from people.models import Contract, ContractLeaveStep, ContractType, ContractTypeLeaveStep
from people.services import audit

MOST = Decimal("99")
CENT = Decimal("0.01")
Terms = Contract.LeaveTerms
UNIT_CHANGE = "Clear this type's leave terms, and its contracts' own terms, before changing the unit."
TWO_PLACES = "At most 2 decimal places."


def unit_word(unit):
    """What a base and its totals are counted in."""
    return "days" if unit == ContractType.Unit.HOURS else "weeks"


def check_unit_change(contract_type, new_unit):
    """ValidationError when the stored unit would change under leave terms
    counted in it: 24 days would become 24 weeks."""
    stored = ContractType.objects.get(pk=contract_type.pk)
    if new_unit == stored.unit:
        return
    if (stored.leave_base is not None or stored.leave_steps.exists()
            or stored.contracts.filter(leave_terms=Terms.OWN).exists()):
        raise ValidationError(UNIT_CHANGE)


def check(base, steps):
    """The steps sorted by years, or ValidationError. `steps` is an iterable
    of (after_years, total)."""
    steps = sorted(steps)
    if base is None:
        if steps:
            raise ValidationError({"leave_base": "Steps need the figure they step up from."})
        return []
    if not Decimal("0") < base <= MOST:
        raise ValidationError({"leave_base": "More than 0 and at most 99."})
    if base != base.quantize(CENT):
        raise ValidationError({"leave_base": TWO_PLACES})
    if len({years for years, _ in steps}) != len(steps):
        raise ValidationError("Two steps have the same number of years.")
    before = base
    for years, total in steps:
        if years < 1:
            raise ValidationError("A step starts after at least 1 complete year.")
        if total != total.quantize(CENT):
            raise ValidationError(TWO_PLACES)
        if total <= before:
            raise ValidationError(f"The total after {_years(years)} must be more than the figure before it ({_plain(before)}).")
        if total > MOST:
            raise ValidationError("A total is at most 99.")
        before = total
    return steps


def _steps(owner):
    return [(s.after_years, s.total) for s in owner.leave_steps.all()]


def resolved(contract):
    """The terms in force for a contract, {"base", "steps"}, or None when
    its allowances are not worked out."""
    if contract.leave_terms == Terms.OWN:
        owner = contract
    elif contract.leave_terms == Terms.USUAL:
        owner = contract.contract_type
    else:
        return None
    if owner.leave_base is None:
        return None
    return {"base": owner.leave_base, "steps": _steps(owner)}


def _plain(number):
    """22.00 as "22", 27.50 as "27.5"."""
    return f"{number.normalize():f}"


def _years(years):
    return f"{years} year" if years == 1 else f"{years} years"


def _steps_text(steps):
    return "; ".join(f"{_plain(total)} after {_years(years)}" for years, total in steps)


def _text(terms, unit):
    base = f"{_plain(terms['base'])} {unit_word(unit)}"
    return f"{base}; {_steps_text(terms['steps'])}" if terms["steps"] else base


def describe(contract):
    """One line for the admin: which terms apply and what they are."""
    ct = contract.contract_type
    terms = resolved(contract)
    if contract.leave_terms == Terms.NONE:
        return "Not worked out"
    if contract.leave_terms == Terms.OWN:
        return f"Own: {_text(terms, ct.unit)}" if terms else "Own: no figure set"
    return f"Usual for {ct.name}: {_text(terms, ct.unit)}" if terms else f"Usual for {ct.name}: none set, so not worked out"


def _show(base):
    return "" if base is None else _plain(base)


def _replace(owner, step_model, key, base, steps):
    owner.leave_base = base
    owner.leave_steps.all().delete()
    step_model.objects.bulk_create([step_model(**{key: owner}, after_years=years, total=total) for years, total in steps])


@transaction.atomic
def set_type_terms(actor, contract_type, base, steps=()):
    """A contract type's usual terms. Every contract of the type on "Usual
    for the contract type" follows them from the next read of the feed."""
    steps = check(base, steps)
    changes = {"leave_base": (_show(contract_type.leave_base), _show(base)),
               "leave_steps": (_steps_text(_steps(contract_type)), _steps_text(steps))}
    _replace(contract_type, ContractTypeLeaveStep, "contract_type", base, steps)
    contract_type.save(update_fields=["leave_base"])
    audit.record(actor, contract_type, changes)
    return contract_type


@transaction.atomic
def set_contract_terms(actor, contract, mode, base=None, steps=()):
    """Which terms a contract takes. Only Own terms hold a figure and
    steps: with either other choice whatever is sent is dropped."""
    if mode not in Terms.values:
        raise ValidationError({"leave_terms": "Choose which leave terms apply."})
    if mode != Terms.OWN:
        base, steps = None, ()
    elif base is None:
        raise ValidationError({"leave_base": "Own terms need a figure."})
    steps = check(base, steps)
    changes = {"leave_terms": (contract.leave_terms, mode),
               "leave_base": (_show(contract.leave_base), _show(base)),
               "leave_steps": (_steps_text(_steps(contract)), _steps_text(steps))}
    contract.leave_terms = mode
    _replace(contract, ContractLeaveStep, "contract", base, steps)
    contract.save(update_fields=["leave_terms", "leave_base"])
    audit.record(actor, contract, changes)
    return contract
