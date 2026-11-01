"""manage.py seed_demo: the shared fictional practice for a staging box."""
from datetime import timedelta
from io import StringIO

import pytest
from django.apps import apps
from django.core import mail
from django.core.mail import send_mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone
from oauth2_provider.models import Application

from absence.models import Absence, Policy, Pot
from accounts.models import AppRole, User
from people.management.commands.seed_demo import CAST
from people.models import AuditEntry, Contract, ContractType, Employee, Team
from people.services import contracts, employments, positions
from tests.factories import make_employee

# The app's own seeded absence policies stay, as on a real box (the one test that wants
# none deletes them itself). Seeding runs the bank-holiday sync for 19 people and takes
# several seconds, so the read-only tests share one seeded database (below).
pytestmark = pytest.mark.seeded_policies

BASE = "tom@example.org"
STAFF_DOMAIN_TAIL = "@example.org"


def seed(**kw):
    out = StringIO()
    call_command("seed_demo", **{"email_base": BASE, "yes_this_is_staging": True, **kw}, stdout=out)
    return out.getvalue()


def by_name(name):
    first, last = name.split()
    return Employee.objects.get(first_name=first, last_name=last)


@pytest.fixture(scope="class")
def seeded_database(django_db_setup, django_db_blocker):
    """One seeding for TestSeeded, rolled back at its end. Each test runs in its own
    savepoint on top of it, so a test may write without the others seeing it."""
    with django_db_blocker.unblock(), transaction.atomic():
        seed()
        yield
        transaction.set_rollback(True)


@pytest.fixture
def seeded(db, seeded_database):
    return None


EXPECTED = {   # name: (team, title, manager, contract type, unit, weekly amount or None to skip)
    "Morgan Ellis": ("Management", "Practice Manager", None, "Management", "hours", 37.5),
    "Jo Whitaker": ("Management", "Assistant Practice Manager", "Morgan Ellis", "Management", "hours", 37.5),
    "Dev Anand": ("Management", "Assistant Practice Manager", "Morgan Ellis", "Management", "hours", 37.5),
    "Rosa Delgado": ("Reception", "Reception Manager", "Morgan Ellis", "Reception", "hours", 37.5),
    "Sophie Brennan": ("Reception", "Receptionist", "Rosa Delgado", "Reception", "hours", None),
    "Liam Doyle": ("Reception", "Receptionist", "Rosa Delgado", "Reception", "hours", None),
    "Aisha Rahman": ("Reception", "Receptionist", "Rosa Delgado", "Reception", "hours", None),
    "Tomasz Kowal": ("Reception", "Receptionist", "Rosa Delgado", "Reception", "hours", None),
    "Priya Nair": ("GPs", "GP Partner", "Morgan Ellis", "Partner", "sessions", 8),
    "Callum Ross": ("GPs", "Salaried GP", "Priya Nair", "Salaried GP", "sessions", 6),
    "Helen Okafor": ("GPs", "Salaried GP", "Priya Nair", "Salaried GP", "sessions", 5),
    "Fiona Marsh": ("Nursing", "Lead Nurse", "Morgan Ellis", "Practice nurse", "hours", None),
    "Grace Tanaka": ("Nursing", "Practice Nurse", "Fiona Marsh", "Practice nurse", "hours", None),
    "Owen Pryce": ("Nursing", "Healthcare Assistant", "Fiona Marsh", "HCA", "hours", None),
    "Elena Fischer": ("Admin/Secretarial", "Secretary", "Jo Whitaker", "Administration", "hours", None),
    "Marcus Bell": ("Admin/Secretarial", "Medical Secretary", "Jo Whitaker", "Administration", "hours", None),
    "Hamid Qureshi": ("Pharmacy", "Head Pharmacist", "Morgan Ellis", "Pharmacy", "hours", None),
    "Ines Costa": ("Pharmacy", "Pharmacy Technician", "Hamid Qureshi", "Pharmacy", "hours", None),
    "Doreen Hughes": ("Cleaning", "Cleaner", "Jo Whitaker", "Cleaning", "hours", 15),
}


@pytest.mark.usefixtures("db", "seeded_database")
class TestSeeded:
    """Reads of one seeded database (and re-runs on top of it)."""

    def test_nineteen_people_with_plus_addresses(self):
        assert Employee.objects.count() == 19 == len(CAST)
        assert set(Employee.objects.values_list("work_email", flat=True)) == {
            f"tom+{p.first.lower()}.{p.last.lower()}{STAFF_DOMAIN_TAIL}" for p in CAST}
        assert by_name("Morgan Ellis").work_email == "tom+morgan.ellis@example.org"

    def test_teams_titles_managers_contracts_and_start_dates(self):
        today = timezone.localdate()
        for name, (team, title, manager, ctype, unit, amount) in EXPECTED.items():
            emp = employments.current(by_name(name), today)
            assert emp is not None and 2015 <= emp.start_date.year <= 2026 and emp.start_date < today, name
            (pos,) = positions.on(emp, today)
            assert (pos.team.name, pos.title.name) == (team, title), name
            assert (pos.line_manager.name if pos.line_manager else None) == manager, name
            (contract,) = contracts.active_on(emp, today)
            assert contract.contract_type.name == ctype and contract.contract_type.unit == unit, name
            if amount is not None:
                assert float(contract.weekly_amount) == amount, name

    def test_patterns_add_up_to_the_contract_and_part_timers_work_fewer_days(self):
        today = timezone.localdate()
        worked = {}
        for name in EXPECTED:
            emp = employments.current(by_name(name), today)
            pattern = emp.patterns.get()
            total = sum(d.am_units + d.pm_units for d in pattern.days.all())
            assert total == emp.contracts.get().weekly_amount, name
            worked[name] = [d.weekday for d in pattern.days.all() if d.am_units + d.pm_units]
        assert worked["Sophie Brennan"] == [0, 1, 2, 3, 4]
        assert [len(worked[n]) for n in ("Liam Doyle", "Aisha Rahman", "Tomasz Kowal")] == [4, 3, 2]
        assert len(worked["Priya Nair"]) == 4 and len(worked["Helen Okafor"]) == 3     # 8 and 5 sessions

    def test_only_the_gps_are_on_sessions(self):
        names = {c.employment.employee.name for c in Contract.objects.filter(contract_type__unit="sessions")}
        assert names == {"Priya Nair", "Callum Ross", "Helen Okafor"}

    def test_team_display_order(self):
        assert list(Team.objects.values_list("name", flat=True)) == [
            "GPs", "Reception", "Admin/Secretarial", "Nursing", "Pharmacy", "Management", "Cleaning"]

    def test_every_person_has_a_login_that_has_not_been_invited(self):
        for employee in Employee.objects.all():
            assert employee.user.email == employee.work_email
            assert not employee.user.has_usable_password()
            assert not employee.user.is_hr_admin and not employee.user.is_superuser
            assert employee.user.password_link_sent_at is None          # no invitation was ever issued

    def test_leave_pots_policies_and_sample_absences(self):
        today = timezone.localdate()
        for employee in Employee.objects.all():
            emp = employments.current(employee, today)
            assert Pot.objects.filter(employment=emp, absence_type__code="AL", year_end__gte=today).count() == 2
        for name in ("Pharmacy", "Cleaning"):          # not seeded by the app: the command adds them
            assert Policy.objects.filter(contract_type__name=name, absence_type__code="AL").count() == 1
            assert Policy.objects.filter(contract_type__name=name, absence_type__code="BH").count() == 1
        booked = Absence.objects.filter(auto_bank_holiday=False)
        assert sorted(booked.values_list("absence_type__code", flat=True)) == ["AL", "AL", "SICK"]
        assert set(booked.values_list("status", flat=True)) == {"approved"}
        last_month = today.replace(day=1) - timedelta(days=1)
        assert booked.get(absence_type__code="SICK").start_date.month == last_month.month
        for week in booked.filter(absence_type__code="AL"):
            assert today < week.start_date <= today + timedelta(days=70)
            assert (week.end_date - week.start_date).days == 4

    def test_the_seeded_policies_are_not_duplicated_or_changed(self):
        assert Policy.objects.filter(contract_type__name="Reception", absence_type__code="AL").count() == 1
        assert Policy.objects.filter(contract_type__name="Partner", absence_type__code="AL").count() == 1

    def test_everything_is_audited_to_a_login_that_cannot_sign_in(self):
        assert set(AuditEntry.objects.values_list("actor_email", flat=True)) == {"tom+seed.demo@example.org"}
        actor = User.objects.get(email="tom+seed.demo@example.org")
        assert not actor.is_active and not actor.has_usable_password() and not hasattr(actor, "employee")

    def test_the_people_api_returns_all_nineteen_with_gps_as_sessions(self, client, settings):
        settings.HR_API_TOKENS = frozenset({"t0k"})
        rows = client.get("/api/v1/people", HTTP_AUTHORIZATION="Bearer t0k").json()["people"]
        assert len(rows) == 19
        sessions = {r["name"] for r in rows if r["unit"] == "sessions"}
        assert sessions == {"Priya Nair", "Callum Ross", "Helen Okafor"}
        assert {r["unit"] for r in rows if r["name"] not in sessions} == {"hours"}
        assert all(len(r["positions"]) == 1 for r in rows)
        assert {r["positions"][0]["team"] for r in rows} == {
            "GPs", "Reception", "Admin/Secretarial", "Nursing", "Pharmacy", "Management", "Cleaning"}
        assert {r["email"] for r in rows} == set(Employee.objects.values_list("work_email", flat=True))
        assert next(r for r in rows if r["name"] == "Rosa Delgado")["positions"] == [
            {"title": "Reception Manager", "team": "Reception"}]

    def test_rerunning_creates_nothing_and_does_not_error(self):
        def snapshot():
            return {m._meta.label: m.objects.count() for m in apps.get_models()
                    if m._meta.app_label in ("people", "absence", "accounts", "onboarding", "oauth2_provider")}
        before = snapshot()
        out = seed()
        assert snapshot() == before
        assert "Created 0 employees, 0 logins" in out

    def test_the_manager_admin_grant_waits_for_the_client(self):
        assert not AppRole.objects.exists()
        assert "skipped" in seed() and "not registered" in seed()
        assert not AppRole.objects.exists()
        Application.objects.create(
            name="shift-central", redirect_uris="https://sc.example/cb/",
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE)
        assert "done, 4 managers" in seed()
        assert set(AppRole.objects.filter(is_admin=True).values_list("user__email", flat=True)) == {
            f"tom+{n}@example.org" for n in ("morgan.ellis", "jo.whitaker", "dev.anand", "rosa.delgado")}
        seed()
        assert AppRole.objects.count() == 4

    def test_a_different_base_is_foreign_to_a_seeded_database(self):
        with pytest.raises(CommandError, match=r"already holds 19 employee"):
            seed(email_base="someone@example.org")
        assert Employee.objects.count() == 19


# --- refusals, and what an empty or foreign database does ---------------------------

def test_the_cast_is_exactly_the_agreed_one():
    assert set(EXPECTED) == {f"{p.first} {p.last}" for p in CAST}


def test_refuses_without_the_flags(db):
    with pytest.raises(CommandError, match="--yes-this-is-staging"):
        call_command("seed_demo", email_base=BASE)
    with pytest.raises(CommandError, match="--email-base"):
        call_command("seed_demo", yes_this_is_staging=True)
    with pytest.raises(CommandError, match="--email-base"):
        call_command("seed_demo")
    assert not Employee.objects.exists() and not User.objects.exists() and not Team.objects.exists()


@pytest.mark.parametrize("base", ["tom", "a@b@c", "tom+x@example.org", "@example.org", "tom@", "to m@example.org"])
def test_refuses_a_bad_base(db, base):
    with pytest.raises(CommandError, match="--email-base"):
        seed(email_base=base)
    assert not Employee.objects.exists() and not User.objects.exists()


def test_refuses_when_the_database_holds_someone_else(db):
    make_employee("Real", "Person", "real.person@practice.example")
    make_employee("Other", "Person", "other.person@practice.example")
    with pytest.raises(CommandError, match=r"already holds 2 employee"):
        seed()
    assert Employee.objects.count() == 2 and not User.objects.exists() and not Team.objects.exists()


def test_an_existing_contract_type_of_the_wrong_unit_is_never_altered(db):
    ContractType.objects.filter(name="Partner").update(unit="hours")
    with pytest.raises(CommandError, match="Partner"):
        seed()
    assert ContractType.objects.get(name="Partner").unit == "hours"
    assert not Employee.objects.exists() and not Team.objects.exists() and not User.objects.exists()


def test_existing_teams_are_used_as_they_are(db):
    Team.objects.create(name="Reception", display_order=3, min_present=2)
    seed()
    team = Team.objects.get(name="Reception")
    assert (team.display_order, team.min_present) == (3, 2)
    assert Team.objects.count() == 7


def test_a_failure_part_way_leaves_nothing_behind(db, monkeypatch):
    from people.management.commands import seed_demo

    def boom(*a, **kw):
        raise RuntimeError("boom")
    monkeypatch.setattr(seed_demo.Command, "_open_pots", boom)
    with pytest.raises(RuntimeError):
        seed()
    assert not Employee.objects.exists() and not User.objects.exists() and not Team.objects.exists()
    assert not ContractType.objects.filter(name="Cleaning").exists() and not AuditEntry.objects.exists()


def test_it_never_sends_email_whatever_the_mail_settings(db, settings, monkeypatch):
    """A box with a relay configured, an empty policy table (so the command builds its own), and
    the invitation sender rigged to record any call: nothing is sent and nothing is called."""
    Policy.objects.all().delete()
    settings.EMAIL_HOST = "smtp.relay.example"
    settings.DEFAULT_FROM_EMAIL = "Practice HR <hr@example.org>"
    backend = settings.EMAIL_BACKEND
    called = []
    monkeypatch.setattr("accounts.mail.send_password_link", lambda *a, **k: called.append(a))
    seed()
    assert mail.outbox == [] and called == []
    # the override held only while the command ran
    assert settings.EMAIL_BACKEND == backend and settings.EMAIL_HOST == "smtp.relay.example"
    send_mail("x", "y", None, ["tom+morgan.ellis@example.org"])
    assert len(mail.outbox) == 1
    # every contract type used has its annual-leave policy, and the hours ones their bank-holiday policy
    for ct in ContractType.objects.filter(contracts__isnull=False).distinct():
        assert Policy.objects.filter(contract_type=ct, absence_type__code="AL").count() == 1, ct
        assert Policy.objects.filter(contract_type=ct, absence_type__code="BH").count() == (
            1 if ct.unit == "hours" else 0), ct
    assert Absence.objects.filter(auto_bank_holiday=False).count() == 3


def test_the_run_uses_a_backend_that_discards_mail(db):
    """The backstop under the services never mailing: anything sent while the command runs is dropped."""
    from people.management.commands.seed_demo import NO_MAIL
    with override_settings(**NO_MAIL):
        send_mail("x", "y", None, ["tom+morgan.ellis@example.org"])
    assert mail.outbox == []
