from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse

from absence.models import Absence, Pot
from absence.services import bookings, calendar, notify
from people.services import positions
from tests.factories import (absence_type, hours_employee, make_contract, make_employee, make_employment,
                             make_pattern, make_team)

User = get_user_model()


def _setup(employee_user):
    boss_user = User.objects.create_user(email="boss@example.org", password="pw")
    boss = make_employee(first="Boss", user=boss_user)
    make_employment(employee=boss, start=date(2026, 1, 1))
    emp = hours_employee(employee=make_employee(user=employee_user))
    positions.add(None, emp, "Receptionist", make_team(), boss, emp.start_date)
    c = Client()
    c.force_login(boss_user)
    a = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, 1), date(2026, 6, 3))
    return c, a, boss_user


def _decide(a):
    return reverse("absence:decide", args=[a.pk])


def test_decide_route_is_the_path_the_emails_link_to(db):
    assert reverse("absence:decide", args=[7]) == notify.DECIDE_PATH.format(pk=7)
    assert reverse("absence:queue") == "/absence/queue/"


def test_queue_lists_routed_requests_only(employee_user, employee_client):
    c, a, _ = _setup(employee_user)
    r = c.get(reverse("absence:queue"))
    body = r.content.decode()
    assert r.status_code == 200
    assert "Sam Patel" in body and "1 Jun 2026 – 3 Jun 2026" in body and _decide(a) in body
    assert employee_client.get(reverse("absence:queue")).status_code == 403


def test_queue_leaves_out_requests_routed_elsewhere_and_decided_ones(employee_user, admin_client):
    c, a, _ = _setup(employee_user)
    other_emp = make_employment(employee=make_employee(first="Peer", last="Jones"), start=date(2026, 1, 1))
    boss2 = make_employee(first="Second", last="Boss")
    make_employment(employee=boss2, start=date(2026, 1, 1))
    positions.add(None, other_emp, "Nurse", make_team("Nursing"), boss2, other_emp.start_date)
    Absence.objects.create(employment=other_emp, absence_type=absence_type("AL"),
                           start_date=date(2026, 7, 6), end_date=date(2026, 7, 6))
    body = c.get(reverse("absence:queue")).content.decode()
    assert "Sam Patel" in body and "Peer Jones" not in body
    # HR admin sees both
    body = admin_client.get(reverse("absence:queue")).content.decode()
    assert "Sam Patel" in body and "Peer Jones" in body
    bookings.decline(User.objects.get(email="boss@example.org"), a)
    assert "Sam Patel" not in c.get(reverse("absence:queue")).content.decode()


def test_decide_approves_and_records_decider(employee_user):
    c, a, boss_user = _setup(employee_user)
    r = c.post(_decide(a), {"action": "approve", "comment": "ok"})
    assert r.status_code == 302 and r.url == reverse("absence:queue")
    a.refresh_from_db()
    assert a.status == "approved" and a.decided_by == boss_user and a.decision_comment == "ok"


def test_hr_admin_can_decide_a_request_routed_to_a_manager(employee_user, admin_client, hr_admin):
    _, a, _ = _setup(employee_user)
    r = admin_client.post(_decide(a), {"action": "decline", "comment": "no"})
    assert r.status_code == 302
    a.refresh_from_db()
    assert a.status == "declined" and a.decided_by == hr_admin


def test_hr_admin_cannot_decide_their_own_request(admin_client, hr_admin):
    emp = hours_employee(employee=make_employee(first="Hera", user=hr_admin))
    a = bookings.request(hr_admin, emp, absence_type("AL"), date(2026, 6, 1))
    assert "Hera" not in admin_client.get(reverse("absence:queue")).content.decode()
    assert admin_client.get(_decide(a)).status_code == 403
    assert admin_client.post(_decide(a), {"action": "approve"}).status_code == 403
    assert Absence.objects.get(pk=a.pk).status == "requested"
    # another HR admin can
    other = User.objects.create_user(email="hr2@example.com", password="pw", is_hr_admin=True)
    c = Client()
    c.force_login(other)
    assert c.post(_decide(a), {"action": "approve"}).status_code == 302
    assert Absence.objects.get(pk=a.pk).decided_by == other


def test_stranger_cannot_decide(employee_user):
    _, a, _ = _setup(employee_user)
    other = User.objects.create_user(email="x@example.org", password="pw")
    c = Client()
    c.force_login(other)
    assert c.get(_decide(a)).status_code == 403
    assert c.post(_decide(a), {"action": "approve"}).status_code == 403


def test_a_routed_approver_sees_a_decided_request_read_only(employee_user, admin_client, hr_admin):
    c, a, _ = _setup(employee_user)
    assert admin_client.post(_decide(a), {"action": "decline", "comment": "no cover"}).status_code == 302
    r = c.get(_decide(a))           # the routed manager, after an HR admin decided
    body = r.content.decode()
    assert r.status_code == 200
    assert "Already declined by hr@example.com on" in body and "no cover" in body
    assert "Approve" not in body.replace("Approvals", "") and 'name="action"' not in body


def test_a_double_post_shows_the_read_only_page_and_writes_nothing(employee_user):
    c, a, boss_user = _setup(employee_user)
    assert c.post(_decide(a), {"action": "approve", "comment": "ok"}).status_code == 302
    before = Absence.objects.get(pk=a.pk)
    r = c.post(_decide(a), {"action": "decline", "comment": "changed my mind"})
    after = Absence.objects.get(pk=a.pk)
    assert r.status_code == 200 and "Already approved by Boss" in r.content.decode()
    assert (after.status, after.decided_at, after.decision_comment) == ("approved", before.decided_at, "ok")


def test_a_cancelled_request_reads_as_cancelled(employee_user):
    c, a, _ = _setup(employee_user)
    bookings.cancel(employee_user, a)
    body = c.get(_decide(a)).content.decode()
    assert "Already cancelled by Sam Patel on" in body and 'name="action"' not in body


def test_a_stranger_gets_403_on_a_decided_request_too(employee_user):
    c, a, _ = _setup(employee_user)
    c.post(_decide(a), {"action": "approve"})
    other = User.objects.create_user(email="x@example.org", password="pw")
    s = Client()
    s.force_login(other)
    assert s.get(_decide(a)).status_code == 403
    assert s.post(_decide(a), {"action": "decline"}).status_code == 403
    assert Absence.objects.get(pk=a.pk).status == "approved"


def test_the_decider_is_warned_when_the_email_did_not_go(employee_user, monkeypatch):
    c, a, _ = _setup(employee_user)
    monkeypatch.setattr(notify, "request_decided", lambda absence: False)
    r = c.post(_decide(a), {"action": "approve"}, follow=True)
    assert "did not go" in r.content.decode() and Absence.objects.get(pk=a.pk).status == "approved"


def test_decide_page_shows_the_calendar_and_the_warning(employee_user, monkeypatch):
    """The page renders what absence.services.calendar returns; the real
    min-present figures are tested with the calendar itself."""
    c, a, _ = _setup(employee_user)
    team = a.employment.positions.first().team
    seen = {}

    def days_for(start, end, t):
        seen["days"] = (start, end, t)
        return [{"day": date(2026, 6, 1), "off": [{"employee": make_employee(first="Pat"), "label": "Leave",
                                                    "partial_hours": None, "halves": ["AM", "PM"]}],
                 "present": 1, "headcount": 3}]

    monkeypatch.setattr(calendar, "days_for", days_for)
    monkeypatch.setattr(calendar, "warning_if_approved", lambda absence, t: "Approving leaves fewer than 2 present")
    body = c.get(_decide(a)).content.decode()
    assert seen["days"] == (date(2026, 6, 1), date(2026, 6, 3), team)
    assert "Mon 1 Jun" in body and "Pat Patel" in body and "1 of 3 present" in body
    assert "fewer than 2" in body


def test_decide_page_shows_the_request_and_balance_without_opening_a_pot(employee_user):
    c, a, _ = _setup(employee_user)
    assert not Pot.objects.exists()
    body = c.get(_decide(a)).content.decode()
    assert "Sam Patel" in body and "1 Jun 2026 – 3 Jun 2026" in body and "22.5" in body
    assert "not opened yet" in body.lower()
    assert not Pot.objects.exists()


def test_decide_page_shows_the_balance_after_when_the_pot_is_open(employee_user):
    from absence.services import pots
    c, a, _ = _setup(employee_user)
    pots.for_day(a.employment, a.absence_type, a.start_date)
    body = c.get(_decide(a)).content.decode()
    assert "Balance after" in body and "187.5" in body


def test_decide_page_survives_a_missing_policy(employee_user):
    boss_user = User.objects.create_user(email="boss@example.org", password="pw")
    boss = make_employee(first="Boss", user=boss_user)
    make_employment(employee=boss, start=date(2026, 1, 1))
    emp = make_employment(employee=make_employee(user=employee_user), start=date(2026, 4, 1))
    positions.add(None, emp, "Receptionist", make_team(), boss, emp.start_date)
    a = Absence.objects.create(employment=emp, absence_type=absence_type("AL"),
                               start_date=date(2026, 6, 1), end_date=date(2026, 6, 1))
    c = Client()
    c.force_login(boss_user)
    r = c.get(_decide(a))
    assert r.status_code == 200 and "Sam Patel" in r.content.decode()


def test_approver_off_that_day_still_decides(employee_user, hr_admin):
    c, a, boss_user = _setup(employee_user)
    boss_emp = boss_user.employee.employments.first()
    make_contract(boss_emp)
    make_pattern(boss_emp)
    off = bookings.request(boss_user, boss_emp, absence_type("AL"), date(2026, 6, 1))
    bookings.approve(hr_admin, off)
    assert c.get(reverse("absence:queue")).status_code == 200
    assert c.get(_decide(a)).status_code == 200
    assert c.post(_decide(a), {"action": "approve", "comment": ""}).status_code == 302
    assert Absence.objects.get(pk=a.pk).status == "approved"


def test_the_requester_is_told_after_the_decision_is_saved(employee_user, monkeypatch):
    c, a, _ = _setup(employee_user)
    told = []
    monkeypatch.setattr(notify, "request_decided",
                        lambda absence: told.append(Absence.objects.get(pk=absence.pk).status) or True)
    c.post(_decide(a), {"action": "approve"})
    assert told == ["approved"]


def test_a_refused_decision_shows_why_and_tells_nobody(employee_user, monkeypatch):
    c, a, _ = _setup(employee_user)
    told = []
    monkeypatch.setattr(notify, "request_decided", lambda absence: told.append(1))

    def refuse(*args, **kw):
        raise ValidationError("Another absence now overlaps these dates.")

    monkeypatch.setattr(bookings, "approve", refuse)
    r = c.post(_decide(a), {"action": "approve"})
    assert r.status_code == 200 and "overlaps these dates" in r.content.decode()
    assert not told and Absence.objects.get(pk=a.pk).status == "requested"


def test_nav_offers_approvals_with_the_waiting_count_to_approvers_only(employee_user, employee_client, admin_client):
    c, a, _ = _setup(employee_user)
    body = c.get(reverse("absence:mine")).content.decode()
    assert body.count("Approvals (1)") == 2          # desktop nav and mobile tab bar
    assert "Approvals" not in employee_client.get(reverse("absence:mine")).content.decode()
    assert "Approvals (1)" in admin_client.get(reverse("absence:mine")).content.decode()
    bookings.decline(User.objects.get(email="boss@example.org"), a)
    body = c.get(reverse("absence:mine")).content.decode()
    assert "Approvals" in body and "Approvals (" not in body


def test_a_non_approver_has_no_waiting_count(employee_user, employee_client):
    _setup(employee_user)
    from people.context_processors import roles
    request = employee_client.get(reverse("absence:mine")).wsgi_request
    assert roles(request)["waiting_count"] == 0
