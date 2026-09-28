from datetime import date

from django.core import mail

from absence import mail as door
from absence.models import EmailFailure
from absence.services import bookings, notify
from people.services import positions
from tests.factories import absence_type, hours_employee, make_employee, make_employment, make_team


def _pair(employee_user, hr_admin):
    boss = make_employee(first="Boss", email="boss@example.org", user=hr_admin)
    make_employment(employee=boss, start=date(2026, 1, 1))
    emp = hours_employee(employee=make_employee(user=employee_user))
    positions.add(None, emp, "Receptionist", make_team(), boss, emp.start_date)
    return emp


def test_submitted_goes_to_manager(configured, employee_user, hr_admin):
    emp = _pair(employee_user, hr_admin)
    a = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, 1))
    assert notify.request_submitted(a) is True
    assert mail.outbox[-1].to == ["boss@example.org"]
    assert "Sam Patel" in mail.outbox[-1].body and "1 Jun 2026" in mail.outbox[-1].body


def test_submitted_carries_the_decide_link_and_replies_to_the_requester(configured, employee_user, hr_admin, settings):
    settings.SITE_URL = "https://hr.example.org/"
    emp = _pair(employee_user, hr_admin)
    a = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, 1))
    notify.request_submitted(a)
    m = mail.outbox[-1]
    assert notify.decide_url(a) == f"https://hr.example.org/absence/decide/{a.pk}/"
    assert notify.decide_url(a) in m.body
    assert m.reply_to == [emp.employee.work_email]


def test_every_message_switches_click_tracking_off(configured, employee_user, hr_admin):
    emp = _pair(employee_user, hr_admin)
    a = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, 1))
    notify.request_submitted(a)
    assert mail.outbox[-1].extra_headers["X-Mailjet-TrackClick"] == "0"
    assert mail.outbox[-1].extra_headers["X-Mailjet-TrackOpen"] == "0"


def test_names_are_not_html_escaped(configured, employee_user, hr_admin):
    emp = hours_employee(employee=make_employee(last="O'Brien", user=employee_user))
    a = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, 1))
    notify.request_submitted(a)
    assert "Sam O'Brien" in mail.outbox[-1].body


def test_submitted_without_manager_goes_to_hr_admins(configured, employee_user, hr_admin):
    emp = hours_employee(employee=make_employee(user=employee_user))
    a = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, 1))
    notify.request_submitted(a)
    assert mail.outbox[-1].to == [hr_admin.email]


def test_unconfigured_returns_false_and_sends_nothing(db, employee_user):
    emp = hours_employee(employee=make_employee(user=employee_user))
    a = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, 1))
    assert notify.request_submitted(a) is False
    assert mail.outbox == []


def test_unconfigured_is_recorded_with_the_subject_only(db, employee_user, hr_admin):
    emp = hours_employee(employee=make_employee(user=employee_user))
    a = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, 1))
    assert notify.request_submitted(a) is False
    [failure] = EmailFailure.objects.all()
    assert failure.subject == "Leave request from Sam Patel"
    assert "not configured" in failure.error
    assert hr_admin.email not in failure.error


def test_relay_fault_returns_false_and_is_recorded(configured, employee_user, hr_admin, monkeypatch):
    def boom(self, *a, **k):
        raise OSError("relay down")
    monkeypatch.setattr("django.core.mail.EmailMessage.send", boom)
    assert door.send("Hello", "body", ["x@example.org"]) is False
    [failure] = EmailFailure.objects.all()
    assert failure.subject == "Hello" and "relay down" in failure.error


def test_bad_address_is_a_failure_not_an_exception(db, configured):
    assert door.send("Hello", "body", ["not an address\n"]) is False
    assert EmailFailure.objects.count() == 1


def test_no_recipients_is_a_recorded_failure(db, configured):
    assert door.send("Hello", "body", []) is False
    assert EmailFailure.objects.get().error == "no recipients"


def test_a_template_fault_never_reaches_the_caller(configured, employee_user, hr_admin, monkeypatch):
    emp = hours_employee(employee=make_employee(user=employee_user))
    a = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, 1))

    def boom(*args, **kwargs):
        raise RuntimeError("template broke")
    monkeypatch.setattr(notify, "render_to_string", boom)
    assert notify.request_submitted(a) is False
    assert mail.outbox == []
    assert EmailFailure.objects.count() == 1


def test_decided_goes_to_requester(configured, employee_user, hr_admin):
    emp = _pair(employee_user, hr_admin)
    a = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, 1))
    bookings.decline(hr_admin, a, "short staffed")
    notify.request_decided(a)
    m = mail.outbox[-1]
    assert m.to == [emp.employee.work_email] and "declined" in m.subject.lower() and "short staffed" in m.body


def test_cancelled_goes_to_the_approver(configured, employee_user, hr_admin):
    emp = _pair(employee_user, hr_admin)
    a = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, 1))
    assert notify.absence_cancelled(a) is True
    m = mail.outbox[-1]
    assert m.to == ["boss@example.org"] and "cancelled" in m.subject and "1 Jun 2026" in m.body


def test_requests_waiting_goes_to_hr_admins_with_a_line_each(configured, employee_user, hr_admin):
    emp = hours_employee(employee=make_employee(user=employee_user))
    rows = [bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, d)) for d in (1, 2)]
    assert notify.requests_waiting(rows) is True
    m = mail.outbox[-1]
    assert m.to == [hr_admin.email] and m.subject == "2 leave request(s) waiting"
    assert "1 Jun 2026" in m.body and "2 Jun 2026" in m.body
    assert notify.decide_url(rows[0]) in m.body


def test_hr_admin_addresses_skips_inactive_admins(db, hr_admin, django_user_model):
    django_user_model.objects.create_user(email="gone@example.com", password="pw",
                                          is_hr_admin=True, is_active=False)
    assert notify.hr_admin_addresses() == [hr_admin.email]


def test_failures_are_listed_in_the_admin_read_only(superuser_client):
    EmailFailure.objects.create(subject="Leave request from Sam Patel", error="email is not configured")
    listing = superuser_client.get("/admin/absence/emailfailure/")
    assert listing.status_code == 200 and b"Leave request from Sam Patel" in listing.content
    assert superuser_client.get("/admin/absence/emailfailure/add/").status_code == 403
