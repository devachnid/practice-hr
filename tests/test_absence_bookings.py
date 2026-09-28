from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from absence.models import Absence, LedgerEntry
from absence.services import balances, bookings, ledger, pots
from tests.factories import absence_type, hours_employee, make_pattern

D = Decimal
MON, WED = date(2026, 6, 1), date(2026, 6, 3)


def test_request_then_approve_writes_booking(db, hr_admin, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    assert a.status == Absence.Status.REQUESTED and a.cost_units == D("22.50")
    pot = pots.for_day(emp, absence_type("AL"), MON)
    assert pot.entries.count() == 0
    bookings.approve(hr_admin, a, "fine")
    a.refresh_from_db()
    assert a.status == Absence.Status.APPROVED and a.decided_by == hr_admin
    line = pot.entries.get(kind=LedgerEntry.Kind.BOOKING)
    assert line.units == D("-22.50") and line.absence == a


def test_decline_writes_nothing(db, hr_admin, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("AL"), MON)
    bookings.decline(hr_admin, a, "short staffed")
    assert Absence.objects.get(pk=a.pk).status == Absence.Status.DECLINED
    assert LedgerEntry.objects.count() == 0


def test_cancel_restores_exactly(db, hr_admin, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    bookings.approve(hr_admin, a)
    pot = pots.for_day(emp, absence_type("AL"), MON)
    before = ledger.balance(pot)
    bookings.cancel(employee_user, a)
    assert ledger.balance(pot) == before + D("22.50")
    assert Absence.objects.get(pk=a.pk).status == Absence.Status.CANCELLED


def test_overlap_refused(db, employee_user):
    emp = hours_employee()
    bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    with pytest.raises(ValidationError):
        bookings.request(employee_user, emp, absence_type("AL"), WED)


def test_partial_only_for_hours_unit(db, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("DEP"), MON,
                         start_time=time(9, 0), end_time=time(10, 30), hours=D("1.5"))
    assert a.status == Absence.Status.APPROVED and a.cost_units == D("1.50")
    from tests.factories import make_contract, make_contract_type, make_employee, make_employment
    gp = make_employment(employee=make_employee(first="Gee"))
    make_contract(gp, make_contract_type("Salaried GP", "sessions", D("9")), amount=D("8"))
    make_pattern(gp, {d: (D("1"), D("1")) for d in range(4)})
    with pytest.raises(ValidationError):
        bookings.request(employee_user, gp, absence_type("DEP"), MON,
                         start_time=time(9, 0), end_time=time(10, 30), hours=D("1.5"))


def test_crossing_leave_year_refused(db, employee_user):
    emp = hours_employee()
    with pytest.raises(ValidationError) as e:
        bookings.request(employee_user, emp, absence_type("AL"), date(2027, 3, 29), date(2027, 4, 2))
    assert "two leave years" in str(e.value)


def test_sickness_needs_no_approval_and_no_pot(db, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("SICK"), MON, WED, category="illness")
    assert a.status == Absence.Status.APPROVED and a.self_certified
    assert LedgerEntry.objects.count() == 0


def test_sickness_over_seven_days_not_self_certified(db, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("SICK"), MON, date(2026, 6, 10), category="illness")
    assert not a.self_certified


def test_negative_balance_allowed_but_reported(db, hr_admin, employee_user):
    emp = hours_employee(amount=D("7.5"))          # 42 hours a year
    make_pattern(emp, {0: (D("3.75"), D("3.75"))}, effective_from=date(2026, 4, 2))
    pot = pots.for_day(emp, absence_type("AL"), MON)
    ledger.sync_entitlement(pot)
    for week in range(7):
        a = bookings.request(employee_user, emp, absence_type("AL"), MON + timedelta(weeks=week))
        bookings.approve(hr_admin, a)
    s = balances.summary(pot, date(2026, 6, 20))
    assert s["remaining"] == D("-10.50")
    assert s["taken"] == D("22.50") and s["booked"] == D("30.00")


def test_summary_keys(db, employee_user):
    emp = hours_employee()
    pot = pots.for_day(emp, absence_type("AL"), MON)
    ledger.sync_entitlement(pot)
    bookings.request(employee_user, emp, absence_type("AL"), MON)
    s = balances.summary(pot, MON)
    assert s == {"entitlement": D("210.00"), "carried_in": D("0"), "taken": D("0"), "booked": D("0"),
                 "pending": D("7.50"), "expired": D("0"), "adjustments": D("0"), "remaining": D("210.00")}
