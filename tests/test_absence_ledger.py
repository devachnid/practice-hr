from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from absence.models import BankHoliday, LedgerEntry, Pot
from absence.services import ledger, pots
from tests.factories import absence_type, hours_employee, make_employment


def test_seeded_bank_holidays(db):
    assert BankHoliday.objects.filter(date=date(2026, 12, 28), nation="EW").exists()
    assert BankHoliday.objects.filter(date=date(2027, 3, 26)).exists()


def test_for_day_creates_once_with_unit(db):
    emp = hours_employee()
    pot = pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    again = pots.for_day(emp, absence_type("AL"), date(2027, 3, 31))
    assert pot == again
    assert (pot.year_start, pot.year_end, pot.unit) == (date(2026, 4, 1), date(2027, 3, 31), "hours")
    assert Pot.objects.count() == 1


def test_for_day_needs_a_contract(db):
    emp = make_employment()
    with pytest.raises(ValidationError):
        pots.for_day(emp, absence_type("AL"), emp.start_date)


def test_write_and_balance(db, hr_admin):
    pot = pots.for_day(hours_employee(), absence_type("AL"), date(2026, 6, 1), sync=False)
    ledger.write(pot, LedgerEntry.Kind.ENTITLEMENT, Decimal("210"), hr_admin, note="year")
    ledger.write(pot, LedgerEntry.Kind.BOOKING, Decimal("-7.5"))
    assert ledger.balance(pot) == Decimal("202.5")
    assert pot.entries.count() == 2


def test_ledger_rows_are_immutable(db):
    pot = pots.for_day(hours_employee(), absence_type("AL"), date(2026, 6, 1))
    row = ledger.write(pot, LedgerEntry.Kind.ENTITLEMENT, Decimal("1"))
    row.units = Decimal("2")
    with pytest.raises(ValidationError):
        row.save()
    with pytest.raises(ValidationError):
        row.delete()


def test_open_pots(db):
    emp = hours_employee(start=date(2025, 4, 1))
    pots.for_day(emp, absence_type("AL"), date(2025, 6, 1))
    current = pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    assert list(pots.open_pots(date(2026, 6, 1))) == [current]


def test_lookup_finds_an_open_pot_and_never_creates_one(db):
    emp = hours_employee()
    al = absence_type("AL")
    assert pots.lookup(emp, al, date(2026, 6, 1)) is None
    assert not Pot.objects.exists()
    pot = pots.for_day(emp, al, date(2026, 6, 1))
    assert pots.lookup(emp, al, date(2027, 3, 31)) == pot          # the same leave year
    assert pots.lookup(emp, al, date(2027, 4, 1)) is None          # the next is not open
    assert Pot.objects.count() == 1


def test_lookup_names_a_missing_policy(db):
    emp = hours_employee()
    emp.contracts.first().contract_type.policies.all().delete()
    with pytest.raises(ValidationError, match="No Annual leave policy"):
        pots.lookup(emp, absence_type("AL"), date(2026, 6, 1))


def test_balance_rows_read_open_pots_only(db):
    from absence.services import balances
    emp = hours_employee()
    today = date(2026, 6, 1)
    rows = {r["type"].code: r for r in balances.rows(emp, today)}
    assert "BH" not in rows and rows["AL"]["pot"] is None and rows["AL"]["summary"] is None
    assert "STUDY" not in rows                       # no policy: not for an employee to see
    with_gaps = {r["type"].code: r for r in balances.rows(emp, today, show_setup_gaps=True)}
    assert "No Study leave policy" in with_gaps["STUDY"]["error"]
    assert not Pot.objects.exists()
    pot = pots.for_day(emp, absence_type("AL"), today)
    rows = {r["type"].code: r for r in balances.rows(emp, today, include_bh=True, show_setup_gaps=True)}
    assert "BH" in rows
    assert rows["AL"]["pot"] == pot and rows["AL"]["summary"]["remaining"] == Decimal("210.00")
