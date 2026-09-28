"""Re-sync entitlements when the rows they are computed from change.
The nightly job repeats this for every open pot as a safety net."""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from absence.models import Policy, PolicyTier
from absence.services import ledger, pots
from people.models import Contract, Employment


def resync_employment(employment, cause):
    for pot in pots.open_pots(timezone.localdate()).filter(employment=employment):
        ledger.sync_entitlement(pot, cause=cause)


def resync_contract_type(contract_type, cause):
    for pot in pots.open_pots(timezone.localdate()):
        if pot.employment.contracts.filter(contract_type=contract_type).exists():
            ledger.sync_entitlement(pot, cause=cause)


@receiver(post_save, sender=Contract)
def _contract_saved(sender, instance, created, **kwargs):
    resync_employment(instance.employment, f"contract {'added' if created else 'changed'}: {instance}")


@receiver(post_save, sender=Employment)
def _employment_saved(sender, instance, created, **kwargs):
    if not created:
        resync_employment(instance, "employment dates changed")


@receiver(post_save, sender=Policy)
def _policy_saved(sender, instance, **kwargs):
    resync_contract_type(instance.contract_type, f"policy changed: {instance}")


@receiver(post_save, sender=PolicyTier)
def _tier_saved(sender, instance, **kwargs):
    resync_contract_type(instance.policy.contract_type, f"tier changed: {instance}")
