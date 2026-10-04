from datetime import date, timedelta

import pytest
from django.core import mail
from django.utils import timezone

from checks.models import Check, CheckType
from checks.services import checks
from compliance.models import ReminderSchedule, ReminderSent
from compliance.services import digest, schedule
from onboarding.models import ChecklistItem
from people.services import employments, positions, titles
from tests.factories import make_employee, make_team

pytestmark = pytest.mark.django_db
D = date(2026, 1, 1)   # schedule arithmetic is pure; a fixed date is fine


def S(x=60, y=30, z=7):
    return ReminderSchedule(start_days_before=x, every_days_before=y, every_days_overdue=z)


def test_defaults_and_singleton():
    s = ReminderSchedule.get()
    assert (s.start_days_before, s.every_days_before, s.every_days_overdue) == (60, 30, 7)
    assert ReminderSchedule.get().pk == s.pk


@pytest.mark.parametrize("days_to_due,last,expected", [
    (61, None, False),      # outside the window
    (60, None, True),       # first day of the window
    (59, D, False),         # sent yesterday
    (30, D, True),          # 30 days after the first send: every Y
    (0, D + timedelta(days=30), True),   # the due date always sends
    (-1, D + timedelta(days=60), False), # day after due: the due-date send was yesterday
    (-7, D + timedelta(days=60), True),  # every Z overdue
])
def test_should_send_follows_the_cadence(days_to_due, last, expected):
    today = D + timedelta(days=60 - days_to_due)
    due = today + timedelta(days=days_to_due)
    assert schedule.should_send(today, due, "overdue" if days_to_due < 0 else "due_soon", last, S()) is expected


def test_y_bigger_than_x_still_sends_at_window_start_and_on_the_day():
    s = S(x=10, y=30, z=7)
    today = D
    assert schedule.should_send(today, today + timedelta(days=10), "due_soon", None, s)
    assert not schedule.should_send(today + timedelta(days=5), today + timedelta(days=10), "due_soon", today, s)
    assert schedule.should_send(today + timedelta(days=10), today + timedelta(days=10), "due_today", today, s)


def _receptionist(hr_admin, user=None, manager=None):
    e = make_employee(user=user)
    emp = employments.start(hr_admin, e, timezone.localdate() - timedelta(days=400))
    positions.add(hr_admin, emp, titles.get_or_create("Receptionist"), make_team(), manager, emp.start_date)
    return e


def test_digest_groups_by_recipient_and_logs_sends(hr_admin, configured, employee_user):
    today = timezone.localdate()
    dbs = CheckType.objects.get(code="dbs"); dbs.positions.add(titles.get_or_create("Receptionist"))
    e = _receptionist(hr_admin, user=employee_user)
    checks.record(hr_admin, e, dbs, today - timedelta(days=5), Check.Outcome.CLEAR, reference="1", dbs_level="basic",
                  expires_on=today + timedelta(days=30))
    out = digest.run(today)
    assert out["reminders_sent"] == 2            # the person (remind_person) and HR
    to = sorted(m.to[0] for m in mail.outbox)
    assert to == ["hr@example.com", "sam@example.com"]
    assert "DBS" in mail.outbox[0].body and e.name in mail.outbox[0].body
    assert ReminderSent.objects.count() == 2
    mail.outbox.clear()
    assert digest.run(today + timedelta(days=1))["reminders_sent"] == 0   # not again tomorrow


def test_manager_told_once_when_a_check_lapses(hr_admin, configured, employee_user):
    today = timezone.localdate()
    mgr_user = type(employee_user).objects.create_user(email="mo@example.com", password="pw")
    mgr = make_employee(first="Mo", last="Khan", user=mgr_user)
    employments.start(hr_admin, mgr, today - timedelta(days=500))
    dbs = CheckType.objects.get(code="dbs"); dbs.positions.add(titles.get_or_create("Receptionist"))
    e = _receptionist(hr_admin, user=employee_user, manager=mgr)
    checks.record(hr_admin, e, dbs, today - timedelta(days=1200), Check.Outcome.CLEAR, reference="1", dbs_level="basic")
    digest.run(today)
    assert any(m.to == ["mo@example.com"] for m in mail.outbox)
    mail.outbox.clear()
    digest.run(today + timedelta(days=7))
    assert not any(m.to == ["mo@example.com"] for m in mail.outbox)      # once
    assert any(m.to == ["hr@example.com"] for m in mail.outbox)          # HR every Z days


def test_checklist_items_remind_their_owner(hr_admin, configured, employee_user):
    today = timezone.localdate()
    e = make_employee(user=employee_user)
    emp = employments.start(hr_admin, e, today + timedelta(days=3))
    positions.add(hr_admin, emp, titles.get_or_create("Receptionist"), make_team(), None, emp.start_date)
    ChecklistItem.objects.filter(checklist__employment=emp, owner="person").update(due_on=today)
    digest.run(today)
    me = [m for m in mail.outbox if m.to == ["sam@example.com"]]
    assert me and "Complete your details" in me[0].body


def test_no_email_without_a_relay_and_nothing_logged(hr_admin, employee_user):
    today = timezone.localdate()
    dbs = CheckType.objects.get(code="dbs"); dbs.positions.add(titles.get_or_create("Receptionist"))
    e = _receptionist(hr_admin, user=employee_user)
    checks.record(hr_admin, e, dbs, today - timedelta(days=5), Check.Outcome.CLEAR, reference="1", dbs_level="basic",
                  expires_on=today + timedelta(days=30))
    out = digest.run(today)
    assert out["reminders_sent"] == 0 and ReminderSent.objects.count() == 0


# ---- beyond the brief's cases ------------------------------------------------

from django.contrib.auth import get_user_model  # noqa: E402
from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402

from absence.models import EmailFailure  # noqa: E402
from compliance.services import nightly  # noqa: E402
from documents.models import Policy  # noqa: E402
from documents.services import policies  # noqa: E402

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


def _dbs_for_receptionists():
    dbs = CheckType.objects.get(code="dbs")
    dbs.positions.add(titles.get_or_create("Receptionist"))
    return dbs


def _to(address):
    return [m for m in mail.outbox if m.to == [address]]


def test_a_missing_check_is_not_sent_every_day(hr_admin, configured, employee_user):
    today = timezone.localdate()
    _dbs_for_receptionists()
    _receptionist(hr_admin, user=employee_user)
    assert digest.run(today)["reminders_sent"] == 2
    for n in range(1, 7):
        assert digest.run(today + timedelta(days=n))["reminders_sent"] == 0, n
    assert digest.run(today + timedelta(days=7))["reminders_sent"] == 2      # every Z days


def test_hr_is_reminded_of_someone_with_no_login(hr_admin, configured):
    today = timezone.localdate()
    _dbs_for_receptionists()
    e = _receptionist(hr_admin)
    assert digest.run(today) == {"reminders_sent": 1, "reminders_failed": 0, "items": 1}
    [m] = mail.outbox
    assert m.to == ["hr@example.com"] and e.name in m.body and "DBS: missing" in m.body


def test_the_manager_is_not_told_which_check_and_sees_only_their_report(hr_admin, configured, employee_user):
    today = timezone.localdate()
    User = get_user_model()
    mgr = make_employee(first="Mo", last="Khan", user=User.objects.create_user(email="mo@example.com", password="pw"))
    employments.start(hr_admin, mgr, today - timedelta(days=500))
    dbs = _dbs_for_receptionists()
    mine = _receptionist(hr_admin, user=employee_user, manager=mgr)
    other = make_employee(first="Ola", last="Ade")
    emp = employments.start(hr_admin, other, today - timedelta(days=400))
    positions.add(hr_admin, emp, titles.get_or_create("Receptionist"), make_team("Nursing"), None, emp.start_date)
    for e in (mine, other):
        checks.record(hr_admin, e, dbs, today - timedelta(days=1200), Check.Outcome.CLEAR, reference="1",
                      dbs_level="basic")
    digest.run(today)
    [m] = _to("mo@example.com")
    assert mine.name in m.body and other.name not in m.body
    assert "DBS" not in m.body and "lapsed" in m.body
    [person] = _to("sam@example.com")
    assert other.name not in person.body
    [hr] = _to("hr@example.com")
    assert mine.name in hr.body and other.name in hr.body


def test_one_line_when_the_hr_admin_is_also_the_person(configured, employee_user):
    today = timezone.localdate()
    employee_user.is_hr_admin = True
    employee_user.save()
    _dbs_for_receptionists()
    _receptionist(employee_user, user=employee_user)
    assert digest.run(today) == {"reminders_sent": 1, "reminders_failed": 0, "items": 1}


def test_a_renewal_starts_a_new_cadence(hr_admin, configured, employee_user):
    today = timezone.localdate()
    dbs = _dbs_for_receptionists()
    e = _receptionist(hr_admin, user=employee_user)
    checks.record(hr_admin, e, dbs, today - timedelta(days=5), Check.Outcome.CLEAR, reference="1", dbs_level="basic",
                  expires_on=today + timedelta(days=30))
    digest.run(today)
    checks.record(hr_admin, e, dbs, today, Check.Outcome.CLEAR, reference="2", dbs_level="basic",
                  expires_on=today + timedelta(days=40))
    assert digest.run(today + timedelta(days=1))["reminders_sent"] == 2


def test_a_failed_send_is_recorded_and_not_logged_as_sent(hr_admin, configured, employee_user, monkeypatch):
    today = timezone.localdate()
    _dbs_for_receptionists()
    _receptionist(hr_admin, user=employee_user)

    def boom(self, *a, **k):
        raise OSError("relay down")
    monkeypatch.setattr("django.core.mail.EmailMessage.send", boom)
    assert digest.run(today) == {"reminders_sent": 0, "reminders_failed": 2, "items": 0}
    assert ReminderSent.objects.count() == 0 and EmailFailure.objects.count() == 2
    monkeypatch.undo()
    assert digest.run(today)["reminders_sent"] == 2       # tried again


def test_policies_remind_the_person_and_hr_once_overdue(hr_admin, configured, employee_user, media):
    today = timezone.localdate()
    e = _receptionist(hr_admin, user=employee_user)
    p = Policy.objects.create(title="Chaperoning")
    policies.issue(hr_admin, p, "v1", SimpleUploadedFile("c.pdf", PDF, content_type="application/pdf"), today, 14)
    digest.run(today)
    assert [m.to for m in mail.outbox] == [["sam@example.com"]]
    assert "Sign Chaperoning (v1): due " in mail.outbox[0].body
    mail.outbox.clear()
    digest.run(today + timedelta(days=15))
    assert sorted(m.to[0] for m in mail.outbox) == ["hr@example.com", "sam@example.com"]
    assert all(e.name in m.body and "overdue since" in m.body for m in mail.outbox)


def test_a_policy_due_outside_the_window_waits(hr_admin, configured, employee_user, media):
    today = timezone.localdate()
    _receptionist(hr_admin, user=employee_user)
    p = Policy.objects.create(title="Chaperoning")
    policies.issue(hr_admin, p, "v1", SimpleUploadedFile("c.pdf", PDF, content_type="application/pdf"), today, 90)
    assert digest.run(today)["reminders_sent"] == 0


def test_a_manager_item_with_no_manager_goes_to_hr(hr_admin, configured, employee_user):
    today = timezone.localdate()
    e = make_employee(user=employee_user)
    emp = employments.start(hr_admin, e, today + timedelta(days=3))
    positions.add(hr_admin, emp, titles.get_or_create("Receptionist"), make_team(), None, emp.start_date)
    ChecklistItem.objects.filter(checklist__employment=emp, title="Buddy named").update(due_on=today)
    digest.run(today)
    [hr] = _to("hr@example.com")
    assert "Buddy named: due today" in hr.body
    assert "Buddy named" not in _to("sam@example.com")[0].body


def test_a_manager_item_goes_to_the_manager(hr_admin, configured, employee_user):
    today = timezone.localdate()
    User = get_user_model()
    mgr = make_employee(first="Mo", last="Khan", user=User.objects.create_user(email="mo@example.com", password="pw"))
    employments.start(hr_admin, mgr, today - timedelta(days=500))
    e = make_employee(user=employee_user)
    emp = employments.start(hr_admin, e, today + timedelta(days=3))
    positions.add(hr_admin, emp, titles.get_or_create("Receptionist"), make_team(), mgr, emp.start_date)
    digest.run(today)
    [m] = _to("mo@example.com")
    assert e.name in m.body and "Induction completed" in m.body and "/people/team/" in m.body
    assert "Induction completed" not in _to("hr@example.com")[0].body


def test_a_leavers_items_stop_90_days_after_the_leaving_date(hr_admin, configured):
    from onboarding.models import Checklist, Kind
    today = timezone.localdate()
    e = make_employee()
    emp = employments.start(hr_admin, e, today - timedelta(days=400))
    emp.end_date = today - timedelta(days=91)
    emp.save()
    cl = Checklist.objects.create(employment=emp, kind=Kind.LEAVER)
    ChecklistItem.objects.create(checklist=cl, title="File closed", owner="hr", due_on=today - timedelta(days=80))
    assert digest.run(today)["reminders_sent"] == 0
    emp.end_date = today - timedelta(days=90)
    emp.save()
    assert digest.run(today)["reminders_sent"] == 1


def test_nightly_wraps_the_digest_and_the_command_reports_it(db, capsys):
    from django.core.management import call_command
    assert nightly.run(timezone.localdate()) == {"reminders_sent": 0, "reminders_failed": 0, "items": 0}
    call_command("hr_nightly")
    assert "compliance: {'reminders_sent': 0" in capsys.readouterr().out


def test_the_settings_are_one_row_edited_in_place(admin_client):
    r = admin_client.get("/admin/compliance/reminderschedule/")
    row = ReminderSchedule.get()
    assert r.status_code == 302 and r["Location"] == f"/admin/compliance/reminderschedule/{row.pk}/change/"
    assert admin_client.get("/admin/compliance/reminderschedule/add/").status_code == 403
    assert admin_client.post(f"/admin/compliance/reminderschedule/{row.pk}/delete/").status_code == 403
    r = admin_client.post(f"/admin/compliance/reminderschedule/{row.pk}/change/",
                          {"start_days_before": 45, "every_days_before": 14, "every_days_overdue": 3})
    assert r.status_code == 302
    row.refresh_from_db()
    assert (row.start_days_before, row.every_days_before, row.every_days_overdue) == (45, 14, 3)
    assert ReminderSchedule.objects.count() == 1


def test_reminder_settings_in_the_compliance_sidebar(db):
    from django.test import RequestFactory

    from hr.admin_site import navigation
    request = RequestFactory().get("/admin/")
    request.user = type("U", (), {"is_active": True, "is_hr_admin": True, "is_superuser": False})()
    group = next(g for g in navigation(request) if g["title"] == "Compliance")
    assert group["items"][-1]["title"] == "Reminder settings"
    assert group["items"][-1]["link"] == "/admin/compliance/reminderschedule/"


def test_an_employee_cannot_reach_the_settings(employee_client):
    assert employee_client.get("/admin/compliance/reminderschedule/").status_code in (302, 403)


def test_the_day_after_expiry_the_lapse_starts_afresh(hr_admin, configured, employee_user):
    today = timezone.localdate()
    dbs = _dbs_for_receptionists()
    e = _receptionist(hr_admin, user=employee_user)
    checks.record(hr_admin, e, dbs, today - timedelta(days=5), Check.Outcome.CLEAR, reference="1", dbs_level="basic",
                  expires_on=today + timedelta(days=1))
    assert digest.run(today)["reminders_sent"] == 2                      # inside the window
    assert digest.run(today + timedelta(days=1))["reminders_sent"] == 2  # the expiry date: due today
    mail.outbox.clear()
    assert digest.run(today + timedelta(days=2))["reminders_sent"] == 2  # lapsed: a new cadence
    assert all("DBS: lapsed on" in m.body for m in mail.outbox)
    assert digest.run(today + timedelta(days=3))["reminders_sent"] == 0
    assert digest.run(today + timedelta(days=9))["reminders_sent"] == 2  # every Z days
