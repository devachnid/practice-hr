from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from absence.models import Absence, LedgerEntry, Policy
from absence.services import bank_holidays, bookings, ledger, pots
from people.services import patterns
from tests.factories import absence_type, hours_employee, make_policy

D = Decimal
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
    assert result == {"created": 10, "removed": 0}   # ten in 2026/27, all weekdays
    a = Absence.objects.get(employment=emp, start_date=date(2026, 5, 4))
    assert a.auto_bank_holiday and a.status == "approved" and a.cost_units == D("7.50")
    pot = pots.for_day(emp, absence_type("BH"), Y0)
    assert ledger.balance(pot) == D("-75.00")


def test_idempotent(db):
    emp = hours_employee()
    _with_pot_handling(emp)
    bank_holidays.sync_auto_absences(emp, Y0, Y1)
    assert bank_holidays.sync_auto_absences(emp, Y0, Y1) == {"created": 0, "removed": 0}


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
    assert ledger.balance(pot) == D("-75.00")


def test_closed_not_charged_creates_nothing(db):
    emp = hours_employee()
    assert bank_holidays.sync_auto_absences(emp, Y0, Y1) == {"created": 0, "removed": 0}


def test_a_booking_on_the_bank_holiday_costs_nothing_and_the_auto_row_still_charges(db, hr_admin):
    emp = hours_employee()
    _with_pot_handling(emp)
    leave = bookings.request(hr_admin, emp, absence_type("AL"), MAY_DAY)
    assert leave.cost_units == D("0.00")
    assert bank_holidays.sync_auto_absences(emp, Y0, Y1) == {"created": 10, "removed": 0}
    auto = Absence.objects.get(employment=emp, auto_bank_holiday=True, start_date=MAY_DAY)
    assert auto.status == "approved" and auto.cost_units == D("7.50")
    bookings.approve(hr_admin, leave)
    assert not leave.ledger_entries.exists()          # nothing charged twice
    assert bank_holidays.sync_auto_absences(emp, Y0, Y1) == {"created": 0, "removed": 0}



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
    assert bank_holidays.sync_auto_absences(emp, Y0, Y1) == {"created": 0, "removed": 0}
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
    emp = hours_employee()                   # seeded Reception: AL "pot" plus a BH policy
    assert bank_holidays.sync_auto_absences(emp, Y0, Y1) == {"created": 10, "removed": 0}
    autos = Absence.objects.filter(employment=emp, auto_bank_holiday=True, status="approved")
    assert {a.cost_units for a in autos} == {D("7.50")}
    pot = pots.for_day(emp, absence_type("BH"), Y0)
    assert sum(e.units for e in pot.entries.filter(kind=LedgerEntry.Kind.BOOKING)) == D("-75.00")
