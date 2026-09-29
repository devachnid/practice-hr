from datetime import date, datetime, timezone

from django.core import mail

from absence.models import Absence, BankHoliday, ClosedDay, EmailFailure
from absence.services import bookings, chase, nightly
from tests.factories import absence_type, hours_employee


def _old_request(requested_on, start=date(2026, 8, 3)):
    emp = hours_employee()
    a = bookings.request(None, emp, absence_type("AL"), start)
    Absence.objects.filter(pk=a.pk).update(
        requested_at=datetime.combine(requested_on, datetime.min.time(), timezone.utc))
    return a


def test_waiting_counts_working_days(db):
    a = _old_request(date(2026, 6, 26))                 # a Friday
    assert chase.waiting(date(2026, 6, 30)) == []       # Mon, Tue: two working days
    assert chase.waiting(date(2026, 7, 1)) == []        # three is not more than three
    assert chase.waiting(date(2026, 7, 2)) == [a]       # Thursday: four


def test_a_bank_holiday_is_not_a_working_day(db):
    a = _old_request(date(2026, 6, 26))
    BankHoliday.objects.create(date=date(2026, 6, 29), name="Test holiday", nation="EW")
    assert chase.waiting(date(2026, 7, 2)) == []        # Tue, Wed, Thu: three
    assert chase.waiting(date(2026, 7, 3)) == [a]


def test_a_scottish_holiday_still_counts_as_a_working_day(db):
    a = _old_request(date(2026, 6, 26))
    BankHoliday.objects.create(date=date(2026, 6, 29), name="Scottish only", nation="S")
    assert chase.waiting(date(2026, 7, 2)) == [a]


def test_a_closed_day_is_not_a_working_day(db):
    a = _old_request(date(2026, 6, 26))
    ClosedDay.objects.create(date=date(2026, 6, 30), reason="Training day")
    assert chase.waiting(date(2026, 7, 2)) == []
    assert chase.waiting(date(2026, 7, 3)) == [a]


def test_only_requested_absences_wait(db):
    a = _old_request(date(2026, 6, 1))
    bookings.approve(None, a)
    assert chase.waiting(date(2026, 6, 30)) == []


def test_automatic_bank_holiday_rows_never_wait(db):
    a = _old_request(date(2026, 6, 1))
    Absence.objects.filter(pk=a.pk).update(auto_bank_holiday=True, status=Absence.Status.APPROVED)
    assert chase.waiting(date(2026, 6, 30)) == []


def test_notify_once(configured, db, hr_admin):
    a = _old_request(date(2026, 6, 1))
    assert chase.notify_once(date(2026, 6, 10)) == 1
    assert mail.outbox[-1].to == [hr_admin.email]
    assert chase.notify_once(date(2026, 6, 11)) == 0
    assert Absence.objects.get(pk=a.pk).chased_at is not None


def test_an_email_that_did_not_go_stamps_nothing_so_the_next_night_tries_again(db, hr_admin):
    a = _old_request(date(2026, 6, 1))                  # email is not configured
    assert chase.notify_once(date(2026, 6, 10)) == 0
    assert Absence.objects.get(pk=a.pk).chased_at is None
    assert len(mail.outbox) == 0


def test_a_retry_after_a_failure_stamps_once_email_works(settings, db, hr_admin):
    a = _old_request(date(2026, 6, 1))
    assert chase.notify_once(date(2026, 6, 10)) == 0
    settings.EMAIL_HOST = "smtp.example"
    settings.DEFAULT_FROM_EMAIL = "Practice HR <hr@example.org>"
    assert chase.notify_once(date(2026, 6, 11)) == 1
    assert Absence.objects.get(pk=a.pk).chased_at is not None


def test_nightly_chases_and_reports_it(configured, db, hr_admin):
    _old_request(date(2026, 6, 1))
    assert nightly.run(date(2026, 6, 10))["chased"] == 1
    assert nightly.run(date(2026, 6, 11))["chased"] == 0


def test_nightly_lists_a_chase_that_could_not_run(db, monkeypatch):
    def boom(today):
        raise RuntimeError("query failed")
    monkeypatch.setattr(chase, "notify_once", boom)
    result = nightly.run(date(2026, 6, 10))
    assert result["chased"] == 0
    assert any("chase" in f for f in result["failed"])


def test_dashboard_lists_waiting(admin_client, db):
    a = _old_request(date(2026, 6, 1), start=date(2026, 8, 3))
    body = admin_client.get("/admin/").content.decode()
    assert "waiting" in body.lower()
    assert a.employment.employee.name in body
    assert "3 Aug 2026" in body
    assert f"/absence/decide/{a.pk}/" in body


def test_dashboard_says_when_nothing_waits(admin_client, db):
    body = admin_client.get("/admin/").content.decode()
    assert "No requests" in body


def test_dashboard_says_email_is_not_configured(admin_client, db):
    assert "Outgoing email is not configured" in admin_client.get("/admin/").content.decode()


def test_dashboard_is_quiet_about_email_when_configured(configured, admin_client, db):
    assert "Outgoing email is not configured" not in admin_client.get("/admin/").content.decode()


def test_dashboard_shows_recorded_email_failures(admin_client, db):
    EmailFailure.objects.create(subject="Leave request from Sam Patel", error="relay refused it")
    body = admin_client.get("/admin/").content.decode()
    assert "Leave request from Sam Patel" in body
    assert "relay refused it" in body


def test_dashboard_shows_only_the_last_ten_email_failures(admin_client, db):
    for i in range(12):
        EmailFailure.objects.create(subject=f"Subject number {i:02d}", error="x")
    body = admin_client.get("/admin/").content.decode()
    assert "Subject number 11" in body and "Subject number 02" in body
    assert "Subject number 01" not in body and "Subject number 00" not in body
