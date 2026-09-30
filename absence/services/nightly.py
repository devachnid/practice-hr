from datetime import timedelta

from django.core.exceptions import ValidationError

from absence.models import AbsenceType, Pot
from absence.services import balances, bank_holidays, chase, ledger, policies, pots, year_end
from people.services import contracts, employments


def _why(subject, e):
    return f"{subject}: {'; '.join(e.messages)}"


def _pot_covering(employment, absence_type, day):
    return Pot.objects.filter(employment=employment, absence_type=absence_type,
                              year_start__lte=day, year_end__gte=day).first()


def _reported(absence_type, e):
    """Which failures to open a pot are worth a line in `failed`: any for
    annual leave (everyone has one); for the bank-holiday pot, used under
    "pot" handling, a missing policy of its own. Another pot-backed type
    with no policy for the contract type is simply not an allowance this
    person has (study leave, say), so it is skipped quietly."""
    if absence_type.code == "AL":
        return True
    return absence_type.code == "BH" and isinstance(e, policies.NoPolicy)


def _open_pots(today, failed):
    """Open this year's and next year's pot of every pot-backed type for
    every employment active today, so a new starter has an entitlement and
    bank-holiday charges before their first booking, and the request and
    decide pages can show next year's balance (spec §5) all year.

    This year is the leave year containing today; next year starts the day
    after it ends, and is opened only if the person is still employed and
    contracted that day and a policy covers it. Annual leave always; the
    bank-holiday pot only where the annual policy's handling is "pot";
    any other pot-backed type (study leave…) where the contract type has a
    policy for it. A type that does not accrue (TOIL) is never opened here:
    it would hold nothing, so its pot opens when TOIL is first earned
    (toil.earn) or booked, and the balances show it at zero until then.
    The pots are opened bare and synced by run()'s loops, which count what
    they write."""
    types = list(AbsenceType.objects.filter(uses_pot=True, accrues=True, active=True)
                 .order_by("display_order", "id"))
    opened = 0
    for employment in employments.active_on(today).select_related("employee"):
        for absence_type in types:
            day = today
            for year in ("this", "next"):
                if year == "next" and not (employment.is_active_on(day)
                                           and contracts.active_on(employment, day).exists()):
                    break                               # leaving before then: nothing to open
                if absence_type.code == "BH" and not balances.bank_holiday_pot_used(employment, day):
                    break
                pot = _pot_covering(employment, absence_type, day)
                if pot is None:
                    try:
                        pot = pots.for_day(employment, absence_type, day, sync=False)
                    except ValidationError as e:
                        if _reported(absence_type, e):
                            failed.append(_why(employment, e))
                        break
                    opened += 1
                day = pot.year_end + timedelta(days=1)
    return opened


def run(today):
    """Close the pots whose leave year has ended and run the carry-in and
    TOIL expiries (year_end.run), open this year's and next year's pots of
    every active employment (_open_pots), then re-sync every open pot's
    entitlement and every open annual-leave pot's automatic bank-holiday
    absences. Idempotent. A pot or employment that cannot be processed (no
    contract, or no policy covers a day) is listed in `failed` and skipped,
    so one bad row never stops the rest."""
    ended = year_end.run(today)
    failed = list(ended["failed"])
    opened = _open_pots(today, failed)
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
