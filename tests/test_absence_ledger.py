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
