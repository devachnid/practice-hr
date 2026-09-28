from datetime import date
from decimal import Decimal

from people.services import contracts, patterns
from tests.factories import make_contract, make_employment

D = Decimal


def test_set_pattern_and_units_on(hr_admin):
    emp = make_employment(start=date(2026, 4, 6))
    pattern, warning = patterns.set_pattern(
        hr_admin, emp, date(2026, 4, 6), {0: (D("3.75"), D("3.75")), 2: (D("4"), D("0"))})
    assert warning is None or "contracted" in warning
    assert patterns.units_on(emp, date(2026, 4, 6), "AM") == D("3.75")   # Monday
    assert patterns.units_on(emp, date(2026, 4, 8), "PM") == D("0")      # Wednesday
    assert patterns.units_on(emp, date(2026, 4, 7), "AM") == D("0")      # Tuesday, absent from dict
    assert patterns.weekly_total(pattern) == D("11.5")


def test_latest_version_on_or_before_wins(hr_admin):
    emp = make_employment(start=date(2026, 1, 5))
    patterns.set_pattern(hr_admin, emp, date(2026, 1, 5), {0: (D("1"), D("1"))})
    patterns.set_pattern(hr_admin, emp, date(2026, 6, 1), {0: (D("1"), D("0"))})
    assert patterns.units_on(emp, date(2026, 5, 25), "PM") == D("1")
    assert patterns.units_on(emp, date(2026, 6, 1), "PM") == D("0")
    assert patterns.pattern_on(emp, date(2025, 12, 1)) is None


def test_total_differs_from_contract_warns_but_saves(hr_admin):
    emp = make_employment(start=date(2026, 4, 6))
    make_contract(emp, amount=D("20"))
    pattern, warning = patterns.set_pattern(hr_admin, emp, date(2026, 4, 6), {0: (D("3"), D("3"))})
    assert pattern.pk
    assert warning == "Pattern totals 6 a week; contracts total 20."


def test_same_effective_from_replaces_days(hr_admin):
    emp = make_employment(start=date(2026, 4, 6))
    patterns.set_pattern(hr_admin, emp, date(2026, 4, 6), {0: (D("1"), D("1"))})
    pattern, _ = patterns.set_pattern(hr_admin, emp, date(2026, 4, 6), {1: (D("1"), D("1"))})
    assert pattern.days.count() == 7
    assert patterns.units_on(emp, date(2026, 4, 6), "AM") == D("0")
    assert patterns.units_on(emp, date(2026, 4, 7), "AM") == D("1")
    assert contracts.unit(emp, date(2026, 4, 6)) is None


def test_zero_hours_contract_still_warns(hr_admin):
    emp = make_employment(start=date(2026, 4, 6))
    make_contract(emp, amount=D("0"))
    _, warning = patterns.set_pattern(hr_admin, emp, date(2026, 4, 6), {0: (D("3"), D("0"))})
    assert warning == "Pattern totals 3 a week; contracts total 0."


def test_no_contract_does_not_warn(hr_admin):
    emp = make_employment(start=date(2026, 4, 6))
    _, warning = patterns.set_pattern(hr_admin, emp, date(2026, 4, 6), {0: (D("3"), D("0"))})
    assert warning is None
