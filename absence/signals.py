"""Re-sync entitlements when the people rows they are computed from change.
Policy and tier edits re-sync from PolicyAdmin.save_related instead (once
per save, as the admin who made it); the nightly job repeats this for
every open pot as a safety net."""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from absence.services import ledger, pots
from people.models import Contract, Employment


def resync_employment(employment, cause):
    for pot in pots.open_pots(timezone.localdate()).filter(employment=employment):
        ledger.sync_entitlement(pot, cause=cause)


@receiver(post_save, sender=Contract)
def _contract_saved(sender, instance, created, **kwargs):
    resync_employment(instance.employment, f"contract {'added' if created else 'changed'}: {instance}")


@receiver(post_save, sender=Employment)
def _employment_saved(sender, instance, created, **kwargs):
    if not created:
        resync_employment(instance, "employment dates changed")
