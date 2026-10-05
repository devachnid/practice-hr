from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from compliance.models import ReminderSchedule
from compliance.services import digest
from people.services import employments, positions, titles
from registers import adapters
from registers.adapters import Result
from registers.models import Lookup, RegisterBody, Registration
from registers.services import due, lookups, nightly, registrations
from tests.factories import make_employee, make_team

pytestmark = pytest.mark.django_db
User = get_user_model()
CLEAR = Result("clear", "Registered with a licence to practise", "Priya Patel", "a" * 64)
PROBLEM = Result("problem", "Suspended", "Priya Patel", "b" * 64)
UNREADABLE = Result("unreadable", "HTTP 503", "", "e" * 64)


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr(lookups, "sleep", lambda seconds: None)


@pytest.fixture
def gmc():
    b = RegisterBody.objects.get(code="gmc")
    b.positions.add(titles.get_or_create("Salaried GP"))
    b.verified = True
    b.save()
    return b


def _gp(hr_admin, manager=None, user=None):
    e = make_employee(first="Priya", last="Patel", user=user)
    emp = employments.start(hr_admin, e, timezone.localdate() - timedelta(days=400))
    positions.add(hr_admin, emp, titles.get_or_create("Salaried GP"), make_team(name=f"Team {e.pk}"), manager,
                  emp.start_date)
    return e


def _manager(hr_admin):
    m = make_employee(first="Mo", last="Khan", user=User.objects.create_user(email="mo@example.com", password="pw"))
    employments.start(hr_admin, m, timezone.localdate() - timedelta(days=800))
    return m


def _items(today=None):
    return due.due_items(today or timezone.localdate(), ReminderSchedule.get())


def test_a_problem_goes_to_hr_and_the_manager_with_the_body_and_the_words(hr_admin, gmc, monkeypatch):
    m = _manager(hr_admin)
    e = _gp(hr_admin, manager=m)
    r = registrations.set_number(hr_admin, e, gmc, "1234567")
    monkeypatch.setattr(adapters, "lookup", lambda *a: PROBLEM)
    lk = lookups.run(r, "scheduled")
    items = _items()
    by = {(i.recipient, i.label): i for i in items}
    hr_item = by[("hr@example.com", "GMC: Suspended")]
    assert hr_item.kind == "registration" and hr_item.state == "overdue"
    assert hr_item.due_on == timezone.localtime(lk.run_at).date()
    assert hr_item.key == f"registration:{e.pk}:gmc:problem" and hr_item.once is False
    assert hr_item.url.endswith(reverse("admin:people_employee_change", args=[e.pk]))
    mgr_item = by[("mo@example.com", "GMC: Suspended")]
    assert mgr_item.url.endswith(reverse("people:team")) and mgr_item.once is False
    assert len(items) == 2                                   # nobody else, not the person


@pytest.mark.parametrize("result", [Result("not_found", "No results were found", "", "c" * 64),
                                    Result("name_mismatch", "Registered", "Amir Khan", "d" * 64)])
def test_not_found_and_a_wrong_name_are_alerts_too(hr_admin, gmc, monkeypatch, result):
    e = _gp(hr_admin)
    r = registrations.set_number(hr_admin, e, gmc, "1234567")
    monkeypatch.setattr(adapters, "lookup", lambda *a: result)
    lookups.run(r, "scheduled")
    labels = {i.label for i in _items()}
    expected = "GMC: not found on the register" if result.outcome == "not_found" else \
        "GMC: the register shows Amir Khan, not this person"
    assert labels == {expected}


def test_a_changed_number_drops_the_old_numbers_alert_until_the_new_one_is_looked_up(hr_admin, gmc, monkeypatch):
    e = _gp(hr_admin)
    r = registrations.set_number(hr_admin, e, gmc, "1234567")
    monkeypatch.setattr(adapters, "lookup", lambda *a: PROBLEM)
    lookups.run(r, "scheduled")
    assert len(_items()) == 1
    r = registrations.set_number(hr_admin, e, gmc, "7654321")
    assert _items() == []                                    # the new number has not been looked up yet
    lookups.run(r, "scheduled")
    [item] = _items()
    assert item.recipient == "hr@example.com" and item.label == "GMC: Suspended"
    assert item.key == f"registration:{e.pk}:gmc:problem"


def test_the_label_comes_from_the_lookup_with_fallbacks_for_empty_words():
    assert due._label("GMC", Lookup(outcome="problem", status_text="")) == "GMC: a problem on the register"
    assert due._label("GMC", Lookup(outcome="problem", status_text="Suspended")) == "GMC: Suspended"
    assert due._label("GMC", Lookup(outcome="name_mismatch", name_on_register="")) == \
        "GMC: the register shows someone else, not this person"


def test_a_clear_result_and_a_fresh_registration_produce_nothing(hr_admin, gmc, monkeypatch):
    e = _gp(hr_admin)
    r = registrations.set_number(hr_admin, e, gmc, "1234567")
    assert _items() == []
    monkeypatch.setattr(adapters, "lookup", lambda *a: CLEAR)
    lookups.run(r, "scheduled")
    assert _items() == []


def test_a_missing_number_is_hrs_from_the_employment_start(hr_admin, gmc):
    e = _gp(hr_admin)
    [item] = _items()
    assert item.recipient == "hr@example.com" and item.label == "GMC number not recorded"
    assert item.state == "missing" and item.due_on == employments.current(e, timezone.localdate()).start_date
    assert item.key == f"registration:{e.pk}:gmc:missing"
    assert item.url.endswith(reverse("admin:people_employee_change", args=[e.pk]))


def test_unreadable_is_hrs_only_after_fourteen_days_or_a_pause(hr_admin, gmc, monkeypatch):
    e = _gp(hr_admin)
    r = registrations.set_number(hr_admin, e, gmc, "1234567")
    monkeypatch.setattr(adapters, "lookup", lambda *a: UNREADABLE)
    lk = lookups.run(r, "scheduled")
    today = timezone.localdate()
    assert _items(today) == []
    Lookup.objects.filter(pk=lk.pk).update(run_at=lk.run_at - timedelta(days=14))
    Registration.objects.filter(pk=r.pk).update(last_checked_at=lk.run_at - timedelta(days=14))
    [item] = _items(today)
    assert item.recipient == "hr@example.com" and item.label.startswith("GMC: could not be read since ")
    assert item.state == "overdue" and item.url.endswith(reverse("admin:registers_lookup_changelist"))
    assert item.kind == "registration_site" and digest._when(item) == ""
    gmc.paused_at = timezone.now()
    gmc.save()
    labels = {i.label for i in _items(today)}
    assert "GMC: checks are paused (the page could not be read)" in labels


def test_a_leaver_and_an_unneeded_body_raise_nothing(hr_admin, gmc, monkeypatch):
    e = _gp(hr_admin)
    r = registrations.set_number(hr_admin, e, gmc, "1234567")
    monkeypatch.setattr(adapters, "lookup", lambda *a: PROBLEM)
    lookups.run(r, "scheduled")
    assert len(_items()) == 1
    gmc.positions.clear()
    assert _items() == []
    gmc.positions.add(titles.get_or_create("Salaried GP"))
    employments.end(hr_admin, employments.current(e, timezone.localdate()), timezone.localdate() - timedelta(days=1),
                    "resigned")
    assert _items() == []


def test_the_digest_carries_registration_lines_in_plain_words(hr_admin, gmc, monkeypatch, configured):
    m = _manager(hr_admin)
    e = _gp(hr_admin, manager=m)
    r = registrations.set_number(hr_admin, e, gmc, "1234567")
    monkeypatch.setattr(adapters, "lookup", lambda *a: PROBLEM)
    lookups.run(r, "scheduled")
    result = digest.run(timezone.localdate())
    assert result["reminders_sent"] == 2
    body = next(m_.body for m_ in mail.outbox if m_.to == ["mo@example.com"])
    assert "Priya Patel" in body and "GMC: Suspended: found " in body and "overdue since" not in body


def test_the_digest_renders_a_paused_body_under_its_own_heading(hr_admin, gmc, configured):
    gmc.paused_at = timezone.now()
    gmc.save()
    result = digest.run(timezone.localdate())
    assert result["reminders_sent"] == 1 and result["reminders_failed"] == 0
    body = next(m_.body for m_ in mail.outbox if m_.to == ["hr@example.com"])
    assert "The registers" in body and "- GMC: checks are paused (the page could not be read)\n" in body


def test_the_nightly_step_runs_the_schedule_syncs_verified_and_never_fails_the_command(hr_admin, gmc,
                                                                                       monkeypatch, capsys):
    e = _gp(hr_admin)
    registrations.set_number(hr_admin, e, gmc, "1234567")
    monkeypatch.setattr(adapters, "lookup", lambda *a: CLEAR)
    monkeypatch.setattr(adapters, "verified", lambda code: code == "nmc")
    result = nightly.run(timezone.localdate())
    assert result["verified"] == 1 and RegisterBody.objects.get(code="nmc").verified
    assert not RegisterBody.objects.get(code="gmc").verified and result["skipped"] == 1 and result["run"] == 0

    def boom(today):
        raise ValueError("Priya Patel 1234567")
    monkeypatch.setattr(nightly, "run", boom)
    call_command("hr_nightly")                       # no CommandError
    out = capsys.readouterr().out
    assert "compliance: {" in out and "registrations: failed" in out


def test_the_nightly_output_has_a_registrations_line(db, capsys):
    call_command("hr_nightly")
    out = capsys.readouterr().out
    assert "registrations: {'run': 0" in out


def test_a_repeat_of_the_same_problem_keeps_its_key_and_a_new_kind_starts_afresh(hr_admin, gmc, monkeypatch):
    e = _gp(hr_admin)
    r = registrations.set_number(hr_admin, e, gmc, "1234567")
    monkeypatch.setattr(adapters, "lookup", lambda *a: PROBLEM)
    lookups.run(r, "scheduled")
    [first] = _items()
    lookups.run(r, "scheduled")
    [second] = _items()
    assert first.key == second.key == f"registration:{e.pk}:gmc:problem"
    monkeypatch.setattr(adapters, "lookup", lambda *a: Result("not_found", "No results", "", "c" * 64))
    lookups.run(r, "scheduled")
    [third] = _items()
    assert third.key == f"registration:{e.pk}:gmc:not_found"


def test_a_problem_then_an_unreadable_page_still_alerts(hr_admin, gmc, monkeypatch):
    m = _manager(hr_admin)
    e = _gp(hr_admin, manager=m)
    r = registrations.set_number(hr_admin, e, gmc, "1234567")
    monkeypatch.setattr(adapters, "lookup", lambda *a: PROBLEM)
    problem = lookups.run(r, "scheduled")
    monkeypatch.setattr(adapters, "lookup", lambda *a: UNREADABLE)
    lookups.run(r, "scheduled")
    items = _items()
    assert {(i.recipient, i.label) for i in items} == {("hr@example.com", "GMC: Suspended"),
                                                       ("mo@example.com", "GMC: Suspended")}
    assert all(i.due_on == timezone.localtime(problem.run_at).date() for i in items)


def test_a_problem_and_fourteen_days_unreadable_are_both_told(hr_admin, gmc, monkeypatch):
    e = _gp(hr_admin)
    r = registrations.set_number(hr_admin, e, gmc, "1234567")
    monkeypatch.setattr(adapters, "lookup", lambda *a: PROBLEM)
    problem = lookups.run(r, "scheduled")
    monkeypatch.setattr(adapters, "lookup", lambda *a: UNREADABLE)
    failed = lookups.run(r, "scheduled")
    Lookup.objects.filter(pk=problem.pk).update(run_at=problem.run_at - timedelta(days=20))
    Lookup.objects.filter(pk=failed.pk).update(run_at=failed.run_at - timedelta(days=15))
    labels = {i.label for i in _items()}
    assert "GMC: Suspended" in labels and any(lb.startswith("GMC: could not be read since ") for lb in labels)


def test_a_new_numbers_unreadable_lookup_does_not_revive_the_old_numbers_problem(hr_admin, gmc, monkeypatch):
    e = _gp(hr_admin)
    r = registrations.set_number(hr_admin, e, gmc, "1234567")
    monkeypatch.setattr(adapters, "lookup", lambda *a: PROBLEM)
    lookups.run(r, "scheduled")
    r = registrations.set_number(hr_admin, e, gmc, "7654321")
    monkeypatch.setattr(adapters, "lookup", lambda *a: UNREADABLE)
    lookups.run(r, "scheduled")
    assert _items() == []


def test_the_registrations_step_runs_before_the_reminders(db, capsys):
    call_command("hr_nightly")
    steps = [line.split(":", 1)[0] for line in capsys.readouterr().out.splitlines()]
    assert steps == ["people", "absence", "registrations", "compliance"]
