"""SHIFT_CENTRAL_URL set: leave lives in AMG Shift Central (its requirements,
PAT-07), so Practice HR's own leave is switched off. The screens say where
leave is, the nightly leaves the pots alone, the payroll file keeps only what
HR still holds, and the absences feed is empty. Nothing is deleted: unset the
setting and everything is as it was (every other test file runs with it unset)."""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.checks import Warning as CheckWarning
from django.test import Client

from absence.models import Absence, LedgerEntry, Pot
from absence.services import bookings, ledger, nightly, payroll
from hr.checks import shift_central_url
from people.services import employments, positions
from tests.factories import absence_type, hours_employee, make_employee, make_employment, make_pot, make_team

User = get_user_model()
SC = "https://shiftcentral.example.org"
JUNE = (date(2026, 6, 1), date(2026, 6, 30))
LEAVE_PAGES = ("/absence/mine/", "/absence/request/", "/absence/calendar/", "/absence/balances/",
               "/absence/balances/team/", "/absence/queue/", "/absence/toil/claim/", "/absence/decide/1/",
               "/absence/toil/1/decide/", "/absence/ledger/1/")


@pytest.fixture
def elsewhere(settings):
    settings.SHIFT_CENTRAL_URL = SC


def _split(body):
    return body.split('<nav class="tabbar"')


def _approver_client(emp):
    boss_user = User.objects.create_user(email="boss@example.org", password="pw")
    boss = make_employee(first="Boss", user=boss_user)
    make_employment(employee=boss, start=date(2026, 1, 1))
    positions.add(None, emp, "Receptionist", make_team(), boss, emp.start_date)
    c = Client()
    c.force_login(boss_user)
    return c


# --- the screens ---------------------------------------------------------------------------------

def test_the_navigation_drops_leave_and_links_to_shift_central(elsewhere, employee_client, employee_user):
    emp = hours_employee(employee=make_employee(user=employee_user))
    for client in (employee_client, _approver_client(emp)):
        desktop, tabbar = _split(client.get("/people/me/").content.decode())
        assert "/absence/" not in desktop + tabbar
        assert "Approvals" not in desktop + tabbar and "Balances" not in desktop + tabbar
        assert f'href="{SC}/" class="nav-link"' in desktop and "Leave and rota" in desktop
        assert f'href="{SC}/" class="tabbar-item"' in tabbar


def test_without_the_setting_the_navigation_is_unchanged(employee_client, employee_user):
    hours_employee(employee=make_employee(user=employee_user))
    body = employee_client.get("/people/me/").content.decode()
    assert 'href="/absence/mine/" class="nav-link' in body and "Leave and rota" not in body


@pytest.mark.parametrize("path", LEAVE_PAGES)
def test_every_leave_page_says_where_leave_is_now(elsewhere, employee_client, employee_user, path):
    hours_employee(employee=make_employee(user=employee_user))
    r = employee_client.get(path)
    body = r.content.decode()
    assert r.status_code == 200
    assert "Leave is now in AMG Shift Central" in body and f'href="{SC}/"' in body


def test_a_leave_page_from_an_old_email_needs_no_sign_in_to_say_so(elsewhere, client, db):
    r = client.get("/absence/decide/7/")          # the link in an approver's old email
    assert r.status_code == 200 and "Leave is now in AMG Shift Central" in r.content.decode()


def test_nothing_can_be_requested_or_decided(elsewhere, employee_client, employee_user):
    emp = hours_employee(employee=make_employee(user=employee_user))
    make_pot(emp, "AL", date(2026, 6, 1))
    r = employee_client.post("/absence/request/", {"absence_type": absence_type("AL").pk,
                                                    "start_date": "2026-06-08", "end_date": "2026-06-09"})
    assert r.status_code == 200 and "Leave is now in AMG Shift Central" in r.content.decode()
    assert Absence.objects.count() == 0


def test_the_payroll_page_stays(elsewhere, admin_client):
    r = admin_client.get("/absence/payroll/")
    assert r.status_code == 200 and "Leave is now in AMG Shift Central" not in r.content.decode()


# --- the admin -----------------------------------------------------------------------------------

def test_the_admin_drops_the_waiting_card_and_the_leave_menu(elsewhere, admin_client):
    body = admin_client.get("/admin/").content.decode()
    assert "Leave requests and TOIL claims waiting" not in body
    for gone in ("/admin/absence/policy/", "/admin/absence/pot/", "/admin/absence/absence/", "/admin/absence/absencetype/"):
        assert f'href="{gone}"' not in body, gone
    assert 'href="/absence/payroll/"' in body and "Compliance" in body


def test_without_the_setting_the_admin_keeps_both(admin_client):
    body = admin_client.get("/admin/").content.decode()
    assert "Leave requests and TOIL claims waiting" in body and 'href="/admin/absence/policy/"' in body


# --- the nightly -----------------------------------------------------------------------------------

def test_the_nightly_leaves_leave_alone(elsewhere, db):
    hours_employee(start=date(2025, 1, 1))
    assert nightly.run(date(2026, 6, 1)) == {"skipped": "leave is in Shift Central"}
    assert Pot.objects.count() == 0 and LedgerEntry.objects.count() == 0 and Absence.objects.count() == 0


def test_the_nightly_command_still_runs_its_other_steps(elsewhere, db, capsys):
    from django.core.management import call_command
    call_command("hr_nightly")
    out = capsys.readouterr().out
    assert "absence: {'skipped': 'leave is in Shift Central'}" in out and "logins_disabled" in out and "compliance:" in out


# --- the payroll file ------------------------------------------------------------------------------

def test_the_payroll_file_keeps_only_what_hr_still_holds(elsewhere, db, hr_admin, employee_user):
    emp = hours_employee(start=date(2025, 1, 1), employee=make_employee(user=employee_user))
    pot = make_pot(emp, "AL", date(2026, 6, 1))
    ledger.write(pot, LedgerEntry.Kind.ADJUSTMENT, Decimal("-300"), hr_admin, note="over-taken", date=date(2026, 6, 2))
    bookings.record(hr_admin, emp, absence_type("SICK"), date(2026, 6, 3), date(2026, 6, 4))
    employments.end(hr_admin, emp, date(2026, 6, 20), "resigned")
    wb = payroll.build(*JUNE)
    assert wb.sheetnames == ["Starters", "Leavers", "Contract changes", "Pay changes"]
    rows = [[c.value for c in row] for row in wb["Leavers"].iter_rows()]
    assert rows[0] == ["Name", "Last day", "Reason", "Unit"]          # no balance columns: HR's pots are not the record
    assert rows[1][0] == "Sam Patel" and len(rows[1]) == 4


def test_without_the_setting_the_payroll_file_has_every_sheet(db):
    assert payroll.build(*JUNE).sheetnames == payroll.SHEETS and len(payroll.SHEETS) == 8


# --- the feed --------------------------------------------------------------------------------------

def test_the_absences_feed_is_empty(elsewhere, client, settings, hr_admin, employee_user):
    settings.HR_API_TOKENS = frozenset({"t0k"})
    emp = hours_employee(start=date(2025, 1, 1), employee=make_employee(user=employee_user))
    bookings.record(hr_admin, emp, absence_type("SICK"), date(2026, 6, 3), date(2026, 6, 4))
    r = client.get("/api/v1/absences?from=2026-06-01&to=2026-06-30", HTTP_AUTHORIZATION="Bearer t0k")
    assert r.status_code == 200 and r.json() == {"absences": []}
    assert client.get("/api/v1/absences", HTTP_AUTHORIZATION="Bearer t0k").status_code == 400     # still checked
    assert client.get("/api/v1/people", HTTP_AUTHORIZATION="Bearer t0k").json()["people"]          # the rest is unchanged


# --- the setting -----------------------------------------------------------------------------------

@pytest.mark.parametrize("value,stored", [("https://sc.example.org/", "https://sc.example.org"), ("", "")])
def test_the_setting_is_read_from_the_environment(value, stored):
    import os
    import subprocess
    import sys
    env = {**os.environ, "DEBUG": "1", "DJANGO_SETTINGS_MODULE": "config.settings", "SHIFT_CENTRAL_URL": value}
    out = subprocess.run([sys.executable, "-c", "import django; django.setup(); from django.conf import settings; "
                          "print(repr(settings.SHIFT_CENTRAL_URL))"], env=env, capture_output=True, text=True, check=True)
    assert out.stdout.strip() == repr(stored)


@pytest.mark.parametrize("value", ["shiftcentral.example.org", "http://shiftcentral.example.org", "javascript:alert(1)"])
def test_an_address_that_is_not_https_is_a_warning(settings, value):
    settings.DEBUG = False
    settings.SHIFT_CENTRAL_URL = value
    (w,) = shift_central_url(None)
    assert isinstance(w, CheckWarning) and w.id == "hr.W003" and "https://" in w.hint


def test_a_good_address_or_none_is_no_warning(settings):
    settings.DEBUG = False
    for value in ("", SC):
        settings.SHIFT_CENTRAL_URL = value
        assert shift_central_url(None) == []
