from django.core.exceptions import ValidationError

from absence.services import bank_holidays, ledger, pots


def _why(pot, e):
    return f"{pot}: {'; '.join(e.messages)}"


def run(today):
    """Safety net behind the signals: re-sync every open pot's entitlement and
    every open annual-leave pot's automatic bank-holiday absences. Idempotent.
    A pot that cannot be synced (no policy covers a day of its year) is listed
    in `failed` and skipped, so one bad pot never stops the rest."""
    synced = revisions = 0
    failed = []
    for pot in pots.open_pots(today):
        try:
            revised = ledger.sync_entitlement(pot, cause="nightly recalculation")
        except ValidationError as e:
            failed.append(_why(pot, e))
            continue
        synced += 1
        if revised is not None:
            revisions += 1
    created = removed = recosted = 0
    for pot in pots.open_pots(today).filter(absence_type__code="AL"):
        try:
            r = bank_holidays.sync_auto_absences(pot.employment, pot.year_start, pot.year_end, today=today)
        except ValidationError as e:
            failed.append(_why(pot, e))
            continue
        created += r["created"]
        removed += r["removed"]
        recosted += r["recosted"]
    return {"pots_synced": synced, "revisions": revisions,
            "bank_holiday_created": created, "bank_holiday_removed": removed,
            "bank_holiday_recosted": recosted, "failed": failed}
