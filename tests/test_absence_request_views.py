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


def test_after_the_nightly_a_next_year_request_shows_next_years_balance_and_warning(employee_client, employee_user):
    from absence.models import Policy
    from absence.services import nightly
    from tests.factories import current_leave_year
    emp = _me(employee_user)
    Policy.objects.update(weeks_per_year=Decimal("1"))                  # 37.50 hours a year
    nightly.run(timezone.localdate())                                   # opens this year's pot and next
    next_start = current_leave_year()[1] + timedelta(days=1)
    monday = next_start + timedelta(days=(7 - next_start.weekday()) % 7 + 21)
    r = employee_client.post("/absence/request/", _form("AL", monday, monday + timedelta(days=11)))
    body = r.content.decode()
    nxt = pots.lookup(emp, absence_type("AL"), monday)
    assert nxt is not None and nxt.year_start == next_start
    assert r.status_code == 200 and "Not opened yet" not in body and "Remaining now" in body
    assert "37.5" in body and "more than your balance" in body.lower()
    assert not Absence.objects.filter(auto_bank_holiday=False).exists()


# --- recording an absence for someone else (I7) ------------------------------------------

def _report_and_manager(employee_user):
    """The employee (Sam, employee_user's record) reporting to a manager
    with a login. Returns (employment, manager's user, manager's client)."""
    from django.contrib.auth import get_user_model
    from django.test import Client

    from people.services import positions
    from tests.factories import make_employment, make_team
    emp = _me(employee_user)
    boss_user = get_user_model().objects.create_user(email="boss@example.org", password="pw")
    boss = make_employee(first="Bea", last="Boss", user=boss_user)
    make_employment(employee=boss, start=emp.start_date)
    positions.add(None, emp, "Receptionist", make_team(), boss, emp.start_date)
    c = Client()
    c.force_login(boss_user)
    return emp, boss_user, c


def _in_this_year(days):
    from tests.factories import current_leave_year
    return current_leave_year()[0] + timedelta(days=days)


def test_a_manager_records_sickness_for_a_report_approved_audited_and_emailed(employee_user, configured):
    from people.models import AuditEntry
    emp, boss_user, boss = _report_and_manager(employee_user)
    url = f"/absence/request/{emp.employee.pk}/"
    body = boss.get(url).content.decode()
    assert f"Record leave for {emp.employee.name}" in body
    day = timezone.localdate()
    r = boss.post(url, _form("SICK", day, category="illness"))
    assert r.status_code == 200 and "Confirm" in r.content.decode() and not Absence.objects.exists()
    r = boss.post(url, _confirmed("SICK", day, category="illness"))
    assert r.status_code == 302
    a = Absence.objects.get()
    assert a.status == Absence.Status.APPROVED and a.employment == emp
    assert a.requested_by == boss_user and a.decided_by == boss_user
    assert AuditEntry.objects.filter(model="absence.absence", object_id=a.pk, actor=boss_user,
                                     field="requested").exists()
    assert [m.to for m in mail.outbox] == [[emp.employee.work_email]]
    assert "approved" in mail.outbox[0].subject and "illness" not in mail.outbox[0].body


def test_annual_leave_recorded_by_the_approver_is_approved_at_once(employee_user, configured):
    from absence.models import LedgerEntry
    emp, boss_user, boss = _report_and_manager(employee_user)
    day = _in_this_year(61)
    r = boss.post(f"/absence/request/{emp.employee.pk}/", _confirmed("AL", day, day + timedelta(days=2)))
    assert r.status_code == 302
    a = Absence.objects.get()
    assert a.status == Absence.Status.APPROVED
    line = a.ledger_entries.get()
    assert line.kind == LedgerEntry.Kind.BOOKING and line.actor == boss_user
    assert [m.to for m in mail.outbox] == [[emp.employee.work_email]]       # no "please decide" email


def test_a_peer_cannot_record_leave_for_someone(employee_user):
    from django.contrib.auth import get_user_model
    from django.test import Client
    emp, _, _ = _report_and_manager(employee_user)
    peer_user = get_user_model().objects.create_user(email="peer@example.org", password="pw")
    hours_employee(employee=make_employee(first="Pat", user=peer_user))
    c = Client()
    c.force_login(peer_user)
    url = f"/absence/request/{emp.employee.pk}/"
    assert c.get(url).status_code == 403
    assert c.post(url, _confirmed("SICK", timezone.localdate(), category="illness")).status_code == 403
    assert not Absence.objects.exists()


def test_an_hr_admin_records_annual_leave_for_anyone(admin_client, hr_admin, employee_user):
    emp = _me(employee_user)                          # nobody manages Sam: HR would decide
    day = _in_this_year(61)
    r = admin_client.post(f"/absence/request/{emp.employee.pk}/", _confirmed("AL", day))
    assert r.status_code == 302
    a = Absence.objects.get()
    assert a.status == Absence.Status.APPROVED and a.decided_by == hr_admin and a.requested_by == hr_admin


def test_recording_for_yourself_goes_to_the_ordinary_request_page(employee_user):
    from django.test import Client
    emp, boss_user, boss = _report_and_manager(employee_user)
    from people.services import access
    me = access.employee_for(boss_user)
    r = boss.get(f"/absence/request/{me.pk}/")
    assert r.status_code == 302 and r["Location"] == "/absence/request/"
    c = Client()
    c.force_login(employee_user)
    assert c.get(f"/absence/request/{me.pk}/").status_code == 403          # Sam is not Bea's approver


def test_mine_and_team_pages_link_to_recording_for_reports(employee_user):
    emp, _, boss = _report_and_manager(employee_user)
    link = f'href="/absence/request/{emp.employee.pk}/"'
    assert link in boss.get("/absence/mine/").content.decode()
    body = boss.get("/absence/balances/team/").content.decode()
    assert link in body and f"Record leave for {emp.employee.name}" in body


def test_an_hr_admin_gets_the_link_for_everyone_employed(admin_client, employee_user):
    emp = _me(employee_user)
    assert f'href="/absence/request/{emp.employee.pk}/"' in admin_client.get("/absence/balances/team/").content.decode()
    assert 'href="/absence/balances/team/"' in admin_client.get("/absence/mine/").content.decode()


def test_an_hr_admin_cancels_their_own_absence_by_the_employee_rule(admin_client, hr_admin, employee_user):
    mine = hours_employee(employee=make_employee(first="Hana", user=hr_admin))
    started = bookings.approve(employee_user, bookings.request(hr_admin, mine, absence_type("AL"), date(2026, 4, 6)))
    soon = bookings.approve(employee_user, bookings.request(
        hr_admin, mine, absence_type("AL"), timezone.localdate() + timedelta(days=14)))
    assert admin_client.post(f"/absence/{started.pk}/cancel/").status_code == 403
    assert Absence.objects.get(pk=started.pk).status == "approved"
    assert admin_client.post(f"/absence/{soon.pk}/cancel/").status_code == 302
    assert Absence.objects.get(pk=soon.pk).status == "cancelled"
    # another person's absence, already started: still an HR admin's to cancel
    other = _me(employee_user)
    theirs = bookings.approve(hr_admin, bookings.request(employee_user, other, absence_type("AL"), date(2026, 4, 7)))
    assert admin_client.post(f"/absence/{theirs.pk}/cancel/").status_code == 302
