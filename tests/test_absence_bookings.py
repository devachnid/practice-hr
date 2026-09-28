from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from absence.models import Absence, LedgerEntry, Pot
from people.models import AuditEntry
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


def _approved_mon_to_wed(hr_admin, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    bookings.approve(hr_admin, a)
    return emp, a


def test_recost_writes_one_adjustment_for_the_difference(db, hr_admin, employee_user):
    emp, a = _approved_mon_to_wed(hr_admin, employee_user)
    pot = pots.for_day(emp, absence_type("AL"), MON)
    make_pattern(emp, {0: (D("3.75"), D("3.75"))}, effective_from=date(2026, 4, 2))   # Mon only
    line = bookings.recost(hr_admin, a, "pattern changed")
    assert line.kind == LedgerEntry.Kind.ADJUSTMENT and line.units == D("15.00")   # 22.50 - 7.50
    assert pot.entries.filter(kind=LedgerEntry.Kind.ADJUSTMENT).count() == 1
    assert a.cost_units == D("7.50") and Absence.objects.get(pk=a.pk).cost_units == D("7.50")
    assert AuditEntry.objects.filter(object_id=a.pk, field="cost_units", before="22.50", after="7.50").exists()


def test_recost_with_no_change_writes_nothing(db, hr_admin, employee_user):
    emp, a = _approved_mon_to_wed(hr_admin, employee_user)
    count = LedgerEntry.objects.count()
    assert bookings.recost(hr_admin, a, "checked") is None
    assert LedgerEntry.objects.count() == count
    assert not LedgerEntry.objects.filter(kind=LedgerEntry.Kind.ADJUSTMENT).exists()


def test_cancel_after_recost_restores_starting_balance(db, hr_admin, employee_user):
    emp = hours_employee()
    pot = pots.for_day(emp, absence_type("AL"), MON)
    ledger.sync_entitlement(pot)
    start = ledger.balance(pot)
    a = bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    bookings.approve(hr_admin, a)
    make_pattern(emp, {0: (D("3.75"), D("3.75"))}, effective_from=date(2026, 4, 2))
    bookings.recost(hr_admin, a, "pattern changed")
    bookings.cancel(employee_user, a)
    assert ledger.balance(pot) == start


def test_recost_refused_unless_approved_and_pot_backed(db, hr_admin, employee_user):
    emp = hours_employee()
    requested = bookings.request(employee_user, emp, absence_type("AL"), MON)
    with pytest.raises(ValidationError):
        bookings.recost(hr_admin, requested, "no")
    sick = bookings.request(employee_user, emp, absence_type("SICK"), date(2026, 6, 8), category="illness")
    assert sick.status == Absence.Status.APPROVED
    with pytest.raises(ValidationError):
        bookings.recost(hr_admin, sick, "no")


def test_stale_second_approve_is_refused(db, hr_admin, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    stale = Absence.objects.get(pk=a.pk)
    bookings.approve(hr_admin, a)
    assert stale.status == Absence.Status.REQUESTED
    with pytest.raises(ValidationError):
        bookings.approve(hr_admin, stale)
    assert LedgerEntry.objects.filter(kind=LedgerEntry.Kind.BOOKING).count() == 1


def test_approve_refuses_a_second_ordinary_booking_over_the_same_days(db, hr_admin, employee_user):
    emp = hours_employee()
    first = bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    bookings.approve(hr_admin, first)
    # a row written before the first existed (say, from an import) and approved afterwards
    second = Absence.objects.create(employment=emp, absence_type=absence_type("AL"), start_date=WED,
                                    end_date=WED, cost_units=D("7.50"))
    with pytest.raises(ValidationError) as e:
        bookings.approve(hr_admin, second)
    assert "overlaps" in str(e.value)
    assert Absence.objects.get(pk=second.pk).status == Absence.Status.REQUESTED


def test_ordinary_bookings_and_automatic_bank_holidays_do_not_clash(db, employee_user):
    emp = hours_employee()
    auto = Absence.objects.create(employment=emp, absence_type=absence_type("BH"), start_date=MON,
                                  end_date=MON, status=Absence.Status.APPROVED, auto_bank_holiday=True)
    assert not bookings.overlaps(emp, MON, WED)
    assert bookings.overlaps(emp, MON, MON, auto=True)
    assert not bookings.overlaps(emp, MON, MON, auto=True, exclude_pk=auto.pk)
    bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    assert bookings.overlaps(emp, WED, WED)
    assert not bookings.overlaps(emp, WED, WED, auto=True)


def test_a_leavers_future_leave_is_cancelled_on_the_pot_it_was_booked_to(db, hr_admin):
    from people.services import contracts, employments
    emp = hours_employee()
    leave = bookings.approve(hr_admin, bookings.request(hr_admin, emp, absence_type("AL"),
                                                        date(2026, 12, 14), date(2026, 12, 16)))
    booking = leave.ledger_entries.get(kind=LedgerEntry.Kind.BOOKING)
    contracts.end(hr_admin, emp.contracts.get(), date(2026, 11, 30))
    employments.end(hr_admin, emp, date(2026, 11, 30), "resigned")
    bookings.cancel(hr_admin, leave)       # no contract on 14 Dec any more: must not matter
    line = leave.ledger_entries.get(kind=LedgerEntry.Kind.CANCELLATION)
    assert line.pot == booking.pot and line.units == D("22.50")
    assert Absence.objects.get(pk=leave.pk).status == Absence.Status.CANCELLED


def test_recost_and_cancel_stay_on_the_booked_pot_after_the_leave_year_changes(db, hr_admin):
    emp = hours_employee(start=date(2025, 10, 1))
    leave = bookings.approve(hr_admin, bookings.request(hr_admin, emp, absence_type("AL"), MON, WED))
    booked_pot = leave.ledger_entries.get().pot
    assert booked_pot.year_start == date(2026, 4, 1)
    # the policy moves to anniversary years: today's resolution of 1 June is the 2025/26 pot
    emp.contracts.first().contract_type.policies.update(leave_year_basis="anniversary")
    make_pattern(emp, {0: (D("3.75"), D("3.75"))}, effective_from=date(2026, 5, 1))   # Mon only
    pots_before = set(Pot.objects.values_list("pk", flat=True))
    line = bookings.recost(hr_admin, leave, "pattern changed")
    assert line.pot == booked_pot and line.units == D("15.00")
    bookings.cancel(hr_admin, leave)
    cancellation = leave.ledger_entries.get(kind=LedgerEntry.Kind.CANCELLATION)
    assert cancellation.pot == booked_pot and cancellation.units == D("7.50")
    assert set(Pot.objects.values_list("pk", flat=True)) == pots_before   # nothing re-resolved
