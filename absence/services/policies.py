from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Q

from absence.models import AbsenceType, Policy
from people.services import contracts, employments


class NoPolicy(ValidationError):
    """No policy covers the contract type on that day. Apart from a missing
    contract, so a page can show the first to an HR admin only."""


def policy_for(employment, absence_type, day):
    """The policy in force on `day` for the employment's contract type and
    this absence type. Raises ValidationError when there is no contract on
    the day, NoPolicy when no policy covers it.

    A type that does not accrue (`accrues` off: TOIL) has no policy of its
    own. Its pot borrows the annual-leave (AL) policy for the contract type
    on the day, and uses only its leave year and its rounding step: the pot
    earns nothing (accrual.entitlement is 0), carries uncapped at year end
    (year_end._close_toil) and its lots expire by the type's own
    `earned_expires_after_days`. So a missing policy for such a type names
    annual leave's."""
    if not absence_type.accrues:
        absence_type = AbsenceType.objects.get(code="AL")
    contract = contracts.active_on(employment, day).first()
    if contract is None:
        raise ValidationError(f"{employment.employee} has no contract on {day:%d %b %Y}.")
    ct = contract.contract_type
    policy = (Policy.objects.filter(contract_type=ct, absence_type=absence_type, effective_from__lte=day)
              .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=day))
              .order_by("-effective_from").first())
    if policy is None:
        raise NoPolicy(f"No {absence_type} policy for {ct} on {day:%d %b %Y}. "
                              f"Add one under Absence › Policies.")
    return policy


def tier_extra_weeks(policy, employment, day):
    years = employments.service_years(employment, day)
    extra = Decimal("0")
    for tier in policy.tiers.all():
        if years >= tier.after_years:
            extra = tier.extra_weeks
    return extra
