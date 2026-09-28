from datetime import date, time
from decimal import Decimal

from absence.models import Absence, BankHoliday, ClosedDay
from absence.services import costing
from tests.factories import absence_type, hours_employee, make_pattern

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
