from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

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


def test_a_change_of_unit_inside_one_pot_is_refused(db):
    from people.models import Contract
    emp = make_employment(start=date(2026, 4, 1))
    gp = make_contract_type("Salaried GP", "sessions", D("9"))
    make_policy(gp)
    make_pattern(emp, {d: (D("1"), D("1")) for d in range(4)})
    make_contract(emp, gp, amount=D("8"), to_date=date(2026, 9, 30))
    pot = pots.for_day(emp, absence_type("AL"), Y)                     # a sessions pot
    reception = make_contract_type()
    make_policy(reception)
    # written without the contract signal, so the pot is only computed here
    Contract.objects.bulk_create([Contract(employment=emp, contract_type=reception,
                                           weekly_amount=D("37.5"), from_date=date(2026, 10, 1))])
    with pytest.raises(ValidationError) as e:
        accrual.entitlement(pot)
    assert str(pot) in str(e.value) and "sessions" in str(e.value) and "hours" in str(e.value)


def test_adding_a_contract_in_another_unit_is_refused_while_the_pot_is_open(db, hr_admin):
    from tests.factories import current_leave_year
    start, _ = current_leave_year()
    emp = make_employment(start=start)
    gp = make_contract_type("Salaried GP", "sessions", D("9"))
    make_policy(gp)
    make_contract(emp, gp, amount=D("8"), to_date=start + timedelta(days=182))
    pots.for_day(emp, absence_type("AL"), start)
    reception = make_contract_type()
    make_policy(reception)
    with pytest.raises(ValidationError) as e:
        contracts.add(hr_admin, emp, reception, D("37.5"), start + timedelta(days=183))
    assert "sessions" in str(e.value)
    assert emp.contracts.count() == 1


# Monthly twelfths (Policy.accrual = monthly): the practice's standard contract.
# 22 days = 4.4 weeks; full time 37.5 hours, so a year is 4.4 × 37.5 = 165.00 and a
# month's twelfth 13.75. The leave year is 1 January to 31 December 2026.

def _monthly_policy(ct=None, **kw):
    kw.setdefault("weeks_per_year", D("4.4"))
    return make_policy(ct or make_contract_type(), year_start_month=1, accrual="monthly", **kw)


def _cal(emp, day=date(2026, 6, 1)):
    return pots.for_day(emp, absence_type("AL"), day)


@pytest.mark.parametrize("amount,expected", [
    (D("37.5"), D("165.00")),      # 12 × 165/12
    (D("18.75"), D("82.50")),      # part-timer: 12 × 4.4 × 18.75/12
])
def test_monthly_full_year(db, amount, expected):
    _monthly_policy()
    assert accrual.entitlement(_cal(hours_employee(start=date(2025, 1, 1), amount=amount))) == expected


def test_monthly_starter_counts_their_first_part_month_in_full(db):
    _monthly_policy()
    emp = hours_employee(start=date(2026, 3, 15))
    # March (from the 15th) to December: 10 months × 13.75 = 137.50
    assert accrual.entitlement(_cal(emp, date(2026, 3, 15))) == D("137.50")


def test_monthly_leaver_counts_their_last_part_month_in_full(db):
    _monthly_policy()
    emp = hours_employee(start=date(2025, 1, 1), end_date=date(2026, 9, 3), leaving_reason="resigned")
    # January to September (to the 3rd): 9 months × 13.75 = 123.75
    assert accrual.entitlement(_cal(emp)) == D("123.75")


def test_monthly_hours_change_is_sampled_on_the_last_active_day_of_the_month(db):
    ct = make_contract_type()
    _monthly_policy(ct)
    emp = make_employment(start=date(2025, 1, 1))
    make_contract(emp, ct, amount=D("37.5"), to_date=date(2026, 6, 19))
    make_contract(emp, ct, amount=D("18.75"), start=date(2026, 6, 20))
    make_pattern(emp)
    # January-May at 37.5: 5/12 × 165 = 68.75; June (sampled on 30 June, 18.75) to December:
    # 7/12 × 82.5 = 48.125; 116.875 is exactly half way between steps and rounds half up to
    # 117.00 (the brief's 116.75 would be rounding down)
    assert accrual.entitlement(_cal(emp)) == D("117.00")


def test_monthly_tier_step_counts_from_the_month_it_is_reached(db):
    ct = make_contract_type()
    policy = _monthly_policy(ct)
    PolicyTier.objects.create(policy=policy, after_years=1, extra_weeks=D("0.2"))    # 23 days after 1 year
    emp = hours_employee(start=date(2025, 5, 10))
    # one year's service on 10 May 2026, so May (sampled on 31 May) is at 4.6 weeks:
    # January-April 4 × 4.4 × 37.5/12 = 55.00, May-December 8 × 4.6 × 37.5/12 = 115.00
    assert accrual.entitlement(_cal(emp)) == D("170.00")


def test_monthly_daily_rates_put_each_twelfth_on_the_months_last_active_day(db):
    _monthly_policy()
    emp = hours_employee(start=date(2026, 3, 15), end_date=date(2026, 9, 3), leaving_reason="resigned")
    rates = [(day, rate) for day, rate in accrual.daily_rates(_cal(emp, date(2026, 3, 15))) if rate]
    assert [day for day, _ in rates] == [date(2026, m, 30 if m in (4, 6) else 31) for m in range(3, 9)] \
        + [date(2026, 9, 3)]
    assert {rate for _, rate in rates} == {D("13.75")}
    assert accrual.entitlement(_cal(emp, date(2026, 3, 15))) == D("96.25")       # 7 × 13.75


def test_monthly_anniversary_year_has_twelve_months_from_its_start(db):
    # an anniversary year from 15 March runs in twelve months from its start: 15 Mar-14 Apr,
    # ..., 15 Feb-14 Mar; there all year: 12 × 13.75 = 165.00, each twelfth on a window's last day
    make_policy(make_contract_type(), weeks_per_year=D("4.4"), leave_year_basis="anniversary", accrual="monthly")
    emp = hours_employee(start=date(2025, 3, 15))
    pot = _cal(emp)
    assert (pot.year_start, pot.year_end) == (date(2026, 3, 15), date(2027, 3, 14))
    assert accrual.entitlement(pot) == D("165.00")
    assert [day for day, rate in accrual.daily_rates(pot) if rate] == \
        [date(2026 + (m > 12), (m - 1) % 12 + 1, 14) for m in range(4, 16)]


def test_monthly_fixed_mid_month_year_starter_counts_from_their_window(db):
    # a 15 March year; starting 20 April falls in the second window (15 Apr-14 May), so
    # 11 of the 12: 11 × 13.75 = 151.25
    make_policy(make_contract_type(), weeks_per_year=D("4.4"), year_start_month=3, year_start_day=15,
                accrual="monthly")
    emp = hours_employee(start=date(2026, 4, 20))
    assert accrual.entitlement(_cal(emp, date(2026, 4, 20))) == D("151.25")


def test_monthly_windows_from_the_31st_clip_to_the_end_of_short_months(db):
    # a year from 31 January: windows start 31 Jan, 28 Feb, 31 Mar, 30 Apr, ... (the same day of
    # the month, clipped), so each ends the day before the next starts; twelve, 165.00 in all
    make_policy(make_contract_type(), weeks_per_year=D("4.4"), year_start_month=1, year_start_day=31,
                accrual="monthly")
    emp = hours_employee(start=date(2025, 1, 1))
    pot = _cal(emp)
    assert (pot.year_start, pot.year_end) == (date(2026, 1, 31), date(2027, 1, 30))
    ends = [date(2026, 2, 27), date(2026, 3, 30), date(2026, 4, 29), date(2026, 5, 30), date(2026, 6, 29),
            date(2026, 7, 30), date(2026, 8, 30), date(2026, 9, 29), date(2026, 10, 30), date(2026, 11, 29),
            date(2026, 12, 30), date(2027, 1, 30)]
    assert [day for day, rate in accrual.daily_rates(pot) if rate] == ends
    assert accrual.entitlement(pot) == D("165.00")


def test_a_year_switching_from_daily_to_monthly_takes_each_month_by_its_policy(db):
    ct = make_contract_type()
    make_policy(ct, weeks_per_year=D("4.4"), year_start_month=1, effective_to=date(2026, 6, 30))
    _monthly_policy(ct, effective_from=date(2026, 7, 1))
    emp = hours_employee(start=date(2025, 1, 1))
    # January-June daily: 165 × 181/365 = 81.82; July-December 6 × 13.75 = 82.50; 164.32 → 164.25
    assert accrual.entitlement(_cal(emp)) == D("164.25")


def test_monthly_still_names_a_missing_policy(db):
    ct = make_contract_type()
    _monthly_policy(ct, effective_to=date(2026, 8, 31))
    emp = hours_employee(start=date(2025, 1, 1))
    pot = pots.for_day(emp, absence_type("AL"), date(2026, 6, 1), sync=False)
    with pytest.raises(ValidationError) as e:
        accrual.entitlement(pot)
    assert "No Annual leave policy for Reception on 01 Sep 2026" in str(e.value)


# The bank-holiday pot, exactly from the calendar: one working day (weekly amount ÷ 5) for
# each England and Wales bank holiday in the pot's year on which the person is employed with
# a contract. 2026 (seeded, 0006) has eight: 1 Jan, 3 and 6 Apr, 4 and 25 May, 31 Aug,
# 25 Dec and 28 Dec (Boxing Day substitute).

def _bank_holiday_pot(emp, day=date(2026, 6, 1)):
    return pots.for_day(emp, absence_type("BH"), day)


def _calendar_year_bh(**kw):
    ct = make_contract_type()
    make_policy(ct, year_start_month=1, bank_holiday_handling="pot", **kw)
    make_policy(ct, "BH", weeks_per_year=D("0"), year_start_month=1, bank_holiday_handling="pot", **kw)
    return ct


@pytest.mark.parametrize("amount,expected", [
    (D("37.5"), D("60.00")),      # 8 × 7.5
    (D("18.75"), D("30.00")),     # 8 × 3.75
])
def test_bank_holiday_pot_is_one_working_day_per_holiday(db, amount, expected):
    _calendar_year_bh()
    emp = hours_employee(start=date(2025, 1, 1), amount=amount)
    assert accrual.bank_holiday_entitlement(_bank_holiday_pot(emp)) == expected


def test_bank_holiday_pot_starter_gets_the_holidays_left_in_the_year(db):
    from absence.models import BankHoliday
    _calendar_year_bh()
    emp = hours_employee(start=date(2026, 3, 15))
    assert BankHoliday.objects.filter(date__range=(date(2026, 3, 15), date(2026, 12, 31)), nation="EW").count() == 7
    # 3 Apr onwards: 7 × 7.5 = 52.50
    assert accrual.bank_holiday_entitlement(_bank_holiday_pot(emp, date(2026, 3, 15))) == D("52.50")


def test_bank_holiday_pot_leaver_gets_the_holidays_up_to_their_last_day(db):
    _calendar_year_bh()
    emp = hours_employee(start=date(2025, 1, 1), end_date=date(2026, 9, 3), leaving_reason="resigned")
    # 1 Jan to 31 Aug: 6 × 7.5 = 45.00
    assert accrual.bank_holiday_entitlement(_bank_holiday_pot(emp)) == D("45.00")


def test_bank_holiday_pot_ignores_the_monthly_basis(db):
    _calendar_year_bh(accrual="monthly")
    emp = hours_employee(start=date(2026, 3, 15))
    # still the 7 holidays from 15 March (52.50), not ten monthly twelfths of 60 (50.00)
    assert accrual.bank_holiday_entitlement(_bank_holiday_pot(emp, date(2026, 3, 15))) == D("52.50")


def test_bank_holiday_pot_counts_a_holiday_on_a_day_the_person_does_not_work(db):
    _calendar_year_bh()
    emp = make_employment(start=date(2025, 1, 1))
    make_contract(emp, make_contract_type(), amount=D("30"))
    make_pattern(emp, {d: (D("3.75"), D("3.75")) for d in (1, 2, 3, 4)})      # Tuesday to Friday
    # pro rata to hours, not to the pattern: 8 × 30/5 = 48.00, Mondays included
    assert accrual.bank_holiday_entitlement(_bank_holiday_pot(emp)) == D("48.00")


def test_bank_holiday_pot_april_year_leaver(db):
    # an April-March year, leaving 30 Nov 2026: 3 and 6 Apr, 4 and 25 May, 31 Aug = 5 × 7.5
    # = 37.50 (the old formula, ten holidays ÷ 5 as weeks accrued daily, gave 50.25)
    emp = hours_employee(start=date(2026, 4, 1), end_date=date(2026, 11, 30), leaving_reason="resigned")
    make_policy(emp.contracts.first().contract_type, "BH", bank_holiday_handling="pot")
    assert accrual.bank_holiday_entitlement(_bank_holiday_pot(emp)) == D("37.50")
