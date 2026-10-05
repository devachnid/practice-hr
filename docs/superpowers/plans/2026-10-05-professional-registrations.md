# Professional Registration Checks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record each clinician's professional registration number once, check it against the regulator's public register on a weekly schedule and on demand, record a clear result as a Professional registration check, and alert HR and the line manager the next morning when something is wrong.

**Architecture:** A new `registers` app: register bodies required by position title, one registration per person per body, an append-only lookup log, and one adapter per body that fetches the regulator's public search page through a single replaceable HTTP function and parses the page's text. A clear or problem lookup records a check through the existing `checks` service, so the Compliance tab, dashboard, checklist hook and check reminders work unchanged; problems ride the existing morning digest as a new due-item source.

**Tech Stack:** Django 5.2, SQLite, django-unfold admin, pytest-django. HTTP through the standard library (`urllib.request`), HTML to text through the standard library (`html.parser`); no new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-05-professional-registrations-design.md`

## Global Constraints

- Services are the only writers; views and admin call services. Pages never write on GET.
- `timezone.localdate()` for "today"; never `date.today()`.
- Tests make no network calls: `registers.http.get` is the one function that touches the network and every test replaces it (Task 2 adds the test that proves nothing connects). Tests never depend on the calendar.
- No PII in logs: the error class, the body code and the registration pk only; never the number, the name or the page.
- The fetched page is never stored: only its SHA-256, the parsed status words (at most 200 characters) and the name shown.
- Politeness: one request at a time, two seconds between requests to the same body, a ten-second timeout, a fixed user agent naming the practice, no retries inside a run.
- No lookup ever raises out of the nightly job.
- Number formats, refused on the form and by the service: GMC seven digits; NMC two digits, a letter, four digits, a letter (`12A3456B`, which corrects the spec's example `AB12C3456`); GPhC seven digits. Whitespace stripped, letters upper-cased.
- The live register pages cannot be reached from the build sandbox. Parsers are written against each body's status vocabulary and tested on synthetic page text; real-page fixtures are captured by a person (Task 7's README) and run through the same tests when present. A body is **verified** only when its fixtures exist.
- Every commit message ends with the two trailer lines the project uses (`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01PkKQLdYCQnRZiVssdedFig`); no model name anywhere else.
- Run before every commit: the task's test files, `.venv/bin/ruff check .`, and `DEBUG=1 .venv/bin/python manage.py makemigrations --check`.

## Review Focus

1. **A number typed with spaces or in lower case** (`"12a 3456 b"`) must save as `12A3456B` and never reach a register in its typed form. Pinned in Task 1 (`test_numbers_are_normalised_before_the_format_is_checked`).
2. **A person whose title changes so a body is no longer needed** keeps the row but is neither checked nor alerted on it, and a leaver is never checked again. Pinned in Task 3 (`test_scheduled_skips_registrations_no_longer_needed_or_not_employed`).
3. **A register page fetched as HTTP 200 that says "no results"** is `not_found`, not `unreadable`, and never `clear` because the vocabulary happened to appear in the page's boilerplate. Pinned in Task 2 (`test_a_no_results_page_is_not_found` for every body).
4. **A surname with an accent or a hyphen on one side only** (`Ní Bhriain` vs `Ni Bhriain`, `Smith-Jones` vs `Smith`) matches; a different surname never does. Pinned in Task 2 (`test_surnames_match_loosely_and_never_wrongly`).
5. **A body paused by three unreadable results** is unpaused by one successful on-demand check and resumes its schedule the same night. Pinned in Task 3 (`test_an_on_demand_success_lifts_a_pause`).

---

## File structure

- `registers/__init__.py`, `registers/apps.py` — the app.
- `registers/models.py` — `RegisterBody`, `Registration`, `Lookup`.
- `registers/migrations/0001_initial.py`, `0002_seed_bodies.py`.
- `registers/numbers.py` — formats and normalisation (pure).
- `registers/names.py` — loose surname matching (pure).
- `registers/http.py` — the one network function and `FetchError`.
- `registers/adapters/__init__.py` — `Result`, the registry, `verified`, `lookup`.
- `registers/adapters/base.py` — HTML to text, the shared fetch-parse-match flow.
- `registers/adapters/gmc.py`, `mpl_wales.py`, `nmc.py`, `gphc.py` — `url`, `parse`.
- `registers/adapters/fixtures/README.md` and `fixtures/<code>/<outcome>.html` (captured later).
- `registers/services/registrations.py` — numbers on people: `needed`, `missing`, `set_number`, `clear_number`, `rows`, `number_fields`.
- `registers/services/lookups.py` — `run`, `scheduled`, the pause rule.
- `registers/services/due.py` — `due_items(today, sched)`.
- `registers/services/nightly.py` — `run(today)`.
- `registers/admin.py` — Register bodies and Registration lookups.
- `registers/views.py`, `registers/urls.py` — Check now (confirm on GET, run on POST).
- `registers/management/commands/registers_parse.py` — parse a saved page.
- `templates/registers/check_now.html`, `templates/people/_registrations.html`.
- Modified: `config/settings.py` (INSTALLED_APPS), `config/urls.py`, `accounts/backends.py` (HR_APPS), `hr/admin_site.py` (nav), `compliance/models.py` + `compliance/migrations/0002_…` + `compliance/admin.py` (the interval setting), `compliance/services/digest.py` (source and wording), `people/management/commands/hr_nightly.py`, `people/admin.py` and `people/admin_forms.py` (number fields, Registrations table), `people/views.py` and `templates/people/me.html` (My record card), `absence/admin_dashboard.py` + `templates/admin/index.html` (card), docs.

---

### Task 1: The `registers` app: models, seed, formats, admin lists, navigation

**Files:**
- Create: `registers/__init__.py`, `registers/apps.py`, `registers/models.py`, `registers/numbers.py`, `registers/admin.py`, `registers/migrations/0001_initial.py` (generated), `registers/migrations/0002_seed_bodies.py`
- Modify: `config/settings.py` (INSTALLED_APPS after `"compliance"`), `accounts/backends.py` (HR_APPS), `hr/admin_site.py` (Compliance group)
- Test: `tests/test_registers_models.py`

**Interfaces:**
- Produces: `RegisterBody(name, code, positions, active, verified, paused_at, display_order)` with `.paused` property; `Registration(employee, body, number, next_check_on, last_outcome, last_status_text, last_name_on_register, last_checked_at)` with `.lookups`; `Lookup(registration, run_at, trigger, requested_by, outcome, status_text, name_on_register, page_hash, error)` with `Lookup.Outcome.{CLEAR,PROBLEM,NOT_FOUND,NAME_MISMATCH,UNREADABLE}` (values `clear`, `problem`, `not_found`, `name_mismatch`, `unreadable`) and `Lookup.Trigger.{SCHEDULED,ON_DEMAND}` (`scheduled`, `on_demand`); `registers.numbers.normalise(value) -> str`, `registers.numbers.check(code, value)` (raises `ValidationError` with the format in words), `registers.numbers.FORMATS`, `registers.numbers.SHARES_NUMBER_WITH = {"mpl_wales": "gmc"}`; seeded body codes `gmc`, `mpl_wales`, `nmc`, `gphc`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_registers_models.py
import pytest
from django.core.exceptions import ValidationError

from registers import numbers
from registers.models import Lookup, RegisterBody, Registration
from tests.factories import make_employee

pytestmark = pytest.mark.django_db


def test_the_four_bodies_are_seeded_without_titles_and_unverified():
    by = {b.code: b for b in RegisterBody.objects.all()}
    assert set(by) == {"gmc", "mpl_wales", "nmc", "gphc"}
    assert [b.code for b in RegisterBody.objects.order_by("display_order")] == ["gmc", "mpl_wales", "nmc", "gphc"]
    assert by["mpl_wales"].name == "Welsh medical performers list"
    assert all(b.active and not b.verified and not b.paused and b.positions.count() == 0 for b in by.values())


@pytest.mark.parametrize("code,value,expected", [
    ("gmc", " 1234567 ", "1234567"),
    ("mpl_wales", "1234567", "1234567"),
    ("nmc", "12a 3456 b", "12A3456B"),
    ("gphc", "2012345", "2012345"),
])
def test_numbers_are_normalised_before_the_format_is_checked(code, value, expected):
    assert numbers.normalise(value) == expected
    numbers.check(code, numbers.normalise(value))      # no error


@pytest.mark.parametrize("code,value,words", [
    ("gmc", "123456", "seven digits"),
    ("gmc", "12345678", "seven digits"),
    ("gmc", "123456A", "seven digits"),
    ("nmc", "AB12C3456", "two digits, a letter, four digits and a letter"),
    ("nmc", "12A3456", "two digits, a letter, four digits and a letter"),
    ("gphc", "201234", "seven digits"),
])
def test_a_number_in_the_wrong_format_is_refused_with_the_format_in_words(code, value, words):
    with pytest.raises(ValidationError) as exc:
        numbers.check(code, value)
    assert words in str(exc.value)


def test_the_welsh_list_shares_the_gmc_number():
    assert numbers.SHARES_NUMBER_WITH == {"mpl_wales": "gmc"}
    assert numbers.FORMATS["mpl_wales"] == numbers.FORMATS["gmc"]


def test_a_registration_is_one_per_person_per_body_and_a_lookup_cascades():
    from django.db import IntegrityError
    from django.utils import timezone
    e = make_employee()
    gmc = RegisterBody.objects.get(code="gmc")
    r = Registration.objects.create(employee=e, body=gmc, number="1234567", next_check_on=timezone.localdate())
    Lookup.objects.create(registration=r, trigger=Lookup.Trigger.SCHEDULED, outcome=Lookup.Outcome.CLEAR)
    with pytest.raises(IntegrityError):
        Registration.objects.create(employee=e, body=gmc, number="7654321", next_check_on=timezone.localdate())


def test_deleting_a_registration_removes_its_lookups():
    from django.utils import timezone
    e = make_employee()
    r = Registration.objects.create(employee=e, body=RegisterBody.objects.get(code="nmc"), number="12A3456B",
                                    next_check_on=timezone.localdate())
    Lookup.objects.create(registration=r, trigger=Lookup.Trigger.ON_DEMAND, outcome=Lookup.Outcome.UNREADABLE,
                          error="FetchError")
    r.delete()
    assert Lookup.objects.count() == 0


def test_admin_lists_render_and_bodies_cannot_be_deleted_or_added(admin_client):
    gmc = RegisterBody.objects.get(code="gmc")
    assert admin_client.get("/admin/registers/registerbody/").status_code == 200
    assert admin_client.get(f"/admin/registers/registerbody/{gmc.pk}/change/").status_code == 200
    assert admin_client.get("/admin/registers/registerbody/add/").status_code == 403
    assert admin_client.post(f"/admin/registers/registerbody/{gmc.pk}/delete/").status_code == 403
    assert admin_client.get("/admin/registers/lookup/").status_code == 200
    assert admin_client.get("/admin/registers/lookup/add/").status_code == 403


def test_the_body_page_shows_verified_and_paused_read_only(admin_client):
    gmc = RegisterBody.objects.get(code="gmc")
    body = admin_client.get(f"/admin/registers/registerbody/{gmc.pk}/change/").content.decode()
    assert "Verified" in body and "Paused" in body
    assert 'name="verified"' not in body and 'name="paused_at"' not in body


def test_unpause_is_an_action_on_the_body(admin_client):
    from django.utils import timezone
    gmc = RegisterBody.objects.get(code="gmc")
    gmc.paused_at = timezone.now()
    gmc.save()
    r = admin_client.post(f"/admin/registers/registerbody/{gmc.pk}/unpause/")
    assert r.status_code == 302
    gmc.refresh_from_db()
    assert gmc.paused_at is None


def test_the_sidebar_lists_bodies_and_lookups_under_compliance(admin_client):
    body = admin_client.get("/admin/").content.decode()
    assert "Register bodies" in body and "Registration lookups" in body
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/user/practice-hr && .venv/bin/python -m pytest -q tests/test_registers_models.py`
Expected: collection error, `ModuleNotFoundError: No module named 'registers'`.

- [ ] **Step 3: Create the app, models and formats**

```python
# registers/__init__.py
```
(empty)

```python
# registers/apps.py
from django.apps import AppConfig


class RegistersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "registers"
```

```python
# registers/numbers.py
"""Registration number formats, refused on the form and by the service
before anything is sent to a register. The Welsh medical performers list
is keyed by the GMC number, so it shares that format and that field."""
import re

from django.core.exceptions import ValidationError

# body code -> (regex, the format in words)
FORMATS = {
    "gmc": (r"[0-9]{7}\Z", "seven digits"),
    "nmc": (r"[0-9]{2}[A-Z][0-9]{4}[A-Z]\Z", "two digits, a letter, four digits and a letter"),
    "gphc": (r"[0-9]{7}\Z", "seven digits"),
}
SHARES_NUMBER_WITH = {"mpl_wales": "gmc"}
FORMATS["mpl_wales"] = FORMATS["gmc"]
MAX_LENGTH = 20


def normalise(value):
    """Whitespace out, letters upper-cased; "" for blank."""
    return re.sub(r"\s+", "", value or "").upper()


def check(code, value):
    """Raise unless `value` (already normalised) is in the body's format."""
    regex, words = FORMATS[code]
    if not re.match(regex, value):
        raise ValidationError(f"A {label(code)} number is {words}.", code="format")


def label(code):
    return {"gmc": "GMC", "mpl_wales": "GMC", "nmc": "NMC PIN", "gphc": "GPhC"}[code]
```

```python
# registers/models.py
"""Professional registrations: the bodies a position title needs (GMC, the
Welsh medical performers list, NMC, GPhC), each person's number with each
body, and the append-only log of lookups against the register. A clear or
problem lookup also records a Professional registration check
(registers.services.lookups); the lookups here are the register's own
words and the audit trail of each run."""
from django.conf import settings
from django.db import models
from django.utils import timezone


class RegisterBody(models.Model):
    name = models.CharField(max_length=60, unique=True)
    code = models.SlugField(max_length=20, unique=True)
    positions = models.ManyToManyField("people.PositionTitle", blank=True, related_name="register_bodies",
                                       help_text="The titles that need a registration with this body.")
    active = models.BooleanField(default=True)
    verified = models.BooleanField(default=False, editable=False,
                                   help_text="Its parser has saved pages to test against; set by the code, not here.")
    paused_at = models.DateTimeField(null=True, blank=True, editable=False,
                                     help_text="Set when three lookups in a row could not read the page.")
    display_order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "register body"
        verbose_name_plural = "register bodies"

    def __str__(self):
        return self.name

    @property
    def paused(self):
        return self.paused_at is not None


class Lookup(models.Model):
    class Outcome(models.TextChoices):
        CLEAR = "clear", "Clear"
        PROBLEM = "problem", "Problem"
        NOT_FOUND = "not_found", "Not found"
        NAME_MISMATCH = "name_mismatch", "Name does not match"
        UNREADABLE = "unreadable", "Could not read the page"

    class Trigger(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        ON_DEMAND = "on_demand", "On demand"

    registration = models.ForeignKey("registers.Registration", on_delete=models.CASCADE, related_name="lookups")
    run_at = models.DateTimeField(default=timezone.now)
    trigger = models.CharField(max_length=10, choices=Trigger.choices)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="+")
    outcome = models.CharField(max_length=14, choices=Outcome.choices)
    status_text = models.CharField(max_length=200, blank=True, default="")
    name_on_register = models.CharField(max_length=120, blank=True, default="")
    page_hash = models.CharField(max_length=64, blank=True, default="")
    error = models.CharField(max_length=80, blank=True, default="")

    class Meta:
        ordering = ["-run_at", "-pk"]
        verbose_name = "registration lookup"

    def __str__(self):
        return f"{self.registration} {self.get_outcome_display()} {self.run_at:%d %b %Y}"


class Registration(models.Model):
    employee = models.ForeignKey("people.Employee", on_delete=models.PROTECT, related_name="registrations")
    body = models.ForeignKey(RegisterBody, on_delete=models.PROTECT, related_name="registrations")
    number = models.CharField(max_length=20)
    next_check_on = models.DateField()
    last_outcome = models.CharField(max_length=14, choices=Lookup.Outcome.choices, blank=True, default="")
    last_status_text = models.CharField(max_length=200, blank=True, default="")
    last_name_on_register = models.CharField(max_length=120, blank=True, default="")
    last_checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["employee", "body"], name="registration_one_per_body")]
        ordering = ["body__display_order", "pk"]

    def __str__(self):
        return f"{self.employee.name}: {self.body} {self.number}"
```

- [ ] **Step 4: Register the app and generate the migration**

In `config/settings.py` add `"registers",` after `"compliance",` in `INSTALLED_APPS`. In `accounts/backends.py` add `"registers"` to the `HR_APPS` set (the apps an HR admin may use in the admin). Then:

Run: `cd /home/user/practice-hr && DEBUG=1 .venv/bin/python manage.py makemigrations registers -n initial`
Expected: `registers/migrations/0001_initial.py` created with the three models.

- [ ] **Step 5: Seed the bodies**

```python
# registers/migrations/0002_seed_bodies.py
from django.db import migrations

# name, code, display_order. No titles: HR assigns the titles that need each
# body (docs/admin/compliance.md#professional-registrations).
BODIES = [
    ("GMC", "gmc", 10),
    ("Welsh medical performers list", "mpl_wales", 20),
    ("NMC", "nmc", 30),
    ("GPhC", "gphc", 40),
]


def seed(apps, schema_editor):
    RegisterBody = apps.get_model("registers", "RegisterBody")
    for name, code, order in BODIES:
        RegisterBody.objects.get_or_create(code=code, defaults={"name": name, "display_order": order})


def unseed(apps, schema_editor):
    RegisterBody = apps.get_model("registers", "RegisterBody")
    RegisterBody.objects.filter(code__in=[b[1] for b in BODIES], registrations=None).delete()


class Migration(migrations.Migration):
    dependencies = [("registers", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
```

- [ ] **Step 6: The admin pages and the sidebar**

```python
# registers/admin.py
"""Register bodies (which titles need each; Unpause after a site change)
and the read-only lookup log. Bodies are code plus a seed: never added or
deleted here, made inactive instead."""
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from unfold.admin import ModelAdmin
from unfold.decorators import action

from registers.models import Lookup, RegisterBody


@admin.register(RegisterBody)
class RegisterBodyAdmin(ModelAdmin):
    list_display = ("name", "code", "active", "verified", "is_paused")
    list_editable = ("active",)
    filter_horizontal = ("positions",)
    fields = ("name", "code", "positions", "active", "display_order", "verified", "paused")
    readonly_fields = ("code", "verified", "paused")
    actions_detail = ["unpause"]

    @admin.display(description="Paused", boolean=True)
    def is_paused(self, obj):
        return obj.paused

    @admin.display(description="Paused")
    def paused(self, obj):
        return f"Since {obj.paused_at:%d %b %Y %H:%M}" if obj.paused else "No"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @action(description="Unpause")
    def unpause(self, request, object_id):
        from registers.services import lookups
        body = self.get_object(request, object_id)
        lookups.unpause(body)
        messages.success(request, f"{body} unpaused: its scheduled checks run again tonight.")
        return HttpResponseRedirect(reverse("admin:registers_registerbody_change", args=[object_id]))


@admin.register(Lookup)
class LookupAdmin(ModelAdmin):
    list_display = ("run_at", "person", "body", "outcome", "status_text", "trigger")
    list_filter = ("registration__body", "outcome", "trigger")
    search_fields = ("registration__employee__first_name", "registration__employee__last_name",
                     "registration__employee__preferred_name")
    list_select_related = ("registration__employee", "registration__body", "requested_by")
    readonly_fields = ("registration", "run_at", "trigger", "requested_by", "outcome", "status_text",
                       "name_on_register", "page_hash", "error")

    @admin.display(description="Person", ordering="registration__employee__last_name")
    def person(self, obj):
        return obj.registration.employee.name

    @admin.display(description="Body", ordering="registration__body__display_order")
    def body(self, obj):
        return obj.registration.body.name

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
```

`lookups.unpause` does not exist until Task 3; for this task add a minimal `registers/services/__init__.py` (empty) and `registers/services/lookups.py` containing only:

```python
# registers/services/lookups.py
"""Running lookups against the registers (filled in by Task 3)."""


def unpause(body):
    """HR's Unpause, or a successful on-demand lookup: the schedule runs again."""
    if body.paused_at is not None:
        body.paused_at = None
        body.save(update_fields=["paused_at"])
```

In `hr/admin_site.py`, in the Compliance group after the Checks item, add:

```python
            _nav_item("Register bodies", "badge", "admin:registers_registerbody_changelist"),
            _nav_item("Registration lookups", "manage_search", "admin:registers_lookup_changelist"),
```

- [ ] **Step 7: Run the tests, ruff and the migration check**

Run: `cd /home/user/practice-hr && .venv/bin/python -m pytest -q tests/test_registers_models.py tests/test_navigation.py tests/test_checks.py && .venv/bin/ruff check . && DEBUG=1 .venv/bin/python manage.py makemigrations --check`
Expected: all pass; `No changes detected`.

- [ ] **Step 8: Commit**

```bash
git add registers config/settings.py accounts/backends.py hr/admin_site.py tests/test_registers_models.py
git commit -m "Registers: bodies, registrations and the lookup log, with admin lists"
```
(plus the two trailer lines)

---

### Task 2: Names, the one network function, and the four adapters

**Files:**
- Create: `registers/names.py`, `registers/http.py`, `registers/adapters/__init__.py`, `registers/adapters/base.py`, `registers/adapters/gmc.py`, `registers/adapters/mpl_wales.py`, `registers/adapters/nmc.py`, `registers/adapters/gphc.py`, `registers/adapters/fixtures/.gitkeep`
- Test: `tests/test_registers_adapters.py`

**Interfaces:**
- Produces: `registers.names.surnames_match(a, b) -> bool`; `registers.http.get(url, timeout=10) -> (status: int, text: str)` raising `registers.http.FetchError(reason)`; `registers.http.user_agent() -> str`; `registers.adapters.Result(outcome, status_text, name_on_register, page_hash)` (frozen dataclass); `registers.adapters.CODES` (`("gmc", "mpl_wales", "nmc", "gphc")`); `registers.adapters.url(code, number) -> str`; `registers.adapters.lookup(code, number, surname) -> Result` (never raises); `registers.adapters.verified(code) -> bool`; each adapter module's `url(number)` and `parse(text) -> (outcome, status_text, name)` where `outcome` is one of `clear`, `problem`, `not_found`, `unreadable`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_registers_adapters.py
"""The parsers against synthetic page text (the live pages are not reachable
from the sandbox; real pages, when captured, run through the same parse in
test_captured_fixtures_parse_as_their_file_name_says), the name rule, and
the proof that nothing here reaches the network."""
import socket
from pathlib import Path

import pytest

from registers import http, names
from registers.adapters import CODES, Result, gmc, gphc, lookup, mpl_wales, nmc, url, verified

FIXTURES = Path("registers/adapters/fixtures")


# ---- names ---------------------------------------------------------------------------------

@pytest.mark.parametrize("a,b,expected", [
    ("Patel", "patel", True),
    ("Ní Bhriain", "Ni Bhriain", True),
    ("Smith-Jones", "Smith", True),
    ("Smith", "Jones-Smith", True),
    ("O'Neill", "ONeill", True),
    ("Patel", "Patil", False),
    ("", "Patel", False),
    ("Smith", "", False),
])
def test_surnames_match_loosely_and_never_wrongly(a, b, expected):
    assert names.surnames_match(a, b) is expected


# ---- the network function --------------------------------------------------------------------

def test_the_user_agent_names_the_practice(settings):
    settings.SITE_URL = "https://hr.example.org/"
    assert http.user_agent() == "PracticeHR/1.0 (+https://hr.example.org; registration checks)"
    settings.SITE_URL = "/"
    assert http.user_agent() == "PracticeHR/1.0 (registration checks)"


def test_nothing_in_the_adapters_reaches_the_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("no network in tests")
    monkeypatch.setattr(socket, "create_connection", refuse)     # what urllib opens connections with
    with pytest.raises(http.FetchError):
        http.get("https://example.invalid/anything")
    for code in CODES:
        r = lookup(code, "1234567" if code != "nmc" else "12A3456B", "Patel")
        assert r.outcome == "unreadable" and r.page_hash == ""


# ---- parsers -------------------------------------------------------------------------------

GMC_CLEAR = """<html><body><h1>Dr Priya Patel</h1><p>GMC number: 1234567</p>
<dl><dt>Registration status</dt><dd>Registered with a licence to practise</dd>
<dt>GP Register</dt><dd>On the GP Register since 2015</dd></dl></body></html>"""
GMC_SUSPENDED = GMC_CLEAR.replace("Registered with a licence to practise", "Suspended")
GMC_NO_LICENCE = GMC_CLEAR.replace("Registered with a licence to practise", "Registered without a licence to practise")
GMC_NOT_GP = GMC_CLEAR.replace("<dt>GP Register</dt><dd>On the GP Register since 2015</dd>", "")
GMC_CONDITIONS = GMC_CLEAR.replace("</dl>", "<dt>Fitness to practise</dt><dd>Conditions on registration</dd></dl>")
GMC_NONE = "<html><body><h1>Search results</h1><p>No results were found for 1234567.</p></body></html>"
GMC_ODD = "<html><body><p>Something else entirely</p></body></html>"


@pytest.mark.parametrize("page,outcome,words", [
    (GMC_CLEAR, "clear", "Registered with a licence to practise"),
    (GMC_SUSPENDED, "problem", "Suspended"),
    (GMC_NO_LICENCE, "problem", "Registered without a licence"),
    (GMC_NOT_GP, "problem", "not on the GP Register"),
    (GMC_CONDITIONS, "problem", "Conditions"),
    (GMC_NONE, "not_found", ""),
    (GMC_ODD, "unreadable", ""),
])
def test_gmc_parse(page, outcome, words):
    got, status, name = gmc.parse(gmc.text_of(page))
    assert got == outcome and words in status
    if outcome in ("clear", "problem"):
        assert name == "Priya Patel"


MPL_PRESENT = """<html><body><table><tr><th>GMC No</th><th>Name</th><th>Status</th></tr>
<tr><td>1234567</td><td>PATEL, Priya</td><td>Included</td></tr></table></body></html>"""
MPL_SUSPENDED = MPL_PRESENT.replace("Included", "Suspended")
MPL_NONE = "<html><body><p>No performers match your search.</p></body></html>"


@pytest.mark.parametrize("page,outcome,words", [
    (MPL_PRESENT, "clear", "Included"),
    (MPL_SUSPENDED, "problem", "Suspended"),
    (MPL_NONE, "not_found", ""),
    (GMC_ODD, "unreadable", ""),
])
def test_mpl_wales_parse(page, outcome, words):
    got, status, name = mpl_wales.parse(mpl_wales.text_of(page), "1234567")
    assert got == outcome and words in status
    if outcome in ("clear", "problem"):
        assert name == "Priya PATEL"


NMC_CLEAR = """<html><body><h2>Priya Patel</h2><p>PIN 12A3456B</p>
<p>Registration status: Effective registration</p><p>Registered nurse - Adult</p></body></html>"""
NMC_LAPSED = NMC_CLEAR.replace("Effective registration", "Lapsed")
NMC_CONDITIONS = NMC_CLEAR.replace("</body>", "<p>Conditions of practice order</p></body>")
NMC_NONE = "<html><body><p>No registrant found with the PIN 12A3456B.</p></body></html>"


@pytest.mark.parametrize("page,outcome,words", [
    (NMC_CLEAR, "clear", "Effective registration"),
    (NMC_LAPSED, "problem", "Lapsed"),
    (NMC_CONDITIONS, "problem", "Conditions"),
    (NMC_NONE, "not_found", ""),
    (GMC_ODD, "unreadable", ""),
])
def test_nmc_parse(page, outcome, words):
    got, status, name = nmc.parse(nmc.text_of(page))
    assert got == outcome and words in status
    if outcome in ("clear", "problem"):
        assert name == "Priya Patel"


GPHC_CLEAR = """<html><body><h2>Priya Patel</h2><p>Registration number: 2012345</p>
<p>Status: Registered</p><p>Pharmacist</p></body></html>"""
GPHC_SUSPENDED = GPHC_CLEAR.replace("Registered", "Suspended")
GPHC_CONDITIONS = GPHC_CLEAR.replace("</body>", "<p>Conditions apply to this registration</p></body>")
GPHC_NONE = "<html><body><p>Your search returned no results.</p></body></html>"


@pytest.mark.parametrize("page,outcome,words", [
    (GPHC_CLEAR, "clear", "Registered"),
    (GPHC_SUSPENDED, "problem", "Suspended"),
    (GPHC_CONDITIONS, "problem", "Conditions"),
    (GPHC_NONE, "not_found", ""),
    (GMC_ODD, "unreadable", ""),
])
def test_gphc_parse(page, outcome, words):
    got, status, name = gphc.parse(gphc.text_of(page))
    assert got == outcome and words in status
    if outcome in ("clear", "problem"):
        assert name == "Priya Patel"


@pytest.mark.parametrize("code,page", [("gmc", GMC_NONE), ("mpl_wales", MPL_NONE), ("nmc", NMC_NONE),
                                       ("gphc", GPHC_NONE)])
def test_a_no_results_page_is_not_found(code, page, monkeypatch):
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (200, page))
    r = lookup(code, "1234567" if code != "nmc" else "12A3456B", "Patel")
    assert r.outcome == "not_found" and r.page_hash != ""


# ---- the shared flow -----------------------------------------------------------------------

def test_lookup_matches_the_name_hashes_the_page_and_never_raises(monkeypatch):
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (200, GMC_CLEAR))
    r = lookup("gmc", "1234567", "Patel")
    assert r == Result("clear", "Registered with a licence to practise", "Priya Patel", r.page_hash)
    assert len(r.page_hash) == 64
    assert lookup("gmc", "1234567", "Khan").outcome == "name_mismatch"
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (503, "down"))
    r = lookup("gmc", "1234567", "Patel")
    assert r.outcome == "unreadable" and r.status_text == "HTTP 503"

    def boom(url, timeout=10):
        raise http.FetchError("timed out")
    monkeypatch.setattr(http, "get", boom)
    r = lookup("gmc", "1234567", "Patel")
    assert r.outcome == "unreadable" and r.status_text == "FetchError"

    def worse(url, timeout=10):
        raise RuntimeError("Priya Patel 1234567")
    monkeypatch.setattr(http, "get", worse)
    r = lookup("gmc", "1234567", "Patel")
    assert r.outcome == "unreadable" and r.status_text == "RuntimeError"    # the class, never the message


def test_a_hit_without_a_name_is_unreadable_not_a_match(monkeypatch):
    page = GMC_CLEAR.replace("<h1>Dr Priya Patel</h1>", "")
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (200, page))
    assert lookup("gmc", "1234567", "Patel").outcome == "unreadable"


def test_urls_carry_the_number_and_only_the_number():
    assert url("gmc", "1234567").endswith("1234567")
    for code, number in (("mpl_wales", "1234567"), ("nmc", "12A3456B"), ("gphc", "2012345")):
        assert number in url(code, number) and " " not in url(code, number)


# ---- captured pages ------------------------------------------------------------------------

def _captured():
    out = []
    for code in CODES:
        for page in sorted((FIXTURES / code).glob("*.html")) if (FIXTURES / code).exists() else []:
            out.append(pytest.param(code, page, id=f"{code}/{page.name}"))
    return out


@pytest.mark.parametrize("code,page", _captured())
def test_captured_fixtures_parse_as_their_file_name_says(code, page, monkeypatch):
    """A saved page is named for its outcome (clear.html, problem.html,
    not_found.html, …); a sidecar <stem>.surname holds the surname to match."""
    expected = page.stem.split("-")[0]
    surname = (page.with_suffix(".surname").read_text().strip() if page.with_suffix(".surname").exists()
               else "Patel")
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (200, page.read_text()))
    r = lookup(code, "1234567" if code != "nmc" else "12A3456B", surname)
    assert r.outcome == expected, r


def test_verified_means_the_clear_and_not_found_pages_are_captured(tmp_path, monkeypatch):
    import registers.adapters as adapters
    monkeypatch.setattr(adapters, "FIXTURES", tmp_path)
    assert not verified("gmc")
    (tmp_path / "gmc").mkdir()
    (tmp_path / "gmc" / "clear.html").write_text("x")
    assert not verified("gmc")
    (tmp_path / "gmc" / "not_found.html").write_text("x")
    assert verified("gmc")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/user/practice-hr && .venv/bin/python -m pytest -q tests/test_registers_adapters.py`
Expected: collection error, `ModuleNotFoundError: No module named 'registers.names'`.

- [ ] **Step 3: Names and the network function**

```python
# registers/names.py
"""Loose surname matching: the register's spelling against the record's.
Case, accents, apostrophes, hyphens and spaces are ignored, and either part
of a double-barrelled surname on either side is enough. Never the preferred
name: the register shows legal names."""
import re
import unicodedata


def _parts(surname):
    text = unicodedata.normalize("NFKD", surname or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = text.replace("'", "").replace("’", "").replace(",", " ").replace(".", " ")
    return [p for p in re.split(r"[\s\-]+", text) if p]


def surnames_match(a, b):
    pa, pb = _parts(a), _parts(b)
    if not pa or not pb:
        return False
    if "".join(pa) == "".join(pb):
        return True
    return bool(set(pa) & set(pb))
```

```python
# registers/http.py
"""The one function that touches the network. Tests replace it; nothing
else in the app opens a connection. A fetch problem is a FetchError with a
short reason (no URL, no body): the caller records the class name only."""
import socket
import urllib.error
import urllib.request

from django.conf import settings

TIMEOUT = 10


class FetchError(Exception):
    pass


def user_agent():
    site = settings.SITE_URL.rstrip("/")
    if site.startswith("http"):
        return f"PracticeHR/1.0 (+{site}; registration checks)"
    return "PracticeHR/1.0 (registration checks)"


def get(url, timeout=TIMEOUT):
    """(HTTP status, body as text). Raises FetchError when no reply came."""
    request = urllib.request.Request(url, headers={"User-Agent": user_agent(), "Accept": "text/html"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:   # noqa: S310 - https URLs built by the adapters
            return reply.status, reply.read().decode(reply.headers.get_content_charset() or "utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except (urllib.error.URLError, socket.timeout, OSError, ValueError) as exc:
        raise FetchError(exc.__class__.__name__) from None
```

- [ ] **Step 4: The adapter package and the shared flow**

```python
# registers/adapters/base.py
"""What every adapter shares: HTML to plain lines, the status vocabulary
match, and the fetch → parse → name-check flow. An adapter supplies url()
and parse(); parse works on the page's text lines, never on markup, so a
change of layout that keeps the words still reads."""
import hashlib
import re
from html.parser import HTMLParser

from registers import http, names


class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "head"}
    BLOCK = {"p", "div", "li", "tr", "td", "th", "dt", "dd", "h1", "h2", "h3", "h4", "br", "table", "section"}

    def __init__(self):
        super().__init__()
        self.lines, self.buf, self.skip = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self._flush()

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK:
            self._flush()

    def handle_data(self, data):
        if not self.skip:
            self.buf.append(data)

    def _flush(self):
        line = re.sub(r"\s+", " ", "".join(self.buf)).strip()
        if line:
            self.lines.append(line)
        self.buf = []

    def close(self):
        super().close()
        self._flush()


def text_of(html):
    """The page as a list of non-empty text lines, block by block."""
    p = _Text()
    p.feed(html)
    p.close()
    return p.lines


def find(lines, phrases):
    """The first (line, phrase) whose line contains the phrase, case-insensitively; else (None, None)."""
    for line in lines:
        low = line.lower()
        for phrase in phrases:
            if phrase.lower() in low:
                return line, phrase
    return None, None


def name_near(lines, marker, titles=("Dr", "Professor", "Mr", "Mrs", "Ms", "Miss", "Mx")):
    """The person's name: the line before the first line containing
    `marker` (the number's label), stripped of a leading title; "" if none."""
    for i, line in enumerate(lines):
        if marker.lower() in line.lower() and i > 0:
            candidate = lines[i - 1]
            for t in titles:
                if candidate.startswith(t + " "):
                    candidate = candidate[len(t) + 1:]
            return candidate.strip()
    return ""


def run(url, parse, number, surname):
    """Fetch the page, parse it, check the name. Returns a Result; never
    raises (an unexpected error is an unreadable result naming its class)."""
    from registers.adapters import Result
    try:
        status, body = http.get(url)
    except http.FetchError:
        return Result("unreadable", "FetchError", "", "")
    except Exception as exc:  # noqa: BLE001 - the class only; the message may carry the number or a name
        return Result("unreadable", exc.__class__.__name__, "", "")
    page_hash = hashlib.sha256(body.encode("utf-8", "replace")).hexdigest()
    if status != 200:
        return Result("unreadable", f"HTTP {status}", "", page_hash)
    try:
        outcome, status_text, name = parse(text_of(body)) if parse.__code__.co_argcount == 1 \
            else parse(text_of(body), number)
    except Exception as exc:  # noqa: BLE001 - as above
        return Result("unreadable", exc.__class__.__name__, "", page_hash)
    if outcome in ("clear", "problem"):
        if not name:
            return Result("unreadable", "name not found on the page", "", page_hash)
        if not names.surnames_match(name, surname):
            outcome = "name_mismatch"
    return Result(outcome, status_text[:200], name[:120], page_hash)
```

```python
# registers/adapters/__init__.py
"""One adapter per register body: url(number) for the public page and
parse(lines) -> (outcome, status_text, name). lookup() is the only entry
point the services use; verified() says whether a body's parser has saved
real pages to test against (registers/adapters/fixtures/README.md)."""
from dataclasses import dataclass
from pathlib import Path

from registers.adapters import base, gmc, gphc, mpl_wales, nmc

CODES = ("gmc", "mpl_wales", "nmc", "gphc")
MODULES = {"gmc": gmc, "mpl_wales": mpl_wales, "nmc": nmc, "gphc": gphc}
FIXTURES = Path(__file__).parent / "fixtures"
REQUIRED_FIXTURES = ("clear.html", "not_found.html")


@dataclass(frozen=True)
class Result:
    outcome: str            # clear | problem | not_found | name_mismatch | unreadable
    status_text: str        # the register's own words, or the error class
    name_on_register: str
    page_hash: str          # "" when nothing was fetched


def url(code, number):
    return MODULES[code].url(number)


def lookup(code, number, surname):
    module = MODULES[code]
    return base.run(module.url(number), module.parse, number, surname)


def verified(code):
    folder = FIXTURES / code
    return all((folder / name).exists() for name in REQUIRED_FIXTURES)
```

The circular import (`base` imports `Result` from the package inside `run`) is deliberate: `base` is imported by the package before `Result` exists, so `run` imports it late.

- [ ] **Step 5: The four adapters**

```python
# registers/adapters/gmc.py
"""The GMC's public register: one page per doctor at /doctors/<number>.
Clear is "Registered with a licence to practise" and on the GP Register.
Vocabulary from the GMC's status wording; a page with none of it is
unreadable, never not found."""
from registers.adapters.base import find, name_near, text_of  # noqa: F401 - text_of re-exported for the tests

PUBLIC = "https://www.gmc-uk.org/doctors/"
NOT_FOUND = ("no results were found", "no results found", "no doctor found", "not on the register",
             "could not find a doctor")
CLEAR = ("Registered with a licence to practise",)
PROBLEM = ("Registered without a licence", "Provisionally registered", "Suspended", "Erased", "Interim order",
           "Conditions", "Undertakings", "Administrative erasure", "Not registered")
GP_REGISTER = ("GP Register",)


def url(number):
    return f"{PUBLIC}{number}"


def parse(lines):
    line, phrase = find(lines, NOT_FOUND)
    if phrase:
        return "not_found", line, ""
    name = name_near(lines, "GMC number")
    line, phrase = find(lines, PROBLEM)
    if phrase:
        return "problem", line, name
    line, phrase = find(lines, CLEAR)
    if phrase:
        gp, _ = find(lines, GP_REGISTER)
        if gp is None:
            return "problem", f"{line}; not on the GP Register", name
        return "clear", line, name
    return "unreadable", "", ""
```

```python
# registers/adapters/mpl_wales.py
"""The All Wales medical performers list (NHS Wales Shared Services
Partnership), searched by GMC number. Clear is a row for the number whose
status is not suspended or conditional."""
from registers.adapters.base import find, text_of  # noqa: F401

PUBLIC = "http://www.primarycareservices.wales.nhs.uk/all-wales-medical-performers-list?gmc="
NOT_FOUND = ("no performers match", "no results", "no records found", "not found")
PROBLEM = ("Suspended", "Conditional", "Conditions", "Removed")


def url(number):
    return f"{PUBLIC}{number}"


def parse(lines, number):
    line, phrase = find(lines, NOT_FOUND)
    if phrase:
        return "not_found", line, ""
    rows = [i for i, line in enumerate(lines) if line.strip() == number]
    if not rows:
        return "unreadable", "", ""
    i = rows[0]
    name = lines[i + 1] if i + 1 < len(lines) else ""
    if "," in name:                       # the list writes "SURNAME, Given"
        last, first = name.split(",", 1)
        name = f"{first.strip()} {last.strip()}"
    status = lines[i + 2] if i + 2 < len(lines) else ""
    _, phrase = find([status], PROBLEM)
    return ("problem" if phrase else "clear"), status, name
```

```python
# registers/adapters/nmc.py
"""The NMC's public register search by PIN. Clear is "Effective
registration" with no restriction, condition or order noted."""
from registers.adapters.base import find, name_near, text_of  # noqa: F401

PUBLIC = "https://www.nmc.org.uk/registration/search-the-register/?pin="
NOT_FOUND = ("no registrant found", "no results", "not found", "no match")
CLEAR = ("Effective registration", "Registered")
PROBLEM = ("Lapsed", "Suspended", "Struck off", "Conditions of practice", "Caution order", "Interim order",
           "Restriction", "Not registered")


def url(number):
    return f"{PUBLIC}{number}"


def parse(lines):
    line, phrase = find(lines, NOT_FOUND)
    if phrase:
        return "not_found", line, ""
    name = name_near(lines, "PIN")
    line, phrase = find(lines, PROBLEM)
    if phrase:
        return "problem", line, name
    line, phrase = find(lines, CLEAR)
    if phrase:
        return "clear", line, name
    return "unreadable", "", ""
```

```python
# registers/adapters/gphc.py
"""The GPhC's public register search by registration number. Clear is
"Registered" with no conditions or interim order."""
from registers.adapters.base import find, name_near, text_of  # noqa: F401

PUBLIC = "https://www.pharmacyregulation.org/registers/pharmacist/registrationnumber/"
NOT_FOUND = ("no results", "returned no results", "not found", "no match")
CLEAR = ("Registered",)
PROBLEM = ("Suspended", "Removed", "Conditions", "Interim order", "Not registered", "Lapsed")


def url(number):
    return f"{PUBLIC}{number}"


def parse(lines):
    line, phrase = find(lines, NOT_FOUND)
    if phrase:
        return "not_found", line, ""
    name = name_near(lines, "Registration number")
    line, phrase = find(lines, PROBLEM)
    if phrase:
        return "problem", line, name
    line, phrase = find(lines, CLEAR)
    if phrase:
        return "clear", line, name
    return "unreadable", "", ""
```

Add an empty `registers/adapters/fixtures/.gitkeep`.

Note on `GMC_NO_LICENCE`: "Registered without a licence to practise" contains the PROBLEM phrase and is matched before CLEAR, so the order of the checks in `parse` (problem before clear) is what makes the test pass; keep it.

- [ ] **Step 6: Run the tests**

Run: `cd /home/user/practice-hr && .venv/bin/python -m pytest -q tests/test_registers_adapters.py && .venv/bin/ruff check .`
Expected: all pass (the captured-fixture test is parametrised over an empty list and is skipped by collection).

- [ ] **Step 7: Commit**

```bash
git add registers tests/test_registers_adapters.py
git commit -m "Registers: the four register adapters, name matching and the one network function"
```
(plus the two trailer lines)

---

### Task 3: Services: numbers on people, running lookups, the schedule and the pause rule

**Files:**
- Create: `registers/services/registrations.py`, `registers/services/lookups.py` (replacing Task 1's stub), `compliance/migrations/0002_reminderschedule_registration_every_days.py` (generated)
- Modify: `compliance/models.py` (the setting), `compliance/admin.py` (`fields`)
- Test: `tests/test_registers_services.py`

**Interfaces:**
- Consumes: Task 1 models and `registers.numbers`; Task 2 `registers.adapters.lookup/verified/url`; `checks.services.checks.record(actor, employee, check_type, done_on, outcome, reference=…, note=…)`; `people.services.employments.current(employee, day)` and `active_on(day)`; `people.services.positions.primary_on(employment, day)`; `people.services.audit.record(actor, obj, changes)`.
- Produces: `registrations.needed(employee, today) -> list[RegisterBody]`; `registrations.missing(employee, today) -> list[RegisterBody]`; `registrations.set_number(actor, employee, body, number) -> Registration` (raises `ValidationError`); `registrations.clear_number(actor, employee, body)`; `registrations.rows(employee, today) -> list[Row]` with `Row(body, registration | None, needed: bool)`; `registrations.number_fields(employee, today) -> list[(field_name, body, label)]`; `lookups.run(registration, trigger, requested_by=None) -> Lookup`; `lookups.scheduled(today) -> dict` (`run`, `clear`, `problem`, `not_found`, `name_mismatch`, `unreadable`, `skipped`); `lookups.unpause(body)`; `lookups.PAUSE_AFTER = 3`; `lookups.PAUSE_BETWEEN_SECONDS = 2`; `lookups.sleep` (a module attribute tests replace); `ReminderSchedule.registration_every_days` (default 7, 1–90).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_registers_services.py
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from checks.models import Check, CheckType
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
        monkeypatch.setattr(lookups.random, "choice", lambda seq, k=k: seq[k])
        lookups.run(r, "scheduled")
        r.refresh_from_db()
        assert (r.next_check_on - timezone.localdate()).days == 7 + jitter

    def boom(code, number, surname):
        raise RuntimeError("Priya Patel")
    monkeypatch.setattr(adapters, "lookup", boom)
    lk = lookups.run(r, "scheduled")
    assert lk.outcome == "unreadable" and lk.error == "RuntimeError" and "Priya" not in lk.status_text


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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/user/practice-hr && .venv/bin/python -m pytest -q tests/test_registers_services.py`
Expected: collection error, `cannot import name 'registrations' from 'registers.services'`.

- [ ] **Step 3: The interval setting**

In `compliance/models.py`, after `every_days_overdue` on `ReminderSchedule`:

```python
    registration_every_days = models.PositiveSmallIntegerField(
        default=7, validators=[MinValueValidator(1), MaxValueValidator(90)],
        verbose_name="check professional registrations every (days)",
        help_text="Each person's registration is looked up on the register again this many days after the "
                  "last time (spread by a day either way so the load is even). 1 to 90.")
```

with `from django.core.validators import MaxValueValidator, MinValueValidator` at the top. In `compliance/admin.py` set `fields = ("start_days_before", "every_days_before", "every_days_overdue", "registration_every_days")`.

Run: `cd /home/user/practice-hr && DEBUG=1 .venv/bin/python manage.py makemigrations compliance -n reminderschedule_registration_every_days`
Expected: `compliance/migrations/0002_reminderschedule_registration_every_days.py`.

- [ ] **Step 4: The registrations service**

```python
# registers/services/registrations.py
"""Each person's registration numbers: which bodies their title needs, and
the one writer of Registration rows. The Welsh medical performers list is
keyed by the GMC number, so setting the GMC number also sets (or makes) the
Welsh row when the title needs it, and clearing it clears both."""
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from people.services import audit, employments, positions
from registers import numbers
from registers.models import RegisterBody, Registration

TWINS = {parent: child for child, parent in numbers.SHARES_NUMBER_WITH.items()}   # gmc -> mpl_wales


@dataclass
class Row:
    body: RegisterBody
    registration: Registration | None
    needed: bool


def _title(employee, today):
    emp = employments.current(employee, today)
    if emp is None:
        return None
    pos = positions.primary_on(emp, today)
    return pos.title if pos is not None else None


def needed(employee, today):
    """The active bodies the person's primary title needs, in display order."""
    title = _title(employee, today)
    if title is None:
        return []
    return list(RegisterBody.objects.filter(active=True, positions=title).order_by("display_order"))


def missing(employee, today):
    have = set(employee.registrations.values_list("body_id", flat=True))
    return [b for b in needed(employee, today) if b.pk not in have]


def rows(employee, today):
    """One row per body the title needs, plus any body a number is still
    held for (needed=False), for the pages."""
    need = needed(employee, today)
    held = {r.body_id: r for r in employee.registrations.select_related("body")}
    out = [Row(b, held.get(b.pk), True) for b in need]
    needed_ids = {b.pk for b in need}
    out += [Row(r.body, r, False) for r in held.values() if r.body_id not in needed_ids]
    return out


def number_fields(employee, today):
    """(form field name, body, label) for each number the Details tab
    shows: one per needed body, except a body that shares another's number."""
    out = []
    for b in needed(employee, today):
        if b.code in numbers.SHARES_NUMBER_WITH:
            continue
        out.append((f"registration_{b.code}", b, f"{numbers.label(b.code)} number"))
    return out


def _twin(employee, body, today):
    code = TWINS.get(body.code)
    if code is None:
        return None
    return next((b for b in needed(employee, today) if b.code == code), None)


@transaction.atomic
def set_number(actor, employee, body, number):
    """Set (or change) the person's number with `body`; checked tonight.
    Audited on the employee as registration:<code>. Raises ValidationError
    on a bad format."""
    today = timezone.localdate()
    value = numbers.normalise(number)
    if not value:
        raise ValidationError("Enter the number.", code="blank")
    numbers.check(body.code, value)
    reg, created = Registration.objects.get_or_create(employee=employee, body=body,
                                                      defaults={"number": value, "next_check_on": today})
    before = "" if created else reg.number
    if not created and reg.number != value:
        reg.number, reg.next_check_on = value, today
        reg.last_outcome, reg.last_status_text, reg.last_name_on_register, reg.last_checked_at = "", "", "", None
        reg.save()
    if before != value:
        audit.record(actor, employee, {f"registration:{body.code}": (before, value)})
    twin = _twin(employee, body, today)
    if twin is not None:
        set_number(actor, employee, twin, value)
    return reg


@transaction.atomic
def clear_number(actor, employee, body):
    """Remove the number (its lookups go with it); the Welsh twin too."""
    reg = Registration.objects.filter(employee=employee, body=body).first()
    if reg is not None:
        audit.record(actor, employee, {f"registration:{body.code}": (reg.number, "")})
        reg.delete()
    twin_code = TWINS.get(body.code)
    if twin_code:
        twin = Registration.objects.filter(employee=employee, body__code=twin_code).first()
        if twin is not None:
            audit.record(actor, employee, {f"registration:{twin_code}": (twin.number, "")})
            twin.delete()
```

- [ ] **Step 5: The lookups service**

```python
# registers/services/lookups.py
"""Running lookups against the registers: one on demand, or everything due
tonight. The one writer of Lookup rows and of the registration's
denormalised "last" fields; a clear or problem result also records a
Professional registration check through the checks service. Never raises."""
import logging
import random
import time
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from checks.models import Check, CheckType
from checks.services import checks
from compliance.models import ReminderSchedule
from people.services import employments
from registers import adapters
from registers.models import Lookup, RegisterBody, Registration
from registers.services import registrations

log = logging.getLogger("hr.registers")
PAUSE_AFTER = 3                 # unreadable results in a row across a body: pause it
PAUSE_BETWEEN_SECONDS = 2       # between two requests to the same body
sleep = time.sleep              # replaced by the tests
COUNTS = ("run", "clear", "problem", "not_found", "name_mismatch", "unreadable", "skipped")
JITTER = (-1, 0, 1)             # days either way, so the load stays spread


def unpause(body):
    """HR's Unpause, or a successful on-demand lookup: the schedule runs again."""
    if body.paused_at is not None:
        body.paused_at = None
        body.save(update_fields=["paused_at"])


def _next_check(today):
    every = ReminderSchedule.get().registration_every_days
    return today + timedelta(days=every + random.choice(JITTER))


def _record_check(registration, outcome, status_text, today):
    check_type = CheckType.objects.get(code="professional_registration")
    result = Check.Outcome.CLEAR if outcome == "clear" else Check.Outcome.NOT_CLEAR
    checks.record(None, registration.employee, check_type, today, result, reference=registration.number,
                  note=f"{registration.body.name}: {status_text}"[:2000])


def _pause_if_dead(body):
    last = list(Lookup.objects.filter(registration__body=body).order_by("-run_at", "-pk")
                .values_list("outcome", flat=True)[:PAUSE_AFTER])
    if len(last) == PAUSE_AFTER and all(o == "unreadable" for o in last) and body.paused_at is None:
        body.paused_at = timezone.now()
        body.save(update_fields=["paused_at"])
        log.warning("register body %s paused after %s unreadable lookups", body.code, PAUSE_AFTER)


def run(registration, trigger, requested_by=None):
    """Look the registration up now. Returns the Lookup written."""
    today = timezone.localdate()
    body = registration.body
    try:
        result = adapters.lookup(body.code, registration.number, registration.employee.last_name)
    except Exception as exc:  # noqa: BLE001 - belt and braces: adapters.lookup never raises
        result = adapters.Result("unreadable", exc.__class__.__name__, "", "")
    with transaction.atomic():
        lk = Lookup.objects.create(
            registration=registration, trigger=trigger, requested_by=requested_by, outcome=result.outcome,
            status_text=result.status_text[:200], name_on_register=result.name_on_register[:120],
            page_hash=result.page_hash, error=result.status_text[:80] if result.outcome == "unreadable" else "")
        registration.last_outcome, registration.last_status_text = result.outcome, result.status_text[:200]
        registration.last_name_on_register, registration.last_checked_at = result.name_on_register[:120], lk.run_at
        registration.next_check_on = _next_check(today)
        registration.save(update_fields=["last_outcome", "last_status_text", "last_name_on_register",
                                         "last_checked_at", "next_check_on"])
        if result.outcome in ("clear", "problem"):
            _record_check(registration, result.outcome, result.status_text, today)
        if result.outcome == "unreadable":
            _pause_if_dead(body)
        elif trigger == Lookup.Trigger.ON_DEMAND:
            unpause(body)
    if result.outcome == "unreadable":
        log.info("registration %s (%s) unreadable: %s", registration.pk, body.code, result.status_text)
    return lk


def _due(today):
    """Registrations due tonight whose person is employed today and whose
    title still needs the body; (registration, skipped-reason) pairs."""
    employed = set(employments.active_on(today).values_list("employee_id", flat=True))
    out = []
    for reg in (Registration.objects.filter(next_check_on__lte=today)
                .select_related("body", "employee").order_by("body__display_order", "pk")):
        body = reg.body
        if reg.employee_id not in employed:
            out.append((reg, "not employed"))
        elif body.pk not in {b.pk for b in registrations.needed(reg.employee, today)}:
            out.append((reg, "not needed"))
        elif not body.active or not body.verified or body.paused_at is not None:
            out.append((reg, "body inactive, unverified or paused"))
        else:
            out.append((reg, ""))
    return out


def scheduled(today):
    """Tonight's lookups, one at a time, a pause between two to the same
    body; a body that pauses mid-run is skipped from then on."""
    counts = dict.fromkeys(COUNTS, 0)
    last_body = None
    for reg, why in _due(today):
        reg.body.refresh_from_db(fields=["paused_at"])
        if why or reg.body.paused_at is not None:
            counts["skipped"] += 1
            continue
        if last_body == reg.body_id:
            sleep(PAUSE_BETWEEN_SECONDS)
        last_body = reg.body_id
        lk = run(reg, Lookup.Trigger.SCHEDULED)
        counts["run"] += 1
        counts[lk.outcome] += 1
    return counts
```

`verified` on the body row is set from the adapter fixtures by the nightly step (Task 4's `sync_verified`); the tests here set it by hand.

- [ ] **Step 6: Run the tests, ruff and the migration check**

Run: `cd /home/user/practice-hr && .venv/bin/python -m pytest -q tests/test_registers_services.py tests/test_registers_models.py tests/test_compliance.py && .venv/bin/ruff check . && DEBUG=1 .venv/bin/python manage.py makemigrations --check`
Expected: all pass; `No changes detected`.

- [ ] **Step 7: Commit**

```bash
git add registers compliance tests/test_registers_services.py
git commit -m "Registers: numbers on people, lookups that record checks, the weekly schedule and the pause rule"
```
(plus the two trailer lines)

---

### Task 4: Alerts in the digest and the nightly step

**Files:**
- Create: `registers/services/due.py`, `registers/services/nightly.py`
- Modify: `compliance/services/digest.py` (SOURCES and `_when`), `people/management/commands/hr_nightly.py`, `templates/email/compliance_digest.txt` (no change needed; verify)
- Test: `tests/test_registers_due.py`

**Interfaces:**
- Consumes: Task 3 services; `compliance.due.DueItem(employee, recipient, kind, label, due_on, state, url, key, once)`, `compliance.due.link`, `compliance.due.active_email`; `absence.services.notify.hr_admin_addresses()`; `people.services.access.line_manager(employee, day)`.
- Produces: `due.due_items(today, sched) -> list[DueItem]` with kind `registration`; `nightly.run(today) -> dict` (the `scheduled` counts plus `verified`: the number of bodies verified); `nightly.sync_verified()`; `nightly.UNREADABLE_AFTER_DAYS = 14`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_registers_due.py
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
    assert hr_item.key == f"registration:{e.pk}:gmc:{lk.pk}" and hr_item.once is False
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/user/practice-hr && .venv/bin/python -m pytest -q tests/test_registers_due.py`
Expected: collection error, `cannot import name 'due' from 'registers.services'`.

- [ ] **Step 3: The due items**

```python
# registers/services/due.py
"""What is due of the registrations, for the morning digest (compliance):
a standing problem, not-found or wrong-name result goes to HR and to the
line manager, with the body and the register's words (a registration
problem is the manager's to act on that day, unlike a lapsed check); a
body the title needs with no number is HR's from the employment start; a
page that has been unreadable for 14 days, or a paused body, is HR's
alone."""
from django.urls import reverse
from django.utils import timezone

from absence.services.notify import hr_admin_addresses
from compliance.due import DueItem, active_email, link
from people.models import Employee
from people.services import access, employments
from registers.models import RegisterBody
from registers.services import registrations

UNREADABLE_AFTER_DAYS = 14
KIND = "registration"


def _label(reg):
    body = reg.body.name
    if reg.last_outcome == "problem":
        return f"{body}: {reg.last_status_text}"
    if reg.last_outcome == "not_found":
        return f"{body}: not found on the register"
    return f"{body}: the register shows {reg.last_name_on_register or 'someone else'}, not this person"


def due_items(today, sched):
    out = []
    hr = hr_admin_addresses()
    lookups_url = link(reverse("admin:registers_lookup_changelist"))
    employed = employments.active_on(today).values("employee_id")
    for e in Employee.objects.filter(pk__in=employed).select_related("user"):
        emp = employments.current(e, today)
        if emp is None:
            continue
        hr_url = link(reverse("admin:people_employee_change", args=[e.pk]))
        rows = [r for r in registrations.rows(e, today) if r.needed]
        for row in rows:
            reg = row.registration
            if reg is None:
                for r in hr:
                    out.append(DueItem(e, r, KIND, f"{row.body.name} number not recorded", emp.start_date, "missing",
                                       hr_url, f"registration:{e.pk}:{row.body.code}:missing"))
                continue
            latest = reg.lookups.order_by("-run_at", "-pk").first()
            if latest is None:
                continue
            if latest.outcome in ("problem", "not_found", "name_mismatch"):
                key = f"registration:{e.pk}:{row.body.code}:{latest.pk}"
                found = timezone.localtime(latest.run_at).date()
                for r in hr:
                    out.append(DueItem(e, r, KIND, _label(reg), found, "overdue", hr_url, key))
                manager = active_email(access.line_manager(e, today))
                if manager:
                    out.append(DueItem(e, manager, KIND, _label(reg), found, "overdue",
                                       link(reverse("people:team")), key))
            elif latest.outcome == "unreadable":
                since = _unreadable_since(reg)
                if since is not None and (today - since).days >= UNREADABLE_AFTER_DAYS:
                    for r in hr:
                        out.append(DueItem(e, r, KIND, f"{row.body.name}: could not be read since {since:%-d %b %Y}",
                                           since, "overdue", lookups_url,
                                           f"registration:{e.pk}:{row.body.code}:unreadable:{since.isoformat()}"))
    for body in RegisterBody.objects.filter(active=True, paused_at__isnull=False):
        paused_on = timezone.localtime(body.paused_at).date()
        for r in hr:
            out.append(DueItem(None, r, KIND, f"{body.name}: checks are paused (the page could not be read)",
                               paused_on, "overdue", lookups_url,
                               f"registration:body:{body.code}:paused:{paused_on.isoformat()}"))
    return out


def _unreadable_since(reg):
    """The date of the first of the unbroken run of unreadable lookups that ends at the latest."""
    since = None
    for lk in reg.lookups.order_by("-run_at", "-pk"):
        if lk.outcome != "unreadable":
            break
        since = timezone.localtime(lk.run_at).date()
    return since
```

A paused body's item has `employee=None`: the digest groups lines by employee and sorts by its name, so give it a stand-in. In `compliance/services/digest.py` change `_body`'s sort key and the regroup to tolerate it:

```python
def _body(rows, today):
    def person(i):
        e = i.employee
        return (e.last_name, e.first_name, e.pk) if e is not None else ("", "", 0)
    rows = sorted(rows, key=lambda i: (*person(i), i.due_on, i.label))
    lines = [{"item": i, "when": _when(i), "who": i.employee.name if i.employee is not None else "The registers"}
             for i in rows]
    return render_to_string("email/compliance_digest.txt", {"lines": lines, "today": today})
```

and in `templates/email/compliance_digest.txt` regroup by `who` instead of `item.employee`:

```
{% regroup lines by who as people %}{% for person in people %}
{{ person.grouper }}
{% for line in person.list %}- {{ line.item.label }}: {{ line.when }}
  {{ line.item.url }}
{% endfor %}{% endfor %}
```

Also in `digest.py`: add `from registers.services import due as registers_due` and `registers_due.due_items` to `SOURCES`, and in `_when` before the `overdue` branch:

```python
    if item.kind == "registration":
        if item.state == "missing":
            return "not recorded"
        return f"found {item.due_on:%-d %b %Y}"
```

The existing digest tests (`tests/test_compliance.py`) must still pass: run them in Step 6.

- [ ] **Step 4: The nightly step**

```python
# registers/services/nightly.py
"""The registrations step of hr_nightly: sync each body's verified flag
from its adapter's fixtures, then run tonight's lookups. Never raises out
of the command: the digest has already gone; the next night retries."""
import logging

from registers import adapters
from registers.models import RegisterBody
from registers.services import lookups

log = logging.getLogger("hr.registers")


def sync_verified():
    n = 0
    for body in RegisterBody.objects.all():
        verified = body.code in adapters.CODES and adapters.verified(body.code)
        if body.verified != verified:
            body.verified = verified
            body.save(update_fields=["verified"])
            if not verified:
                log.info("register body %s is not verified: no saved pages to test its parser", body.code)
        n += verified
    return n


def run(today):
    verified = sync_verified()
    counts = lookups.scheduled(today)
    return {**counts, "verified": verified}
```

In `people/management/commands/hr_nightly.py`, after the compliance block:

```python
        from registers.services import nightly as registers_nightly
        try:
            self.stdout.write(f"registrations: {registers_nightly.run(today)}")
        except Exception as exc:  # noqa: BLE001 - the class only; the next night retries
            log.error("nightly registrations step failed: %s", exc.__class__.__name__)
            self.stdout.write("registrations: failed")
```

(Import at the top with the others rather than inline; the inline form above only shows where it goes.)

- [ ] **Step 5: Run the tests**

Run: `cd /home/user/practice-hr && .venv/bin/python -m pytest -q tests/test_registers_due.py tests/test_compliance.py tests/test_nightly.py tests/test_absence_nightly.py && .venv/bin/ruff check .`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add registers compliance/services/digest.py templates/email/compliance_digest.txt people/management/commands/hr_nightly.py tests/test_registers_due.py
git commit -m "Registers: problems in the morning digest, the nightly step"
```
(plus the two trailer lines)

---

### Task 5: The employee page: number fields, the Registrations table and Check now

**Files:**
- Create: `registers/views.py`, `registers/urls.py`, `templates/registers/check_now.html`
- Modify: `config/urls.py`, `people/admin_forms.py` (`EmployeeForm`), `people/admin.py` (`get_fields`, `save_model`, `compliance_summary`, `change_view`)
- Test: `tests/test_registers_pages.py`

**Interfaces:**
- Consumes: Task 3 `registrations.number_fields/rows/set_number/clear_number`, `lookups.run`; Task 2 `adapters.url`; `people.services.access.can_view_restricted(user)`; `people.services.audit.viewed(actor, obj, section)`.
- Produces: URL `registers:check_now` (`/registers/<registration pk>/check/`: GET a confirmation page, POST runs the lookup and redirects to the employee's admin page); `EmployeeForm.registration_fields` (the dynamic `(name, body, label)` list on a change form).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_registers_pages.py
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from people.models import AuditEntry
from people.services import employments, positions, titles
from registers import adapters
from registers.adapters import Result
from registers.models import Lookup, RegisterBody, Registration
from registers.services import lookups, registrations
from tests.factories import make_employee, make_team

pytestmark = pytest.mark.django_db
User = get_user_model()
CLEAR = Result("clear", "Registered with a licence to practise", "Priya Patel", "a" * 64)


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr(lookups, "sleep", lambda seconds: None)


@pytest.fixture
def gp_bodies():
    gmc, mpl = RegisterBody.objects.get(code="gmc"), RegisterBody.objects.get(code="mpl_wales")
    title = titles.get_or_create("Salaried GP")
    gmc.positions.add(title)
    mpl.positions.add(title)
    for b in (gmc, mpl):
        b.verified = True
        b.save()
    return gmc, mpl


def _gp(hr_admin, user=None):
    e = make_employee(first="Priya", last="Patel", user=user)
    emp = employments.start(hr_admin, e, timezone.localdate() - timedelta(days=400))
    positions.add(hr_admin, emp, titles.get_or_create("Salaried GP"), make_team(), None, emp.start_date)
    return e


def _change_post(e, **extra):
    data = {"first_name": "Priya", "last_name": "Patel", "work_email": e.work_email, "preferred_name": "",
            "personal_email": "", "phone": "", "address_line1": "", "address_line2": "", "town": "",
            "postcode": "", "ni_number": "", "bank_account_name": "", "bank_sort_code": "",
            "bank_account_number": "", "emergency_contacts-TOTAL_FORMS": 0, "emergency_contacts-INITIAL_FORMS": 0,
            "employments-TOTAL_FORMS": 0, "employments-INITIAL_FORMS": 0, "_save": "Save"}
    data.update(extra)
    return data


# ---- the Details tab ---------------------------------------------------------------------------

def test_the_details_tab_has_one_number_field_per_needed_body_and_saves_through_the_service(admin_client, hr_admin,
                                                                                             gp_bodies):
    gmc, mpl = gp_bodies
    e = _gp(hr_admin)
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert 'name="registration_gmc"' in body and "GMC number" in body
    assert 'name="registration_mpl_wales"' not in body        # shares the GMC number
    r = admin_client.post(f"/admin/people/employee/{e.pk}/change/", _change_post(e, registration_gmc="1234567"))
    assert r.status_code == 302
    assert Registration.objects.get(employee=e, body=gmc).number == "1234567"
    assert Registration.objects.get(employee=e, body=mpl).number == "1234567"
    assert AuditEntry.objects.filter(model="people.employee", object_id=e.pk, field="registration:gmc").exists()
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert 'value="1234567"' in body


def test_a_bad_number_is_a_form_error_and_blank_clears_it(admin_client, hr_admin, gp_bodies):
    gmc, _ = gp_bodies
    e = _gp(hr_admin)
    r = admin_client.post(f"/admin/people/employee/{e.pk}/change/", _change_post(e, registration_gmc="12"))
    assert r.status_code == 200 and "A GMC number is seven digits." in r.content.decode()
    assert not Registration.objects.filter(employee=e).exists()
    registrations.set_number(hr_admin, e, gmc, "1234567")
    r = admin_client.post(f"/admin/people/employee/{e.pk}/change/", _change_post(e, registration_gmc=""))
    assert r.status_code == 302 and not Registration.objects.filter(employee=e).exists()


def test_no_field_for_a_title_that_needs_no_body_and_none_on_the_add_page(admin_client, hr_admin, gp_bodies):
    e = make_employee()
    employments.start(hr_admin, e, timezone.localdate() - timedelta(days=10))
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert "registration_" not in body
    assert "registration_" not in admin_client.get("/admin/people/employee/add/").content.decode()


def test_a_shared_number_across_two_people_is_a_warning_not_a_refusal(admin_client, hr_admin, gp_bodies):
    gmc, _ = gp_bodies
    other = _gp(hr_admin)
    registrations.set_number(hr_admin, other, gmc, "1234567")
    e = _gp(hr_admin)
    r = admin_client.post(f"/admin/people/employee/{e.pk}/change/", _change_post(e, registration_gmc="1234567"),
                          follow=True)
    assert Registration.objects.get(employee=e, body=gmc).number == "1234567"
    assert "is also recorded for Priya Patel" in r.content.decode()


# ---- the Compliance tab -------------------------------------------------------------------------

def test_the_compliance_tab_lists_registrations_with_check_now_and_the_register_link(admin_client, hr_admin,
                                                                                    gp_bodies, monkeypatch):
    gmc, mpl = gp_bodies
    e = _gp(hr_admin)
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert "Registrations" in body and "No number recorded" in body
    registrations.set_number(hr_admin, e, gmc, "1234567")
    monkeypatch.setattr(adapters, "lookup", lambda *a: CLEAR)
    lookups.run(Registration.objects.get(employee=e, body=gmc), "scheduled")
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert "Registered with a licence to practise" in body and "Priya Patel" in body
    assert "Not checked yet" in body                       # the Welsh row
    reg = Registration.objects.get(employee=e, body=gmc)
    assert f'href="/registers/{reg.pk}/check/"' in body and "Check now" in body
    assert f'href="{adapters.url("gmc", "1234567")}"' in body and "On the register" in body


def test_the_tab_says_when_a_body_is_paused_or_not_verified(admin_client, hr_admin, gp_bodies):
    gmc, _ = gp_bodies
    e = _gp(hr_admin)
    registrations.set_number(hr_admin, e, gmc, "1234567")
    gmc.verified = False
    gmc.save()
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert "not verified" in body
    gmc.verified, gmc.paused_at = True, timezone.now()
    gmc.save()
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert "paused" in body and "not verified" not in body


# ---- Check now ---------------------------------------------------------------------------------

def test_check_now_confirms_on_get_runs_on_post_and_is_hrs_only(admin_client, hr_admin, gp_bodies, monkeypatch):
    gmc, _ = gp_bodies
    e = _gp(hr_admin)
    reg = registrations.set_number(hr_admin, e, gmc, "1234567")
    monkeypatch.setattr(adapters, "lookup", lambda *a: CLEAR)
    r = admin_client.get(f"/registers/{reg.pk}/check/")
    assert r.status_code == 200 and "Check Priya Patel" in r.content.decode() and Lookup.objects.count() == 0
    r = admin_client.post(f"/registers/{reg.pk}/check/", follow=True)
    assert r.redirect_chain[0][0].endswith(f"/admin/people/employee/{e.pk}/change/")
    assert "GMC: Registered with a licence to practise (Priya Patel)" in r.content.decode()
    lk = Lookup.objects.get()
    assert lk.trigger == "on_demand" and lk.requested_by == hr_admin
    assert AuditEntry.objects.filter(kind="viewed", field="checks", object_id=e.pk).exists()
    c = Client()
    c.force_login(User.objects.create_user(email="x@example.com", password="pw"))
    assert c.get(f"/registers/{reg.pk}/check/").status_code == 403
    assert c.post(f"/registers/{reg.pk}/check/").status_code == 403 and Lookup.objects.count() == 1
    anon = Client().post(f"/registers/{reg.pk}/check/")
    assert anon.status_code == 302 and anon["Location"].startswith("/accounts/login/")


def test_check_now_on_an_unverified_body_says_so_and_runs(admin_client, hr_admin, gp_bodies, monkeypatch):
    gmc, _ = gp_bodies
    gmc.verified = False
    gmc.save()
    e = _gp(hr_admin)
    reg = registrations.set_number(hr_admin, e, gmc, "1234567")
    monkeypatch.setattr(adapters, "lookup", lambda *a: Result("unreadable", "HTTP 503", "", "e" * 64))
    r = admin_client.post(f"/registers/{reg.pk}/check/", follow=True)
    body = r.content.decode()
    assert "could not be read" in body and "not yet verified" in body and Lookup.objects.count() == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/user/practice-hr && .venv/bin/python -m pytest -q tests/test_registers_pages.py`
Expected: failures (no `registration_gmc` field; 404 on `/registers/...`).

- [ ] **Step 3: The number fields on the employee form**

The number fields are declared on the form class that `EmployeeAdmin.get_form` builds for one person (a field named in the admin's fieldsets must be a declared form field or a model field, or `modelform_factory` refuses it), so the form itself only carries their names and checks them. In `people/admin_forms.py`, add to `EmployeeForm`:

```python
    registration_fields = ()      # (field name, body, label): EmployeeAdmin.get_form declares them per person
```

and add to `clean()` (before the `create_login` early return):

```python
        from registers import numbers
        for name, body, _ in self.registration_fields:
            value = numbers.normalise(data.get(name))
            data[name] = value
            if value:
                try:
                    numbers.check(body.code, value)
                except ValidationError as exc:
                    self.add_error(name, exc)
```

`EmployeeAdmin.get_form` already sets `actor` on the add form only. Replace it so both branches set it, and so a change form declares one number field per body the person's title needs (HR only), with the stored number as its initial value. The dynamic class is built **before** `super().get_form` and passed as `form=`, so its declared fields are on `base_fields` for `get_fields`, the fieldsets and the POST alike:

```python
    def get_form(self, request, obj=None, **kwargs):
        attrs = {"actor": request.user}
        if obj is not None:
            attrs.update(dict.fromkeys(admin_forms.EmployeeForm.LOGIN_FIELDS))
            if access.can_view_restricted(request.user):
                from registers.services import registrations
                held = {r.body_id: r.number for r in obj.registrations.all()}
                fields = registrations.number_fields(obj, timezone.localdate())
                for name, body, label in fields:
                    attrs[name] = forms.CharField(
                        label=label, required=False, max_length=20, widget=UnfoldAdminTextInputWidget,
                        initial=held.get(body.pk, ""),
                        help_text=f"{body.name}; checked on the register tonight and every few days after.")
                attrs["registration_fields"] = tuple(fields)
        kwargs["form"] = type(admin_forms.EmployeeForm.__name__, (admin_forms.EmployeeForm,), attrs)
        return super().get_form(request, obj, **kwargs)
```

with `from django import forms` and `from unfold.widgets import UnfoldAdminTextInputWidget` added to `people/admin.py`'s imports. (The login fields are removed by the `None` entries exactly as before; `actor` is now set on both pages.)

In `EmployeeAdmin.get_fields`, after the restricted-field removal and before the login-field handling, place the number fields after `ni_number` on a change page:

```python
        if obj is not None and access.can_view_restricted(request.user):
            from registers.services import registrations
            names = [n for n, _, _ in registrations.number_fields(obj, timezone.localdate())]
            fields = [f for f in fields if f not in names]
            at = fields.index("ni_number") + 1 if "ni_number" in fields else len(fields)
            fields[at:at] = names
```

(`super().get_fields` builds the form through `get_form` above, so the declared number fields are already in the list, at the end; the insert moves them after the NI number.)

In `EmployeeAdmin.save_model`, in the `change` branch after `obj.refresh_from_db()`:

```python
            from registers.services import registrations
            for name, body, _ in form.registration_fields:
                if name not in form.changed_data:
                    continue
                value = form.cleaned_data.get(name) or ""
                if value:
                    registrations.set_number(request.user, fresh, body, value)
                    others = (Registration.objects.filter(body=body, number=value).exclude(employee=fresh)
                              .select_related("employee"))
                    for other in others:
                        messages.warning(request, f"The {body.name} number {value} is also recorded for "
                                                  f"{other.employee.name}. The register's name check will "
                                                  "tell them apart; check the numbers if that is not intended.")
                else:
                    registrations.clear_number(request.user, fresh, body)
```

with `from registers.models import Registration` at the top of `people/admin.py`.

- [ ] **Step 4: The Registrations table on the Compliance tab**

In `compliance_summary`, after `check_rows` is built and before `policy_rows`:

```python
        from registers import adapters
        from registers.services import registrations
        reg_rows = []
        for row in registrations.rows(obj, today):
            reg, body = row.registration, row.body
            note = "" if row.needed else " (their title no longer needs it)"
            if reg is None:
                reg_rows.append((body.name + note, "No number recorded", "", "", "", "",
                                 _link(reverse("admin:people_employee_change", args=[obj.pk]), "Add it under Details")))
                continue
            state = ("paused" if body.paused else "") or ("not verified" if not body.verified else "")
            outcome = (f"{reg.last_status_text}" if reg.last_outcome in ("clear", "problem")
                       else reg.get_last_outcome_display() if reg.last_outcome else "Not checked yet")
            if state:
                outcome = f"{outcome} ({state})"
            links = format_html('{} {}', _link(reverse("registers:check_now", args=[reg.pk]), "Check now"),
                                _link(adapters.url(body.code, reg.number), "On the register"))
            reg_rows.append((body.name + note, reg.number, outcome, reg.last_name_on_register,
                             _day(timezone.localtime(reg.last_checked_at).date()) if reg.last_checked_at else "",
                             _day(reg.next_check_on), links))
```

and render it first in the returned `format_html`:

```python
        return format_html(
            '<h3 class="font-semibold mb-2">Registrations</h3>{}'
            '<h3 class="font-semibold mb-2">Checks</h3>{}{}'
            '<h3 class="font-semibold mb-2">Policies</h3>{}'
            '<h3 class="font-semibold mb-2">Open checklist items</h3>{}',
            _table(("Body", "Number", "Last result", "Name shown", "Checked", "Next check", ""), reg_rows,
                   "Their position needs no professional registration."),
            starts, ...
```

(`_table` takes a head tuple, rows and an empty message, as the three existing tables show.)

- [ ] **Step 5: Check now**

```python
# registers/views.py
"""Check now: HR looks a registration up this minute. GET is a confirmation
page (a page never writes on GET); POST runs the lookup through
lookups.run, audits the view of the person's checks as the Compliance tab
does, and goes back to their page with the register's words."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from people.services import access, audit
from registers.models import Lookup, Registration
from registers.services import lookups

WORDS = {"clear": "{body}: {status} ({name})", "problem": "{body}: {status} ({name})",
         "not_found": "{body}: the number was not found on the register.",
         "name_mismatch": "{body}: the register shows {name}, not this person.",
         "unreadable": "{body}: the page could not be read ({status}). Try again later; if it keeps failing, "
                       "the register's page may have changed."}


@login_required
@require_http_methods(["GET", "POST"])
def check_now(request, pk):
    if not access.can_view_restricted(request.user):
        raise PermissionDenied
    reg = get_object_or_404(Registration.objects.select_related("employee", "body"), pk=pk)
    back = reverse("admin:people_employee_change", args=[reg.employee_id])
    if request.method == "GET":
        return render(request, "registers/check_now.html", {"registration": reg, "back": back})
    lk = lookups.run(reg, Lookup.Trigger.ON_DEMAND, request.user)
    audit.viewed(request.user, reg.employee, "checks")
    text = WORDS[lk.outcome].format(body=reg.body.name, status=lk.status_text, name=lk.name_on_register)
    if not reg.body.verified:
        text += " This register's parser is not yet verified: read the result with care."
    (messages.success if lk.outcome == "clear" else messages.warning)(request, text)
    return redirect(back)
```

```python
# registers/urls.py
from django.urls import path

from . import views

app_name = "registers"
urlpatterns = [
    path("<int:pk>/check/", views.check_now, name="check_now"),
]
```

In `config/urls.py` add `path("registers/", include("registers.urls")),` after the checks line.

```html
{# templates/registers/check_now.html #}
{% extends "base.html" %}
{% comment %}registers:check_now, GET — confirm before the lookup runs
(the POST writes a Lookup and, on a clear or problem result, a check).{% endcomment %}
{% block title %}Check {{ registration.employee.name }}'s {{ registration.body }} registration{% endblock %}
{% block content %}
<div class="stack">
<div class="page-head"><h1>Check {{ registration.employee.name }}'s {{ registration.body }} registration now?</h1></div>
<section class="card">
  <p>This looks up {{ registration.body }} number <strong>{{ registration.number }}</strong> on the register
  this minute and records what it says.{% if not registration.body.verified %} This register's parser is not yet
  verified against a saved page, so read the result with care.{% endif %}</p>
  <form method="post">{% csrf_token %}
    <div class="form-actions">
      <button type="submit" class="btn btn-primary">Check now</button>
      <a href="{{ back }}" class="btn btn-quiet">Back</a>
    </div>
  </form>
</section>
</div>
{% endblock %}
```

- [ ] **Step 6: Run the tests**

Run: `cd /home/user/practice-hr && .venv/bin/python -m pytest -q tests/test_registers_pages.py tests/test_people_admin.py tests/test_auto_login.py tests/test_compliance_admin.py tests/test_csp.py && .venv/bin/ruff check .`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add registers config/urls.py people/admin.py people/admin_forms.py templates/registers tests/test_registers_pages.py
git commit -m "Registers: number fields on the employee page, the Registrations table and Check now"
```
(plus the two trailer lines)

---

### Task 6: The dashboard count and the My record card

**Files:**
- Create: `templates/people/_registrations.html`
- Modify: `absence/admin_dashboard.py` (`COMPLIANCE`, `compliance_people`), `templates/admin/index.html` (the card's sentence), `people/views.py` (`me`), `templates/people/me.html`, `docs/admin/compliance.md` (the card table row, in Task 7)
- Test: `tests/test_registers_pages.py` (append)

**Interfaces:**
- Consumes: Task 3 `registrations.rows`; `absence.admin_dashboard.compliance_people` contract (`{key: [employee pk, …]}`) and `people.admin.ComplianceFilter`, which filters Employees by those keys.
- Produces: dashboard key `registration_problems` labelled "Registration problems"; `me` context `registrations` (the `rows` list).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_registers_pages.py`:

```python
# ---- the dashboard and My record ------------------------------------------------------------------

def test_the_dashboard_counts_standing_problems_and_opens_the_people(admin_client, hr_admin, gp_bodies, monkeypatch):
    gmc, _ = gp_bodies
    e = _gp(hr_admin)
    reg = registrations.set_number(hr_admin, e, gmc, "1234567")
    monkeypatch.setattr(adapters, "lookup", lambda *a: Result("problem", "Suspended", "Priya Patel", "b" * 64))
    lookups.run(reg, "scheduled")
    body = admin_client.get("/admin/").content.decode()
    assert "Registration problems" in body
    listed = admin_client.get("/admin/people/employee/?compliance=registration_problems").content.decode()
    assert e.work_email in listed
    monkeypatch.setattr(adapters, "lookup", lambda *a: CLEAR)
    lookups.run(reg, "scheduled")
    listed = admin_client.get("/admin/people/employee/?compliance=registration_problems").content.decode()
    assert e.work_email not in listed


def test_my_record_shows_the_persons_registrations_in_plain_words(hr_admin, gp_bodies, monkeypatch):
    gmc, _ = gp_bodies
    user = User.objects.create_user(email="priya@example.com", password="pw")
    e = _gp(hr_admin, user=user)
    c = Client()
    c.force_login(user)
    body = c.get("/people/me/").content.decode()
    assert "Registrations" in body and "GMC" in body and "HR has not recorded your number yet" in body
    reg = registrations.set_number(hr_admin, e, gmc, "1234567")
    body = c.get("/people/me/").content.decode()
    assert "1234567" in body and "Not checked yet" in body and "Check now" not in body
    monkeypatch.setattr(adapters, "lookup", lambda *a: CLEAR)
    lookups.run(reg, "scheduled")
    body = c.get("/people/me/").content.decode()
    assert "Registered, checked " in body
    monkeypatch.setattr(adapters, "lookup", lambda *a: Result("problem", "Suspended", "Priya Patel", "b" * 64))
    lookups.run(reg, "scheduled")
    body = c.get("/people/me/").content.decode()
    assert "HR will be in touch about your GMC registration" in body and "Suspended" not in body


def test_my_record_has_no_registrations_card_for_a_title_that_needs_none(hr_admin, employee_user):
    e = make_employee(user=employee_user)
    employments.start(hr_admin, e, timezone.localdate() - timedelta(days=10))
    c = Client()
    c.force_login(employee_user)
    assert "Registrations" not in c.get("/people/me/").content.decode()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/user/practice-hr && .venv/bin/python -m pytest -q tests/test_registers_pages.py -k "dashboard or my_record"`
Expected: FAIL (`"Registration problems" not in body`; no Registrations card).

- [ ] **Step 3: The dashboard**

In `absence/admin_dashboard.py` add to `COMPLIANCE` (last):

```python
    ("registration_problems", "Registration problems"),
```

and in `compliance_people`, inside the per-employee loop after the signatures line:

```python
        from registers.services import registrations
        out["registration_problems"] += [
            e.pk for r in registrations.rows(e, today)
            if r.needed and r.registration is not None
            and r.registration.last_outcome in ("problem", "not_found", "name_mismatch")]
```

Update the card's sentence in `templates/admin/index.html`: "Checks, registrations and signatures of the people employed today, and checklist items past their due date. Each number opens the people it counts."

(`ComplianceFilter` in `people/admin.py` reads `COMPLIANCE` for its choices and `compliance_people` for the pks, so the new key needs nothing there; check its `lookups()` builds from `COMPLIANCE` and not a literal list, and fix it if it does.)

- [ ] **Step 4: The My record card**

```html
{# templates/people/_registrations.html #}
{% comment %}My record's Registrations card: one row per body the person's
title needs, in plain words. HR runs the checks; nothing here is a control.
Expects registrations (registers.services.registrations.rows).{% endcomment %}
{% if registrations %}
<section class="card">
  <h2>Registrations</h2>
  <div class="table-scroll">
  <table class="list">
    <thead><tr><th scope="col">Body</th><th scope="col">Number</th><th scope="col">Status</th></tr></thead>
    <tbody>
    {% for row in registrations %}{% if row.needed %}
      <tr>
        <th scope="row">{{ row.body.name }}</th>
        <td>{{ row.registration.number|default:"" }}</td>
        <td>{% if not row.registration %}HR has not recorded your number yet.
            {% elif row.registration.last_outcome == "clear" %}Registered, checked {{ row.registration.last_checked_at|date:"j M Y" }}.
            {% elif row.registration.last_outcome == "" or row.registration.last_outcome == "unreadable" %}Not checked yet.
            {% else %}HR will be in touch about your {{ row.body.name }} registration.{% endif %}</td>
      </tr>
    {% endif %}{% endfor %}
    </tbody>
  </table>
  </div>
</section>
{% endif %}
```

In `people/views.py:me`, in `ctx`, add `"registrations": registrations.rows(employee, today)` with `from registers.services import registrations` imported at the top (people's views already import other apps' services the same way for checks). In `templates/people/me.html` add `{% include "people/_registrations.html" %}` before `{% include "people/_checks.html" %}`.

- [ ] **Step 5: Run the tests**

Run: `cd /home/user/practice-hr && .venv/bin/python -m pytest -q tests/test_registers_pages.py tests/test_compliance_admin.py tests/test_people_views.py && .venv/bin/ruff check .`
Expected: all pass (if `tests/test_people_views.py` does not exist, run `tests/test_people*.py`).

- [ ] **Step 6: Commit**

```bash
git add absence/admin_dashboard.py templates/admin/index.html people/views.py templates/people tests/test_registers_pages.py
git commit -m "Registers: the dashboard count and the My record card"
```
(plus the two trailer lines)

---

### Task 7: The parse command, the fixture README, docs and the backlog

**Files:**
- Create: `registers/management/__init__.py`, `registers/management/commands/__init__.py`, `registers/management/commands/registers_parse.py`, `registers/adapters/fixtures/README.md`
- Modify: `docs/admin/compliance.md`, `docs/admin/people.md`, `docs/admin/README.md`, `docs/guides/hr-administrator.md`, `docs/guides/manager.md`, `README.md`, `docs/superpowers/backlog.md`
- Test: `tests/test_registers_docs.py`, `tests/test_docs.py` (no change: it reads the page lists; confirm compliance.md's new anchors resolve)

**Interfaces:**
- Consumes: Task 2 `adapters.MODULES`, `base.text_of`, `names.surnames_match`.
- Produces: `manage.py registers_parse <code> <file> [--surname X]` printing the parse result; the fixture README a person follows.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_registers_docs.py
"""The parse command a person uses while capturing pages, and the docs'
bold labels against the UI."""
import re
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db
ROOT = Path(__file__).resolve().parent.parent

PAGE = """<html><body><h1>Dr Priya Patel</h1><p>GMC number: 1234567</p>
<p>Registration status: Registered with a licence to practise</p><p>GP Register: yes</p></body></html>"""


def test_registers_parse_prints_the_outcome_and_the_name_match(tmp_path):
    page = tmp_path / "clear.html"
    page.write_text(PAGE)
    out = StringIO()
    call_command("registers_parse", "gmc", str(page), "--surname", "Patel", stdout=out)
    text = out.getvalue()
    assert "outcome: clear" in text and "name: Priya Patel" in text and "surname matches: yes" in text
    out = StringIO()
    call_command("registers_parse", "gmc", str(page), "--surname", "Khan", stdout=out)
    assert "surname matches: no" in out.getvalue()


def test_the_fixture_readme_names_every_body_and_outcome():
    text = (ROOT / "registers/adapters/fixtures/README.md").read_text()
    for code in ("gmc", "mpl_wales", "nmc", "gphc"):
        assert f"`{code}/`" in text
    for outcome in ("clear.html", "problem.html", "not_found.html"):
        assert outcome in text
    assert "registers_parse" in text and ".surname" in text


def _bold(path):
    text = re.sub(r"```.*?```", "", path.read_text(), flags=re.S)
    return set(re.findall(r"\*\*([^*]+)\*\*", text))


def test_the_guides_name_the_ui_labels_that_exist():
    labels = _bold(ROOT / "docs/guides/hr-administrator.md") | _bold(ROOT / "docs/guides/manager.md")
    for label in ("Register bodies", "Registration lookups", "Check now", "On the register",
                  "Check professional registrations every (days)", "Unpause", "GMC number"):
        assert label in labels, label
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/user/practice-hr && .venv/bin/python -m pytest -q tests/test_registers_docs.py`
Expected: FAIL (`Unknown command: 'registers_parse'`; README missing).

- [ ] **Step 3: The parse command**

```python
# registers/management/commands/registers_parse.py
"""Parse a saved register page the way a lookup would, for the person
capturing fixtures: `manage.py registers_parse gmc page.html --surname Patel`."""
from django.core.management.base import BaseCommand, CommandError

from registers import names
from registers.adapters import MODULES, base


class Command(BaseCommand):
    help = "Parse a saved register page (HTML) with a body's adapter and print what a lookup would record."

    def add_arguments(self, parser):
        parser.add_argument("code", choices=sorted(MODULES))
        parser.add_argument("path")
        parser.add_argument("--surname", default="", help="The person's surname, to show whether it would match.")
        parser.add_argument("--number", default="", help="The number, for the Welsh list's row match.")

    def handle(self, *args, **options):
        module = MODULES[options["code"]]
        try:
            html = open(options["path"], encoding="utf-8", errors="replace").read()
        except OSError as exc:
            raise CommandError(f"cannot read the page: {exc.__class__.__name__}") from None
        lines = base.text_of(html)
        parse = module.parse
        outcome, status, name = (parse(lines, options["number"]) if parse.__code__.co_argcount == 2
                                 else parse(lines))
        self.stdout.write(f"outcome: {outcome}")
        self.stdout.write(f"status text: {status}")
        self.stdout.write(f"name: {name}")
        if options["surname"]:
            self.stdout.write(f"surname matches: {'yes' if names.surnames_match(name, options['surname']) else 'no'}")
        self.stdout.write(f"lines of text: {len(lines)}")
```

- [ ] **Step 4: The fixture README**

```markdown
<!-- registers/adapters/fixtures/README.md -->
# Register page fixtures

The parsers in `registers/adapters/` are tested against saved copies of
real result pages kept here, one folder per body: `gmc/`, `mpl_wales/`,
`nmc/`, `gphc/`. A body is **verified** (and its scheduled checks run) only
when its folder holds at least `clear.html` and `not_found.html`. The
build sandbox cannot reach the regulators' sites, so a person captures
them.

## How to capture a page

1. On a machine that can reach the site, open the body's public search for
   a real number you know the answer for (your own, or a colleague's with
   their agreement).
2. Save the result page as HTML (browser: *Save page as… → Web page, HTML
   only*). Do not save a "complete" page with images and scripts.
3. Name the file for the outcome the page shows: `clear.html`,
   `problem.html` (any lapsed, suspended, conditions, erased, no-licence
   or not-on-the-GP-register page; several may be saved as
   `problem-suspended.html`, `problem-conditions.html` and so on),
   `not_found.html` (a number that does not exist), and optionally
   `unreadable.html` (a page that is not a result at all, such as an
   error page).
4. Beside each `clear` or `problem` page put a `<stem>.surname` file holding
   the surname the page shows, e.g. `clear.surname` containing `Patel`, so
   the name check is tested too.
5. Trim nothing by hand. If a page is very large, remove `<script>` and
   `<style>` blocks only; the parsers read text, not markup.
6. Run the parser on it:

   ```
   DEBUG=1 .venv/bin/python manage.py registers_parse gmc registers/adapters/fixtures/gmc/clear.html --surname Patel
   ```

   It prints the outcome, the status words, the name it found and whether
   the surname matches. If the outcome is wrong, the status vocabulary in
   that body's adapter (`NOT_FOUND`, `CLEAR`, `PROBLEM`, and the name
   marker in `name_near(...)`) needs the page's actual words; change them,
   keep the tests in `tests/test_registers_adapters.py` passing, and run
   the parser again.
7. Run the suite: `.venv/bin/python -m pytest -q tests/test_registers_adapters.py`.
   The captured pages are picked up automatically and must parse as their
   file names say.
8. Commit the pages. The next nightly run marks the body verified.

Pages contain a real person's name and registration number, which are
public on the register; nothing else personal should be in them. Do not
capture a page for anyone who has not agreed.
```

- [ ] **Step 5: Docs**

`docs/admin/compliance.md`: after the Checks section's "Who sees what", add a `## Professional registrations` section with these subsections, in the page's voice:

- **The mental model**: bodies (the four, with their codes), one number per person per body, the Welsh list keyed by the GMC number, lookups weekly spread across nights and on demand, a clear or problem lookup recording a *Professional registration* check (so the Compliance tab, card, checklist hook and reminders all see it), the lookup log under **Registration lookups**.
- **Register bodies** (`/admin/registers/registerbody/`): the titles that need each; **Active**; **Verified** (set by the code from saved pages; a body without them runs on demand only); **Paused** and **Unpause**.
- **What clear means**, per body, as in the spec §2.
- **Recording a number**: on the person's Details tab, **GMC number** (also the Welsh list), **NMC PIN number**, **GPhC number**; formats; the shared-number warning; audit as `registration:<code>`.
- **Check now** and **On the register** on the Compliance tab; the confirmation page; the result message; "not yet verified" wording.
- **The schedule**: **Check professional registrations every (days)** on Reminder settings, default 7, 1–90; a new number checked that night; the ±1 day spread; politeness (one at a time, two seconds, ten-second timeout, the user agent naming the practice from `SITE_URL`).
- **When a page cannot be read**: unreadable results, the 14-day HR reminder, pausing after three in a row, Unpause, what to do (open **On the register** yourself; if the site has changed, capture new pages as `registers/adapters/fixtures/README.md` says).
- **Terms of use**: the practice reads public pages at a gentle rate and identifies itself; if a regulator objects, make the body inactive and record the check by hand as before.
- Update **Who is reminded of what** with three rows (problem/not found/wrong name → HR and the line manager, with the body and the words, each day while it stands on the reminder cadence; number not recorded → HR from the employment start; unreadable 14 days or paused → HR). Update **The Compliance card** table with **Registration problems**. Update **The Compliance tab** paragraph (Registrations table first). Update **In the nightly output** with the `registrations:` line and its counts.

`docs/admin/people.md`: under the NI number section add **Registration numbers** (HR-only, one per body the title needs, audited as `registration:<code>`, link to compliance.md).

`docs/admin/README.md`: add "professional registrations and the register lookups" to the Compliance row.

`docs/guides/hr-administrator.md`: after "Asking someone for evidence", add `## Professional registrations` with:
- `### How to say which titles need a registration` (Compliance › **Register bodies**, **Positions**, Save; the Welsh list for GP titles too).
- `### How to record someone's registration number` (their record, Details tab, **GMC number** / **NMC PIN number** / **GPhC number**, Save; "A GMC number is seven digits." etc.; the shared-number warning).
- `### How to check a registration now` (Compliance tab, **Check now**, confirm, read the message; **On the register** to see the page yourself).
- `### When a registration check fails` (what each result means and what to do: problem → speak to the person and their manager the same day, record the outcome; wrong person → check the number; not found → check the number, then the register by hand; could not be read → try again later, then "the register's page may have changed", see the admin doc; "checks are paused" → **Unpause** on the body under **Register bodies** after a successful Check now; every run, with the register's words, is under Compliance, **Registration lookups**).
- In **Reminder settings** add step 5 for **Check professional registrations every (days)** and renumber Save.
- In **Recording a check**, after the first paragraph, one sentence: professional registration is recorded for you by the register checks when a number is on file; see Professional registrations.

`docs/guides/manager.md`: in "What you can see of a report's checks", a paragraph: a registration problem comes to you by email with the body and the register's words, unlike other checks, because it needs acting on that day; what to do.

`README.md`: one line in the features list.

`docs/superpowers/backlog.md`: item 3 becomes delivered in the Next list's numbering (remove it, renumber), with a smaller item "capture the register page fixtures per `registers/adapters/fixtures/README.md` so the bodies become verified" and a Later note on the GMC download service; the loose ends list gains "lookups are never pruned (with the reminder log)".

- [ ] **Step 6: Run the tests**

Run: `cd /home/user/practice-hr && .venv/bin/python -m pytest -q tests/test_registers_docs.py tests/test_docs.py tests/test_policies.py && .venv/bin/ruff check .`
Expected: all pass (every relative link and anchor resolves; every bold label exists).

- [ ] **Step 7: Full suite and commit**

Run: `cd /home/user/practice-hr && .venv/bin/python -m pytest -q && .venv/bin/ruff check . && DEBUG=1 .venv/bin/python manage.py makemigrations --check`
Expected: all pass.

```bash
git add registers docs README.md tests/test_registers_docs.py
git commit -m "Registers: the parse command, the fixture guide and the docs"
```
(plus the two trailer lines)

---

## Self-review notes (written with the spec open)

- **Spec coverage.** §1 models, formats, seed → Task 1; check recording → Task 3; §2 adapters, what clear means, name matching, verification and pausing → Tasks 2 and 3; §3 services, due items, the schedule setting → Tasks 3 and 4; §4 Details tab, Compliance tab, Check now, admin, dashboard, My record, nightly → Tasks 1, 4, 5, 6; §5 errors, audit, privacy → Tasks 3 (logs), 5 (duplicate warning, audit of Check now, unverified wording); §6 testing → each task, the no-network proof in Task 2, captured pages in Task 2's parametrised test; Documentation → Task 7.
- **Deviations from the spec, deliberate.** The dashboard number opens Employees filtered to the people counted (the card's existing contract) rather than the lookups list. The NMC PIN format is two digits, a letter, four digits, a letter. A `not_found` on the Welsh list is an alert like any not-found (the spec's "for a GP in post" is every case here, since only employed people with a needed body are alerted). Check now confirms on GET because the admin change form cannot nest a form; the confirmation page writes nothing.
- **Type consistency.** `Result(outcome, status_text, name_on_register, page_hash)` is the same in Tasks 2–5; `adapters.lookup(code, number, surname)` is what Task 3 patches; `registrations.rows` returns `Row(body, registration, needed)` used by Tasks 4, 5 and 6; `lookups.run(registration, trigger, requested_by=None)` returns the `Lookup`; `lookups.scheduled(today)` returns the seven counts Task 4's nightly spreads; the setting is `registration_every_days` everywhere.
- **Review Focus pins:** 1 → `test_numbers_are_normalised_before_the_format_is_checked` (Task 1); 2 → `test_scheduled_skips_registrations_no_longer_needed_or_not_employed` (Task 3); 3 → `test_a_no_results_page_is_not_found` (Task 2); 4 → `test_surnames_match_loosely_and_never_wrongly` (Task 2); 5 → `test_an_on_demand_success_lifts_a_pause` (Task 3).
- **Known judgement calls for the executor:** the GMC "not on the GP Register" rule applies to every GMC registration (the practice's doctors are GPs); `name_near` reads the line before the number's label, which the fixture README tells the capturer to tune; a body deactivated keeps its rows and is neither checked nor alerted; `verified` is written only by the nightly sync and the tests.
