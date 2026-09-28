from datetime import date

from absence.services import nightly, pots
from tests.factories import absence_type, hours_employee


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
