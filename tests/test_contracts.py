from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from people.services import contracts
from tests.factories import make_contract_type, make_employment


def test_sum_of_concurrent_contracts(hr_admin):
    emp = make_employment(start=date(2026, 4, 1))
    ct = make_contract_type()
    contracts.add(hr_admin, emp, ct, Decimal("18.75"), date(2026, 4, 1))
    contracts.add(hr_admin, emp, ct, Decimal("18.75"), date(2026, 4, 1),
                  basis="fixed_term", to_date=date(2027, 3, 31))
    assert contracts.contracted_amount(emp, date(2026, 10, 1)) == Decimal("37.5")
    assert contracts.contracted_amount(emp, date(2027, 4, 1)) == Decimal("18.75")
    assert contracts.fte(emp, date(2026, 10, 1)) == Decimal("1")
    assert contracts.fte(emp, date(2027, 4, 1)) == Decimal("0.5")


def test_touching_contracts_do_not_clash(hr_admin):
    emp = make_employment(start=date(2026, 1, 1))
    ct = make_contract_type()
    a = contracts.add(hr_admin, emp, ct, Decimal("30"), date(2026, 1, 1), to_date=date(2026, 3, 31))
    contracts.add(hr_admin, emp, ct, Decimal("20"), date(2026, 4, 1))
    assert contracts.contracted_amount(emp, date(2026, 3, 31)) == Decimal("30")
    assert contracts.contracted_amount(emp, date(2026, 4, 1)) == Decimal("20")
    assert a.to_date == date(2026, 3, 31)


def test_mixed_units_refused(hr_admin):
    emp = make_employment()
    hours = make_contract_type()
    sessions = make_contract_type("Salaried GP", "sessions", Decimal("9"))
    contracts.add(hr_admin, emp, hours, Decimal("15"), emp.start_date)
    with pytest.raises(ValidationError):
        contracts.add(hr_admin, emp, sessions, Decimal("2"), emp.start_date)


def test_fixed_term_needs_end(hr_admin):
    emp = make_employment()
    with pytest.raises(ValidationError):
        contracts.add(hr_admin, emp, make_contract_type(), Decimal("10"), emp.start_date, basis="fixed_term")


def test_unit_and_zero_when_no_contract(db):
    emp = make_employment()
    assert contracts.unit(emp, emp.start_date) is None
    assert contracts.contracted_amount(emp, emp.start_date) == Decimal("0")
    assert contracts.fte(emp, emp.start_date) == Decimal("0")


def test_contract_outside_employment_refused(hr_admin):
    emp = make_employment(start=date(2026, 4, 6))
    with pytest.raises(ValidationError):
        contracts.add(hr_admin, emp, make_contract_type(), Decimal("10"), date(2026, 4, 1))
