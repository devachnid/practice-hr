from datetime import date
from decimal import Decimal

from absence.models import Absence, LedgerEntry, Policy
from absence.services import bank_holidays, bookings, ledger, pots
from people.services import patterns
from tests.factories import absence_type, hours_employee, make_policy

D = Decimal
Y0, Y1 = date(2026, 4, 1), date(2027, 3, 31)


def _with_pot_handling(emp):
    ct = emp.contracts.first().contract_type
    ct.policies.filter(absence_type__code="AL").update(bank_holiday_handling=Policy.BankHolidays.PRO_RATA_POT)
    make_policy(ct, "BH", bank_holiday_handling="pot")


def test_creates_one_per_working_bank_holiday(db):
    emp = hours_employee()
    _with_pot_handling(emp)
    result = bank_holidays.sync_auto_absences(emp, Y0, Y1)
    assert result == {"created": 10, "removed": 0, "skipped": 0}   # ten in 2026/27, all weekdays
    a = Absence.objects.get(employment=emp, start_date=date(2026, 5, 4))
    assert a.auto_bank_holiday and a.status == "approved" and a.cost_units == D("7.50")
    pot = pots.for_day(emp, absence_type("BH"), Y0)
    assert ledger.balance(pot) == D("-75.00")


def test_idempotent(db):
    emp = hours_employee()
    _with_pot_handling(emp)
    bank_holidays.sync_auto_absences(emp, Y0, Y1)
    assert bank_holidays.sync_auto_absences(emp, Y0, Y1) == {"created": 0, "removed": 0, "skipped": 0}


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
    assert bank_holidays.sync_auto_absences(emp, Y0, Y1) == {"created": 0, "removed": 0, "skipped": 0}


def test_day_already_booked_off_is_skipped_without_writing_anything(db, hr_admin):
    emp = hours_employee()
    _with_pot_handling(emp)
    bookings.request(hr_admin, emp, absence_type("AL"), date(2026, 5, 4))
    assert bank_holidays.sync_auto_absences(emp, Y0, Y1) == {"created": 9, "removed": 0, "skipped": 1}
    autos = Absence.objects.filter(employment=emp, auto_bank_holiday=True)
    assert not autos.filter(start_date=date(2026, 5, 4)).exists()
    count = Absence.objects.count()
    assert bank_holidays.sync_auto_absences(emp, Y0, Y1) == {"created": 0, "removed": 0, "skipped": 1}
    assert Absence.objects.count() == count


def test_bank_holiday_created_once_the_overlapping_leave_is_cancelled(db, hr_admin):
    emp = hours_employee()
    _with_pot_handling(emp)
    leave = bookings.request(hr_admin, emp, absence_type("AL"), date(2026, 5, 4))
    bank_holidays.sync_auto_absences(emp, Y0, Y1)
    bookings.cancel(hr_admin, leave)
    assert bank_holidays.sync_auto_absences(emp, Y0, Y1) == {"created": 1, "removed": 0, "skipped": 0}
    assert Absence.objects.get(employment=emp, auto_bank_holiday=True, start_date=date(2026, 5, 4)).status == "approved"
