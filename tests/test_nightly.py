from datetime import date

from django.contrib.auth import get_user_model

from people.services import nightly
from tests.factories import make_employee, make_employment

User = get_user_model()


def test_leaver_login_disabled_returner_kept(db):
    u1 = User.objects.create_user(email="left@example.org", password="pw")
    u2 = User.objects.create_user(email="back@example.org", password="pw")
    left = make_employee(first="Lee", user=u1)
    make_employment(employee=left, start=date(2025, 1, 1), end_date=date(2026, 5, 31), leaving_reason="resigned")
    back = make_employee(first="Bea", user=u2)
    make_employment(employee=back, start=date(2025, 1, 1), end_date=date(2026, 5, 31), leaving_reason="resigned")
    make_employment(employee=back, start=date(2026, 7, 1))
    result = nightly.run(date(2026, 6, 1))
    assert result == {"logins_disabled": 1}
    assert not User.objects.get(pk=u1.pk).is_active
    assert User.objects.get(pk=u2.pk).is_active


def test_command_runs(db, capsys):
    from django.core.management import call_command
    call_command("hr_nightly")
    assert "logins_disabled" in capsys.readouterr().out


def test_the_command_runs_for_the_practices_day(db, monkeypatch):
    from datetime import date

    from django.core.management import call_command
    from django.utils import timezone

    from people.services import nightly
    seen = []
    monkeypatch.setattr(timezone, "localdate", lambda *a, **k: date(2026, 7, 1))
    monkeypatch.setattr(nightly, "run", lambda today: seen.append(today) or {})
    call_command("hr_nightly")
    assert seen == [date(2026, 7, 1)]
