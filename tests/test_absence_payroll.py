from datetime import date, timedelta
from decimal import Decimal

import openpyxl
from django.core.management import call_command
from django.utils import timezone

from absence.models import Absence, AbsenceType, LedgerEntry, PayrollRun
from absence.services import bookings, ledger, payroll, toil
from people.models import AuditEntry, PayRecord
from people.services import contracts, employments
from tests.factories import (absence_type, hours_employee, make_contract_type, make_employee, make_policy,
                             make_pot)

JUNE = (date(2026, 6, 1), date(2026, 6, 30))


def _sheet(wb, name):
    ws = wb[name]
    return [[c.value for c in row] for row in ws.iter_rows()]


def _cells(wb):
    return [str(c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row if c.value is not None]


def test_sections(db, hr_admin, employee_user):
    starter = hours_employee(start=date(2026, 6, 15))
    leaver = hours_employee(employee=make_employee(first="Lee"), start=date(2025, 1, 1))
    employments.end(hr_admin, leaver, date(2026, 6, 20), "resigned")
    changed = hours_employee(employee=make_employee(first="Cha"), start=date(2025, 1, 1), amount=Decimal("20"))
    contracts.add(hr_admin, changed, make_contract_type(), Decimal("10"), date(2026, 6, 1))
    PayRecord.objects.create(employment=changed, from_date=date(2026, 6, 1), basis="annual", amount=26000)
    bookings.request(employee_user, changed, absence_type("SICK"), date(2026, 6, 3), date(2026, 6, 4), category="mental")
    unpaid = bookings.request(employee_user, changed, absence_type("UNPAID"), date(2026, 6, 10))
    bookings.approve(hr_admin, unpaid)
    ct = changed.contracts.first().contract_type
    make_policy(ct, "TOIL")
    toil.earn(hr_admin, changed, Decimal("2"), date(2026, 6, 5), "late")
    wb = payroll.build(*JUNE)
    assert wb.sheetnames == ["Starters", "Leavers", "Contract changes", "Pay changes", "Sickness", "Unpaid",
                             "Family leave", "TOIL"]
    assert _sheet(wb, "Starters")[1][0] == starter.employee.name
    assert _sheet(wb, "Leavers")[1][0] == leaver.employee.name
    assert any(r[0] == changed.employee.name for r in _sheet(wb, "Contract changes")[1:])
    assert _sheet(wb, "Pay changes")[1][3] == 26000
    sick_rows = _sheet(wb, "Sickness")
    assert sick_rows[1][1] == date(2026, 6, 3) and "mental" not in str(sick_rows)
    assert _sheet(wb, "Unpaid")[1][3] == 7.5
    assert _sheet(wb, "TOIL")[1][2] == 2


def test_sickness_category_appears_nowhere_in_the_workbook(db, employee_user):
    emp = hours_employee(start=date(2026, 6, 1))
    bookings.request(employee_user, emp, absence_type("SICK"), date(2026, 6, 3), category="mental")
    wb = payroll.build(*JUNE)
    assert _sheet(wb, "Sickness")[1][0] == emp.employee.name
    text = " ".join(_cells(wb)).lower()
    assert "mental" not in text and "category" not in text


def test_sheets_follow_type_flags_not_codes(db, employee_user, hr_admin):
    emp = hours_employee(start=date(2026, 6, 1))
    # a health-sensitive type of the practice's own goes to Sickness, dates only
    own = AbsenceType.objects.create(name="Long-term condition", code="LTC", payroll_reportable=True,
                                     health_sensitive=True, needs_approval=False)
    bookings.request(employee_user, emp, own, date(2026, 6, 3))
    # a type that is not payroll_reportable appears nowhere
    hidden = AbsenceType.objects.create(name="Sabbatical", code="SAB", paid=False, needs_approval=False)
    bookings.request(employee_user, emp, hidden, date(2026, 6, 10))
    # reportable and unpaid without being UNPAID (the seeded dependants leave) is still Unpaid
    bookings.request(employee_user, emp, absence_type("DEP"), date(2026, 6, 11))
    wb = payroll.build(*JUNE)
    assert [r[1] for r in _sheet(wb, "Sickness")[1:]] == [date(2026, 6, 3)]
    assert [r[5] for r in _sheet(wb, "Unpaid")[1:]] == ["Dependants leave"]
    assert "Sabbatical" not in " ".join(_cells(wb))


def test_family_leave_sheet_clips_to_the_month_and_counts_its_kit_days(db, employee_user, hr_admin):
    emp = hours_employee(start=date(2025, 1, 1))
    a = bookings.request(employee_user, emp, absence_type("MAT"), date(2026, 5, 18), date(2027, 2, 12),
                         expected_start=date(2026, 5, 4), expected_return=date(2027, 2, 15))
    bookings.approve(hr_admin, a)
    bookings.add_kit_day(employee_user, a, date(2026, 8, 3))
    bookings.add_kit_day(employee_user, a, date(2026, 6, 9))
    rows = _sheet(payroll.build(*JUNE), "Family leave")
    assert rows[0][:4] == ["Name", "Type", "From", "To"]
    assert rows[1] == [emp.employee.name, "Maternity leave", date(2026, 6, 1), date(2026, 6, 30), date(2026, 5, 4), None,
                       date(2027, 2, 15), 1]


def test_toil_sheet_only_when_toil_is_paid(db, hr_admin):
    emp = hours_employee(start=date(2026, 6, 1))
    make_policy(emp.contracts.first().contract_type, "TOIL")
    toil.earn(hr_admin, emp, Decimal("2"), date(2026, 6, 5), "late")
    assert len(_sheet(payroll.build(*JUNE), "TOIL")) == 2
    AbsenceType.objects.filter(code="TOIL").update(paid=False)
    assert len(_sheet(payroll.build(*JUNE), "TOIL")) == 1        # headers only


def test_leavers_carry_pot_balances_at_the_leaving_date(db, hr_admin):
    emp = hours_employee(start=date(2025, 1, 1))
    pot = make_pot(emp, "AL", date(2026, 6, 1))
    ledger.write(pot, LedgerEntry.Kind.ADJUSTMENT, Decimal("-300"), hr_admin, note="over-taken", date=date(2026, 6, 2))
    employments.end(hr_admin, emp, date(2026, 6, 20), "resigned")
    rows = _sheet(payroll.build(*JUNE), "Leavers")
    header, row = rows[0], rows[1]
    assert header[:4] == ["Name", "Last day", "Reason", "Unit"]
    col = header.index("Annual leave balance")
    assert row[col] == float(ledger.balance(pot)) < 0           # a debt reaches payroll
    assert row[2] == "Resigned" and row[3] == "hours"
    assert row[header.index("Bank holiday balance")] in (None, 0)   # not a pot with a policy: blank or nil


def test_leaver_without_policy_for_a_type_has_a_blank_balance(db, hr_admin):
    emp = hours_employee(start=date(2025, 1, 1))
    employments.end(hr_admin, emp, date(2026, 6, 20), "resigned")
    rows = _sheet(payroll.build(*JUNE), "Leavers")
    assert rows[1][rows[0].index("Annual leave balance")] is None     # no pot open yet


def test_run_saves_file_and_row(db, hr_admin, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    hours_employee(start=date(2026, 6, 15))
    run = payroll.run(hr_admin, date(2026, 6, 1), date(2026, 6, 30))
    assert (tmp_path / "payroll" / "2026-06.xlsx").exists()
    assert run.counts["Starters"] == 1 and PayrollRun.objects.count() == 1
    assert run.path == "payroll/2026-06.xlsx" and run.generated_by == hr_admin
    assert openpyxl.load_workbook(tmp_path / run.path)["Starters"].max_row == 2
    assert AuditEntry.objects.filter(model="absence.payrollrun", object_id=run.pk).exists()


def test_generating_a_period_again_records_a_second_run_and_replaces_the_file(db, hr_admin, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    hours_employee(start=date(2026, 6, 15))
    first = payroll.run(hr_admin, *JUNE)
    hours_employee(employee=make_employee(first="Late"), start=date(2026, 6, 20))
    second = payroll.run(hr_admin, *JUNE)
    assert PayrollRun.objects.count() == 2 and first.counts["Starters"] == 1 and second.counts["Starters"] == 2
    assert list((tmp_path / "payroll").iterdir()) == [tmp_path / "payroll" / "2026-06.xlsx"]
    assert openpyxl.load_workbook(tmp_path / second.path)["Starters"].max_row == 3


def test_view_requires_hr_admin(employee_client, admin_client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    assert employee_client.get("/absence/payroll/").status_code == 403
    assert employee_client.post("/absence/payroll/", {"period": "2026-06"}).status_code == 403
    assert admin_client.get("/absence/payroll/").status_code == 200
    r = admin_client.post("/absence/payroll/", {"period": "2026-06"})
    assert r.status_code == 200 and r["Content-Type"].startswith("application/vnd.openxmlformats")
    assert "2026-06.xlsx" in r["Content-Disposition"]
    assert PayrollRun.objects.count() == 1


def test_view_lists_runs_and_rejects_a_bad_period(admin_client, hr_admin, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    payroll.run(hr_admin, *JUNE)
    assert b"June 2026" in admin_client.get("/absence/payroll/").content
    r = admin_client.post("/absence/payroll/", {"period": "2026-13"})
    assert r.status_code == 200 and not r["Content-Type"].startswith("application/vnd") and PayrollRun.objects.count() == 1
    assert admin_client.post("/absence/payroll/", {"period": "junk"}).status_code == 200


def test_command_writes_the_month(db, settings, tmp_path, capsys):
    settings.MEDIA_ROOT = tmp_path
    hours_employee(start=date(2026, 2, 10))
    call_command("payroll_report", period="2026-02")
    run = PayrollRun.objects.get()
    assert (run.period_start, run.period_end) == (date(2026, 2, 1), date(2026, 2, 28)) and run.generated_by is None
    assert str(tmp_path / "payroll" / "2026-02.xlsx") in capsys.readouterr().out


def test_a_spanning_unpaid_absence_is_split_between_the_months(db, hr_admin, employee_user):
    emp = hours_employee(start=date(2026, 4, 1))
    a = bookings.request(employee_user, emp, absence_type("UNPAID"), date(2026, 6, 29), date(2026, 7, 3))
    bookings.approve(hr_admin, a)
    june = _sheet(payroll.build(date(2026, 6, 1), date(2026, 6, 30)), "Unpaid")
    july = _sheet(payroll.build(date(2026, 7, 1), date(2026, 7, 31)), "Unpaid")
    assert june[0][:5] == ["Name", "From", "To", "Units", "Unit"]
    assert june[1][1:5] == [date(2026, 6, 29), date(2026, 6, 30), 15.0, "hours"]
    assert july[1][1:5] == [date(2026, 7, 1), date(2026, 7, 3), 22.5, "hours"]
    assert june[1][3] + july[1][3] == float(Absence.objects.get(pk=a.pk).cost_units)


def test_a_spanning_sickness_absence_is_clipped_to_the_month(db, employee_user):
    emp = hours_employee(start=date(2026, 4, 1))
    bookings.request(employee_user, emp, absence_type("SICK"), date(2026, 6, 29), date(2026, 7, 3), category="illness")
    assert _sheet(payroll.build(*JUNE), "Sickness")[1][1:] == [date(2026, 6, 29), date(2026, 6, 30), "Yes"]
    assert _sheet(payroll.build(date(2026, 7, 1), date(2026, 7, 31)), "Sickness")[1][1:] == [
        date(2026, 7, 1), date(2026, 7, 3), "Yes"]


def test_leaver_balance_ignores_lines_dated_after_the_leaving_date_but_keeps_the_proration(db, hr_admin):
    # recorded the day after the last day, whatever today is: the pro-rating
    # revision is dated today, after the leaving date
    today = timezone.localdate()
    leaving = today - timedelta(days=1)
    emp = hours_employee(start=leaving - timedelta(days=500))
    pot = make_pot(emp, "AL", leaving)
    employments.end(hr_admin, emp, leaving, "resigned")               # pro-rates the entitlement
    ledger.sync_entitlement(pot)      # the signal only re-syncs open pots: yesterday's year may have ended
    at_leaving = ledger.balance(pot)
    assert pot.entries.filter(kind=LedgerEntry.Kind.REVISION, date__gt=leaving).exists()
    ledger.write(pot, LedgerEntry.Kind.ADJUSTMENT, Decimal("-40"), hr_admin, note="later", date=today)
    rows = _sheet(payroll.build(*payroll.month(f"{leaving:%Y-%m}")), "Leavers")
    assert rows[1][rows[0].index("Annual leave balance")] == float(at_leaving)
    assert ledger.balance(pot) == at_leaving - 40


def test_automatic_bank_holiday_rows_are_never_reported(db):
    emp = hours_employee(start=date(2026, 4, 1))
    AbsenceType.objects.filter(code="BH").update(paid=False, payroll_reportable=True)
    Absence.objects.create(employment=emp, absence_type=absence_type("BH"), status=Absence.Status.APPROVED,
                           start_date=date(2026, 6, 8), end_date=date(2026, 6, 8), cost_units=Decimal("7.5"),
                           auto_bank_holiday=True)
    assert len(_sheet(payroll.build(*JUNE), "Unpaid")) == 1       # headers only


def test_toil_carried_at_year_end_is_listed_once_in_its_month(db, hr_admin):
    from absence.services import year_end
    emp = hours_employee(start=date(2026, 1, 1))
    make_policy(emp.contracts.first().contract_type, "TOIL", weeks_per_year=Decimal("0"), toil_expires_after_days=90)
    toil.earn(hr_admin, emp, Decimal("3"), date(2027, 3, 10), "late clinic")
    year_end.run(date(2027, 4, 1))                     # carries the 3 to the 2027/28 pot, dated 10 Mar
    rows = _sheet(payroll.build(date(2027, 3, 1), date(2027, 3, 31)), "TOIL")[1:]
    assert [(r[1], r[2], r[3]) for r in rows] == [(date(2027, 3, 10), 3.0, "TOIL earned")]


def test_sickness_sheet_says_whether_it_was_self_certified(db, employee_user):
    emp = hours_employee(start=date(2026, 4, 1))
    bookings.request(employee_user, emp, absence_type("SICK"), date(2026, 6, 1), date(2026, 6, 3), category="illness")
    bookings.request(employee_user, emp, absence_type("SICK"), date(2026, 6, 8), date(2026, 6, 19), category="injury")
    rows = _sheet(payroll.build(*JUNE), "Sickness")
    assert rows[0] == ["Name", "From", "To", "Self-certified"]
    assert [r[1:] for r in rows[1:]] == [[date(2026, 6, 1), date(2026, 6, 3), "Yes"],
                                          [date(2026, 6, 8), date(2026, 6, 19), "No"]]
    assert "injury" not in str(rows) and "illness" not in str(rows)
