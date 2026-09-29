from datetime import date
from decimal import Decimal

from absence.services import leave_year, rounding
from tests.factories import make_contract_type, make_employment, make_policy


def test_fixed_year_from_first_april(db):
    p = make_policy(make_contract_type())
    emp = make_employment(start=date(2020, 1, 1))
    assert leave_year.bounds(p, emp, date(2026, 3, 31)) == (date(2025, 4, 1), date(2026, 3, 31))
    assert leave_year.bounds(p, emp, date(2026, 4, 1)) == (date(2026, 4, 1), date(2027, 3, 31))


def test_anniversary_year(db):
    p = make_policy(make_contract_type(), leave_year_basis="anniversary")
    emp = make_employment(start=date(2025, 7, 14))
    assert leave_year.bounds(p, emp, date(2026, 7, 13)) == (date(2025, 7, 14), date(2026, 7, 13))
    assert leave_year.bounds(p, emp, date(2026, 7, 14)) == (date(2026, 7, 14), date(2027, 7, 13))


def test_anniversary_on_29_feb(db):
    p = make_policy(make_contract_type(), leave_year_basis="anniversary")
    emp = make_employment(start=date(2024, 2, 29))
    assert leave_year.bounds(p, emp, date(2025, 6, 1)) == (date(2025, 2, 28), date(2026, 2, 27))


def test_round_to():
    assert rounding.round_to(Decimal("104.712"), Decimal("0.25")) == Decimal("104.75")
    assert rounding.round_to(Decimal("184.109"), Decimal("0.25")) == Decimal("184.00")
    assert rounding.round_to(Decimal("47.75"), Decimal("0.5")) == Decimal("48.0")
    assert rounding.round_to(Decimal("47.74"), Decimal("0.5")) == Decimal("47.5")
