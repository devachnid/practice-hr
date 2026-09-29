from datetime import date, time
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from absence.models import Absence, BankHoliday, ClosedDay
from absence.services import costing
from tests.factories import absence_type, hours_employee, make_pattern, make_policy

D = Decimal
MON, TUE, WED = date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3)


def absence(emp, start, end=None, **kw):
    kw.setdefault("absence_type", absence_type("AL"))
    return Absence(employment=emp, start_date=start, end_date=end or start, **kw)


def test_full_days(db):
    a = absence(hours_employee(), MON, WED)
    assert costing.halves_covered(a) == [(MON, "AM"), (MON, "PM"), (TUE, "AM"), (TUE, "PM"),
                                         (WED, "AM"), (WED, "PM")]
    assert costing.cost(a) == D("22.50")


def test_pm_start_am_end(db):
    a = absence(hours_employee(), MON, WED, start_half="PM", end_half="AM")
    assert costing.cost(a) == D("15.00")


def test_weekend_and_no_pattern_cost_zero(db):
    emp = hours_employee(start=date(2026, 4, 1))
    assert costing.cost(absence(emp, date(2026, 6, 6), date(2026, 6, 7))) == D("0.00")
    before_pattern = hours_employee(start=date(2026, 1, 5))
    before_pattern.patterns.all().delete()
    assert costing.cost(absence(before_pattern, date(2026, 6, 1))) == D("0.00")


def test_bank_holiday_closed_not_charged(db):
    BankHoliday.objects.get_or_create(date=MON, nation="EW", defaults={"name": "Test"})
    assert costing.cost(absence(hours_employee(), MON, WED)) == D("15.00")


def test_closed_day_never_charged(db):
    ClosedDay.objects.create(date=TUE, reason="Training")
    assert costing.cost(absence(hours_employee(), MON, WED)) == D("15.00")


def test_partial_day(db):
    emp = hours_employee()
    a = absence(emp, MON, start_time=time(9, 0), end_time=time(10, 30), hours=D("1.5"))
    assert costing.cost(a) == D("1.50")


def test_partial_day_capped_at_halves_touched(db):
    emp = hours_employee()
    make_pattern(emp, {0: (D("3.75"), D("0"))}, effective_from=date(2026, 5, 1))
    a = absence(emp, MON, start_time=time(9, 0), end_time=time(13, 0), hours=D("4"))
    assert costing.cost(a) == D("3.75")
    b = absence(emp, MON, start_time=time(9, 0), end_time=time(14, 0), hours=D("5"))
    assert costing.cost(b) == D("3.75")


def test_midday_boundary_with_a_working_afternoon(db):
    emp = hours_employee()                                    # 3.75 / 3.75
    four = absence(emp, MON, start_time=time(9, 0), end_time=time(13, 0), hours=D("4"))
    assert costing.cost(four) == D("3.75")                    # ends at 13:00: AM only
    both = absence(emp, MON, start_time=time(9, 0), end_time=time(13, 1), hours=D("7"))
    assert costing.cost(both) == D("7.00")                    # touches PM: cap 7.5
    afternoon = absence(emp, MON, start_time=time(13, 0), end_time=time(17, 0), hours=D("4"))
    assert costing.cost(afternoon) == D("3.75")               # starts at 13:00: PM only


def test_type_without_a_policy_rounds_to_quarter_and_skips_bank_holidays(db):
    BankHoliday.objects.get_or_create(date=MON, nation="EW", defaults={"name": "Test"})
    emp = hours_employee()
    a = absence(emp, MON, WED, absence_type=absence_type("COMP"))   # no policy for compassionate
    assert costing.cost(a) == D("15.00")
    b = absence(emp, TUE, start_time=time(9, 0), end_time=time(10, 10), hours=D("1.1"),
                absence_type=absence_type("DEP"))
    assert costing.cost(b) == D("1.00")                       # 1.1 rounds to the quarter


def test_single_day_half_markers(db):
    emp = hours_employee()
    assert costing.halves_covered(absence(emp, MON, start_half="PM")) == [(MON, "PM")]
    assert costing.halves_covered(absence(emp, MON, end_half="AM")) == [(MON, "AM")]
    assert costing.cost(absence(emp, MON, start_half="PM")) == D("3.75")


def test_pot_backed_type_with_no_policy_is_an_error_not_a_zero(db):
    emp = hours_employee()
    emp.contracts.first().contract_type.policies.all().delete()
    with pytest.raises(ValidationError) as e:
        costing.cost(absence(emp, MON, WED))
    assert "No Annual leave policy for Reception" in str(e.value)


def test_automatic_bank_holiday_is_charged_whatever_its_own_policy_handling_says(db):
    BankHoliday.objects.get_or_create(date=MON, nation="EW", defaults={"name": "Test"})
    emp = hours_employee()
    make_policy(emp.contracts.first().contract_type, "BH")        # handling left at "closed"
    auto = absence(emp, MON, absence_type=absence_type("BH"), auto_bank_holiday=True)
    assert costing.cost(auto) == D("7.50")
    assert costing.cost(absence(emp, MON, WED)) == D("15.00")     # an ordinary booking skips it
