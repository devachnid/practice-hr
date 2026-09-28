from absence.services import bank_holidays, ledger, pots


def run(today):
    """Safety net behind the signals: re-sync every open pot's entitlement and
    every open annual-leave pot's automatic bank-holiday absences. Idempotent."""
    synced = revisions = 0
    for pot in pots.open_pots(today):
        synced += 1
        if ledger.sync_entitlement(pot, cause="nightly recalculation") is not None:
            revisions += 1
    created = removed = 0
    for pot in pots.open_pots(today).filter(absence_type__code="AL"):
        r = bank_holidays.sync_auto_absences(pot.employment, pot.year_start, pot.year_end)
        created += r["created"]
        removed += r["removed"]
    return {"pots_synced": synced, "revisions": revisions,
            "bank_holiday_created": created, "bank_holiday_removed": removed}
