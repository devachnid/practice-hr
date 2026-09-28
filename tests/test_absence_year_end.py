from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from absence.models import LedgerEntry, Policy
from absence.services import bookings, ledger, nightly, pots, toil, year_end
from people.models import AuditEntry
from tests.factories import (absence_type, hours_employee, make_contract, make_contract_type, make_employment,
                             make_pattern, make_policy)

D = Decimal
K = LedgerEntry.Kind
JUNE_MON = date(2026, 6, 1)     # a Monday with no bank holiday for seven weeks after it


def _pot_2026(emp):
    pot = pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    ledger.sync_entitlement(pot)
    return pot


def _next_pot(emp):
    return pots.for_day(emp, absence_type("AL"), date(2027, 4, 1))


def _toil_employee(days=90):
    emp = hours_employee()
    make_policy(emp.contracts.first().contract_type, "TOIL", weeks_per_year=D("0"), toil_expires_after_days=days)
    return emp


def _take_toil(hr_admin, employee_user, emp, day):
    a = bookings.request(employee_user, emp, absence_type("TOIL"), day)
    return bookings.approve(hr_admin, a)


# --- close ------------------------------------------------------------------

def test_close_carries_up_to_cap_and_expires_rest(db):
    emp = hours_employee(start=date(2025, 4, 1))
    Policy.objects.update(carry_over_max_weeks=D("1"))           # 37.5 hours
    pot = _pot_2026(emp)                                          # 210, nothing taken
    result = year_end.close(pot)
    assert result == {"carried": D("37.50"), "expired": D("172.50")}
    nxt = _next_pot(emp)
    carry = nxt.entries.get(kind=K.CARRY_IN)
    assert carry.units == D("37.50") and carry.note == "year end: carried in from 2026/27"
    expiry = pot.entries.get(kind=K.EXPIRY)                        # R10: one line for the whole remaining
    assert expiry.units == D("-210.00") and expiry.date == date(2027, 3, 31)
    assert expiry.note == "year end close: 37.50 carried to 2027-04-01, 172.50 expired"
    assert ledger.balance(pot) == D("0")
    assert ledger.balance(nxt) == D("247.50")                      # opened synced: 210 + 37.50


def test_close_twice_is_a_no_op(db):
    emp = hours_employee(start=date(2025, 4, 1))
    Policy.objects.update(carry_over_max_weeks=D("1"))
    pot = _pot_2026(emp)
    year_end.close(pot)
    assert year_end.close(pot) == {"carried": D("0"), "expired": D("0"), "skipped": True}
    nxt = _next_pot(emp)
    assert pot.entries.filter(kind=K.EXPIRY).count() == 1
    assert nxt.entries.filter(kind=K.CARRY_IN).count() == 1
    year_end.run(date(2027, 4, 2))
    year_end.run(date(2027, 4, 2))
    assert pot.entries.filter(kind=K.EXPIRY).count() == 1
    assert nxt.entries.filter(kind=K.CARRY_IN).count() == 1


def test_the_next_pots_carry_in_does_not_mark_it_closed(db):
    emp = hours_employee(start=date(2025, 4, 1))
    Policy.objects.update(carry_over_max_weeks=D("1"))
    year_end.close(_pot_2026(emp))
    nxt = _next_pot(emp)
    result = year_end.close(nxt)
    assert "skipped" not in result and result["carried"] == D("37.50")


def test_no_cap_means_no_carry(db):
    emp = hours_employee(start=date(2025, 4, 1))
    pot = _pot_2026(emp)
    assert year_end.close(pot) == {"carried": D("0"), "expired": D("210.00")}
    assert ledger.balance(pot) == D("0")
    assert not LedgerEntry.objects.filter(kind=K.CARRY_IN).exists()


def test_a_zero_balance_still_marks_the_pot_closed(db):
    emp = hours_employee(start=date(2025, 4, 1))
    pot = _pot_2026(emp)
    ledger.write(pot, K.ADJUSTMENT, D("-210"), note="all used elsewhere")
    assert year_end.close(pot) == {"carried": D("0"), "expired": D("0")}
    assert pot.entries.get(kind=K.EXPIRY).units == D("0")
    assert year_end.close(pot)["skipped"] is True


def test_negative_balance_carries_in_full(db, hr_admin, employee_user):
    emp = hours_employee(start=date(2025, 4, 1), amount=D("7.5"))
    make_pattern(emp, {0: (D("3.75"), D("3.75"))}, effective_from=date(2026, 4, 1))
    pot = _pot_2026(emp)                                          # 42 hours
    for week in range(7):
        a = bookings.request(employee_user, emp, absence_type("AL"), JUNE_MON + timedelta(weeks=week))
        bookings.approve(hr_admin, a)
    assert ledger.balance(pot) == D("-10.50")
    result = year_end.close(pot)
    assert result == {"carried": D("-10.50"), "expired": D("0")}
    nxt = _next_pot(emp)
    assert nxt.entries.get(kind=K.CARRY_IN).units == D("-10.50")
    assert pot.entries.get(kind=K.EXPIRY).units == D("10.50")
    assert ledger.balance(pot) == D("0")


def _leaver(end=date(2027, 3, 31)):
    emp = hours_employee(start=date(2025, 4, 1))
    emp.end_date = end
    emp.save()
    emp.contracts.update(to_date=end)
    return emp


def test_a_leavers_positive_balance_expires(db):
    emp = _leaver()
    Policy.objects.update(carry_over_max_weeks=D("1"))
    pot = _pot_2026(emp)
    assert year_end.close(pot) == {"carried": D("0"), "expired": D("210.00")}
    expiry = pot.entries.get(kind=K.EXPIRY)
    assert expiry.units == D("-210.00") and expiry.note == "year end close: leaver, 210.00 expired"
    assert emp.pots.count() == 1                                  # no next pot opened
    assert year_end.close(pot)["skipped"] is True


def test_a_leavers_negative_balance_is_left_and_reported(db):
    emp = _leaver()
    pot = _pot_2026(emp)
    ledger.write(pot, K.ADJUSTMENT, D("-217.50"), note="over-taken")
    assert year_end.close(pot) == {"carried": D("0"), "expired": D("0"), "leaver_debt": D("-7.50")}
    assert not pot.entries.filter(kind=K.EXPIRY).exists()
    assert ledger.balance(pot) == D("-7.50")
    result = year_end.run(date(2027, 4, 2))
    assert result["closed"] == 0 and len(result["leaver_debts"]) == 1
    assert str(pot) in result["leaver_debts"][0]
    ledger.write(pot, K.ADJUSTMENT, D("7.50"), note="recovered in final pay")
    assert year_end.run(date(2027, 4, 3))["closed"] == 1          # settled: now it closes at zero
    assert pot.entries.get(kind=K.EXPIRY).units == D("0")


def test_an_expiry_is_reversible_by_an_adjustment(db):
    emp = hours_employee(start=date(2025, 4, 1))
    pot = _pot_2026(emp)
    year_end.close(pot)
    ledger.write(pot, K.ADJUSTMENT, D("210"), note="reversed by HR")
    year_end.run(date(2027, 4, 2))
    assert ledger.balance(pot) == D("210")
    assert pot.entries.filter(kind=K.EXPIRY).count() == 1


# --- carry-in expiry ------------------------------------------------------------

def _carried(emp):
    Policy.objects.update(carry_over_max_weeks=D("1"), carry_over_expires_after_days=90)
    year_end.close(_pot_2026(emp))
    return _next_pot(emp)


def test_carry_in_expires_after_days(db):
    emp = hours_employee(start=date(2025, 4, 1))
    nxt = _carried(emp)
    assert year_end.expire_carry_in(nxt, date(2027, 6, 29)) is None
    assert year_end.expire_carry_in(nxt, date(2027, 6, 30)) is None   # the deadline: still usable
    row = year_end.expire_carry_in(nxt, date(2027, 7, 1))
    assert row.kind == K.EXPIRY and row.units == D("-37.50") and row.note == "carry-in expired"
    assert year_end.expire_carry_in(nxt, date(2027, 7, 2)) is None


def test_leave_taken_by_the_deadline_uses_the_carry_in_first(db, hr_admin, employee_user):
    emp = hours_employee(start=date(2025, 4, 1))
    nxt = _carried(emp)
    for day in (date(2027, 6, 7), date(2027, 6, 8)):                # 15 hours taken before the deadline
        bookings.approve(hr_admin, bookings.request(employee_user, emp, absence_type("AL"), day))
    bookings.approve(hr_admin, bookings.request(employee_user, emp, absence_type("AL"), date(2027, 7, 5)))
    row = year_end.expire_carry_in(nxt, date(2027, 7, 1))
    assert row.units == D("-22.50")


def test_carry_in_expiry_never_takes_more_than_remains(db):
    emp = hours_employee(start=date(2025, 4, 1))
    nxt = _carried(emp)
    ledger.write(nxt, K.ADJUSTMENT, D("-237.50"), date=date(2027, 8, 1), note="bought out")
    row = year_end.expire_carry_in(nxt, date(2027, 7, 1))
    assert row.units == D("-10.00")
    assert ledger.balance(nxt) == D("0")


def test_a_negative_carry_in_never_expires(db):
    emp = hours_employee(start=date(2025, 4, 1))
    Policy.objects.update(carry_over_expires_after_days=90)
    pot = _pot_2026(emp)
    ledger.write(pot, K.ADJUSTMENT, D("-220"), note="over-taken")
    year_end.close(pot)
    assert year_end.expire_carry_in(_next_pot(emp), date(2027, 7, 1)) is None


# --- TOIL ------------------------------------------------------------------------

def test_toil_earned_and_expired(db, hr_admin):
    emp = _toil_employee()
    row = toil.earn(hr_admin, emp, D("3"), date(2026, 6, 1), "late clinic")
    assert row.kind == K.TOIL_EARNED and row.units == D("3") and row.date == date(2026, 6, 1)
    pot = row.pot
    assert pot.absence_type.code == "TOIL" and ledger.balance(pot) == D("3")    # TOIL accrues nothing
    assert year_end.expire_toil(pot, date(2026, 8, 29)) == []
    assert year_end.expire_toil(pot, date(2026, 8, 30)) == []                  # the deadline: still usable
    expired = year_end.expire_toil(pot, date(2026, 8, 31))
    assert [e.units for e in expired] == [D("-3")]
    assert year_end.expire_toil(pot, date(2026, 9, 1)) == []


def test_toil_earned_is_audited(db, hr_admin):
    emp = _toil_employee()
    row = toil.earn(hr_admin, emp, D("2.5"), date(2026, 6, 1), "late clinic")
    entry = AuditEntry.objects.get(model="absence.ledgerentry", object_id=row.pk)
    assert entry.actor == hr_admin and entry.after == "2.50" and entry.note == "late clinic"


@pytest.mark.parametrize("units", [D("0"), D("-1")])
def test_toil_earn_refuses_non_positive_units(db, hr_admin, units):
    emp = _toil_employee()
    with pytest.raises(ValidationError):
        toil.earn(hr_admin, emp, units, date(2026, 6, 1), "nothing")
    assert not LedgerEntry.objects.filter(kind=K.TOIL_EARNED).exists()


def test_toil_taken_is_consumed_oldest_first(db, hr_admin, employee_user):
    emp = _toil_employee()
    first = toil.earn(hr_admin, emp, D("5"), date(2026, 6, 1), "clinic")      # deadline 30 Aug
    toil.earn(hr_admin, emp, D("5"), date(2026, 7, 1), "clinic")              # deadline 29 Sep
    _take_toil(hr_admin, employee_user, emp, date(2026, 6, 15))               # 7.5: all of the first, 2.5 of the second
    pot = first.pot
    assert year_end.expire_toil(pot, date(2026, 9, 1)) == []
    expired = year_end.expire_toil(pot, date(2026, 9, 30))
    assert [e.units for e in expired] == [D("-2.50")]
    assert ledger.balance(pot) == D("0")


def test_toil_taken_after_an_expiry_draws_on_what_is_left(db, hr_admin, employee_user):
    emp = _toil_employee()
    first = toil.earn(hr_admin, emp, D("5"), date(2026, 6, 1), "clinic")
    toil.earn(hr_admin, emp, D("10"), date(2026, 7, 1), "clinic")
    pot = first.pot
    assert [e.units for e in year_end.expire_toil(pot, date(2026, 9, 1))] == [D("-5")]
    _take_toil(hr_admin, employee_user, emp, date(2026, 9, 7))               # 7.5 from the second
    assert [e.units for e in year_end.expire_toil(pot, date(2026, 9, 30))] == [D("-2.50")]
    assert ledger.balance(pot) == D("0")


def test_a_toil_expiry_reversed_by_an_adjustment_stays_reversed(db, hr_admin):
    emp = _toil_employee()
    pot = toil.earn(hr_admin, emp, D("3"), date(2026, 6, 1), "clinic").pot
    year_end.expire_toil(pot, date(2026, 8, 31))
    ledger.write(pot, K.ADJUSTMENT, D("3"), hr_admin, note="expiry reversed")
    assert year_end.expire_toil(pot, date(2026, 9, 1)) == []
    assert ledger.balance(pot) == D("3")


# --- run, nightly, command ----------------------------------------------------------

def test_run_and_command(db, capsys):
    emp = hours_employee(start=date(2025, 4, 1))
    _pot_2026(emp)
    result = year_end.run(date(2027, 4, 1))
    assert result["closed"] == 1 and result["expired_total"] == D("210.00") and result["failed"] == []
    from django.core.management import call_command
    call_command("absence_year_end", today="2027-04-02")
    out = capsys.readouterr().out
    assert "'closed': 0" in out and "'failed': []" in out


def test_run_expires_carry_in_and_toil_on_open_pots(db, hr_admin):
    emp = _toil_employee()
    Policy.objects.filter(absence_type__code="AL").update(
        carry_over_max_weeks=D("1"), carry_over_expires_after_days=90)
    toil.earn(hr_admin, emp, D("3"), date(2027, 5, 1), "clinic")
    year_end.close(pots.for_day(emp, absence_type("AL"), date(2026, 6, 1)))
    result = year_end.run(date(2027, 7, 31))
    assert result["closed"] == 0                                    # the 2026/27 pot was closed above
    assert result["carry_in_expired"] == 1 and result["toil_expired"] == 1
    assert year_end.run(date(2027, 7, 31))["carry_in_expired"] == 0


def _no_policy_next_year():
    """An employee whose contract type's policies end with the 2026/27 year."""
    other = make_contract_type("Other")
    bad = make_employment(start=date(2025, 4, 1))
    make_contract(bad, other)
    make_policy(other, effective_to=date(2027, 3, 31))
    make_pattern(bad)
    return pots.for_day(bad, absence_type("AL"), date(2026, 6, 1))


def test_run_reports_a_pot_it_cannot_close_and_closes_the_rest(db):
    emp = hours_employee(start=date(2025, 4, 1))
    good = _pot_2026(emp)
    bad = _no_policy_next_year()
    result = year_end.run(date(2027, 4, 2))
    assert result["closed"] == 1 and good.entries.filter(kind=K.EXPIRY).exists()
    assert len(result["failed"]) == 1 and str(bad) in result["failed"][0]
    assert not bad.entries.filter(kind=K.EXPIRY).exists()


def test_nightly_runs_the_year_end_and_keeps_its_failures(db):
    emp = hours_employee(start=date(2025, 4, 1))
    _pot_2026(emp)
    bad = _no_policy_next_year()
    result = nightly.run(date(2027, 4, 2))
    assert result["year_end_closed"] == 1
    assert result["carry_in_expired"] == 0 and result["toil_expired"] == 0 and result["leaver_debts"] == []
    assert any(str(bad) in f for f in result["failed"])
    assert nightly.run(date(2027, 4, 2))["year_end_closed"] == 0
