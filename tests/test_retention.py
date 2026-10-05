"""The retention report: who is past their retention period, by category.
Read-only, HR admin only. Dates are derived from today, so nothing here
expires with the calendar."""

import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone

from people.services import retention
from tests.factories import make_employee, make_employment

ROOT = Path(__file__).resolve().parents[1]
SHORT = {"personal": 30, "pay": 60, "health": 60, "audit": 90}


def _left(days_ago, first="Old", **kw):
    """An employee whose last employment ended `days_ago` days ago."""
    today = timezone.localdate()
    e = make_employee(first=first, **kw)
    make_employment(employee=e, start=today - timedelta(days=days_ago + 2000),
                    end_date=today - timedelta(days=days_ago), leaving_reason="resigned")
    return e


def test_due_lists_leavers_past_period(db, settings):
    settings.RETENTION_DAYS = SHORT
    old = _left(100, first="Old")
    fresh = _left(10, first="New")
    rows = retention.due(timezone.localdate())
    cats = {(r["employee"].pk, r["category"]) for r in rows}
    assert (old.pk, "personal") in cats and (old.pk, "pay") in cats and (old.pk, "audit") in cats
    assert (old.pk, "health") in cats
    assert all(pk != fresh.pk for pk, _ in cats)


def test_due_reports_when_the_period_ended_and_when_it_fell_due(db, settings):
    settings.RETENTION_DAYS = SHORT
    today = timezone.localdate()
    e = _left(45)
    (row,) = retention.due(today)      # only "personal" (30) has passed at 45 days
    assert row["category"] == "personal"
    assert row["employee"] == e
    assert row["ended"] == today - timedelta(days=45)
    assert row["due_since"] == today - timedelta(days=15)


def test_a_category_is_due_only_after_its_last_day(db, settings):
    settings.RETENTION_DAYS = SHORT
    _left(30)                           # the period ends today: not yet past it
    assert retention.due(timezone.localdate()) == []
    _left(31, first="Later")
    assert [r["category"] for r in retention.due(timezone.localdate())] == ["personal"]


def test_a_current_employee_is_never_due(db, settings):
    settings.RETENTION_DAYS = SHORT
    today = timezone.localdate()
    make_employment(employee=make_employee(first="Open"), start=today - timedelta(days=3000))
    make_employment(employee=make_employee(first="Ends"), start=today - timedelta(days=3000),
                    end_date=today + timedelta(days=5))
    assert retention.due(today) == []


def test_someone_who_returned_is_not_due_for_their_first_spell(db, settings):
    settings.RETENTION_DAYS = SHORT
    today = timezone.localdate()
    e = make_employee(first="Back")
    make_employment(employee=e, start=today - timedelta(days=3000),
                    end_date=today - timedelta(days=500), leaving_reason="resigned")
    make_employment(employee=e, start=today - timedelta(days=100))
    assert retention.due(today) == []


def test_someone_about_to_rejoin_is_not_due(db, settings):
    settings.RETENTION_DAYS = SHORT
    today = timezone.localdate()
    e = make_employee(first="Soon")
    make_employment(employee=e, start=today - timedelta(days=3000),
                    end_date=today - timedelta(days=500), leaving_reason="resigned")
    make_employment(employee=e, start=today + timedelta(days=7))
    assert retention.due(today) == []


def test_the_clock_is_the_local_date_not_the_server_date(db, settings):
    """Judged on the date passed in, so the view can hand it timezone.localdate()."""
    settings.RETENTION_DAYS = SHORT
    e = _left(100)
    long_ago = timezone.localdate() - timedelta(days=500)
    assert retention.due(long_ago) == []
    assert {r["employee"] for r in retention.due(timezone.localdate())} == {e}


# --- the page -----------------------------------------------------------------

def test_view_is_admin_only(employee_client, admin_client):
    assert employee_client.get("/people/retention/").status_code == 403
    assert admin_client.get("/people/retention/").status_code == 200


def test_anonymous_is_sent_to_sign_in(client, db):
    r = client.get("/people/retention/")
    assert r.status_code == 302 and "/accounts/login/" in r["Location"]


def test_superuser_may_see_it(superuser_client):
    assert superuser_client.get("/people/retention/").status_code == 200


def test_page_lists_who_which_category_and_how_overdue(admin_client, settings):
    settings.RETENTION_DAYS = SHORT
    _left(100, first="Olive", last="Overdue")
    _left(10, first="Fiona", last="Fresh")
    body = admin_client.get("/people/retention/").content.decode()
    assert "Olive Overdue" in body
    assert "Fiona Fresh" not in body
    ended = timezone.localdate() - timedelta(days=100)
    assert ended.strftime("%-d %b %Y") in body
    assert "70 days" in body            # personal: 100 - 30
    assert "10 days" in body            # audit:    100 - 90
    assert "manual" in body.lower()     # nothing is deleted for them


def test_page_says_so_when_nothing_is_due(admin_client, settings):
    settings.RETENTION_DAYS = SHORT
    assert "Nothing is past its retention period" in admin_client.get("/people/retention/").content.decode()


def test_page_is_read_only(admin_client, settings, db):
    from people.models import Employee
    settings.RETENTION_DAYS = SHORT
    _left(100)
    assert admin_client.post("/people/retention/").status_code == 405
    assert Employee.objects.count() == 1


def test_page_shows_no_sickness_or_pay_detail(admin_client, settings):
    settings.RETENTION_DAYS = SHORT
    e = _left(100, first="Olive", last="Overdue")
    from absence.models import Absence
    from tests.factories import absence_type
    Absence.objects.create(employment=e.employments.get(), absence_type=absence_type("SICK"), status="approved",
                           start_date=timezone.localdate() - timedelta(days=200),
                           end_date=timezone.localdate() - timedelta(days=199))
    body = admin_client.get("/people/retention/").content.decode().lower()
    assert "sick" not in body and "£" not in body and "salary" not in body


def test_admin_navigation_has_retention_beside_payroll(admin_client, db):
    body = admin_client.get("/admin/").content.decode()
    assert 'href="/people/retention/"' in body
    assert body.index("/absence/payroll/") < body.index("/people/retention/") \
        < body.index("/admin/accounts/user/")


# --- the settings -----------------------------------------------------------------

def _settings_run(expr, env):
    base = {k: v for k, v in os.environ.items()
            if k not in ("DEBUG", "SECRET_KEY", "DB_PATH", "OIDC_RSA_PRIVATE_KEY",
                         "OIDC_RSA_PRIVATE_KEY_FILE")
            and not k.startswith("RETENTION_DAYS")}
    base.update({"DJANGO_SETTINGS_MODULE": "config.settings", "DEBUG": "1", **env})
    return subprocess.run(
        [sys.executable, "-c", f"from config import settings as s; print(repr({expr}))"],
        env=base, cwd=ROOT, capture_output=True, text=True)


def test_retention_defaults():
    r = _settings_run("s.RETENTION_DAYS", {})
    assert r.returncode == 0, r.stderr
    assert eval(r.stdout) == {"personal": 2190, "pay": 2190, "health": 2190, "audit": 2555,
                                 "checks": 2190, "files": 2190, "signatures": 2190}


def test_retention_days_are_overridable_per_category_from_the_environment():
    r = _settings_run("s.RETENTION_DAYS", {"RETENTION_DAYS_PAY": "3650", "RETENTION_DAYS_AUDIT": "100"})
    assert r.returncode == 0, r.stderr
    assert eval(r.stdout) == {"personal": 2190, "pay": 3650, "health": 2190, "audit": 100,
                                 "checks": 2190, "files": 2190, "signatures": 2190}


@pytest.mark.parametrize("bad", ["six years", "", "12.5", "0", "-30"])
def test_an_invalid_retention_value_is_a_clear_configuration_error(bad):
    r = _settings_run("s.RETENTION_DAYS", {"RETENTION_DAYS_HEALTH": bad})
    assert r.returncode != 0
    assert "ImproperlyConfigured" in r.stderr
    assert "RETENTION_DAYS_HEALTH" in r.stderr
