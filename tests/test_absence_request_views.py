from datetime import date, timedelta
from decimal import Decimal

from django.core import mail
from django.utils import timezone

from absence.models import Absence, Pot
from absence.services import bookings, pots
from tests.factories import absence_type, hours_employee, make_employee

BLANK = {"start_half": "", "end_half": "", "hours": "", "category": "", "expected_start": "",
         "expected_return": ""}


def _me(employee_user, **kw):
    return hours_employee(employee=make_employee(user=employee_user), **kw)


def _form(code, start, end=None, **kw):
    data = dict(BLANK, absence_type=absence_type(code).pk, start_date=str(start),
                end_date=str(end or start))
    data.update(kw)
    return data


def _confirmed(code, start, end=None, **kw):
    return _form(code, start, end, confirm="1", **kw)


def test_request_page_shows_balance_and_submits(employee_client, employee_user):
    emp = _me(employee_user)
    pots.for_day(emp, absence_type("AL"), timezone.localdate())     # the nightly opened it
    r = employee_client.get("/absence/request/")
    body = r.content.decode()
    assert r.status_code == 200 and "remaining" in body.lower() and "210" in body
    # step one: checked and shown, nothing written
    r = employee_client.post("/absence/request/", _form("AL", "2026-06-01", "2026-06-03"))
    body = r.content.decode()
    assert r.status_code == 200 and "Confirm request" in body and "22.5" in body
    assert 'name="confirm" value="1"' in body
    assert not Absence.objects.exists()
    # step two: the same fields plus confirm=1
    r = employee_client.post("/absence/request/", _confirmed("AL", "2026-06-01", "2026-06-03"))
    assert r.status_code == 302
    a = Absence.objects.get()
    assert a.status == "requested" and a.cost_units == Decimal("22.50")


def test_confirm_step_carries_the_same_fields(employee_client, employee_user):
    _me(employee_user)
    r = employee_client.post("/absence/request/", _form("AL", "2026-06-01", "2026-06-03", end_half="AM"))
    body = r.content.decode()
    for name, value in (("start_date", "2026-06-01"), ("end_date", "2026-06-03"), ("end_half", "AM"),
                        ("absence_type", str(absence_type("AL").pk))):
        assert f'type="hidden" name="{name}" value="{value}"' in body, name


def test_balance_after_and_negative_warning_before_confirming(employee_client, employee_user):
    emp = _me(employee_user, amount=Decimal("7.5"))
    pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))           # 42.00 accrued
    r = employee_client.post("/absence/request/", _form("AL", "2026-06-01", "2026-06-30"))
    body = r.content.decode()
    assert r.status_code == 200 and "more than your balance" in body.lower()
    assert "-123" in body                                             # 42 - 165
    assert not Absence.objects.exists()


def test_pages_open_no_pot_on_get(employee_client, employee_user):
    _me(employee_user)
    for url in ("/absence/request/", "/absence/mine/"):
        r = employee_client.get(url)
        assert r.status_code == 200 and "not opened yet" in r.content.decode().lower(), url
    assert not Pot.objects.exists()


def test_preview_with_no_pot_says_so_and_writes_nothing(employee_client, employee_user):
    _me(employee_user)
    r = employee_client.post("/absence/request/", _form("AL", "2026-06-01"))
    assert r.status_code == 200 and "not opened yet" in r.content.decode().lower()
    assert not Pot.objects.exists() and not Absence.objects.exists()


def test_missing_policy_shows_a_message_not_a_500(employee_client, employee_user):
    emp = _me(employee_user)
    emp.contracts.first().contract_type.policies.all().delete()
    r = employee_client.get("/absence/request/")
    # the employee is not shown the admin's "add a policy" note in the balances
    assert r.status_code == 200 and "Add one under" not in r.content.decode()
    r = employee_client.post("/absence/request/", _form("AL", "2026-06-01"))
    assert r.status_code == 200 and "No Annual leave policy for Reception" in r.content.decode()


def test_negative_balance_warns_on_page(employee_client, employee_user):
    emp = _me(employee_user, amount=Decimal("7.5"))
    pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    r = employee_client.post("/absence/request/", _confirmed("AL", "2026-06-01", "2026-06-30"))
    assert r.status_code == 302
    r = employee_client.get("/absence/mine/")
    assert "more than your balance" in r.content.decode().lower()


def test_partial_day_request(employee_client, employee_user):
    _me(employee_user)
    r = employee_client.post("/absence/request/", _confirmed(
        "DEP", "2026-06-01", partial="on", start_time="09:00", end_time="10:30", hours="1.5"))
    assert r.status_code == 302
    assert Absence.objects.get().cost_units == Decimal("1.50")


def test_dates_after_employment_end_refused(employee_client, employee_user):
    today = timezone.localdate()
    _me(employee_user, end_date=today + timedelta(days=30), leaving_reason="resigned")
    later = today + timedelta(days=60)
    r = employee_client.post("/absence/request/", _confirmed("AL", later))
    body = r.content.decode()
    assert r.status_code == 200 and "outside your employment" in body
    assert not Absence.objects.exists()


def test_overlap_message_shown(employee_client, employee_user):
    _me(employee_user)
    employee_client.post("/absence/request/", _confirmed("AL", "2026-06-01"))
    r = employee_client.post("/absence/request/", _form("AL", "2026-06-01"))       # refused at step one
    assert r.status_code == 200 and "already an absence" in r.content.decode()
    r = employee_client.post("/absence/request/", _confirmed("AL", "2026-06-01"))
    assert r.status_code == 200 and "already an absence" in r.content.decode()
    assert Absence.objects.count() == 1


def test_sickness_needs_a_category_and_is_recorded_at_once(employee_client, employee_user):
    _me(employee_user)
    r = employee_client.post("/absence/request/", _confirmed("SICK", "2026-06-01"))
    assert r.status_code == 200 and "Say which kind" in r.content.decode()
    r = employee_client.post("/absence/request/", _confirmed("SICK", "2026-06-01", category="illness"),
                             follow=True)
    assert "Recorded." in r.content.decode()
    assert Absence.objects.get().status == "approved"
    assert not mail.outbox


def test_no_relay_shows_the_approver_link(employee_client, employee_user, settings):
    settings.EMAIL_HOST = ""
    _me(employee_user)
    r = employee_client.post("/absence/request/", _confirmed("AL", "2026-06-01"), follow=True)
    a = Absence.objects.get()
    assert f"/absence/decide/{a.pk}/" in r.content.decode()


def test_relay_emails_the_approver_and_shows_no_link(employee_client, employee_user, hr_admin, configured):
    _me(employee_user)
    r = employee_client.post("/absence/request/", _confirmed("AL", "2026-06-01"), follow=True)
    a = Absence.objects.get()
    assert "Sent for approval." in r.content.decode()
    assert f"/absence/decide/{a.pk}/" not in r.content.decode()
    assert len(mail.outbox) == 1 and mail.outbox[0].to == [hr_admin.email]


def test_family_leave_takes_expected_dates(employee_client, employee_user):
    _me(employee_user)
    r = employee_client.post("/absence/request/", _confirmed(
        "MAT", "2026-07-01", "2027-03-31", expected_start="2026-07-01", expected_return="2027-04-01"))
    assert r.status_code == 302
    a = Absence.objects.get()
    assert (a.expected_start, a.expected_return, a.actual_start) == (date(2026, 7, 1), date(2027, 4, 1), None)


def test_family_dates_ignored_for_other_types(employee_client, employee_user):
    _me(employee_user)
    r = employee_client.post("/absence/request/", _confirmed("AL", "2026-06-01", expected_return="2026-06-02"))
    assert r.status_code == 302
    assert Absence.objects.get().expected_return is None


def test_cancel_own_future_only(employee_client, employee_user, hr_admin):
    emp = _me(employee_user)
    soon = timezone.localdate() + timedelta(days=14)
    a = bookings.request(employee_user, emp, absence_type("AL"), soon)
    bookings.approve(hr_admin, a)
    past = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 4, 6))
    bookings.approve(hr_admin, past)
    assert employee_client.post(f"/absence/{a.pk}/cancel/").status_code == 302
    assert Absence.objects.get(pk=a.pk).status == "cancelled"
    assert employee_client.post(f"/absence/{past.pk}/cancel/").status_code == 403
    assert Absence.objects.get(pk=past.pk).status == "approved"


def test_cannot_cancel_someone_elses(employee_client, employee_user, hr_admin):
    _me(employee_user)
    other = hours_employee(employee=make_employee(first="Other"))
    a = bookings.request(hr_admin, other, absence_type("AL"), timezone.localdate() + timedelta(days=14))
    assert employee_client.post(f"/absence/{a.pk}/cancel/").status_code == 403
    assert Absence.objects.get(pk=a.pk).status == "requested"


def test_automatic_bank_holiday_rows_are_listed_and_never_cancelled(employee_client, employee_user,
                                                                     admin_client):
    emp = _me(employee_user)
    auto = Absence.objects.create(employment=emp, absence_type=absence_type("BH"),
                                  start_date=timezone.localdate() + timedelta(days=14),
                                  end_date=timezone.localdate() + timedelta(days=14),
                                  status=Absence.Status.APPROVED, auto_bank_holiday=True)
    body = employee_client.get("/absence/mine/").content.decode()
    assert "Bank holiday (automatic)" in body and f"/absence/{auto.pk}/cancel/" not in body
    assert employee_client.post(f"/absence/{auto.pk}/cancel/").status_code == 403
    assert admin_client.post(f"/absence/{auto.pk}/cancel/").status_code == 403
    assert Absence.objects.get(pk=auto.pk).status == "approved"


def test_kit_day_added_to_family_leave(employee_client, employee_user):
    emp = _me(employee_user)
    a = bookings.request(employee_user, emp, absence_type("MAT"), date(2026, 7, 1), date(2027, 3, 31))
    r = employee_client.post(f"/absence/{a.pk}/kit-day/", {"date": "2026-09-15"})
    assert r.status_code == 302 and a.kit_days.count() == 1


def test_kit_day_refused_outside_family_leave(employee_client, employee_user, hr_admin):
    emp = _me(employee_user)
    leave = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, 1))
    r = employee_client.post(f"/absence/{leave.pk}/kit-day/", {"date": "2026-06-01"}, follow=True)
    assert "family leave" in r.content.decode() and not leave.kit_days.exists()
    other = hours_employee(employee=make_employee(first="Other"))
    theirs = bookings.request(hr_admin, other, absence_type("MAT"), date(2026, 7, 1), date(2027, 3, 31))
    assert employee_client.post(f"/absence/{theirs.pk}/kit-day/", {"date": "2026-09-15"}).status_code == 403


def test_leave_link_in_both_navs(employee_client, employee_user):
    _me(employee_user)
    body = employee_client.get("/people/me/").content.decode()
    assert body.count('href="/absence/mine/"') == 2


def test_no_employee_record(employee_client):
    assert employee_client.get("/absence/request/").status_code == 200
    assert employee_client.get("/absence/mine/").status_code == 200


def test_part_day_fields_only_for_an_hours_allowance(employee_client, employee_user):
    from tests.factories import make_contract, make_contract_type, make_employment, make_pattern, make_policy
    emp = make_employment(employee=make_employee(user=employee_user), start=date(2026, 4, 1))
    ct = make_contract_type("GP", unit="sessions", full_time=Decimal("8"))
    make_contract(emp, ct, amount=Decimal("8"))
    make_policy(ct)
    make_pattern(emp, {d: (Decimal("1"), Decimal("1")) for d in range(4)})
    body = employee_client.get("/absence/request/").content.decode()
    assert 'name="start_date"' in body and 'name="hours"' not in body and 'name="partial"' not in body
    r = employee_client.post("/absence/request/", _confirmed("AL", "2026-06-01", "2026-06-03"))
    assert r.status_code == 302 and Absence.objects.get().cost_units == Decimal("6.0")
