from datetime import date

from absence.services import nightly, pots
from tests.factories import (absence_type, hours_employee, make_contract, make_contract_type,
                             make_employment, make_pattern, make_policy)


def test_nightly_syncs_open_pots_and_bank_holidays(db):
    emp = hours_employee(start=date(2026, 4, 1))
    pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    result = nightly.run(date(2026, 6, 1))
    assert result["pots_synced"] == 1 and result["revisions"] == 1
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
    assert result["pots_synced"] == 1 and result["revisions"] == 1
    assert len(result["failed"]) == 1 and str(bad_pot) in result["failed"][0]


def test_bank_holiday_keys_count_created_then_nothing(db):
    from absence.models import Policy
    emp = hours_employee()
    ct = emp.contracts.first().contract_type
    ct.policies.filter(absence_type__code="AL").update(bank_holiday_handling=Policy.BankHolidays.PRO_RATA_POT)
    make_policy(ct, "BH", bank_holiday_handling="pot")
    pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    first = nightly.run(date(2026, 6, 1))
    assert first["bank_holiday_created"] == 10 and first["failed"] == []
    second = nightly.run(date(2026, 6, 1))
    assert second["bank_holiday_created"] == 0 and second["bank_holiday_removed"] == 0


def test_missing_bank_holiday_policy_is_reported_in_failed(db):
    from absence.models import Policy
    emp = hours_employee()
    pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    emp.contracts.first().contract_type.policies.filter(absence_type__code="AL").update(
        bank_holiday_handling=Policy.BankHolidays.PRO_RATA_POT)
    result = nightly.run(date(2026, 6, 1))
    assert any("No Bank holiday policy for Reception" in f for f in result["failed"])
    assert result["bank_holiday_created"] == 0
