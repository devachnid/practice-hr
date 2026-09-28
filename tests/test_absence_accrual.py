from datetime import date
from decimal import Decimal

import pytest

from absence.models import PolicyTier
from absence.services import accrual, pots
from people.services import contracts
from tests.factories import (absence_type, hours_employee, make_contract, make_contract_type,
                             make_employment, make_pattern, make_policy)

D = Decimal
Y = date(2026, 6, 1)   # any day in the 2026/27 fixed year


def al(emp):
    return pots.for_day(emp, absence_type("AL"), Y)


@pytest.mark.parametrize("amount,expected", [
    (D("37.5"), D("210.00")),      # full-timer: 5.6 weeks × 37.5
    (D("18.75"), D("105.00")),     # part-timer
])
def test_full_year(db, amount, expected):
    assert accrual.entitlement(al(hours_employee(amount=amount))) == expected


def test_mid_year_starter(db):
    emp = hours_employee(start=date(2026, 10, 1))
    pot = pots.for_day(emp, absence_type("AL"), date(2026, 10, 1))   # no contract on Y itself
    assert accrual.entitlement(pot) == D("104.75")      # 210 × 182/365 = 104.71


def test_mid_year_leaver(db):
    emp = hours_employee(end_date=date(2026, 9, 30), leaving_reason="resigned")
    assert accrual.entitlement(al(emp)) == D("105.25")      # 210 × 183/365 = 105.29


def test_tier_step_in_month_seven(db):
    emp = hours_employee(continuous_service_date=date(2021, 10, 1))
    policy = emp.contracts.first().contract_type.policies.get()
    PolicyTier.objects.create(policy=policy, after_years=5, extra_weeks=D("1"))
    # 183 days at 5.6 weeks, 182 at 6.6: 37.5 × (5.6×183 + 6.6×182) / 365 = 228.70
    assert accrual.entitlement(al(emp)) == D("228.75")


def test_fixed_term_ending_month_nine(db, hr_admin):
    emp = hours_employee(amount=D("18.75"))
    ct = make_contract_type()
    contracts.add(hr_admin, emp, ct, D("18.75"), date(2026, 4, 1), basis="fixed_term",
                  to_date=date(2026, 12, 31))
    # 275 days at 37.5, 90 at 18.75: 5.6 × (37.5×275 + 18.75×90) / 365 = 184.11
    assert accrual.entitlement(al(emp)) == D("184.00")


def test_sessions_unit(db):
    emp = make_employment(start=date(2026, 4, 1))
    ct = make_contract_type("Salaried GP", "sessions", D("9"))
    make_contract(emp, ct, amount=D("8"))
    make_policy(ct, weeks_per_year=D("6"))
    make_pattern(emp, {d: (D("1"), D("1")) for d in range(4)})
    assert accrual.entitlement(al(emp)) == D("48.0")


def test_leap_year_same_as_common(db):
    emp = hours_employee(start=date(2023, 4, 1))
    pot_leap = pots.for_day(emp, absence_type("AL"), date(2024, 2, 29))   # 2023/24 has 366 days
    pot_common = pots.for_day(emp, absence_type("AL"), date(2025, 6, 1))
    assert accrual.entitlement(pot_leap) == accrual.entitlement(pot_common) == D("210.00")


def test_bank_holiday_pot_pro_rata(db):
    emp = hours_employee(amount=D("18.75"))
    policy = emp.contracts.first().contract_type.policies.get()
    make_policy(policy.contract_type, "BH", bank_holiday_handling="pot")
    pot = pots.for_day(emp, absence_type("BH"), Y)
    # 10 bank holidays fall in 2026/27 (both Easters) → 10/5 weeks × 18.75 = 37.5
    assert accrual.bank_holiday_entitlement(pot) == D("37.50")


def test_entitlement_reads_its_rows_once_not_per_day(db, django_assert_max_num_queries):
    from absence.models import Pot
    emp = hours_employee(continuous_service_date=date(2021, 10, 1))
    policy = emp.contracts.first().contract_type.policies.get()
    PolicyTier.objects.create(policy=policy, after_years=5, extra_weeks=D("1"))
    make_policy(policy.contract_type, "BH", bank_holiday_handling="pot")
    al_pot = Pot.objects.get(pk=al(emp).pk)
    bh_pot = Pot.objects.get(pk=pots.for_day(emp, absence_type("BH"), Y).pk)
    with django_assert_max_num_queries(30):
        assert accrual.entitlement(al_pot) == D("228.75")
    with django_assert_max_num_queries(30):
        assert accrual.bank_holiday_entitlement(bh_pot) == D("75.00")

