"""TOIL claims (absence.services.toil): earned by a claim the person's
approver decides, as leave is. Dates are offsets from today, so nothing here
expires with the calendar."""
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.utils import timezone

from absence.models import AbsenceType, LedgerEntry, ToilClaim
from absence.services import chase, ledger, nightly, notify, payroll, pots, toil, year_end
from people.models import AuditEntry
from people.services import positions
from tests.factories import (absence_type, current_leave_year, hours_employee, make_contract,
                             make_contract_type, make_employee, make_employment, make_policy, make_team)

D = Decimal
K = LedgerEntry.Kind
S = ToilClaim.Status
User = get_user_model()


def _today():
    return timezone.localdate()


def _worked(days_ago=3):
    return _today() - timedelta(days=days_ago)


def _people(employee_user):
    """Sam (employee_user), whose approver is Boss. Returns (sam's employment, boss's user)."""
    start = current_leave_year()[0] - timedelta(days=400)
    boss_user = User.objects.create_user(email="boss@example.org", password="pw")
    boss = make_employee(first="Boss", last="Jones", user=boss_user)
    make_employment(employee=boss, start=start)
    emp = hours_employee(start=start, employee=make_employee(user=employee_user))
    positions.add(None, emp, "Receptionist", make_team(), boss, start)
    return emp, boss_user


def _claim(employee_user, emp, units="2.5", reason="Late clinic", day=None):
    return toil.claim(employee_user, emp, day or _worked(), D(units), reason)


# --- what a claim may be ---------------------------------------------------------------

def test_a_claim_waits_for_the_approver_and_writes_nothing(employee_user):
    emp, _ = _people(employee_user)
    c = _claim(employee_user, emp)
    assert (c.status, c.units, c.day, c.reason, c.requested_by) == (S.REQUESTED, D("2.5"), _worked(),
                                                                     "Late clinic", employee_user)
    assert c.earned is None and not LedgerEntry.objects.filter(kind=K.TOIL_EARNED).exists()
    assert str(c) == f"Sam Patel: 2.5 hours on {_worked():%d %b %Y}"
    assert AuditEntry.objects.filter(model="absence.toilclaim", object_id=c.pk, actor=employee_user).exists()


def test_a_claim_for_today_is_allowed_and_for_tomorrow_refused(employee_user):
    emp, _ = _people(employee_user)
    assert _claim(employee_user, emp, day=_today()).status == S.REQUESTED
    with pytest.raises(ValidationError, match="already worked"):
        _claim(employee_user, emp, day=_today() + timedelta(days=1))
    assert ToilClaim.objects.count() == 1


def test_a_claim_needs_employment_and_a_contract_on_the_day(employee_user, hr_admin):
    _people(employee_user)
    newby = hours_employee(start=_today() - timedelta(days=30), employee=make_employee(first="Newby"))
    with pytest.raises(ValidationError, match="not employed"):
        toil.claim(hr_admin, newby, newby.start_date - timedelta(days=1), D("1"), "Late clinic")
    bare = make_employment(employee=make_employee(first="Nocon"), start=_today() - timedelta(days=30))
    with pytest.raises(ValidationError, match="no contract"):
        toil.claim(hr_admin, bare, _worked(), D("1"), "Late clinic")
    assert not ToilClaim.objects.exists()


@pytest.mark.parametrize("units", ["0", "-1", "0.00"])
def test_a_claim_is_for_more_than_zero(employee_user, units):
    emp, _ = _people(employee_user)
    with pytest.raises(ValidationError, match="more than zero"):
        _claim(employee_user, emp, units=units)


@pytest.mark.parametrize("units,ok", [("0.25", True), ("1.75", True), ("1.1", False), ("0.3", False)])
def test_hours_are_claimed_in_quarter_hours(employee_user, units, ok):
    emp, _ = _people(employee_user)
    if ok:
        assert _claim(employee_user, emp, units=units).units == D(units)
    else:
        with pytest.raises(ValidationError, match="steps of 0.25 hours"):
            _claim(employee_user, emp, units=units)


@pytest.mark.parametrize("units,ok", [("0.5", True), ("2", True), ("0.25", False), ("1.75", False)])
def test_sessions_are_claimed_in_half_sessions(hr_admin, units, ok):
    emp = make_employment(start=current_leave_year()[0] - timedelta(days=30))
    ct = make_contract_type("Salaried GP", unit="sessions", full_time=D("9"))
    make_contract(emp, ct, amount=D("6"))
    make_policy(ct)
    if ok:
        assert toil.claim(hr_admin, emp, _worked(), D(units), "Extra surgery").units == D(units)
    else:
        with pytest.raises(ValidationError, match="steps of 0.5 sessions"):
            toil.claim(hr_admin, emp, _worked(), D(units), "Extra surgery")


@pytest.mark.parametrize("reason", ["", "   "])
def test_a_claim_says_why(employee_user, reason):
    emp, _ = _people(employee_user)
    with pytest.raises(ValidationError, match="Say what"):
        _claim(employee_user, emp, reason=reason)


def test_a_claim_older_than_the_expiry_window_is_refused(employee_user):
    emp, _ = _people(employee_user)
    assert _claim(employee_user, emp, day=_today() - timedelta(days=365)).status == S.REQUESTED
    with pytest.raises(ValidationError, match="more than 365 days ago, so it would already have expired"):
        _claim(employee_user, emp, day=_today() - timedelta(days=366))
    AbsenceType.objects.filter(code="TOIL").update(earned_expires_after_days=30)
    with pytest.raises(ValidationError, match="more than 30 days ago"):
        _claim(employee_user, emp, day=_today() - timedelta(days=31))
    AbsenceType.objects.filter(code="TOIL").update(earned_expires_after_days=None)   # never expires: no limit
    assert _claim(employee_user, emp, day=_today() - timedelta(days=366)).status == S.REQUESTED


def test_earn_refuses_a_closed_pot(employee_user, hr_admin):
    emp, _ = _people(employee_user)
    last_year_day = current_leave_year()[0] - timedelta(days=10)
    year_end.close(pots.for_day(emp, absence_type("TOIL"), last_year_day))
    with pytest.raises(ValidationError, match="is closed"):
        toil.earn(hr_admin, emp, D("1"), last_year_day, "Late clinic")
    assert not LedgerEntry.objects.filter(kind=K.TOIL_EARNED).exists()


# --- who decides ------------------------------------------------------------------------

def test_the_approver_recording_a_claim_approves_it_at_once(employee_user):
    emp, boss_user = _people(employee_user)
    c = toil.claim(boss_user, emp, _worked(), D("3"), "Covered the late surgery")
    assert c.status == S.APPROVED and c.decided_by == boss_user and c.requested_by == boss_user
    assert c.earned.units == D("3") and c.earned.date == _worked()


def test_an_hr_admin_recording_a_claim_approves_it_at_once(employee_user, hr_admin):
    emp, _ = _people(employee_user)
    c = toil.claim(hr_admin, emp, _worked(), D("3"), "Flu clinic", requested_by=hr_admin)
    assert c.status == S.APPROVED and c.decided_by == hr_admin and c.earned is not None


def test_nobody_decides_their_own_claim_not_even_an_hr_admin(employee_user, hr_admin):
    emp, _ = _people(employee_user)
    c = _claim(employee_user, emp)
    for decide in (toil.approve, toil.decline):
        with pytest.raises(ValidationError, match="your own"):
            decide(employee_user, c)
    hr_self = hours_employee(start=emp.start_date, employee=make_employee(first="Hilary", user=hr_admin))
    own = toil.claim(hr_admin, hr_self, _worked(), D("1"), "Payroll late")
    assert own.status == S.REQUESTED                     # an HR admin's own claim goes to another HR admin
    with pytest.raises(ValidationError, match="your own"):
        toil.approve(hr_admin, own)
    assert not LedgerEntry.objects.filter(kind=K.TOIL_EARNED).exists()


def test_approving_writes_one_earned_line_dated_the_day_worked_and_links_it(employee_user):
    emp, boss_user = _people(employee_user)
    c = _claim(employee_user, emp, units="2.5", reason="Late clinic")
    toil.approve(boss_user, c, "Thanks")
    c.refresh_from_db()
    line = LedgerEntry.objects.get(kind=K.TOIL_EARNED)
    assert c.earned == line and c.status == S.APPROVED and c.decided_by == boss_user
    assert c.decided_at is not None and c.decision_comment == "Thanks"
    assert (line.units, line.date, line.note, line.actor) == (D("2.5"), _worked(), "TOIL claim: Late clinic", boss_user)
    assert line.pot.absence_type.code == "TOIL" and ledger.balance(line.pot) == D("2.5")
    assert AuditEntry.objects.filter(model="absence.toilclaim", object_id=c.pk, field="status",
                                     before="requested", after="approved").exists()


def test_approve_updates_the_callers_copy(employee_user):
    emp, boss_user = _people(employee_user)
    c = _claim(employee_user, emp)
    toil.approve(boss_user, c)
    assert c.status == S.APPROVED and c.earned_id is not None


def test_declining_writes_nothing_to_the_ledger(employee_user):
    emp, boss_user = _people(employee_user)
    c = _claim(employee_user, emp)
    toil.decline(boss_user, c, "Not agreed in advance")
    c.refresh_from_db()
    assert (c.status, c.decided_by, c.decision_comment) == (S.DECLINED, boss_user, "Not agreed in advance")
    assert c.earned is None and not LedgerEntry.objects.exists()


def test_a_claim_is_decided_once(employee_user):
    emp, boss_user = _people(employee_user)
    c = _claim(employee_user, emp)
    stale = ToilClaim.objects.get(pk=c.pk)
    toil.approve(boss_user, c)
    for decide in (toil.approve, toil.decline):
        with pytest.raises(ValidationError, match="Only a claim still waiting"):
            decide(boss_user, stale)                     # a stale copy is re-read under the lock
    assert LedgerEntry.objects.filter(kind=K.TOIL_EARNED).count() == 1


def test_the_claimant_or_an_hr_admin_cancels_a_waiting_claim(employee_user, hr_admin):
    emp, boss_user = _people(employee_user)
    c = _claim(employee_user, emp)
    with pytest.raises(ValidationError, match="Only the person"):
        toil.cancel(boss_user, c)
    toil.cancel(employee_user, c)
    c.refresh_from_db()
    assert (c.status, c.cancelled_by) == (S.CANCELLED, employee_user) and c.cancelled_at is not None
    other = _claim(employee_user, emp)
    toil.cancel(hr_admin, other)
    assert ToilClaim.objects.get(pk=other.pk).status == S.CANCELLED
    assert not LedgerEntry.objects.exists()


def test_an_approved_claim_is_not_cancelled_hr_adjusts_instead(employee_user, hr_admin):
    emp, boss_user = _people(employee_user)
    c = toil.approve(boss_user, _claim(employee_user, emp))
    for who in (employee_user, hr_admin):
        with pytest.raises(ValidationError, match="Only a claim still waiting"):
            toil.cancel(who, c)
    assert ToilClaim.objects.get(pk=c.pk).status == S.APPROVED


# --- expiry, payroll, the chase ------------------------------------------------------------

def test_claimed_toil_expires_365_days_after_the_day_worked_via_the_nightly(employee_user):
    emp, boss_user = _people(employee_user)
    worked = _worked(10)
    toil.approve(boss_user, _claim(employee_user, emp, units="3", day=worked))
    expired = LedgerEntry.objects.filter(kind=K.EXPIRY, note__startswith=year_end.TOIL_EXPIRED)
    nightly.run(worked + timedelta(days=365))
    assert not expired.exists()                                     # the deadline: still usable
    nightly.run(worked + timedelta(days=366))
    assert [(e.units, e.date) for e in expired] == [(D("-3"), worked + timedelta(days=366))]


def test_the_payroll_toil_sheet_lists_claimed_toil(employee_user):
    emp, boss_user = _people(employee_user)
    toil.approve(boss_user, _claim(employee_user, emp, units="2", reason="Late clinic"))
    worked, today = _worked(), _today()
    wb = payroll.build(min(worked, today).replace(day=1), today)
    rows = [[v.date() if hasattr(v, "date") else v for v in r] for r in wb["TOIL"].iter_rows(values_only=True)][1:]
    assert rows == [["Sam Patel", today, 2.0, "TOIL earned", "TOIL claim: Late clinic", worked, today]]


def _old_claim(employee_user, emp, working_days_ago=6):
    c = _claim(employee_user, emp)
    asked = _today() - timedelta(days=working_days_ago * 2)          # weekends and all: well past the limit
    ToilClaim.objects.filter(pk=c.pk).update(requested_at=timezone.make_aware(
        timezone.datetime.combine(asked, timezone.datetime.min.time())))
    return ToilClaim.objects.get(pk=c.pk)


def test_the_chase_includes_claims_by_the_same_working_day_rule(employee_user):
    emp, _ = _people(employee_user)
    fresh = _claim(employee_user, emp)
    old = _old_claim(employee_user, emp)
    waiting = chase.waiting(_today())
    assert old in waiting and fresh not in waiting


def test_the_chase_emails_hr_once_about_a_claim_and_stamps_it(configured, employee_user, hr_admin):
    emp, _ = _people(employee_user)
    old = _old_claim(employee_user, emp)
    assert chase.notify_once(_today()) == 1
    m = mail.outbox[-1]
    assert m.to == [hr_admin.email] and m.subject == "1 TOIL claim(s) waiting"
    assert notify.claim_decide_url(old) in m.body and "Sam Patel" in m.body
    assert ToilClaim.objects.get(pk=old.pk).chased_at is not None
    assert chase.notify_once(_today()) == 0


# --- email ---------------------------------------------------------------------------------

def test_the_claim_decide_path_is_its_route():
    from django.urls import reverse
    assert reverse("absence:toil_decide", args=[7]) == notify.CLAIM_DECIDE_PATH.format(pk=7)


def test_a_submitted_claim_emails_the_approver_with_the_link(configured, employee_user, settings):
    settings.SITE_URL = "https://hr.example.org"
    emp, _ = _people(employee_user)
    c = _claim(employee_user, emp)
    assert notify.claim_submitted(c) is True
    m = mail.outbox[-1]
    assert m.to == ["boss.jones.1@example.org"] and m.subject == "TOIL claim from Sam Patel"
    assert f"https://hr.example.org/absence/toil/{c.pk}/decide/" in m.body
    assert "2.50 hours" in m.body and "Late clinic" in m.body and m.reply_to == [emp.employee.work_email]


def test_a_decided_claim_emails_the_claimant(configured, employee_user):
    emp, boss_user = _people(employee_user)
    c = toil.decline(boss_user, _claim(employee_user, emp), "Not agreed")
    assert notify.claim_decided(c) is True
    m = mail.outbox[-1]
    assert m.to == [emp.employee.work_email] and m.subject == "Your TOIL claim was declined"
    assert "Not agreed" in m.body and "2.50 hours" in m.body


def test_claim_emails_never_raise(employee_user):
    emp, _ = _people(employee_user)
    c = _claim(employee_user, emp)
    assert notify.claim_submitted(c) is False                       # email is not configured
    assert AbsenceType.objects.get(code="TOIL")                     # nothing else disturbed


# --- a claim for a day in a leave year that has ended (a January year: 2 Jan for 30 Dec) ------

@contextmanager
def _on(day):
    """timezone.now() (so localdate(), created_at, requested_at) at noon on `day`."""
    moment = timezone.make_aware(datetime.combine(day, time(12)))
    with mock.patch("django.utils.timezone.now", return_value=moment):
        yield


def _january_people(employee_user):
    """Sam and Boss on an hours contract whose annual leave (so TOIL) runs from 1 January."""
    from absence.models import Policy
    boss_user = User.objects.create_user(email="boss@example.org", password="pw")
    boss = make_employee(first="Boss", last="Jones", user=boss_user)
    make_employment(employee=boss, start=date(2025, 1, 1))
    emp = hours_employee(start=date(2025, 1, 1), employee=make_employee(user=employee_user))
    positions.add(None, emp, "Receptionist", make_team(), boss, date(2025, 1, 1))
    Policy.objects.update(year_start_month=1)
    return emp, boss_user


def test_a_claim_for_a_closed_year_lands_on_the_current_pot_dated_the_day_worked(employee_user):
    emp, boss_user = _january_people(employee_user)
    with _on(date(2026, 12, 2)):
        old = toil.claim(boss_user, emp, date(2026, 12, 1), D("1"), "Flu clinic").earned.pot
    with _on(date(2027, 1, 2)):
        year_end.run(date(2027, 1, 2))                               # the 2026 pot closes overnight
        assert year_end.is_closed(old)
        c = toil.claim(employee_user, emp, date(2026, 12, 30), D("3"), "Covered the late surgery")
        toil.approve(boss_user, c)
    line = ToilClaim.objects.get(pk=c.pk).earned
    assert (line.date, line.units, line.pot.year_start) == (date(2026, 12, 30), D("3"), date(2027, 1, 1))
    assert ledger.balance(line.pot) == D("4") and ledger.balance(old) == D("0")
    ours = LedgerEntry.objects.filter(kind=K.EXPIRY, note=year_end._toil_marker(line))
    year_end.expire_toil(line.pot, date(2027, 12, 30))                  # 365 days after 30 Dec: still usable
    assert not ours.exists()
    year_end.expire_toil(line.pot, date(2027, 12, 31))
    assert [e.units for e in ours] == [D("-3")]


def test_a_claim_for_an_ended_year_with_no_pot_opens_none_for_it(employee_user):
    emp, boss_user = _january_people(employee_user)
    with _on(date(2027, 1, 2)):
        c = toil.approve(boss_user, toil.claim(employee_user, emp, date(2026, 12, 30), D("2"), "Late clinic"))
    assert ToilClaim.objects.get(pk=c.pk).earned.pot.year_start == date(2027, 1, 1)
    assert not pots.lookup(emp, absence_type("TOIL"), date(2026, 12, 30))


def _leaver_claim(employee_user, left_days_before_year=20, worked_days_before_year=40):
    """Sam left `left_days_before_year` days before this leave year began, and
    claims, a month into this one, a day worked before he left (in the year
    that has ended). Returns (employment, boss, claim, the last day, today)."""
    emp, boss_user = _people(employee_user)
    start = current_leave_year()[0]
    last, today = start - timedelta(days=left_days_before_year), start + timedelta(days=30)
    type(emp).objects.filter(pk=emp.pk).update(end_date=last, leaving_reason="resigned")
    emp.refresh_from_db()
    with _on(today):
        c = toil.claim(employee_user, emp, start - timedelta(days=worked_days_before_year), D("2"), "Late clinic")
    return emp, boss_user, c, last, today


def test_a_leavers_late_claim_lands_on_the_pot_of_their_last_day(employee_user):
    emp, boss_user, c, last, today = _leaver_claim(employee_user)
    with _on(today):
        toil.approve(boss_user, c)
    line = ToilClaim.objects.get(pk=c.pk).earned
    assert (line.date, line.units) == (c.day, D("2"))
    assert line.pot.year_start == pots.bounds(emp, absence_type("TOIL"), last)[0]
    assert not emp.pots.filter(year_start__gt=last).exists()


def test_a_leavers_late_claim_for_a_closed_pot_is_refused_and_writes_nothing(employee_user):
    emp, boss_user, c, last, today = _leaver_claim(employee_user)
    year_end.close(pots.for_day(emp, absence_type("TOIL"), last))
    with _on(today), pytest.raises(ValidationError, match="is closed"):
        toil.approve(boss_user, c)
    assert ToilClaim.objects.get(pk=c.pk).status == S.REQUESTED
    assert not LedgerEntry.objects.filter(kind=K.TOIL_EARNED).exists()
    assert not emp.pots.filter(year_start__gt=last).exists()


def test_a_current_employees_late_claim_still_lands_on_the_pot_open_today(employee_user):
    emp, boss_user = _people(employee_user)
    start = current_leave_year()[0]
    with _on(start + timedelta(days=30)):
        c = toil.claim(employee_user, emp, start - timedelta(days=10), D("2"), "Late clinic")
        toil.approve(boss_user, c)
    line = ToilClaim.objects.get(pk=c.pk).earned
    assert (line.date, line.pot.year_start) == (start - timedelta(days=10), start)


def test_claimed_toil_is_on_payroll_in_the_month_it_was_approved(employee_user):
    emp, boss_user = _january_people(employee_user)
    with _on(date(2026, 12, 20)):
        waiting = toil.claim(employee_user, emp, date(2026, 12, 18), D("1.5"), "Late clinic")
    with _on(date(2027, 1, 2)):
        year_end.run(date(2027, 1, 2))
        c = toil.claim(employee_user, emp, date(2026, 12, 30), D("3"), "Covered the late surgery")
        toil.approve(boss_user, c)
        toil.approve(boss_user, waiting)                  # its own year's pot has not opened: the current one

    def rows(first, last):
        return [list(r) for r in payroll.build(first, last)["TOIL"].iter_rows(values_only=True)]

    head, *jan = rows(date(2027, 1, 1), date(2027, 1, 31))
    assert head == ["Name", "Date", "Units", "Kind", "Note", "Day worked", "Approved"]
    as_dates = [[v.date() if hasattr(v, "date") else v for v in r] for r in jan]
    assert sorted(as_dates, key=lambda r: r[5]) == [
        ["Sam Patel", date(2027, 1, 2), 1.5, "TOIL earned", "TOIL claim: Late clinic", date(2026, 12, 18),
         date(2027, 1, 2)],
        ["Sam Patel", date(2027, 1, 2), 3.0, "TOIL earned", "TOIL claim: Covered the late surgery",
         date(2026, 12, 30), date(2027, 1, 2)]]
    assert rows(date(2026, 12, 1), date(2026, 12, 31))[1:] == []           # worked in December, approved in January
