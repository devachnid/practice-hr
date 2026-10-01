from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from absence.models import Absence, LedgerEntry, Policy
from absence.services import bank_holidays, bookings, ledger, pots
from people.services import patterns
from tests.factories import absence_type, hours_employee, make_policy

D = Decimal
NOTHING = {"created": 0, "removed": 0, "recosted": 0, "kept_cancelled": 0}
Y0, Y1 = date(2026, 4, 1), date(2027, 3, 31)
MAY_DAY, FRI = date(2026, 5, 4), date(2026, 5, 8)   # May Day bank holiday week


def _with_pot_handling(emp):
    ct = emp.contracts.first().contract_type
    ct.policies.filter(absence_type__code="AL").update(bank_holiday_handling=Policy.BankHolidays.PRO_RATA_POT)
    make_policy(ct, "BH", bank_holiday_handling="pot")


def test_creates_one_per_working_bank_holiday(db):
    emp = hours_employee()
    _with_pot_handling(emp)
    result = bank_holidays.sync_auto_absences(emp, Y0, Y1)
    assert result == NOTHING | {"created": 10}   # ten in 2026/27, all weekdays
    a = Absence.objects.get(employment=emp, start_date=date(2026, 5, 4))
    assert a.auto_bank_holiday and a.status == "approved" and a.cost_units == D("7.50")
    pot = pots.for_day(emp, absence_type("BH"), Y0)
    assert sum(e.units for e in pot.entries.filter(kind=LedgerEntry.Kind.BOOKING)) == D("-75.00")
    assert ledger.balance(pot) == D("0.00")      # the pot opened with its 75.00 entitlement


def test_idempotent(db):
    emp = hours_employee()
    _with_pot_handling(emp)
    bank_holidays.sync_auto_absences(emp, Y0, Y1)
    assert bank_holidays.sync_auto_absences(emp, Y0, Y1) == NOTHING


def test_non_working_day_not_created_and_pattern_change_removes(db, hr_admin):
    emp = hours_employee()
    _with_pot_handling(emp)
    bank_holidays.sync_auto_absences(emp, Y0, Y1)
    patterns.set_pattern(hr_admin, emp, date(2026, 4, 1), {d: (D("3.75"), D("3.75")) for d in (1, 2, 3, 4)})
    result = bank_holidays.sync_auto_absences(emp, Y0, Y1)
    assert result["removed"] == 6      # the six Monday bank holidays
    assert Absence.objects.filter(employment=emp, auto_bank_holiday=True, status="approved").count() == 4
    pot = pots.for_day(emp, absence_type("BH"), Y0)
    assert pot.entries.filter(kind=LedgerEntry.Kind.CANCELLATION).count() == 6


def test_included_in_annual_draws_on_al(db):
    emp = hours_employee()
    ct = emp.contracts.first().contract_type
    ct.policies.filter(absence_type__code="AL").update(bank_holiday_handling=Policy.BankHolidays.INCLUDED_IN_ANNUAL)
    bank_holidays.sync_auto_absences(emp, Y0, Y1)
    pot = pots.for_day(emp, absence_type("AL"), Y0)
    assert sum(e.units for e in pot.entries.filter(kind=LedgerEntry.Kind.BOOKING)) == D("-75.00")
    assert ledger.balance(pot) == D("135.00")    # opened with 210.00, ten bank holidays charged


def test_closed_not_charged_creates_nothing(db):
    emp = hours_employee()
    assert bank_holidays.sync_auto_absences(emp, Y0, Y1) == NOTHING


def test_a_booking_on_the_bank_holiday_costs_nothing_and_the_auto_row_still_charges(db, hr_admin):
    emp = hours_employee()
    _with_pot_handling(emp)
    leave = bookings.request(hr_admin, emp, absence_type("AL"), MAY_DAY)
    assert leave.cost_units == D("0.00")
    assert bank_holidays.sync_auto_absences(emp, Y0, Y1) == NOTHING | {"created": 10}
    auto = Absence.objects.get(employment=emp, auto_bank_holiday=True, start_date=MAY_DAY)
    assert auto.status == "approved" and auto.cost_units == D("7.50")
    bookings.approve(hr_admin, leave)
    assert not leave.ledger_entries.exists()          # nothing charged twice
    assert bank_holidays.sync_auto_absences(emp, Y0, Y1) == NOTHING



def _with_annual_handling(emp):
    ct = emp.contracts.first().contract_type
    ct.policies.filter(absence_type__code="AL").update(bank_holiday_handling=Policy.BankHolidays.INCLUDED_IN_ANNUAL)


def _week_off(hr_admin, emp):
    leave = bookings.request(hr_admin, emp, absence_type("AL"), MAY_DAY, FRI)
    return bookings.approve(hr_admin, leave)


@pytest.mark.parametrize("handling,charged_to", [("pot", "BH"), ("annual", "AL")])
@pytest.mark.parametrize("booking_first", [True, False])
def test_week_off_over_a_bank_holiday(db, hr_admin, handling, charged_to, booking_first):
    emp = hours_employee()
    (_with_pot_handling if handling == "pot" else _with_annual_handling)(emp)
    if booking_first:
        leave = _week_off(hr_admin, emp)
        bank_holidays.sync_auto_absences(emp, Y0, Y1)
    else:
        bank_holidays.sync_auto_absences(emp, Y0, Y1)
        leave = _week_off(hr_admin, emp)
    assert leave.status == "approved" and leave.cost_units == D("30.00")      # four days, not five
    booking = leave.ledger_entries.get()
    assert booking.units == D("-30.00") and booking.pot.absence_type.code == "AL"
    auto = Absence.objects.get(employment=emp, auto_bank_holiday=True, start_date=MAY_DAY)
    assert auto.status == "approved" and auto.cost_units == D("7.50")
    line = auto.ledger_entries.get()
    assert line.units == D("-7.50") and line.pot.absence_type.code == charged_to


def test_week_off_over_a_bank_holiday_when_closed(db, hr_admin):
    emp = hours_employee()                                  # closed_not_charged
    leave = _week_off(hr_admin, emp)
    assert leave.cost_units == D("30.00")
    assert bank_holidays.sync_auto_absences(emp, Y0, Y1) == NOTHING
    assert not Absence.objects.filter(employment=emp, auto_bank_holiday=True).exists()


def test_pot_handling_with_no_bank_holiday_policy_is_an_error_naming_it(db):
    emp = hours_employee()
    ct = emp.contracts.first().contract_type
    ct.policies.filter(absence_type__code="AL").update(bank_holiday_handling=Policy.BankHolidays.PRO_RATA_POT)
    with pytest.raises(ValidationError) as e:
        bank_holidays.sync_auto_absences(emp, Y0, Y1)
    assert "No Bank holiday policy for Reception" in str(e.value)
    assert not Absence.objects.filter(employment=emp, auto_bank_holiday=True).exists()


@pytest.mark.seeded_policies
def test_seeded_policies_charge_every_working_bank_holiday_for_hours_staff(db):
    # the seeded hours types' leave year is the calendar year (0012): starting 1 April 2026,
    # the 2026 pot has the seven holidays from Good Friday on, each one working day
    emp = hours_employee()                   # seeded Reception: AL "pot" plus a BH policy
    year = (date(2026, 1, 1), date(2026, 12, 31))
    assert bank_holidays.sync_auto_absences(emp, *year) == NOTHING | {"created": 7}
    autos = Absence.objects.filter(employment=emp, auto_bank_holiday=True, status="approved")
    assert {a.cost_units for a in autos} == {D("7.50")}
    pot = pots.for_day(emp, absence_type("BH"), Y0)
    assert (pot.year_start, pot.year_end) == year
    assert sum(e.units for e in pot.entries.filter(kind=LedgerEntry.Kind.BOOKING)) == D("-52.50")
    assert ledger.balance(pot) == D("0.00")      # opened with 7 × 7.5 = 52.50


def test_a_shorter_monday_re_costs_future_monday_bank_holidays_only(db, hr_admin):
    emp = hours_employee()
    _with_pot_handling(emp)
    bank_holidays.sync_auto_absences(emp, Y0, Y1, today=Y0)
    bh_pot = pots.for_day(emp, absence_type("BH"), Y0)
    before = ledger.balance(bh_pot)
    # Mondays cut from 7.5 to 4 hours for the whole year; only 29 Mar 2027 is still ahead
    days = {d: (D("3.75"), D("3.75")) for d in range(1, 5)} | {0: (D("2"), D("2"))}
    patterns.set_pattern(hr_admin, emp, Y0, days)
    today = date(2027, 1, 1)
    assert bank_holidays.sync_auto_absences(emp, Y0, Y1, today=today) == NOTHING | {"recosted": 1}
    easter_monday = Absence.objects.get(employment=emp, auto_bank_holiday=True, start_date=date(2027, 3, 29))
    assert easter_monday.cost_units == D("4.00")
    adjustment = bh_pot.entries.get(kind=LedgerEntry.Kind.ADJUSTMENT)
    assert adjustment.units == D("3.50") and adjustment.absence == easter_monday
    assert ledger.balance(bh_pot) == before + D("3.50")
    past_monday = Absence.objects.get(employment=emp, auto_bank_holiday=True, start_date=MAY_DAY)
    assert past_monday.cost_units == D("7.50")                  # a past charge is left alone
    assert bank_holidays.sync_auto_absences(emp, Y0, Y1, today=today)["recosted"] == 0


# --- HR's cancellation of an automatic row stands ---------------------------------------------

def _this_year_with_a_holiday():
    """An employee on pot handling from the start of the current leave year,
    and a bank holiday on a Wednesday in it that they work."""
    from datetime import timedelta

    from absence.models import BankHoliday
    from tests.factories import current_leave_year
    start, end = current_leave_year()
    day = start + timedelta(days=60)
    day += timedelta(days=(2 - day.weekday()) % 7)
    BankHoliday.objects.get_or_create(date=day, nation="EW", defaults={"name": "Test holiday"})
    emp = hours_employee(start=start)
    _with_pot_handling(emp)
    return emp, start, end, day


def test_a_cancelled_automatic_row_stays_cancelled(db, hr_admin):
    emp, start, end, day = _this_year_with_a_holiday()
    bank_holidays.sync_auto_absences(emp, start, end)
    auto = Absence.objects.get(employment=emp, auto_bank_holiday=True, start_date=day)
    bookings.cancel(hr_admin, auto)                           # not to be charged
    result = bank_holidays.sync_auto_absences(emp, start, end)
    assert result == NOTHING | {"kept_cancelled": 1}
    assert Absence.objects.filter(employment=emp, start_date=day).count() == 1
    assert bank_holidays.sync_auto_absences(emp, start, end)["kept_cancelled"] == 1


def test_a_row_the_sync_cancelled_comes_back_when_implied_again(db, hr_admin):
    emp, start, end, day = _this_year_with_a_holiday()
    bank_holidays.sync_auto_absences(emp, start, end)
    working = {d: (D("3.75"), D("3.75")) for d in range(5)}
    patterns.set_pattern(hr_admin, emp, start, {d: v for d, v in working.items() if d != 2})    # no Wednesdays
    assert bank_holidays.sync_auto_absences(emp, start, end)["removed"] >= 1
    gone = Absence.objects.get(employment=emp, auto_bank_holiday=True, start_date=day)
    assert (gone.status, gone.cancel_reason) == ("cancelled", bank_holidays.NOT_IMPLIED)
    patterns.set_pattern(hr_admin, emp, start, working)
    result = bank_holidays.sync_auto_absences(emp, start, end)
    assert result["created"] >= 1 and result["kept_cancelled"] == 0
    assert Absence.objects.get(employment=emp, start_date=day, status="approved").auto_bank_holiday


def test_rows_cancelled_by_a_leaving_date_come_back_when_it_is_cleared(db, hr_admin):
    from datetime import timedelta

    from people.services import employments
    emp, start, end, day = _this_year_with_a_holiday()
    bank_holidays.sync_auto_absences(emp, start, end)
    employments.end(hr_admin, emp, day - timedelta(days=1), "resigned")
    gone = Absence.objects.get(employment=emp, auto_bank_holiday=True, start_date=day)
    assert (gone.status, gone.cancel_reason) == ("cancelled", bank_holidays.NOT_IMPLIED)
    employments.end(hr_admin, emp, None, "")                  # the leaving date was a mistake
    result = bank_holidays.sync_auto_absences(emp, start, end)
    assert result["created"] >= 1 and result["kept_cancelled"] == 0
    assert Absence.objects.filter(employment=emp, start_date=day, status="approved").exists()


def test_cancel_stores_a_reason_and_other_cancellations_have_none(db, hr_admin):
    from datetime import timedelta

    from tests.factories import current_leave_year
    start, _ = current_leave_year()
    emp = hours_employee(start=start)
    monday = start + timedelta(days=70)
    monday -= timedelta(days=monday.weekday())
    one = bookings.request(hr_admin, emp, absence_type("AL"), monday)
    two = bookings.request(hr_admin, emp, absence_type("AL"), monday + timedelta(days=1))
    bookings.cancel(hr_admin, one, reason="changed their mind " * 5)
    bookings.cancel(hr_admin, two)
    one.refresh_from_db()
    two.refresh_from_db()
    assert one.cancel_reason == ("changed their mind " * 5)[:60]
    assert two.cancel_reason == ""
    recorded = bookings.record(hr_admin, emp, absence_type("AL"), monday + timedelta(days=1))
    assert recorded.status == "approved" and recorded.cancel_reason == ""


def test_automatic_rows_cancelled_before_the_reason_existed_count_as_not_implied(db, hr_admin):
    import importlib
    from datetime import timedelta

    from django.apps import apps
    migration = importlib.import_module("absence.migrations.0015_absence_cancel_reason")
    assert migration.NOT_IMPLIED == bank_holidays.NOT_IMPLIED
    emp, start, end, day = _this_year_with_a_holiday()
    bank_holidays.sync_auto_absences(emp, start, end)
    auto = Absence.objects.get(employment=emp, auto_bank_holiday=True, start_date=day)
    bookings.cancel(hr_admin, auto)
    leave = bookings.request(hr_admin, emp, absence_type("AL"), day + timedelta(days=1))          # a Thursday
    bookings.cancel(hr_admin, leave)
    migration.mark_earlier_cancellations(apps, None)
    auto.refresh_from_db()
    leave.refresh_from_db()
    assert (auto.cancel_reason, leave.cancel_reason) == (bank_holidays.NOT_IMPLIED, "")
    assert bank_holidays.sync_auto_absences(emp, start, end)["created"] == 1


# --- HR undoes an opt-out: charge_again ---------------------------------------------------------

def test_charge_again_brings_the_automatic_row_back_at_once(db, hr_admin):
    from people.models import AuditEntry
    emp, start, end, day = _this_year_with_a_holiday()
    bank_holidays.sync_auto_absences(emp, start, end)
    auto = Absence.objects.get(employment=emp, auto_bank_holiday=True, start_date=day)
    bookings.cancel(hr_admin, auto)
    assert bank_holidays.sync_auto_absences(emp, start, end)["kept_cancelled"] == 1
    result = bank_holidays.charge_again(hr_admin, auto)
    assert result == NOTHING | {"created": 1}
    auto.refresh_from_db()
    assert (auto.status, auto.cancel_reason) == ("cancelled", bank_holidays.NOT_IMPLIED)
    back = Absence.objects.get(employment=emp, auto_bank_holiday=True, start_date=day, status="approved")
    assert back.cost_units == D("7.50") and back.decided_by == hr_admin
    entry = AuditEntry.objects.get(model="absence.absence", object_id=auto.pk, field="cancel_reason")
    assert (entry.actor, entry.before, entry.after) == (hr_admin, "", bank_holidays.NOT_IMPLIED)
    assert bank_holidays.sync_auto_absences(emp, start, end) == NOTHING


def test_charge_again_leaves_a_day_no_longer_implied_uncharged(db, hr_admin):
    emp, start, end, day = _this_year_with_a_holiday()
    bank_holidays.sync_auto_absences(emp, start, end)
    auto = Absence.objects.get(employment=emp, auto_bank_holiday=True, start_date=day)
    bookings.cancel(hr_admin, auto)
    working = {d: (D("3.75"), D("3.75")) for d in range(5) if d != 2}         # no Wednesdays now
    patterns.set_pattern(hr_admin, emp, start, working)
    assert bank_holidays.charge_again(hr_admin, auto)["created"] == 0
    assert not Absence.objects.filter(employment=emp, start_date=day, status="approved").exists()


@pytest.mark.parametrize("which", ["approved", "not automatic"])
def test_charge_again_refuses_anything_but_a_cancelled_automatic_row(db, hr_admin, which):
    emp, start, end, day = _this_year_with_a_holiday()
    if which == "approved":
        bank_holidays.sync_auto_absences(emp, start, end)
        row = Absence.objects.get(employment=emp, auto_bank_holiday=True, start_date=day)
    else:
        from datetime import timedelta
        row = bookings.request(hr_admin, emp, absence_type("AL"), day + timedelta(days=1))
        bookings.cancel(hr_admin, row)
    with pytest.raises(ValidationError, match="Only a cancelled automatic bank-holiday row"):
        bank_holidays.charge_again(hr_admin, row)
    row.refresh_from_db()
    assert row.cancel_reason == ""
