from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from checks.models import Check
from compliance.models import ReminderSchedule
from people.models import AuditEntry
from people.services import employments, positions, titles
from registers import adapters
from registers.adapters import Result
from registers.models import Lookup, RegisterBody, Registration
from registers.services import lookups, registrations
from tests.factories import make_employee, make_team

pytestmark = pytest.mark.django_db
CLEAR = Result("clear", "Registered with a licence to practise", "Priya Patel", "a" * 64)
PROBLEM = Result("problem", "Suspended", "Priya Patel", "b" * 64)
NOT_FOUND = Result("not_found", "No results were found", "", "c" * 64)
MISMATCH = Result("name_mismatch", "Registered with a licence to practise", "Amir Khan", "d" * 64)
UNREADABLE = Result("unreadable", "HTTP 503", "", "e" * 64)


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(lookups, "sleep", lambda seconds: None)


@pytest.fixture
def gp_bodies():
    """A GP title needing both the GMC and the Welsh list (the twin rows)."""
    gmc, mpl = RegisterBody.objects.get(code="gmc"), RegisterBody.objects.get(code="mpl_wales")
    title = titles.get_or_create("Salaried GP")
    gmc.positions.add(title)
    mpl.positions.add(title)
    for b in (gmc, mpl):
        b.verified = True
        b.save()
    return gmc, mpl


@pytest.fixture
def gmc_only():
    """A GP title needing the GMC alone, for tests that count lookups."""
    gmc = RegisterBody.objects.get(code="gmc")
    gmc.positions.add(titles.get_or_create("Salaried GP"))
    gmc.verified = True
    gmc.save()
    return gmc


def _gp(hr_admin, last="Patel", start_days_ago=400, end=None):
    e = make_employee(first="Priya", last=last)
    emp = employments.start(hr_admin, e, timezone.localdate() - timedelta(days=start_days_ago))
    positions.add(hr_admin, emp, titles.get_or_create("Salaried GP"), make_team(name=f"Team {e.pk}"), None,
                  emp.start_date)
    if end:
        employments.end(hr_admin, emp, end, "resigned")
    return e


def _answer(monkeypatch, result):
    monkeypatch.setattr(adapters, "lookup", lambda code, number, surname: result)


# ---- numbers on people ---------------------------------------------------------------------

def test_needed_follows_the_primary_title_and_active_bodies(hr_admin, gp_bodies):
    gmc, mpl = gp_bodies
    e = _gp(hr_admin)
    assert [b.code for b in registrations.needed(e, timezone.localdate())] == ["gmc", "mpl_wales"]
    assert [b.code for b in registrations.missing(e, timezone.localdate())] == ["gmc", "mpl_wales"]
    mpl.active = False
    mpl.save()
    assert [b.code for b in registrations.needed(e, timezone.localdate())] == ["gmc"]
    assert registrations.needed(make_employee(), timezone.localdate()) == []


def test_setting_the_gmc_number_makes_both_gp_rows_due_tonight_and_audits(hr_admin, gp_bodies):
    gmc, mpl = gp_bodies
    e = _gp(hr_admin)
    r = registrations.set_number(hr_admin, e, gmc, " 1234567 ")
    assert r.number == "1234567" and r.next_check_on == timezone.localdate()
    assert Registration.objects.get(employee=e, body=mpl).number == "1234567"
    entry = AuditEntry.objects.get(model="people.employee", object_id=e.pk, field="registration:gmc")
    assert entry.before == "" and entry.after == "1234567" and entry.actor == hr_admin
    assert registrations.missing(e, timezone.localdate()) == []
    registrations.set_number(hr_admin, e, gmc, "7654321")
    assert Registration.objects.get(employee=e, body=mpl).number == "7654321"
    assert AuditEntry.objects.filter(field="registration:gmc", before="1234567", after="7654321").exists()


def test_a_bad_number_is_refused_and_nothing_written(hr_admin, gp_bodies):
    gmc, _ = gp_bodies
    e = _gp(hr_admin)
    with pytest.raises(ValidationError) as exc:
        registrations.set_number(hr_admin, e, gmc, "12345")
    assert "seven digits" in str(exc.value)
    assert not Registration.objects.filter(employee=e).exists()


def test_clearing_a_number_removes_the_row_its_lookups_and_the_welsh_twin(hr_admin, gp_bodies, monkeypatch):
    gmc, mpl = gp_bodies
    e = _gp(hr_admin)
    registrations.set_number(hr_admin, e, gmc, "1234567")
    _answer(monkeypatch, CLEAR)
    lookups.run(Registration.objects.get(employee=e, body=gmc), "on_demand", hr_admin)
    registrations.clear_number(hr_admin, e, gmc)
    assert not Registration.objects.filter(employee=e).exists() and Lookup.objects.count() == 0
    assert AuditEntry.objects.filter(field="registration:gmc", before="1234567", after="").exists()


def test_rows_and_number_fields_cover_needed_bodies_with_and_without_numbers(hr_admin, gp_bodies):
    gmc, mpl = gp_bodies
    e = _gp(hr_admin)
    today = timezone.localdate()
    rows = registrations.rows(e, today)
    assert [(r.body.code, r.registration, r.needed) for r in rows] == [("gmc", None, True), ("mpl_wales", None, True)]
    registrations.set_number(hr_admin, e, gmc, "1234567")
    rows = registrations.rows(e, today)
    assert all(r.registration is not None for r in rows)
    assert registrations.number_fields(e, today) == [("registration_gmc", gmc, "GMC number")]
    nmc = RegisterBody.objects.get(code="nmc")
    nmc.positions.add(titles.get_or_create("Salaried GP"))
    assert [f[0] for f in registrations.number_fields(e, today)] == ["registration_gmc", "registration_nmc"]


def test_a_number_kept_after_the_title_no_longer_needs_it_shows_as_not_needed(hr_admin, gp_bodies):
    gmc, mpl = gp_bodies
    e = _gp(hr_admin)
    registrations.set_number(hr_admin, e, gmc, "1234567")
    mpl.positions.clear()
    rows = {r.body.code: r for r in registrations.rows(e, timezone.localdate())}
    assert rows["mpl_wales"].needed is False and rows["mpl_wales"].registration is not None


# ---- running one lookup ----------------------------------------------------------------------

def test_a_clear_lookup_records_a_professional_registration_check(hr_admin, gmc_only, monkeypatch):
    gmc = gmc_only
    e = _gp(hr_admin)
    r = registrations.set_number(hr_admin, e, gmc, "1234567")
    _answer(monkeypatch, CLEAR)
    lk = lookups.run(r, "scheduled")
    r.refresh_from_db()
    assert lk.outcome == "clear" and lk.trigger == "scheduled" and lk.requested_by is None
    assert lk.status_text == CLEAR.status_text and lk.name_on_register == "Priya Patel" and lk.page_hash == "a" * 64
    assert (r.last_outcome, r.last_status_text, r.last_name_on_register) == ("clear", CLEAR.status_text, "Priya Patel")
    assert r.last_checked_at is not None
    c = Check.objects.get(employee=e, check_type__code="professional_registration")
    assert c.outcome == Check.Outcome.CLEAR and c.reference == "1234567" and c.recorded_by is None
    assert c.note == "GMC: Registered with a licence to practise"
    assert c.done_on == timezone.localdate() and c.expires_on is not None


def test_a_problem_records_a_not_clear_check_and_the_rest_record_none(hr_admin, gmc_only, monkeypatch):
    gmc = gmc_only
    e = _gp(hr_admin)
    r = registrations.set_number(hr_admin, e, gmc, "1234567")
    _answer(monkeypatch, PROBLEM)
    lookups.run(r, "scheduled")
    c = Check.objects.get(employee=e, check_type__code="professional_registration")
    assert c.outcome == Check.Outcome.NOT_CLEAR and c.note == "GMC: Suspended"
    for result in (NOT_FOUND, MISMATCH, UNREADABLE):
        _answer(monkeypatch, result)
        lk = lookups.run(r, "on_demand", hr_admin)
        assert lk.outcome == result.outcome and lk.requested_by == hr_admin
    assert Check.objects.filter(employee=e).count() == 1
    r.refresh_from_db()
    assert r.last_outcome == "unreadable" and r.last_status_text == "HTTP 503"


def test_run_spreads_the_next_check_and_never_raises(hr_admin, gmc_only, monkeypatch):
    gmc = gmc_only
    e = _gp(hr_admin)
    r = registrations.set_number(hr_admin, e, gmc, "1234567")
    _answer(monkeypatch, CLEAR)
    for k, jitter in enumerate(lookups.JITTER):
        monkeypatch.setattr(lookups, "jitter", lambda k=k: lookups.JITTER[k])
        lookups.run(r, "scheduled")
        r.refresh_from_db()
        assert (r.next_check_on - timezone.localdate()).days == 7 + jitter

    def boom(code, number, surname):
        raise RuntimeError("Priya Patel")
    monkeypatch.setattr(adapters, "lookup", boom)
    lk = lookups.run(r, "scheduled")
    assert lk.outcome == "unreadable" and lk.error == "RuntimeError" and "Priya" not in lk.status_text


@pytest.mark.parametrize("error", [ValidationError("Priya Patel 1234567"), RuntimeError("Priya Patel 1234567")])
def test_a_failing_check_record_keeps_the_lookup_and_logs_no_name(hr_admin, gmc_only, monkeypatch, caplog, error):
    r = registrations.set_number(hr_admin, _gp(hr_admin), gmc_only, "1234567")
    _answer(monkeypatch, PROBLEM)

    def refuse(*args, **kwargs):
        raise error
    monkeypatch.setattr(lookups.checks, "record", refuse)
    with caplog.at_level("ERROR", logger="hr.registers"):
        lk = lookups.run(r, "scheduled")
    r.refresh_from_db()
    assert Lookup.objects.get(pk=lk.pk).outcome == "problem" and r.last_outcome == "problem"
    assert r.next_check_on > timezone.localdate() and not Check.objects.exists()
    assert error.__class__.__name__ in caplog.text
    assert "Priya" not in caplog.text and "1234567" not in caplog.text


def test_the_interval_setting_has_its_bounds_and_drives_the_spread(hr_admin, gmc_only, monkeypatch):
    s = ReminderSchedule.get()
    assert s.registration_every_days == 7
    s.registration_every_days = 30
    s.full_clean()
    s.save()
    r = registrations.set_number(hr_admin, _gp(hr_admin), gmc_only, "1234567")
    _answer(monkeypatch, CLEAR)
    lookups.run(r, "scheduled")
    r.refresh_from_db()
    assert 29 <= (r.next_check_on - timezone.localdate()).days <= 31
    for bad in (0, 91):
        s.registration_every_days = bad
        with pytest.raises(ValidationError):
            s.full_clean()


# ---- the schedule ------------------------------------------------------------------------------

def test_scheduled_runs_only_what_is_due_on_verified_active_unpaused_bodies(hr_admin, gp_bodies, monkeypatch):
    gmc, mpl = gp_bodies
    e = _gp(hr_admin)
    registrations.set_number(hr_admin, e, gmc, "1234567")
    later = Registration.objects.get(employee=e, body=mpl)
    later.next_check_on = timezone.localdate() + timedelta(days=3)
    later.save()
    calls = []

    def answer(code, number, surname):
        calls.append((code, number, surname))
        return CLEAR
    monkeypatch.setattr(adapters, "lookup", answer)
    counts = lookups.scheduled(timezone.localdate())
    assert calls == [("gmc", "1234567", "Patel")]
    assert counts == {"run": 1, "clear": 1, "problem": 0, "not_found": 0, "name_mismatch": 0, "unreadable": 0,
                      "skipped": 0}
    gmc.verified = False
    gmc.save()
    Registration.objects.filter(body=gmc).update(next_check_on=timezone.localdate())
    assert lookups.scheduled(timezone.localdate())["skipped"] == 1 and len(calls) == 1


def test_scheduled_skips_registrations_no_longer_needed_or_not_employed(hr_admin, gp_bodies, monkeypatch):
    gmc, mpl = gp_bodies
    leaver = _gp(hr_admin, last="Khan", end=timezone.localdate() - timedelta(days=1))
    registrations.set_number(hr_admin, leaver, gmc, "1111111")
    changed = _gp(hr_admin, last="Shah")
    registrations.set_number(hr_admin, changed, gmc, "2222222")
    mpl.positions.clear()                     # their title no longer needs the Welsh list
    calls = []
    monkeypatch.setattr(adapters, "lookup", lambda code, number, surname: calls.append((code, number)) or CLEAR)
    counts = lookups.scheduled(timezone.localdate())
    # the leaver's GMC row (not employed; no Welsh twin was made, since nothing
    # was needed of them) and the other's Welsh row (no longer needed)
    assert calls == [("gmc", "2222222")] and counts["skipped"] == 2


def test_scheduled_waits_between_requests_to_the_same_body_only(hr_admin, gp_bodies, monkeypatch):
    gmc, mpl = gp_bodies
    for last, n in (("Patel", "1111111"), ("Khan", "2222222")):
        registrations.set_number(hr_admin, _gp(hr_admin, last=last), gmc, n)
    waits = []
    monkeypatch.setattr(lookups, "sleep", lambda seconds: waits.append(seconds))
    _answer(monkeypatch, CLEAR)
    lookups.scheduled(timezone.localdate())
    # four lookups: gmc, gmc, mpl, mpl in body order; a wait before the second of each body
    assert waits == [lookups.PAUSE_BETWEEN_SECONDS, lookups.PAUSE_BETWEEN_SECONDS]


def test_three_unreadable_results_pause_the_body_and_the_schedule_skips_it(hr_admin, gmc_only, monkeypatch):
    gmc = gmc_only
    rows = [registrations.set_number(hr_admin, _gp(hr_admin, last=f"P{i}"), gmc, f"{i}234567") for i in range(1, 4)]
    _answer(monkeypatch, UNREADABLE)
    lookups.run(rows[0], "scheduled")
    lookups.run(rows[1], "scheduled")
    gmc.refresh_from_db()
    assert not gmc.paused
    lookups.run(rows[2], "scheduled")
    gmc.refresh_from_db()
    assert gmc.paused
    Registration.objects.filter(body=gmc).update(next_check_on=timezone.localdate())
    assert lookups.scheduled(timezone.localdate()) == {"run": 0, "clear": 0, "problem": 0, "not_found": 0,
                                                      "name_mismatch": 0, "unreadable": 0, "skipped": 3}


def test_an_on_demand_success_lifts_a_pause(hr_admin, gmc_only, monkeypatch):
    gmc = gmc_only
    r = registrations.set_number(hr_admin, _gp(hr_admin), gmc, "1234567")
    gmc.paused_at = timezone.now()
    gmc.save()
    _answer(monkeypatch, UNREADABLE)
    lookups.run(r, "on_demand", hr_admin)
    gmc.refresh_from_db()
    assert gmc.paused                                  # a failure changes nothing
    _answer(monkeypatch, CLEAR)
    lookups.run(r, "on_demand", hr_admin)
    gmc.refresh_from_db()
    assert not gmc.paused
    r.refresh_from_db()
    r.next_check_on = timezone.localdate()
    r.save()
    assert lookups.scheduled(timezone.localdate())["run"] == 1


def test_a_scheduled_run_on_a_paused_body_never_happens_but_on_demand_does(hr_admin, gmc_only, monkeypatch):
    gmc = gmc_only
    r = registrations.set_number(hr_admin, _gp(hr_admin), gmc, "1234567")
    gmc.paused_at = timezone.now()
    gmc.save()
    _answer(monkeypatch, CLEAR)
    assert lookups.scheduled(timezone.localdate())["skipped"] >= 1
    assert lookups.run(r, "on_demand", hr_admin).outcome == "clear"
