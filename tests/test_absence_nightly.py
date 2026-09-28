from datetime import date
from decimal import Decimal

from absence.services import nightly, pots
from tests.factories import (absence_type, hours_employee, make_contract, make_contract_type,
                             make_employment, make_pattern, make_policy)


def test_nightly_syncs_open_pots_and_bank_holidays(db):
    emp = hours_employee(start=date(2026, 4, 1))
    pot = pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))     # opened with 210.00
    emp.contracts.update(weekly_amount=Decimal("18.75"))              # behind the signals' back
    result = nightly.run(date(2026, 6, 1))
    assert result["pots_opened"] == 0
    assert result["pots_synced"] == 1 and result["revisions"] == 1
    assert pot.entries.get(kind="revision").units == Decimal("-105.00")
    assert nightly.run(date(2026, 6, 1))["revisions"] == 0


def test_command_includes_absence(db, capsys):
    from django.core.management import call_command
    call_command("hr_nightly")
    assert "absence:" in capsys.readouterr().out


def test_a_pot_with_no_policy_is_reported_and_the_rest_still_sync(db):
    good = hours_employee(start=date(2026, 4, 1))
    other = make_contract_type("Other")
    bad = make_employment(start=date(2026, 4, 1))
    make_contract(bad, other)
    make_policy(other)
    make_pattern(bad)
    al = absence_type("AL")
    pots.for_day(good, al, date(2026, 6, 1))
    bad_pot = pots.for_day(bad, al, date(2026, 6, 1))
    other.policies.all().delete()   # the policy ends: no policy covers the pot's year
    result = nightly.run(date(2026, 6, 1))
    assert result["pots_synced"] == 1 and result["revisions"] == 0    # good opened with its entitlement
    assert len(result["failed"]) == 1 and str(bad_pot) in result["failed"][0]


def test_bank_holiday_keys_count_created_then_nothing(db):
    from absence.models import Policy
    emp = hours_employee()
    ct = emp.contracts.first().contract_type
    ct.policies.filter(absence_type__code="AL").update(bank_holiday_handling=Policy.BankHolidays.PRO_RATA_POT)
    make_policy(ct, "BH", bank_holiday_handling="pot")
    first = nightly.run(date(2026, 6, 1))                            # opens the pots itself
    assert first["bank_holiday_created"] == 10 and first["failed"] == []
    second = nightly.run(date(2026, 6, 1))
    assert second["bank_holiday_created"] == 0 and second["bank_holiday_removed"] == 0
    assert second["bank_holiday_recosted"] == 0


def test_missing_bank_holiday_policy_is_reported_in_failed(db):
    from absence.models import Policy
    emp = hours_employee()
    pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    emp.contracts.first().contract_type.policies.filter(absence_type__code="AL").update(
        bank_holiday_handling=Policy.BankHolidays.PRO_RATA_POT)
    result = nightly.run(date(2026, 6, 1))
    assert any("No Bank holiday policy for Reception" in f for f in result["failed"])
    assert result["bank_holiday_created"] == 0


def test_nightly_removes_automatic_bank_holidays_after_the_leaving_date(db, hr_admin):
    from absence.models import Absence, LedgerEntry, Policy
    from absence.services import bank_holidays
    from people.services import contracts, employments
    emp = hours_employee(start=date(2026, 4, 1))
    ct = emp.contracts.first().contract_type
    ct.policies.filter(absence_type__code="AL").update(bank_holiday_handling=Policy.BankHolidays.PRO_RATA_POT)
    make_policy(ct, "BH", bank_holiday_handling="pot")
    pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    bank_holidays.sync_auto_absences(emp, date(2026, 4, 1), date(2027, 3, 31))
    contracts.end(hr_admin, emp.contracts.get(), date(2026, 11, 30))
    employments.end(hr_admin, emp, date(2026, 11, 30), "resigned")
    result = nightly.run(date(2026, 10, 1))
    # 25 and 28 Dec, 1 Jan, and Easter 2027 fall after the leaving date
    assert result["bank_holiday_removed"] == 5 and result["failed"] == []
    live = Absence.objects.filter(employment=emp, auto_bank_holiday=True, status="approved")
    assert live.count() == 5 and max(a.start_date for a in live) <= date(2026, 11, 30)
    cancellations = LedgerEntry.objects.filter(kind=LedgerEntry.Kind.CANCELLATION)
    assert cancellations.count() == 5 and {c.pot.absence_type.code for c in cancellations} == {"BH"}


def _pot_handling(emp):
    from absence.models import Policy
    ct = emp.contracts.first().contract_type
    ct.policies.filter(absence_type__code="AL").update(bank_holiday_handling=Policy.BankHolidays.PRO_RATA_POT)
    make_policy(ct, "BH", bank_holiday_handling="pot")


def test_a_new_starter_gets_entitlement_and_bank_holidays_from_one_run(db):
    from absence.models import Absence, LedgerEntry
    from absence.services import ledger
    emp = hours_employee(start=date(2026, 4, 1))       # never booked: no pot yet
    _pot_handling(emp)
    result = nightly.run(date(2026, 6, 1))
    assert result["pots_opened"] == 2 and result["failed"] == []
    assert result["bank_holiday_created"] == 10
    al = pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    bh = pots.for_day(emp, absence_type("BH"), date(2026, 6, 1))
    assert al.entries.get(kind=LedgerEntry.Kind.ENTITLEMENT).units == Decimal("210.00")
    assert bh.entries.get(kind=LedgerEntry.Kind.ENTITLEMENT).units == Decimal("75.00")
    assert Absence.objects.filter(employment=emp, auto_bank_holiday=True, status="approved").count() == 10
    assert ledger.balance(bh) == Decimal("0.00")        # 75 accrued, ten 7.5-hour days charged
    again = nightly.run(date(2026, 6, 1))
    assert (again["pots_opened"], again["revisions"], again["bank_holiday_created"]) == (0, 0, 0)


def test_bootstrap_reports_an_employment_with_no_policy(db):
    other = make_contract_type("Other")
    emp = make_employment(start=date(2026, 4, 1))
    make_contract(emp, other)
    make_pattern(emp)
    result = nightly.run(date(2026, 6, 1))
    assert result["pots_opened"] == 0
    assert len(result["failed"]) == 1 and "No Annual leave policy for Other" in result["failed"][0]
    assert str(emp) in result["failed"][0]


def test_bootstrap_skips_employments_not_active_today(db):
    hours_employee(start=date(2026, 7, 1))              # starts next month
    assert nightly.run(date(2026, 6, 1))["pots_opened"] == 0
