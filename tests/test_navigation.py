"""Who sees which navigation link, and how many items the mobile tab bar holds."""
import re
from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client

from people.services import positions
from tests.factories import hours_employee, make_employee, make_employment, make_team

User = get_user_model()


def _employee(user):
    return hours_employee(employee=make_employee(user=user))


def _approver_of(emp):
    boss_user = User.objects.create_user(email="boss@example.org", password="pw")
    boss = make_employee(first="Boss", user=boss_user)
    make_employment(employee=boss, start=date(2026, 1, 1))
    positions.add(None, emp, "Receptionist", make_team(), boss, emp.start_date)
    c = Client()
    c.force_login(boss_user)
    return c


def _split(body):
    desktop, tabbar = body.split('<nav class="tabbar"')
    return desktop, tabbar


def test_an_employee_sees_leave_calendar_and_balances_but_not_approvals(employee_client, employee_user):
    _employee(employee_user)
    desktop, tabbar = _split(employee_client.get("/absence/mine/").content.decode())
    for href in ("/absence/mine/", "/absence/calendar/", "/absence/balances/", "/documents/policies/"):
        assert f'href="{href}" class="nav-link' in desktop, href
    assert 'href="/documents/policies/" class="tabbar-link"' in tabbar
    assert "/absence/queue/" not in desktop + tabbar
    assert "/people/team/" not in desktop + tabbar
    assert "/admin/" not in desktop + tabbar


def test_an_approver_also_sees_approvals(employee_user):
    c = _approver_of(_employee(employee_user))
    desktop, tabbar = _split(c.get("/absence/mine/").content.decode())
    for href in ("/absence/mine/", "/absence/calendar/", "/absence/balances/", "/absence/queue/"):
        assert f'href="{href}" class="nav-link' in desktop, href
    assert 'href="/absence/queue/" class="tabbar-item' in tabbar


def test_an_hr_admin_sees_approvals_and_admin(admin_client, hr_admin):
    _employee(hr_admin)
    desktop, tabbar = _split(admin_client.get("/absence/mine/").content.decode())
    assert 'href="/absence/queue/" class="nav-link' in desktop
    assert 'href="/admin/" class="nav-link' in desktop
    assert 'href="/admin/" class="tabbar-link"' in tabbar


def test_the_admin_navigation_has_payroll_and_retention_for_hr_admins(admin_client, db):
    body = admin_client.get("/admin/").content.decode()
    assert 'href="/absence/payroll/"' in body and 'href="/people/retention/"' in body


def test_the_mobile_tab_bar_holds_at_most_five_items(employee_user, admin_client, hr_admin):
    """Approver and HR admin are the fullest bars; Calendar, Balances and Policies live in More."""
    _employee(hr_admin)
    approver = _approver_of(_employee(employee_user))
    for client in (approver, admin_client):
        tabbar = _split(client.get("/absence/mine/").content.decode())[1]
        outside_sheet = tabbar.split('<div class="tabbar-sheet">')[0]
        items = re.findall(r'class="tabbar-item', outside_sheet)      # "More" is the summary, counted here
        assert 1 <= len(items) <= 5
        assert "Calendar" not in outside_sheet and "Balances" not in outside_sheet
        sheet = tabbar.split('<div class="tabbar-sheet">')[1]
        assert 'href="/absence/calendar/"' in sheet and 'href="/absence/balances/"' in sheet
        assert "Policies" not in outside_sheet and 'href="/documents/policies/"' in sheet
