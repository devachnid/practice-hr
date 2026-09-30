from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest import mock

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from absence.models import AbsenceType, LedgerEntry, Policy
from absence.services import bookings, ledger, nightly, pots, toil, year_end
from people.models import AuditEntry
from tests.factories import (absence_type, current_leave_year, hours_employee, make_contract, make_contract_type,
                             make_employment, make_pattern, make_policy)

D = Decimal
K = LedgerEntry.Kind
JUNE_MON = date(2026, 6, 1)     # a Monday with no bank holiday for seven weeks after it


def _pot_2026(emp):
    pot = pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    ledger.sync_entitlement(pot)
    return pot


def _next_pot(emp):
    return pots.for_day(emp, absence_type("AL"), date(2027, 4, 1))


def _toil_employee(days=90):
    """An hours employee whose TOIL expires `days` after the day it is earned
    (the type's own setting: TOIL has no policy)."""
    emp = hours_employee()
    AbsenceType.objects.filter(code="TOIL").update(earned_expires_after_days=days)
    return emp


@contextmanager
def _booked_on(day):
    """Ledger lines written inside are stamped (created_at) at noon on `day`."""
    moment = timezone.make_aware(datetime.combine(day, time(12)))
    with mock.patch("django.utils.timezone.now", return_value=moment):
        yield


def _book(hr_admin, employee_user, emp, code, day, booked_on):
    with _booked_on(booked_on):
        return bookings.approve(hr_admin, bookings.request(employee_user, emp, absence_type(code), day))


def _take_toil(hr_admin, employee_user, emp, day, booked_on):
    return _book(hr_admin, employee_user, emp, "TOIL", day, booked_on)


# --- close ------------------------------------------------------------------

def test_close_carries_up_to_cap_and_expires_rest(db):
    emp = hours_employee(start=date(2025, 4, 1))
    Policy.objects.update(carry_over_max_weeks=D("1"))           # 37.5 hours
    pot = _pot_2026(emp)                                          # 210, nothing taken
    result = year_end.close(pot)
    assert result == {"carried": D("37.50"), "expired": D("172.50")}
    nxt = _next_pot(emp)
    carry = nxt.entries.get(kind=K.CARRY_IN)
    assert carry.units == D("37.50") and carry.note == "year end: carried in from 2026/27"
    expiry = pot.entries.get(kind=K.EXPIRY)                        # R10: one line for the whole remaining
    assert expiry.units == D("-210.00") and expiry.date == date(2027, 3, 31)
    assert expiry.note == "year end close: 37.50 carried to 2027-04-01, 172.50 expired"
    assert ledger.balance(pot) == D("0")
    assert ledger.balance(nxt) == D("247.50")                      # opened synced: 210 + 37.50


def test_close_twice_is_a_no_op(db):
    emp = hours_employee(start=date(2025, 4, 1))
    Policy.objects.update(carry_over_max_weeks=D("1"))
    pot = _pot_2026(emp)
    year_end.close(pot)
    assert year_end.close(pot) == {"carried": D("0"), "expired": D("0"), "skipped": True}
    nxt = _next_pot(emp)
    assert pot.entries.filter(kind=K.EXPIRY).count() == 1
    assert nxt.entries.filter(kind=K.CARRY_IN).count() == 1
    year_end.run(date(2027, 4, 2))
    year_end.run(date(2027, 4, 2))
    assert pot.entries.filter(kind=K.EXPIRY).count() == 1
    assert nxt.entries.filter(kind=K.CARRY_IN).count() == 1


def test_the_next_pots_carry_in_does_not_mark_it_closed(db):
    emp = hours_employee(start=date(2025, 4, 1))
    Policy.objects.update(carry_over_max_weeks=D("1"))
    year_end.close(_pot_2026(emp))
    nxt = _next_pot(emp)
    result = year_end.close(nxt)
    assert "skipped" not in result and result["carried"] == D("37.50")


def test_no_cap_means_no_carry(db):
    emp = hours_employee(start=date(2025, 4, 1))
    pot = _pot_2026(emp)
    assert year_end.close(pot) == {"carried": D("0"), "expired": D("210.00")}
    assert ledger.balance(pot) == D("0")
    assert not LedgerEntry.objects.filter(kind=K.CARRY_IN).exists()


def test_a_zero_balance_still_marks_the_pot_closed(db):
    emp = hours_employee(start=date(2025, 4, 1))
    pot = _pot_2026(emp)
    ledger.write(pot, K.ADJUSTMENT, D("-210"), note="all used elsewhere")
    assert year_end.close(pot) == {"carried": D("0"), "expired": D("0")}
    assert pot.entries.get(kind=K.EXPIRY).units == D("0")
    assert year_end.close(pot)["skipped"] is True


def test_close_resyncs_the_old_year_first(db):
    emp = hours_employee(start=date(2025, 4, 1))
    Policy.objects.update(carry_over_max_weeks=D("10"))                  # a cap of 187.50 hours
    pot = _pot_2026(emp)                                                  # 210
    emp.contracts.update(weekly_amount=D("18.75"))    # recorded after 1 April, behind the signals' back
    assert year_end.close(pot) == {"carried": D("105.00"), "expired": D("0")}
    assert pot.entries.get(kind=K.REVISION, note="year end").units == D("-105.00")
    assert ledger.balance(pot) == D("0")


def test_negative_balance_carries_in_full(db, hr_admin, employee_user):
    emp = hours_employee(start=date(2025, 4, 1), amount=D("7.5"))
    make_pattern(emp, {0: (D("3.75"), D("3.75"))}, effective_from=date(2026, 4, 1))
    pot = _pot_2026(emp)                                          # 42 hours
    for week in range(7):
        a = bookings.request(employee_user, emp, absence_type("AL"), JUNE_MON + timedelta(weeks=week))
        bookings.approve(hr_admin, a)
    assert ledger.balance(pot) == D("-10.50")
    result = year_end.close(pot)
    assert result == {"carried": D("-10.50"), "expired": D("0")}
    nxt = _next_pot(emp)
    assert nxt.entries.get(kind=K.CARRY_IN).units == D("-10.50")
    assert pot.entries.get(kind=K.EXPIRY).units == D("10.50")
    assert ledger.balance(pot) == D("0")


def _leaver(end=date(2027, 3, 31)):
    emp = hours_employee(start=date(2025, 4, 1))
    emp.end_date = end
    emp.save()
    emp.contracts.update(to_date=end)
    return emp


def test_a_leavers_positive_balance_expires(db):
    emp = _leaver()
    Policy.objects.update(carry_over_max_weeks=D("1"))
    pot = _pot_2026(emp)
    assert year_end.close(pot) == {"carried": D("0"), "expired": D("210.00")}
    expiry = pot.entries.get(kind=K.EXPIRY)
    assert expiry.units == D("-210.00") and expiry.note == "year end close: leaver, 210.00 expired"
    assert emp.pots.count() == 1                                  # no next pot opened
    assert year_end.close(pot)["skipped"] is True


def test_a_leavers_negative_balance_is_left_and_reported(db):
    emp = _leaver()
    pot = _pot_2026(emp)
    ledger.write(pot, K.ADJUSTMENT, D("-217.50"), note="over-taken")
    assert year_end.close(pot) == {"carried": D("0"), "expired": D("0"), "leaver_debt": D("-7.50")}
    assert not pot.entries.filter(kind=K.EXPIRY).exists()
    assert ledger.balance(pot) == D("-7.50")
    result = year_end.run(date(2027, 4, 2))
    assert result["closed"] == 0 and len(result["leaver_debts"]) == 1
    assert str(pot) in result["leaver_debts"][0]
    ledger.write(pot, K.ADJUSTMENT, D("7.50"), note="recovered in final pay")
    assert year_end.run(date(2027, 4, 3))["closed"] == 1          # settled: now it closes at zero
    assert pot.entries.get(kind=K.EXPIRY).units == D("0")


def test_an_expiry_is_reversible_by_an_adjustment(db):
    emp = hours_employee(start=date(2025, 4, 1))
    pot = _pot_2026(emp)
    year_end.close(pot)
    ledger.write(pot, K.ADJUSTMENT, D("210"), note="reversed by HR")
    year_end.run(date(2027, 4, 2))
    assert ledger.balance(pot) == D("210")
    assert pot.entries.filter(kind=K.EXPIRY).count() == 1


# --- carry-in expiry ------------------------------------------------------------

def _carried(emp):
    Policy.objects.update(carry_over_max_weeks=D("1"), carry_over_expires_after_days=90)
    year_end.close(_pot_2026(emp))
    return _next_pot(emp)


def test_carry_in_expires_after_days(db):
    emp = hours_employee(start=date(2025, 4, 1))
    nxt = _carried(emp)
    assert year_end.expire_carry_in(nxt, date(2027, 6, 29)) is None
    assert year_end.expire_carry_in(nxt, date(2027, 6, 30)) is None   # the deadline: still usable
    row = year_end.expire_carry_in(nxt, date(2027, 7, 1))
    assert row.kind == K.EXPIRY and row.units == D("-37.50") and row.note == "carry-in expired"
    assert year_end.expire_carry_in(nxt, date(2027, 7, 2)) is None


def test_leave_booked_by_the_deadline_uses_the_carry_in_first(db, hr_admin, employee_user):
    emp = hours_employee(start=date(2025, 4, 1))
    nxt = _carried(emp)                                              # 37.50, deadline 30 Jun 2027
    for day in (date(2027, 6, 7), date(2027, 6, 8)):                # 15 hours taken before the deadline
        _book(hr_admin, employee_user, emp, "AL", day, booked_on=date(2027, 5, 20))
    row = year_end.expire_carry_in(nxt, date(2027, 7, 1))
    assert row.units == D("-22.50")


def test_leave_booked_by_the_deadline_for_after_it_still_uses_the_carry_in(db, hr_admin, employee_user):
    emp = hours_employee(start=date(2025, 4, 1))
    nxt = _carried(emp)
    _book(hr_admin, employee_user, emp, "AL", date(2027, 7, 5), booked_on=date(2027, 6, 30))
    row = year_end.expire_carry_in(nxt, date(2027, 7, 1))
    assert row.units == D("-30.00")


def test_leave_booked_after_the_deadline_does_not_use_the_carry_in(db, hr_admin, employee_user):
    emp = hours_employee(start=date(2025, 4, 1))
    nxt = _carried(emp)
    _book(hr_admin, employee_user, emp, "AL", date(2027, 6, 28), booked_on=date(2027, 7, 1))   # backdated
    _book(hr_admin, employee_user, emp, "AL", date(2027, 7, 12), booked_on=date(2027, 7, 1))
    row = year_end.expire_carry_in(nxt, date(2027, 7, 2))
    assert row.units == D("-37.50")


def test_a_cancelled_booking_does_not_use_the_carry_in(db, hr_admin, employee_user):
    emp = hours_employee(start=date(2025, 4, 1))
    nxt = _carried(emp)
    a = _book(hr_admin, employee_user, emp, "AL", date(2027, 6, 7), booked_on=date(2027, 5, 20))
    _book(hr_admin, employee_user, emp, "AL", date(2027, 6, 8), booked_on=date(2027, 5, 20))
    with _booked_on(date(2027, 6, 1)):
        bookings.cancel(hr_admin, a)
    row = year_end.expire_carry_in(nxt, date(2027, 7, 1))
    assert row.units == D("-30.00")


def test_carry_in_expiry_never_takes_more_than_remains(db):
    emp = hours_employee(start=date(2025, 4, 1))
    nxt = _carried(emp)
    ledger.write(nxt, K.ADJUSTMENT, D("-237.50"), date=date(2027, 8, 1), note="bought out")
    row = year_end.expire_carry_in(nxt, date(2027, 7, 1))
    assert row.units == D("-10.00")
    assert ledger.balance(nxt) == D("0")


def test_a_negative_carry_in_never_expires(db):
    emp = hours_employee(start=date(2025, 4, 1))
    Policy.objects.update(carry_over_expires_after_days=90)
    pot = _pot_2026(emp)
    ledger.write(pot, K.ADJUSTMENT, D("-220"), note="over-taken")
    year_end.close(pot)
    assert year_end.expire_carry_in(_next_pot(emp), date(2027, 7, 1)) is None


def test_a_blank_carry_over_expiry_never_expires_the_carry_in(db):
    start = current_leave_year()[0]
    last = date(start.year - 1, start.month, start.day)
    emp = hours_employee(start=last)
    Policy.objects.update(carry_over_max_weeks=D("1"), carry_over_expires_after_days=None)
    pot = pots.for_day(emp, absence_type("AL"), last + timedelta(days=60))
    ledger.sync_entitlement(pot)
    year_end.close(pot)
    nxt = pots.for_day(emp, absence_type("AL"), start)
    assert nxt.entries.filter(kind=K.CARRY_IN, units__gt=0).exists()
    assert year_end.expire_carry_in(nxt, start + timedelta(days=1000)) is None
    Policy.objects.update(carry_over_expires_after_days=1)
    assert year_end.expire_carry_in(nxt, start + timedelta(days=1000)).kind == K.EXPIRY


# --- TOIL ------------------------------------------------------------------------

def test_toil_earned_and_expired(db, hr_admin):
    emp = _toil_employee()
    row = toil.earn(hr_admin, emp, D("3"), date(2026, 6, 1), "late clinic")
    assert row.kind == K.TOIL_EARNED and row.units == D("3") and row.date == date(2026, 6, 1)
    pot = row.pot
    assert pot.absence_type.code == "TOIL" and ledger.balance(pot) == D("3")    # TOIL accrues nothing
    assert year_end.expire_toil(pot, date(2026, 8, 29)) == []
    assert year_end.expire_toil(pot, date(2026, 8, 30)) == []                  # the deadline: still usable
    expired = year_end.expire_toil(pot, date(2026, 8, 31))
    assert [e.units for e in expired] == [D("-3")]
    assert year_end.expire_toil(pot, date(2026, 9, 1)) == []


def test_toil_expires_365_days_after_the_day_it_was_earned_as_seeded(db, hr_admin):
    emp = hours_employee()                                        # the TOIL type as migrated: 365 days
    pot = toil.earn(hr_admin, emp, D("3"), date(2026, 6, 1), "late clinic").pot
    assert year_end.expire_toil(pot, date(2027, 6, 1)) == []                   # the deadline: still usable
    expired = year_end.expire_toil(pot, date(2027, 6, 2))
    assert [(e.units, e.date) for e in expired] == [(D("-3"), date(2027, 6, 2))]


def test_a_toil_lot_reads_the_expiry_from_the_type_not_a_policy(db, hr_admin):
    emp = _toil_employee(30)
    pot = toil.earn(hr_admin, emp, D("3"), date(2026, 6, 1), "late clinic").pot
    AbsenceType.objects.filter(code="TOIL").update(earned_expires_after_days=None)   # never
    pot.absence_type.refresh_from_db()
    assert [lot["deadline"] for lot in year_end._toil_lots(pot)] == [None]
    assert year_end.expire_toil(pot, date(2030, 1, 1)) == []


def test_a_toil_lot_has_no_deadline_only_when_the_expiry_is_blank(db, hr_admin):
    start = current_leave_year()[0]
    emp = hours_employee(start=start)
    day = start + timedelta(days=10)
    AbsenceType.objects.filter(code="TOIL").update(earned_expires_after_days=30)
    pot = toil.earn(hr_admin, emp, D("3"), day, "late clinic").pot
    pot.absence_type.refresh_from_db()
    assert [lot["deadline"] for lot in year_end._toil_lots(pot)] == [day + timedelta(days=30)]
    AbsenceType.objects.filter(code="TOIL").update(earned_expires_after_days=0)      # refused by clean, but read as days
    pot.absence_type.refresh_from_db()
    assert [lot["deadline"] for lot in year_end._toil_lots(pot)] == [day]
    AbsenceType.objects.filter(code="TOIL").update(earned_expires_after_days=None)
    pot.absence_type.refresh_from_db()
    assert [lot["deadline"] for lot in year_end._toil_lots(pot)] == [None]


def test_toil_earned_is_audited(db, hr_admin):
    emp = _toil_employee()
    row = toil.earn(hr_admin, emp, D("2.5"), date(2026, 6, 1), "late clinic")
    entry = AuditEntry.objects.get(model="absence.ledgerentry", object_id=row.pk)
    assert entry.actor == hr_admin and entry.after == "2.50" and entry.note == "late clinic"


@pytest.mark.parametrize("units", [D("0"), D("-1")])
def test_toil_earn_refuses_non_positive_units(db, hr_admin, units):
    emp = _toil_employee()
    with pytest.raises(ValidationError):
        toil.earn(hr_admin, emp, units, date(2026, 6, 1), "nothing")
    assert not LedgerEntry.objects.filter(kind=K.TOIL_EARNED).exists()


def test_toil_taken_is_consumed_oldest_first(db, hr_admin, employee_user):
    emp = _toil_employee()
    first = toil.earn(hr_admin, emp, D("5"), date(2026, 6, 1), "clinic")      # deadline 30 Aug
    toil.earn(hr_admin, emp, D("5"), date(2026, 7, 1), "clinic")              # deadline 29 Sep
    _take_toil(hr_admin, employee_user, emp, date(2026, 6, 15), booked_on=date(2026, 6, 10))  # 7.5: 5 + 2.5
    pot = first.pot
    assert year_end.expire_toil(pot, date(2026, 9, 1)) == []
    expired = year_end.expire_toil(pot, date(2026, 9, 30))
    assert [e.units for e in expired] == [D("-2.50")]
    assert ledger.balance(pot) == D("0")


def test_toil_taken_after_an_expiry_draws_on_what_is_left(db, hr_admin, employee_user):
    emp = _toil_employee()
    first = toil.earn(hr_admin, emp, D("5"), date(2026, 6, 1), "clinic")
    toil.earn(hr_admin, emp, D("10"), date(2026, 7, 1), "clinic")
    pot = first.pot
    assert [e.units for e in year_end.expire_toil(pot, date(2026, 9, 1))] == [D("-5")]
    _take_toil(hr_admin, employee_user, emp, date(2026, 9, 7), booked_on=date(2026, 9, 2))    # 7.5 from the second
    assert [e.units for e in year_end.expire_toil(pot, date(2026, 9, 30))] == [D("-2.50")]
    assert ledger.balance(pot) == D("0")


def test_toil_booked_by_the_deadline_for_after_it_still_uses_it(db, hr_admin, employee_user):
    emp = _toil_employee()
    pot = toil.earn(hr_admin, emp, D("7.5"), date(2026, 6, 1), "clinic").pot            # deadline 30 Aug
    toil.earn(hr_admin, emp, D("7.5"), date(2026, 8, 1), "clinic")                      # deadline 30 Oct
    _take_toil(hr_admin, employee_user, emp, date(2026, 9, 7), booked_on=date(2026, 8, 30))
    assert year_end.expire_toil(pot, date(2026, 8, 31)) == []                          # the first was used
    assert [e.units for e in year_end.expire_toil(pot, date(2026, 11, 1))] == [D("-7.50")]  # the second was not
    assert ledger.balance(pot) == D("0")


def test_toil_booked_after_the_deadline_draws_on_the_next_line(db, hr_admin, employee_user):
    emp = _toil_employee()
    pot = toil.earn(hr_admin, emp, D("7.5"), date(2026, 6, 1), "clinic").pot
    toil.earn(hr_admin, emp, D("7.5"), date(2026, 8, 1), "clinic")
    _take_toil(hr_admin, employee_user, emp, date(2026, 9, 7), booked_on=date(2026, 8, 31))
    assert [e.units for e in year_end.expire_toil(pot, date(2026, 8, 31))] == [D("-7.50")]
    assert year_end.expire_toil(pot, date(2026, 11, 1)) == []
    assert ledger.balance(pot) == D("0")


def _toil_2026_27(hr_admin, days=90):
    emp = _toil_employee(days)
    return emp, toil.earn(hr_admin, emp, D("3"), date(2027, 3, 25), "clinic")


def test_toil_at_year_end_carries_forward_with_its_earned_date(db, hr_admin):
    emp, earned = _toil_2026_27(hr_admin)                          # deadline 23 Jun 2027
    old = earned.pot
    result = year_end.run(date(2027, 4, 1))
    assert result["closed"] == 1 and result["carried_total"] == D("3") and result["toil_expired"] == 0
    assert ledger.balance(old) == D("0")
    closing = old.entries.get(kind=K.EXPIRY)
    assert closing.units == D("-3") and closing.note == "year end close: 3.00 TOIL carried forward, 0.00 expired"
    new = pots.for_day(emp, absence_type("TOIL"), date(2027, 4, 1))
    carried = new.entries.get(kind=K.TOIL_EARNED)
    assert carried.units == D("3") and carried.date == date(2027, 3, 25)
    assert carried.note == "carried from 01 Apr 2026–31 Mar 2027"
    assert not new.entries.filter(kind=K.CARRY_IN).exists()
    assert year_end.expire_toil(new, date(2027, 6, 23)) == []
    assert [e.units for e in year_end.expire_toil(new, date(2027, 6, 24))] == [D("-3")]


def test_toil_at_year_end_carries_only_the_unused_part(db, hr_admin, employee_user):
    emp = _toil_employee()
    toil.earn(hr_admin, emp, D("10"), date(2027, 3, 1), "clinic")
    _take_toil(hr_admin, employee_user, emp, date(2027, 3, 15), booked_on=date(2027, 3, 10))
    year_end.run(date(2027, 4, 1))
    new = pots.for_day(emp, absence_type("TOIL"), date(2027, 4, 1))
    assert [(e.units, e.date) for e in new.entries.filter(kind=K.TOIL_EARNED)] == [(D("2.50"), date(2027, 3, 1))]


def test_toil_past_its_deadline_at_year_end_expires(db, hr_admin):
    emp = _toil_employee()
    old = toil.earn(hr_admin, emp, D("3"), date(2026, 12, 1), "clinic").pot         # deadline 1 Mar 2027
    toil.earn(hr_admin, emp, D("2"), date(2027, 3, 25), "clinic")
    assert year_end.close(old) == {"carried": D("2"), "expired": D("3")}
    new = pots.for_day(emp, absence_type("TOIL"), date(2027, 4, 1))
    assert [e.units for e in new.entries.filter(kind=K.TOIL_EARNED)] == [D("2")]


def test_a_toil_adjustment_is_a_lot_that_carries_and_expires(db, hr_admin):
    emp = _toil_employee()
    old = toil.earn(hr_admin, emp, D("2"), date(2027, 3, 1), "clinic").pot           # deadline 30 May
    with _booked_on(date(2027, 3, 20)):
        ledger.write(old, K.ADJUSTMENT, D("4"), hr_admin, date=date(2027, 3, 20), note="HR added")  # deadline 18 Jun
    with _booked_on(date(2027, 3, 25)):
        ledger.write(old, K.ADJUSTMENT, D("-3"), hr_admin, date=date(2027, 3, 25), note="HR removed")
    year_end.run(date(2027, 4, 1))                                    # the -3 used the 2, then 1 of the 4
    new = pots.for_day(emp, absence_type("TOIL"), date(2027, 4, 1))
    carried = new.entries.get(kind=K.TOIL_EARNED)
    assert (carried.units, carried.date) == (D("3"), date(2027, 3, 20))
    assert carried.note == "carried from 01 Apr 2026–31 Mar 2027"
    assert ledger.balance(old) == D("0")
    assert year_end.expire_toil(new, date(2027, 6, 18)) == []
    assert [e.units for e in year_end.expire_toil(new, date(2027, 6, 19))] == [D("-3")]


def test_a_toil_adjustment_expires_by_the_policy_days(db, hr_admin):
    emp = _toil_employee()
    pot = toil.earn(hr_admin, emp, D("1"), date(2026, 6, 1), "clinic").pot
    ledger.write(pot, K.ADJUSTMENT, D("4"), hr_admin, date=date(2026, 7, 1), note="HR added")   # deadline 29 Sep
    assert [e.units for e in year_end.expire_toil(pot, date(2026, 9, 29))] == [D("-1")]
    assert [e.units for e in year_end.expire_toil(pot, date(2026, 9, 30))] == [D("-4")]
    assert ledger.balance(pot) == D("0")


def test_toil_year_end_twice_writes_nothing(db, hr_admin):
    emp, earned = _toil_2026_27(hr_admin)
    year_end.run(date(2027, 4, 1))
    count = LedgerEntry.objects.count()
    second = year_end.run(date(2027, 4, 1))
    assert second["closed"] == 0 and LedgerEntry.objects.count() == count


def test_a_toil_expiry_reversed_by_an_adjustment_stays_reversed(db, hr_admin):
    emp = _toil_employee()
    pot = toil.earn(hr_admin, emp, D("3"), date(2026, 6, 1), "clinic").pot
    year_end.expire_toil(pot, date(2026, 8, 31))
    ledger.write(pot, K.ADJUSTMENT, D("3"), hr_admin, date=date(2026, 8, 31), note="expiry reversed")
    assert year_end.expire_toil(pot, date(2026, 9, 1)) == []
    assert ledger.balance(pot) == D("3")


# --- run, nightly, command ----------------------------------------------------------

def test_run_and_command(db, capsys):
    emp = hours_employee(start=date(2025, 4, 1))
    _pot_2026(emp)
    result = year_end.run(date(2027, 4, 1))
    assert result["closed"] == 1 and result["expired_total"] == D("210.00") and result["failed"] == []
    from django.core.management import call_command
    call_command("absence_year_end", today="2027-04-02")
    out = capsys.readouterr().out
    assert "'closed': 0" in out and "'failed': []" in out


def test_run_expires_carry_in_and_toil_on_open_pots(db, hr_admin):
    emp = _toil_employee()
    Policy.objects.filter(absence_type__code="AL").update(
        carry_over_max_weeks=D("1"), carry_over_expires_after_days=90)
    toil.earn(hr_admin, emp, D("3"), date(2027, 5, 1), "clinic")
    year_end.close(pots.for_day(emp, absence_type("AL"), date(2026, 6, 1)))
    result = year_end.run(date(2027, 7, 31))
    assert result["closed"] == 0                                    # the 2026/27 pot was closed above
    assert result["carry_in_expired"] == 1 and result["toil_expired"] == 1
    assert year_end.run(date(2027, 7, 31))["carry_in_expired"] == 0


def _no_policy_next_year():
    """An employee whose contract type's policies end with the 2026/27 year."""
    other = make_contract_type("Other")
    bad = make_employment(start=date(2025, 4, 1))
    make_contract(bad, other)
    make_policy(other, effective_to=date(2027, 3, 31))
    make_pattern(bad)
    return pots.for_day(bad, absence_type("AL"), date(2026, 6, 1))


def test_run_reports_a_pot_it_cannot_close_and_closes_the_rest(db):
    emp = hours_employee(start=date(2025, 4, 1))
    good = _pot_2026(emp)
    bad = _no_policy_next_year()
    result = year_end.run(date(2027, 4, 2))
    assert result["closed"] == 1 and good.entries.filter(kind=K.EXPIRY).exists()
    assert len(result["failed"]) == 1 and str(bad) in result["failed"][0]
    assert not bad.entries.filter(kind=K.EXPIRY).exists()


def test_nightly_runs_the_year_end_and_keeps_its_failures(db):
    emp = hours_employee(start=date(2025, 4, 1))
    _pot_2026(emp)
    bad = _no_policy_next_year()
    result = nightly.run(date(2027, 4, 2))
    assert result["year_end_closed"] == 1
    assert result["carried_total"] == D("0") and result["expired_total"] == D("210.00")
    assert result["carry_in_expired"] == 0 and result["toil_expired"] == 0 and result["leaver_debts"] == []
    assert any(str(bad) in f for f in result["failed"])
    assert nightly.run(date(2027, 4, 2))["year_end_closed"] == 0


# --- a closed pot takes no more lines (C2) ------------------------------------------

def _closed_2026(emp):
    pot = _pot_2026(emp)
    year_end.close(pot)
    return pot


def test_a_request_waiting_over_the_year_end_blocks_the_close_and_is_reported(db, hr_admin, employee_user):
    emp = hours_employee(start=date(2025, 4, 1))
    pot = _pot_2026(emp)
    waiting = bookings.request(employee_user, emp, absence_type("AL"), date(2027, 3, 15))
    result = year_end.run(date(2027, 4, 1))
    assert result["closed"] == 0
    assert result["failed"] == [f"{pot}: 1 request(s) waiting — decide them first"]
    assert not year_end.is_closed(pot)
    bookings.approve(hr_admin, waiting)                      # decided: the next night closes it
    assert year_end.run(date(2027, 4, 2))["closed"] == 1
    assert year_end.is_closed(pot) and ledger.balance(pot) == D("0")


def test_a_waiting_request_of_another_type_or_year_does_not_block_the_close(db, employee_user):
    emp = hours_employee(start=date(2025, 4, 1))
    pot = _pot_2026(emp)
    bookings.request(employee_user, emp, absence_type("UNPAID"), date(2027, 3, 15))
    bookings.request(employee_user, emp, absence_type("AL"), date(2027, 4, 12))
    assert year_end.run(date(2027, 4, 1))["closed"] == 1 and year_end.is_closed(pot)


def _waiting_on_closed_pot(emp, employee_user, day=date(2027, 3, 15)):
    """A request left on a pot that has since closed, as a row written before
    the guards existed would be: the services now refuse to make one."""
    from absence.models import Absence
    return Absence.objects.create(employment=emp, absence_type=absence_type("AL"), start_date=day, end_date=day,
                                  cost_units=D("7.50"), requested_by=employee_user)


def test_approving_against_a_closed_pot_is_refused(db, hr_admin, employee_user):
    emp = hours_employee(start=date(2025, 4, 1))
    pot = _closed_2026(emp)
    a = _waiting_on_closed_pot(emp, employee_user)
    count = LedgerEntry.objects.count()
    with pytest.raises(ValidationError, match="closed.*adjust the current year's pot"):
        bookings.approve(hr_admin, a)
    a.refresh_from_db()
    assert a.status == a.Status.REQUESTED and LedgerEntry.objects.count() == count
    assert ledger.balance(pot) == D("0")


def test_requesting_leave_on_a_closed_pot_is_refused(db, employee_user):
    emp = hours_employee(start=date(2025, 4, 1))
    _closed_2026(emp)
    with pytest.raises(ValidationError, match="closed"):
        bookings.request(employee_user, emp, absence_type("AL"), date(2027, 3, 15))


def test_cancelling_an_approved_absence_on_a_closed_pot_is_refused(db, hr_admin, employee_user):
    emp = hours_employee(start=date(2025, 4, 1))
    a = _book(hr_admin, employee_user, emp, "AL", date(2027, 3, 15), booked_on=date(2027, 3, 1))
    pot = a.ledger_entries.get().pot
    year_end.close(pot)
    with pytest.raises(ValidationError, match="closed"):
        bookings.cancel(hr_admin, a)
    a.refresh_from_db()
    assert a.status == a.Status.APPROVED and ledger.balance(pot) == D("0")


def test_recosting_an_absence_on_a_closed_pot_is_refused(db, hr_admin, employee_user):
    emp = hours_employee(start=date(2025, 4, 1))
    a = _book(hr_admin, employee_user, emp, "AL", date(2027, 3, 15), booked_on=date(2027, 3, 1))
    pot = a.ledger_entries.get().pot
    year_end.close(pot)
    make_pattern(emp, {0: (D("3.75"), D("0"))}, effective_from=date(2027, 3, 1))
    with pytest.raises(ValidationError, match="closed"):
        bookings.recost(hr_admin, a, "pattern changed")
    assert ledger.balance(pot) == D("0")


def test_admin_recalculation_of_a_closed_pot_is_refused(admin_client, hr_admin):
    emp = hours_employee(start=date(2025, 4, 1))
    pot = _closed_2026(emp)
    emp.contracts.update(weekly_amount=D("18.75"))
    count = pot.entries.count()
    resp = admin_client.post("/admin/absence/pot/", {"action": "recalculate", "_selected_action": [pot.pk]},
                             follow=True)
    assert "closed" in resp.content.decode() and "0 pot(s) revised." in resp.content.decode()
    assert pot.entries.count() == count


# --- a booking is dated from its request (I3) -----------------------------------------

def _request_on(employee_user, emp, code, day, requested_on):
    with _booked_on(requested_on):
        return bookings.request(employee_user, emp, absence_type(code), day)


def test_leave_requested_by_the_deadline_and_approved_after_it_uses_the_carry_in(db, hr_admin, employee_user):
    emp = hours_employee(start=date(2025, 4, 1))
    nxt = _carried(emp)                                              # 37.50
    Policy.objects.update(carry_over_expires_after_days=30)          # deadline 1 May 2027
    a = _request_on(employee_user, emp, "AL", date(2027, 5, 10), requested_on=date(2027, 4, 28))
    with _booked_on(date(2027, 5, 4)):                               # a slow approver
        bookings.approve(hr_admin, a)
    row = year_end.expire_carry_in(nxt, date(2027, 5, 5))
    assert row.units == D("-30.00")                                  # the 7.50 requested in time was used


def test_a_request_waiting_on_the_deadline_defers_the_carry_in_expiry(db, hr_admin, employee_user):
    emp = hours_employee(start=date(2025, 4, 1))
    nxt = _carried(emp)
    Policy.objects.update(carry_over_expires_after_days=30)
    a = _request_on(employee_user, emp, "AL", date(2027, 5, 10), requested_on=date(2027, 4, 28))
    _request_on(employee_user, emp, "AL", date(2027, 5, 11), requested_on=date(2027, 5, 2))   # after: no hold
    assert year_end.expire_carry_in(nxt, date(2027, 5, 2)) is None   # still waiting: try again tomorrow
    assert year_end.run(date(2027, 5, 3))["carry_in_expired"] == 0
    with _booked_on(date(2027, 5, 4)):
        bookings.approve(hr_admin, a)
    assert year_end.expire_carry_in(nxt, date(2027, 5, 5)).units == D("-30.00")


def test_a_request_declined_after_the_deadline_lets_the_carry_in_expire_whole(db, hr_admin, employee_user):
    emp = hours_employee(start=date(2025, 4, 1))
    nxt = _carried(emp)
    Policy.objects.update(carry_over_expires_after_days=30)
    a = _request_on(employee_user, emp, "AL", date(2027, 5, 10), requested_on=date(2027, 4, 28))
    assert year_end.expire_carry_in(nxt, date(2027, 5, 3)) is None
    bookings.decline(hr_admin, a)
    assert year_end.expire_carry_in(nxt, date(2027, 5, 3)).units == D("-37.50")


def test_toil_requested_by_the_deadline_and_approved_after_it_uses_the_lot(db, hr_admin, employee_user):
    emp = _toil_employee()
    pot = toil.earn(hr_admin, emp, D("7.5"), date(2026, 6, 1), "clinic").pot            # deadline 30 Aug
    a = _request_on(employee_user, emp, "TOIL", date(2026, 9, 7), requested_on=date(2026, 8, 28))
    assert year_end.expire_toil(pot, date(2026, 9, 1)) == []                           # waiting: deferred
    with _booked_on(date(2026, 9, 2)):
        bookings.approve(hr_admin, a)
    assert year_end.expire_toil(pot, date(2026, 9, 3)) == []                           # used in time
    assert ledger.balance(pot) == D("0")
