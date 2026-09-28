from django.core.exceptions import ValidationError

from absence.models import AbsenceType, Policy, Pot
from absence.services import bank_holidays, chase, ledger, policies, pots, year_end
from people.services import employments


def _why(subject, e):
    return f"{subject}: {'; '.join(e.messages)}"


def _has_pot(employment, absence_type, today):
    return Pot.objects.filter(employment=employment, absence_type=absence_type,
                              year_start__lte=today, year_end__gte=today).exists()


def _open_current_pots(today, failed):
    """Open this year's annual-leave pot, and the bank-holiday pot where the
    annual policy's handling is "pot", for every employment active today, so
    a new starter has an entitlement and bank-holiday charges before their
    first booking. The pots are synced by run()'s loops, not here."""
    al, bh = AbsenceType.objects.get(code="AL"), AbsenceType.objects.get(code="BH")
    opened = 0
    for employment in employments.active_on(today).select_related("employee"):
        try:
            if not _has_pot(employment, al, today):
                pots.for_day(employment, al, today, sync=False)
                opened += 1
            if _has_pot(employment, bh, today):
                continue
        except ValidationError as e:
            failed.append(_why(employment, e))
            continue
        try:
            handling = policies.policy_for(employment, al, today).bank_holiday_handling
        except ValidationError:
            continue        # the annual pot already exists; its own sync below reports this
        if handling != Policy.BankHolidays.PRO_RATA_POT:
            continue
        try:
            pots.for_day(employment, bh, today, sync=False)
            opened += 1
        except ValidationError as e:
            failed.append(_why(employment, e))
    return opened


def run(today):
    """Close the pots whose leave year has ended and run the carry-in and
    TOIL expiries (year_end.run), open the current pots of every active
    employment, then re-sync every open pot's entitlement and every open
    annual-leave pot's automatic bank-holiday absences. Idempotent. A pot or
    employment that cannot be processed (no contract, or no policy covers a
    day) is listed in `failed` and skipped, so one bad row never stops the
    rest."""
    ended = year_end.run(today)
    failed = list(ended["failed"])
    opened = _open_current_pots(today, failed)
    open_pots = list(pots.open_pots(today))     # after the bootstrap: the new pots are synced too
    synced = revisions = 0
    for pot in open_pots:
        try:
            revised = ledger.sync_entitlement(pot, cause="nightly recalculation")
        except ValidationError as e:
            failed.append(_why(pot, e))
            continue
        synced += 1
        if revised is not None:
            revisions += 1
    created = removed = recosted = 0
    for pot in open_pots:
        if pot.absence_type.code != "AL":
            continue
        try:
            r = bank_holidays.sync_auto_absences(pot.employment, pot.year_start, pot.year_end, today=today)
        except ValidationError as e:
            failed.append(_why(pot, e))
            continue
        created += r["created"]
        removed += r["removed"]
        recosted += r["recosted"]
    chased = 0
    try:
        chased = chase.notify_once(today)
    except Exception as e:  # noqa: BLE001 - notify never raises, but the query might; the rest of the night stands
        failed.append(f"chase: {e.__class__.__name__}: {e}")
    return {"pots_opened": opened, "pots_synced": synced, "revisions": revisions,
            "bank_holiday_created": created, "bank_holiday_removed": removed,
            "bank_holiday_recosted": recosted, "year_end_closed": ended["closed"],
            "carried_total": ended["carried_total"], "expired_total": ended["expired_total"],
            "carry_in_expired": ended["carry_in_expired"], "toil_expired": ended["toil_expired"],
            "leaver_debts": ended["leaver_debts"], "chased": chased, "failed": failed}
