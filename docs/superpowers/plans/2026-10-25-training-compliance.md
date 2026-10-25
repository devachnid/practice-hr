# Training Compliance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record each person's training against the courses their role needs, let staff upload their own certificates for HR or their manager to verify, record a face-to-face session once for everyone who attended, show HR the filtered training matrix with a CSV download, and remind people through the existing morning digest.

**Architecture:** A new `training` app on the shared compliance pieces: `Course` (required by position title or of everyone), append-only `TrainingRecord` (verified, pending or rejected; a certificate as a `documents.File`), and `TrainingSession` (one verified record per attendee, an optional attendance sheet shared by all). Services are the only writers; pages, admin and the digest read `training.state`. The two helpers checks and training share (expiry arithmetic, the status rule) move into `compliance/validity.py`.

**Tech Stack:** Django 5.2, SQLite, django-unfold admin, pytest-django. The standard library's `csv` for the download; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-25-training-compliance-design.md`

## Global Constraints

- Services are the only writers; views and admin call services. Pages never write on GET; a POST-only view answers 405 to GET.
- `timezone.localdate()` for "today"; never `date.today()`. Tests pass `today` where they can and never depend on the calendar (a record done "30 days ago" is computed from `timezone.localdate()`, never typed).
- Tests make no network calls. Emails in tests go to Django's in-memory outbox (the `configured` fixture sets `EMAIL_HOST`).
- Append-only: no record or session is ever edited or deleted; `expires_on` on a verified record is the one field HR may change (`training.set_expiry`). A wrong self-recorded entry is rejected with a note and stays.
- A manager acts only for their direct reports on the day (`access.direct_reports`), every attendee of a session included; one outsider refuses the whole call and writes nothing.
- Every file is a `documents.File` written by `documents.files.add` and read only through `documents.files.open` (the access rule and the audit "viewed" row). The HR note is never shown to the person, never in the digest, never in the CSV.
- No PII in logs; secrets from the environment only; no model name anywhere in the repository.
- Every commit message ends with the two trailer lines the project uses (`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01PkKQLdYCQnRZiVssdedFig`); this is the project's own rule for this repository and overrides any other attribution wording.
- Run before every commit: the task's test files, `.venv/bin/ruff check .`, and `DEBUG=1 .venv/bin/python manage.py makemigrations --check`. Before the final commit, the whole suite (`.venv/bin/pytest -q`, about seven minutes).
- Shell commands run from `/home/user/practice-hr` (the shell's working directory resets between commands: prefix each with `cd /home/user/practice-hr &&`).

## Review Focus

1. **A manager records a session naming one person who is not their report.** Nothing is written: no session, no record, no file. Pinned in Task 5 (`test_one_outsider_refuses_the_whole_session_and_writes_nothing`).
2. **Someone uploads nothing for an online course, or a file for a face-to-face one.** Online without a file is refused with a message on the page; face to face with or without a file is accepted. Pinned in Task 4 (`test_self_record_needs_a_certificate_for_an_online_course_only`).
3. **A rejected entry followed by a new upload.** The rejected one counts for nothing, the row reads *Awaiting verification* again, and the rejection note is no longer shown. Pinned in Task 4 (`test_a_rejected_record_counts_for_nothing_and_a_new_upload_clears_the_note`).
4. **Someone with an employment but no position, or a title that no longer needs a course.** `everyone` courses are still required of the first; the second keeps the record as *Not required* and nobody is reminded. Pinned in Task 4 (`test_everyone_courses_need_no_position_and_a_dropped_title_is_not_chased`) and Task 6 (`test_a_leaver_and_a_not_required_course_produce_nothing`).
5. **A course name with a comma, a person with an HR note, a filter typed with HTML.** The CSV quotes the name, carries no note, and the page escapes the filter text. Pinned in Task 7 (`test_the_csv_quotes_names_and_carries_no_note`, `test_the_filter_text_is_escaped_on_the_page`).

---

## File structure

- `compliance/validity.py` — `expires_from(done_on, validity_months)`, `status(expires_on, has_latest, required, today, window_days)`, `WINDOW_DAYS`. Pure.
- `training/__init__.py`, `training/apps.py` — the app.
- `training/models.py` — `Course`, `TrainingSession`, `TrainingRecord`.
- `training/migrations/0001_initial.py`, `0002_seed_courses.py`.
- `training/services/__init__.py`.
- `training/services/training.py` — `Row`, `LABELS`, `PROBLEMS`, `required_for`, `build_row`, `state`, `summary`, `to_verify`, `record`, `self_record`, `verify`, `reject`, `set_expiry`.
- `training/services/sessions.py` — `record_session`.
- `training/services/matrix.py` — `Matrix`, `Entry`, `build`, `to_csv`, `filename`, `SHOW`.
- `training/services/due.py` — `due_items(today, sched)`.
- `training/forms.py` — the site's forms: `SelfRecordForm`, `RecordForm`, `SessionForm`, `RejectForm`, `MatrixFilterForm`.
- `training/admin_forms.py` — the admin's `AdminRecordForm`, `AdminSessionForm`.
- `training/views.py`, `training/urls.py` — self-record, person page, record, verify, reject, session, matrix, matrix CSV.
- `training/admin.py` — Courses, Training records (Verify / Reject actions), Training sessions.
- `templates/people/_training.html`, `templates/people/_team_training.html`, `templates/training/person.html`, `templates/training/reject.html`, `templates/training/session.html`, `templates/training/matrix.html`, `templates/training/admin/verify.html`, `templates/training/admin/reject.html`, `templates/email/training_rejected.txt`.
- Modified: `checks/services/checks.py` (import the shared helpers), `config/settings.py` (INSTALLED_APPS, RETENTION_DAYS), `config/urls.py`, `accounts/backends.py` (HR_APPS), `hr/admin_site.py` (nav), `onboarding/middleware.py` (ALLOWED_PREFIXES), `people/services/access.py` (three rules and two `can_view_file` cases), `people/views.py` (My record and My team context, retention labels), `templates/people/me.html`, `templates/people/team.html`, `templates/onboarding/getting_started.html`, `onboarding/views.py` (Getting started context), `people/admin.py` (Compliance tab table), `compliance/services/digest.py` (source and wording), `absence/admin_dashboard.py` (two counts, matrix links), `templates/admin/index.html` (card text), docs.
- Tests: `tests/test_validity.py`, `tests/test_training_models.py`, `tests/test_training_access.py`, `tests/test_training_services.py`, `tests/test_training_sessions.py`, `tests/test_training_due.py`, `tests/test_training_matrix.py`, `tests/test_training_pages.py`, `tests/test_training_admin.py`, `tests/test_training_docs.py`.

---

### Task 1: The shared helpers move into `compliance/validity.py`

**Files:**
- Create: `compliance/validity.py`
- Modify: `checks/services/checks.py:43-80` (`expires_from`, `_status`)
- Test: `tests/test_validity.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `compliance.validity.expires_from(done_on: date, validity_months: int | None) -> date | None`; `compliance.validity.status(expires_on: date | None, has_latest: bool, required: bool, today: date, window_days: int) -> str` returning one of `not_required`, `missing`, `current`, `due_soon`, `lapsed`; `compliance.validity.WINDOW_DAYS = 60`. `checks.expires_from(done_on, check_type)` keeps its signature and calls the shared function, so every existing checks test passes unchanged.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_validity.py
"""The expiry arithmetic and the status rule checks and training share."""
import calendar
from datetime import date, timedelta

import pytest

from compliance import validity

Y = 2031      # a fixed year: the arithmetic is pure, no calendar dependence


def test_expires_from_adds_calendar_months_clipped_to_the_month_end():
    assert validity.expires_from(date(Y, 1, 31), 12) == date(Y + 1, 1, 31)
    assert validity.expires_from(date(Y, 1, 31), 1) == date(Y, 2, 29 if calendar.isleap(Y) else 28)
    assert validity.expires_from(date(Y, 12, 15), 13) == date(Y + 2, 1, 15)
    assert validity.expires_from(date(Y, 3, 31), 36) == date(Y + 3, 3, 31)


def test_a_blank_validity_never_expires():
    assert validity.expires_from(date(Y, 1, 31), None) is None


@pytest.mark.parametrize("expires_in,has_latest,required,expected", [
    (None, False, False, "not_required"),
    (10, True, False, "not_required"),       # a record the title no longer needs
    (None, False, True, "missing"),
    (None, True, True, "current"),           # a one-off: no expiry, current for good
    (61, True, True, "current"),
    (60, True, True, "due_soon"),            # the window's first day
    (0, True, True, "due_soon"),             # valid through today
    (-1, True, True, "lapsed"),
])
def test_status_follows_the_expiry_and_the_window(expires_in, has_latest, required, expected):
    today = date(Y, 6, 1)
    expires_on = today + timedelta(days=expires_in) if expires_in is not None else None
    assert validity.status(expires_on, has_latest, required, today, window_days=60) == expected


def test_the_window_is_the_callers():
    today = date(Y, 6, 1)
    assert validity.status(today + timedelta(days=20), True, True, today, window_days=10) == "current"
    assert validity.status(today + timedelta(days=10), True, True, today, window_days=10) == "due_soon"
    assert validity.WINDOW_DAYS == 60
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_validity.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'compliance.validity'`

- [ ] **Step 3: Write the module**

```python
# compliance/validity.py
"""The expiry arithmetic and the status rule that checks and training
share. Pure functions of dates: no models, no "today" of their own."""
import calendar
from datetime import timedelta

WINDOW_DAYS = 60     # "due soon" starts this many days before expiry, unless the reminder schedule says otherwise


def expires_from(done_on, validity_months):
    """`done_on` plus the months, clipped to the month's end (31 Jan plus one
    month is 28 or 29 Feb); None for a blank validity, which never expires."""
    if validity_months is None:
        return None
    month = done_on.month - 1 + validity_months
    year = done_on.year + month // 12
    month = month % 12 + 1
    day = min(done_on.day, calendar.monthrange(year, month)[1])
    return done_on.replace(year=year, month=month, day=day)


def status(expires_on, has_latest, required, today, window_days):
    """not_required, missing, current, due_soon (expiry within the window,
    today included) or lapsed (expiry before today)."""
    if not required:
        return "not_required"
    if not has_latest:
        return "missing"
    if expires_on is None:
        return "current"
    if expires_on < today:
        return "lapsed"
    if expires_on <= today + timedelta(days=window_days):
        return "due_soon"
    return "current"
```

- [ ] **Step 4: Point checks at it**

In `checks/services/checks.py`, add `from compliance import validity` to the imports (alphabetically, after `from checks.models import Check, CheckType`), delete the `import calendar` line, and replace the two functions:

```python
def expires_from(done_on, check_type):
    """done_on plus the type's validity_months (compliance.validity); None for a one-off."""
    return validity.expires_from(done_on, check_type.validity_months)
```

```python
def _status(latest, required, today, window_days):
    if required and latest is not None:
        if latest.awaiting:
            return "awaiting"
        if latest.outcome not in CLEAR:
            return "missing"
    return validity.status(latest.expires_on if latest is not None else None, latest is not None, required,
                           today, window_days)
```

Nothing else in the file changes.

- [ ] **Step 5: Run the tests, the checks tests and the lint**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_validity.py tests/test_checks.py tests/test_compliance.py -q && .venv/bin/ruff check .`
Expected: all pass (the checks tests unchanged), ruff clean.

- [ ] **Step 6: Commit**

```bash
cd /home/user/practice-hr && git add compliance/validity.py checks/services/checks.py tests/test_validity.py && git commit -q -F - <<'MSG'
Compliance: the expiry arithmetic and the status rule move to compliance.validity

Checks keeps its signatures and calls the shared functions; training
(spec 4) will call the same two.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01PkKQLdYCQnRZiVssdedFig
MSG
```

---

### Task 2: The `training` app: models, seed, course admin, settings and navigation

**Files:**
- Create: `training/__init__.py`, `training/apps.py`, `training/models.py`, `training/migrations/0001_initial.py` (generated), `training/migrations/0002_seed_courses.py`, `training/services/__init__.py`, `training/admin.py` (Courses only for now), `training/urls.py` (empty list for now)
- Modify: `config/settings.py:57-78` (INSTALLED_APPS), `config/urls.py` (mount `training/`), `accounts/backends.py:13` (HR_APPS), `hr/admin_site.py:115-127` (Compliance nav)
- Test: `tests/test_training_models.py`

**Interfaces:**
- Produces the models every later task uses:
  - `Course(name, code, validity_months, everyone, positions, delivery, display_order, active)` with `Course.Delivery.ONLINE = "online"`, `Course.Delivery.FACE_TO_FACE = "face_to_face"`; ordering `display_order, name`; `positions` M2M `people.PositionTitle` related_name `courses`.
  - `TrainingSession(course, held_on, trainer, note, attendance_sheet, recorded_by, recorded_at)`; `attendance_sheet` FK `documents.File` related_name `attendance_sheet_of`; `records` reverse from TrainingRecord.
  - `TrainingRecord(employee, course, done_on, expires_on, note, certificate, session, recorded_by, recorded_at, verified_by, verified_at, rejected_at, rejected_note)`; `certificate` FK `documents.File` related_name `certificate_of`; `employee` related_name `training_records`; `course` related_name `records`; properties `counts` (verified and not rejected), `pending` (neither), `rejected`.
  - URL namespace `training` mounted at `/training/`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_training_models.py
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from training.models import Course, TrainingRecord, TrainingSession

pytestmark = pytest.mark.django_db


def test_seeded_courses_exist_with_the_spec_defaults_and_nothing_required():
    by = {c.code: c for c in Course.objects.all()}
    assert set(by) == {"basic_life_support", "fire_safety", "information_governance", "infection_control",
                       "safeguarding_children", "safeguarding_adults", "equality_diversity", "health_safety",
                       "conflict_resolution", "chaperone"}
    assert by["basic_life_support"].delivery == "face_to_face" and by["basic_life_support"].validity_months == 12
    assert by["fire_safety"].delivery == "online" and by["fire_safety"].validity_months == 12
    assert by["safeguarding_children"].validity_months == 36
    assert by["chaperone"].validity_months is None
    assert all(not c.everyone and not c.positions.exists() and c.active for c in by.values())
    assert [c.code for c in Course.objects.all()][:2] == ["basic_life_support", "fire_safety"]   # display order


def test_validity_months_cannot_be_zero():
    c = Course(name="X", code="x", validity_months=0)
    with pytest.raises(ValidationError):
        c.full_clean()


def test_a_record_is_pending_then_counts_or_is_rejected(hr_admin):
    from tests.factories import make_employee
    e = make_employee()
    course = Course.objects.get(code="fire_safety")
    r = TrainingRecord.objects.create(employee=e, course=course, done_on=timezone.localdate(), recorded_by=hr_admin)
    assert r.pending and not r.counts and not r.rejected
    r.verified_by, r.verified_at = hr_admin, timezone.now()
    assert r.counts and not r.pending
    r.rejected_at = timezone.now()
    assert r.rejected and not r.counts and not r.pending
    assert str(r) == f"Fire safety for {e}"


def test_a_session_orders_newest_first_and_names_itself(hr_admin):
    course = Course.objects.get(code="basic_life_support")
    today = timezone.localdate()
    old = TrainingSession.objects.create(course=course, held_on=today - timedelta(days=30), recorded_by=hr_admin)
    new = TrainingSession.objects.create(course=course, held_on=today, trainer="Resus UK", recorded_by=hr_admin)
    assert list(TrainingSession.objects.all()) == [new, old]
    assert str(new) == f"Basic life support on {today:%d %b %Y}"


def test_the_app_is_an_hr_app_with_its_courses_in_the_compliance_sidebar(admin_client):
    from django.test import RequestFactory

    from accounts.backends import HR_APPS
    from hr.admin_site import navigation
    assert "training" in HR_APPS
    request = RequestFactory().get("/admin/")
    request.user = type("U", (), {"is_active": True, "is_hr_admin": True, "is_superuser": False})()
    group = next(g for g in navigation(request) if g["title"] == "Compliance")
    titles = [i["title"] for i in group["items"]]
    assert titles[:5] == ["Check types", "Checks", "Register bodies", "Registration lookups", "Files"]
    assert titles.index("Signatures") + 1 == titles.index("Courses")
    assert "Training records" in titles and "Training sessions" in titles
    assert admin_client.get("/admin/training/course/").status_code == 200


def test_courses_are_made_inactive_never_deleted(admin_client):
    c = Course.objects.get(code="chaperone")
    assert admin_client.get(f"/admin/training/course/{c.pk}/delete/").status_code == 403
    body = admin_client.get(f"/admin/training/course/{c.pk}/change/").content.decode()
    assert 'name="everyone"' in body and 'name="code"' not in body      # code is read-only once added
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_training_models.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'training'`

- [ ] **Step 3: Create the app and its models**

```python
# training/__init__.py
```
(empty)

```python
# training/apps.py
from django.apps import AppConfig


class TrainingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "training"
```

```python
# training/services/__init__.py
```
(empty)

```python
# training/models.py
"""Courses a role needs, and each person's training records. A Course says
who needs it (position titles, or everyone) and how long it lasts; a
TrainingRecord is one completion, verified when HR or a manager recorded
it, pending while a self-recorded one waits, or rejected with a note. A
TrainingSession is a face-to-face group: one verified record per attendee
points at it. Records are append-only: a renewal is a new row, and the
latest counting one by done_on is the one that counts
(training.services.training.state)."""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Course(models.Model):
    class Delivery(models.TextChoices):
        ONLINE = "online", "Online"
        FACE_TO_FACE = "face_to_face", "Face to face"

    name = models.CharField(max_length=60, unique=True)
    code = models.SlugField(max_length=40, unique=True)
    validity_months = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1)],
                                                       help_text="Blank: a one-off course that is never renewed.")
    everyone = models.BooleanField(default=False, verbose_name="required of everyone",
                                   help_text="Every currently employed person needs it, whatever their title.")
    positions = models.ManyToManyField("people.PositionTitle", blank=True, related_name="courses",
                                       help_text="The titles that need this course (ignored when it is required "
                                                 "of everyone).")
    delivery = models.CharField(max_length=12, choices=Delivery.choices, default=Delivery.ONLINE,
                                help_text="Online: a self-recorded completion needs its certificate. Face to "
                                          "face: usually recorded as a session.")
    display_order = models.PositiveIntegerField(default=100)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class TrainingSession(models.Model):
    """A face-to-face group on one day. Recording one makes a verified
    TrainingRecord per attendee (training.services.sessions)."""
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="sessions")
    held_on = models.DateField()
    trainer = models.CharField(max_length=120, blank=True, default="",
                               help_text="An outside provider or a colleague's name.")
    note = models.TextField(blank=True, default="")
    attendance_sheet = models.ForeignKey("documents.File", null=True, blank=True, on_delete=models.PROTECT,
                                         related_name="attendance_sheet_of")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-held_on", "-id"]

    def __str__(self):
        return f"{self.course} on {self.held_on:%d %b %Y}"


class TrainingRecord(models.Model):
    employee = models.ForeignKey("people.Employee", on_delete=models.PROTECT, related_name="training_records")
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="records")
    done_on = models.DateField()
    expires_on = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True, default="", help_text="Seen by HR and the line manager, never the person.")
    certificate = models.ForeignKey("documents.File", null=True, blank=True, on_delete=models.PROTECT,
                                    related_name="certificate_of")
    session = models.ForeignKey(TrainingSession, null=True, blank=True, on_delete=models.PROTECT,
                                related_name="records")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")
    recorded_at = models.DateTimeField(auto_now_add=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")
    verified_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_note = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["-done_on", "-id"]
        indexes = [models.Index(fields=["employee", "course"])]

    def __str__(self):
        return f"{self.course} for {self.employee}"

    @property
    def rejected(self):
        return self.rejected_at is not None

    @property
    def counts(self):
        return self.verified_at is not None and self.rejected_at is None

    @property
    def pending(self):
        return self.verified_at is None and self.rejected_at is None
```

- [ ] **Step 4: Register the app, mount the URLs, make it an HR app**

In `config/settings.py` `INSTALLED_APPS`, add `"training",` after `"registers",`.

In `accounts/backends.py` line 13, add `"training"` to `HR_APPS`:
```python
HR_APPS = {"accounts", "people", "absence", "documents", "checks", "onboarding", "compliance", "registers", "training"}
```

Create `training/urls.py` (the views come in Tasks 8 to 10; an empty list lets the mount exist now):
```python
from django.urls import path  # noqa: F401 - the routes are added task by task

app_name = "training"
urlpatterns = []
```

In `config/urls.py`, add `path("training/", include("training.urls")),` after the `registers/` line.

- [ ] **Step 5: Generate the schema migration and write the seed**

Run: `cd /home/user/practice-hr && DEBUG=1 .venv/bin/python manage.py makemigrations training -n initial`
Expected: `training/migrations/0001_initial.py` created with the three models.

```python
# training/migrations/0002_seed_courses.py
from django.db import migrations

# name, code, delivery, validity_months, display_order. No titles and not
# required of everyone: HR sets that up (docs/admin/compliance.md). A
# starting list, not a rule.
COURSES = [
    ("Basic life support", "basic_life_support", "face_to_face", 12, 10),
    ("Fire safety", "fire_safety", "online", 12, 20),
    ("Information governance", "information_governance", "online", 12, 30),
    ("Infection prevention and control", "infection_control", "online", 12, 40),
    ("Safeguarding children", "safeguarding_children", "online", 36, 50),
    ("Safeguarding adults", "safeguarding_adults", "online", 36, 60),
    ("Equality and diversity", "equality_diversity", "online", 36, 70),
    ("Health and safety", "health_safety", "online", 36, 80),
    ("Conflict resolution", "conflict_resolution", "online", 36, 90),
    ("Chaperone", "chaperone", "online", None, 100),
]


def seed(apps, schema_editor):
    Course = apps.get_model("training", "Course")
    for name, code, delivery, months, order in COURSES:
        Course.objects.get_or_create(code=code, defaults={
            "name": name, "delivery": delivery, "validity_months": months, "display_order": order})


def unseed(apps, schema_editor):
    Course = apps.get_model("training", "Course")
    Course.objects.filter(code__in=[c[1] for c in COURSES]).delete()


class Migration(migrations.Migration):
    dependencies = [("training", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
```

- [ ] **Step 6: The course admin and the navigation**

```python
# training/admin.py
"""Unfold admin over training. Courses are set up here (the titles that
need each, or everyone). Records and sessions follow in later tasks."""
from django.contrib import admin
from unfold.admin import ModelAdmin

from training.models import Course


@admin.register(Course)
class CourseAdmin(ModelAdmin):
    list_display = ("name", "delivery", "validity_months", "everyone", "active")
    list_editable = ("active",)
    list_filter = ("delivery", "everyone", "active")
    filter_horizontal = ("positions",)

    def get_readonly_fields(self, request, obj=None):
        # the services and the reminder keys name a course by its code:
        # settable when a course is added, never changed after
        fields = tuple(super().get_readonly_fields(request, obj))
        return fields + ("code",) if obj is not None else fields

    def has_delete_permission(self, request, obj=None):
        return False                      # make it inactive instead: records point at it
```

In `hr/admin_site.py`, in the Compliance group, after the `Signatures` item add three (the fourth, the matrix, comes in Task 10):
```python
            _nav_item("Courses", "school", "admin:training_course_changelist"),
            _nav_item("Training records", "workspace_premium", "admin:training_trainingrecord_changelist"),
            _nav_item("Training sessions", "groups_2", "admin:training_trainingsession_changelist"),
```
`_nav_item` returns None for a route that is not registered, so the two record and session items only appear once their `ModelAdmin`s exist. Register them now as placeholders at the end of `training/admin.py` (Task 9 replaces both):
```python
from training.models import TrainingRecord, TrainingSession  # noqa: E402 - placeholders until Task 9


@admin.register(TrainingRecord)
class TrainingRecordAdmin(ModelAdmin):
    list_display = ("employee", "course", "done_on", "expires_on")


@admin.register(TrainingSession)
class TrainingSessionAdmin(ModelAdmin):
    list_display = ("course", "held_on", "trainer")
```
(Put the import at the top with the `Course` import rather than mid-file; the comment is for the reader of this plan.)

- [ ] **Step 7: Run the tests, the migration check and the lint**

Run: `cd /home/user/practice-hr && DEBUG=1 .venv/bin/python manage.py makemigrations --check && .venv/bin/pytest tests/test_training_models.py tests/test_checks.py::test_compliance_sidebar_lists_check_types_and_checks tests/test_navigation.py -q && .venv/bin/ruff check .`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
cd /home/user/practice-hr && git add training config/settings.py config/urls.py accounts/backends.py hr/admin_site.py tests/test_training_models.py && git commit -q -F - <<'MSG'
Training: the app, its three models, the seeded courses and the course admin

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01PkKQLdYCQnRZiVssdedFig
MSG
```

---

### Task 3: Who may see and record training (`people/services/access.py`)

**Files:**
- Modify: `people/services/access.py:72-93` (`can_view_file`, then three new functions after `can_view_checks`)
- Test: `tests/test_training_access.py`

**Interfaces:**
- Consumes: `TrainingRecord`, `TrainingSession` (Task 2) through their reverse relations on `documents.File` (`certificate_of`, `attendance_sheet_of`).
- Produces:
  - `access.can_view_training(user, employee) -> bool`: HR, the person, their current line manager.
  - `access.may_record_training_for(user, employee, day) -> bool`: HR for anyone (themselves included, as HR records their own checks today); otherwise the line manager of `employee` on `day`, never for themselves.
  - `access.may_verify(user, record) -> bool`: `may_record_training_for(user, record.employee, today)`.
  - `access.can_view_file` gains: a file that is a training certificate opens for the person's current line manager; a file that is an attendance sheet opens for a manager with a direct report on that session.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_training_access.py
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from documents.models import File
from documents.services import files
from people.services import access
from tests.factories import make_employee, make_employment, make_position
from training.models import Course, TrainingRecord, TrainingSession

pytestmark = pytest.mark.django_db
User = get_user_model()
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


def _user(email):
    return User.objects.create_user(email=email, password="pw")


def _cast():
    """A person with a login, their manager (with a login), and a bystander (with a login)."""
    person = make_employee(user=_user("sam@example.com"))
    manager = make_employee(first="Mo", last="Khan", user=_user("mo@example.com"))
    other = make_employee(first="Jo", last="Bloggs", user=_user("jo@example.com"))
    today = timezone.localdate()
    make_position(make_employment(person, start=today - timedelta(days=400)), manager=manager)
    make_employment(manager, start=today - timedelta(days=800))
    make_employment(other, start=today - timedelta(days=800))
    return person, manager, other


def test_can_view_training_is_hr_the_person_and_their_manager(hr_admin):
    person, manager, other = _cast()
    assert access.can_view_training(hr_admin, person)
    assert access.can_view_training(person.user, person)
    assert access.can_view_training(manager.user, person)
    assert not access.can_view_training(other.user, person)
    assert not access.can_view_training(person.user, manager)


def test_may_record_training_for_is_hr_or_the_manager_never_yourself(hr_admin):
    person, manager, other = _cast()
    today = timezone.localdate()
    assert access.may_record_training_for(hr_admin, person, today)
    assert access.may_record_training_for(manager.user, person, today)
    assert not access.may_record_training_for(other.user, person, today)
    assert not access.may_record_training_for(person.user, person, today)        # that is self_record
    assert not access.may_record_training_for(manager.user, manager, today)
    # HR records their own training, as HR records their own checks today
    me = make_employee(first="Pat", last="Rees", user=hr_admin)
    make_employment(me, start=today - timedelta(days=10))
    assert access.may_record_training_for(hr_admin, me, today)
    # the manager of record on another day
    assert not access.may_record_training_for(manager.user, person, today - timedelta(days=500))


def test_may_verify_follows_may_record_for_the_records_person(hr_admin):
    person, manager, other = _cast()
    r = TrainingRecord.objects.create(employee=person, course=Course.objects.get(code="fire_safety"),
                                      done_on=timezone.localdate(), recorded_by=person.user)
    assert access.may_verify(hr_admin, r) and access.may_verify(manager.user, r)
    assert not access.may_verify(other.user, r) and not access.may_verify(person.user, r)


def test_a_certificate_opens_for_the_manager_a_contract_does_not(hr_admin):
    person, manager, other = _cast()
    cert = files.add(hr_admin, person, File.Category.CERTIFICATE, "Fire safety certificate",
                     SimpleUploadedFile("c.pdf", PDF))
    TrainingRecord.objects.create(employee=person, course=Course.objects.get(code="fire_safety"),
                                  done_on=timezone.localdate(), certificate=cert, recorded_by=hr_admin,
                                  verified_by=hr_admin, verified_at=timezone.now())
    plain = files.add(hr_admin, person, File.Category.CERTIFICATE, "Some other certificate",
                      SimpleUploadedFile("d.pdf", PDF))
    assert access.can_view_file(manager.user, cert)
    assert not access.can_view_file(manager.user, plain)          # a certificate not on a training record
    assert not access.can_view_file(other.user, cert)
    assert access.can_view_file(person.user, cert) and access.can_view_file(hr_admin, cert)


def test_an_attendance_sheet_opens_for_hr_and_a_manager_with_a_report_on_it(hr_admin):
    person, manager, other = _cast()
    sheet = files.add(hr_admin, None, File.Category.CERTIFICATE, "BLS attendance sheet",
                      SimpleUploadedFile("s.pdf", PDF))
    session = TrainingSession.objects.create(course=Course.objects.get(code="basic_life_support"),
                                             held_on=timezone.localdate(), attendance_sheet=sheet,
                                             recorded_by=hr_admin)
    assert access.can_view_file(hr_admin, sheet)
    assert not access.can_view_file(manager.user, sheet)            # nobody of theirs on it yet
    TrainingRecord.objects.create(employee=person, course=session.course, done_on=session.held_on,
                                  session=session, recorded_by=hr_admin, verified_by=hr_admin,
                                  verified_at=timezone.now())
    assert access.can_view_file(manager.user, sheet)
    assert not access.can_view_file(other.user, sheet)
    assert not access.can_view_file(person.user, sheet)             # the sheet is not the person's file
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_training_access.py -q`
Expected: FAIL with `AttributeError: module 'people.services.access' has no attribute 'can_view_training'` (and the two file tests fail on the manager assertions).

- [ ] **Step 3: Write the rules**

Replace `can_view_file` in `people/services/access.py` with:

```python
def can_view_file(user, file):
    """HR always; the person their own unless HR-only; any employee a
    policy version's file (category Policy, no person: the policies page's
    Read link); a line manager their report's training certificate and the
    attendance sheet of a session a report was at; nobody else (managers
    never see any other document)."""
    if can_view_restricted(user):
        return True
    me = employee_for(user)
    if me is None:
        return False
    if file.category == "policy" and file.employee_id is None and not file.hr_only:
        return True
    if file.employee_id == me.pk and not file.hr_only:
        return True
    return _training_file_for_manager(me, file)


def _training_file_for_manager(me, file):
    from django.utils import timezone

    from training.models import TrainingRecord
    day = timezone.localdate()
    if file.employee_id is not None:
        return (not file.hr_only and file.certificate_of.exists()
                and line_manager(file.employee, day) == me)
    if not file.attendance_sheet_of.exists():
        return False
    reports = {emp.employee_id for emp in direct_reports(me, day)}
    return TrainingRecord.objects.filter(session__attendance_sheet=file, employee_id__in=reports).exists()
```

After `can_view_checks`, add:

```python
def can_view_training(user, employee):
    """A person's training in detail: HR, the person, and their current line
    manager (training is not health or identity material: the manager
    chases and records it)."""
    from django.utils import timezone
    if can_view_restricted(user):
        return True
    me = employee_for(user)
    if me is None:
        return False
    return me.pk == employee.pk or line_manager(employee, timezone.localdate()) == me


def may_record_training_for(user, employee, day):
    """Who records training for someone: HR (themselves included, as HR
    records their own checks), or the person's line manager on `day`.
    A manager never records their own: that is training.self_record."""
    if can_view_restricted(user):
        return True
    me = employee_for(user)
    if me is None or me.pk == employee.pk:
        return False
    return line_manager(employee, day) == me


def may_verify(user, record):
    """Who verifies or rejects a pending record: the same people who could
    have recorded it for the person today."""
    from django.utils import timezone
    return may_record_training_for(user, record.employee, timezone.localdate())
```

- [ ] **Step 4: Run the tests, the file tests and the lint**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_training_access.py tests/test_documents_files.py tests/test_access.py -q && .venv/bin/ruff check .`
Expected: all pass (the existing file rules unchanged: `test_download_refused_to_another_employee_and_to_the_manager` still passes because a contract is not a training certificate).

- [ ] **Step 5: Commit**

```bash
cd /home/user/practice-hr && git add people/services/access.py tests/test_training_access.py && git commit -q -F - <<'MSG'
Access: who sees and records training, and the two training files a manager may open

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01PkKQLdYCQnRZiVssdedFig
MSG
```

---

### Task 4: The training service: what is required, each person's state, recording, verifying and rejecting

**Files:**
- Create: `training/services/training.py`, `templates/email/training_rejected.txt`
- Test: `tests/test_training_services.py`

**Interfaces:**
- Consumes: `compliance.validity` (Task 1), the models (Task 2), `access.may_record_training_for`, `access.may_verify`, `access.employee_for`, `access.can_view_restricted` (Task 3), `documents.services.files.add` / `files.sniff`, `people.services.audit.record`, `people.services.employments.current`, `people.services.positions.primary_on`, `compliance.due.active_email` / `link`, `absence.mail.send`, `accounts.mail.email_is_configured`.
- Produces:
  - `LABELS: dict[str, str]`, `PROBLEMS = ("due_soon", "lapsed", "missing")`, `STATUSES` (the six).
  - `Row(course, latest, pending, rejected, status, expires_on)` dataclass with `.label`.
  - `required_for(employee, today) -> list[Course]`.
  - `build_row(course, records, required, today, window_days) -> Row` where `records` are that person's records of that course, newest `done_on` first (the matrix in Task 7 reuses it).
  - `state(employee, today, window_days=validity.WINDOW_DAYS) -> list[Row]`; `summary(employee, today, window_days=...) -> dict` with the six status counts and `next_expiry`.
  - `to_verify(today) -> QuerySet[TrainingRecord]` (pending records of people employed today).
  - `record(actor, employee, course, done_on, upload=None, expires_on=None, note="") -> TrainingRecord`.
  - `self_record(actor, course, done_on, upload=None) -> TrainingRecord`.
  - `verify(actor, record) -> TrainingRecord`; `reject(actor, record, note) -> TrainingRecord`; `set_expiry(actor, record, expires_on) -> TrainingRecord`.
  - Helpers Task 5 reuses: `check_course(course)`, `check_date(done_on, today, what="done")`, `new_record(employee, course, done_on, actor, expires_on=None, note="", verified=False, session=None)`, `attach(actor, record, upload)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_training_services.py
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from compliance import validity
from documents.models import File
from people.models import AuditEntry
from people.services import titles
from tests.factories import make_employee, make_employment, make_position
from training.models import Course, TrainingRecord
from training.services import training

pytestmark = pytest.mark.django_db
User = get_user_model()
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


def _pdf(name="cert.pdf"):
    return SimpleUploadedFile(name, PDF)


@pytest.fixture
def fire():
    c = Course.objects.get(code="fire_safety")            # online, 12 months
    c.positions.add(titles.get_or_create("Receptionist"))
    return c


@pytest.fixture
def bls():
    c = Course.objects.get(code="basic_life_support")     # face to face, 12 months
    c.everyone = True
    c.save()
    return c


def _receptionist(user=None, manager=None, days=400, title="Receptionist"):
    e = make_employee(user=user)
    emp = make_employment(e, start=timezone.localdate() - timedelta(days=days))
    make_position(emp, title=title, manager=manager)
    return e


def _manager():
    m = make_employee(first="Mo", last="Khan", user=User.objects.create_user(email="mo@example.com", password="pw"))
    make_employment(m, start=timezone.localdate() - timedelta(days=800))
    return m


def test_required_is_by_title_or_everyone_and_needs_an_employment(fire, bls):
    e = _receptionist()
    assert [c.code for c in training.required_for(e, timezone.localdate())] == ["basic_life_support", "fire_safety"]
    nurse = _receptionist(title="Practice Nurse")
    assert [c.code for c in training.required_for(nurse, timezone.localdate())] == ["basic_life_support"]
    nobody = make_employee(first="Jo", last="Bloggs")
    assert training.required_for(nobody, timezone.localdate()) == []
    fire.active = False
    fire.save()
    assert [c.code for c in training.required_for(e, timezone.localdate())] == ["basic_life_support"]


def test_everyone_courses_need_no_position_and_a_dropped_title_is_not_chased(fire, bls, hr_admin):
    today = timezone.localdate()
    e = make_employee()
    make_employment(e, start=today - timedelta(days=10))           # employed, no position yet
    assert [c.code for c in training.required_for(e, today)] == ["basic_life_support"]
    r = _receptionist()
    training.record(hr_admin, r, fire, today - timedelta(days=5), upload=_pdf())
    fire.positions.clear()
    rows = {row.course.code: row for row in training.state(r, today)}
    assert rows["fire_safety"].status == "not_required" and rows["fire_safety"].latest is not None
    assert rows["fire_safety"].label == "Not required"


def test_record_defaults_the_expiry_verifies_at_once_stores_the_certificate_and_audits(fire, hr_admin):
    today = timezone.localdate()
    e = _receptionist()
    done = today - timedelta(days=30)
    r = training.record(hr_admin, e, fire, done, upload=_pdf(), note="Seen the certificate")
    assert r.counts and r.verified_by == hr_admin and r.recorded_by == hr_admin
    assert r.expires_on == validity.expires_from(done, 12)
    assert r.certificate.category == File.Category.CERTIFICATE and r.certificate.employee == e
    assert r.certificate.title == "Fire safety certificate" and not r.certificate.hr_only
    kinds = set(AuditEntry.objects.filter(model="training.trainingrecord", object_id=r.pk)
                .values_list("field", flat=True))
    assert kinds == {"recorded", "certificate"}
    [row] = [x for x in training.state(e, today) if x.course == fire]
    assert row.status == "current" and row.latest == r and row.expires_on == r.expires_on


def test_status_table_and_a_renewal_wins(fire, hr_admin):
    today = timezone.localdate()
    e = _receptionist()
    assert [x.status for x in training.state(e, today) if x.course == fire] == ["missing"]
    old = training.record(hr_admin, e, fire, today - timedelta(days=400), upload=_pdf())
    assert [x.status for x in training.state(e, today) if x.course == fire] == ["lapsed"]
    TrainingRecord.objects.filter(pk=old.pk).update(expires_on=today + timedelta(days=30))
    assert [x.status for x in training.state(e, today, window_days=60) if x.course == fire] == ["due_soon"]
    assert [x.status for x in training.state(e, today, window_days=10) if x.course == fire] == ["current"]
    new = training.record(hr_admin, e, fire, today - timedelta(days=1), upload=_pdf())
    [row] = [x for x in training.state(e, today) if x.course == fire]
    assert row.latest == new and row.status == "current" and TrainingRecord.objects.filter(employee=e).count() == 2


def test_self_record_needs_a_certificate_for_an_online_course_only(fire, bls, employee_user):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    with pytest.raises(ValidationError, match="certificate"):
        training.self_record(employee_user, fire, today)
    r = training.self_record(employee_user, fire, today, upload=_pdf())
    assert r.pending and r.recorded_by == employee_user and r.certificate is not None
    s = training.self_record(employee_user, bls, today - timedelta(days=2))        # face to face: no file needed
    assert s.pending and s.certificate is None
    assert AuditEntry.objects.filter(model="training.trainingrecord", field="self_recorded").count() == 2
    rows = {x.course.code: x for x in training.state(e, today)}
    assert rows["fire_safety"].status == "awaiting_verification" and rows["fire_safety"].pending == r
    assert rows["fire_safety"].label == "Awaiting verification" and rows["fire_safety"].latest is None


def test_self_record_is_for_yourself_only_and_dates_are_checked(fire, employee_user, hr_admin):
    today = timezone.localdate()
    _receptionist(user=employee_user)
    with pytest.raises(ValidationError, match="after today"):
        training.self_record(employee_user, fire, today + timedelta(days=1), upload=_pdf())
    with pytest.raises(PermissionDenied):
        training.self_record(hr_admin, fire, today, upload=_pdf())          # HR with no employee record
    fire.active = False
    fire.save()
    with pytest.raises(ValidationError, match="no longer"):
        training.self_record(employee_user, fire, today, upload=_pdf())


def test_verify_makes_it_count_and_is_for_hr_or_the_manager(fire, employee_user, hr_admin):
    today = timezone.localdate()
    m = _manager()
    e = _receptionist(user=employee_user, manager=m)
    r = training.self_record(employee_user, fire, today - timedelta(days=3), upload=_pdf())
    with pytest.raises(PermissionDenied):
        training.verify(employee_user, r)
    other = User.objects.create_user(email="jo@example.com", password="pw")
    with pytest.raises(PermissionDenied):
        training.verify(other, r)
    training.verify(m.user, r)
    r.refresh_from_db()
    assert r.counts and r.verified_by == m.user and r.verified_at is not None
    assert [x.status for x in training.state(e, today) if x.course == fire] == ["current"]
    with pytest.raises(ValidationError, match="not waiting"):
        training.verify(hr_admin, r)
    assert AuditEntry.objects.filter(model="training.trainingrecord", object_id=r.pk, field="verified").exists()


def test_reject_needs_a_note_emails_the_person_and_counts_for_nothing(fire, employee_user, hr_admin, configured):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    r = training.self_record(employee_user, fire, today, upload=_pdf())
    with pytest.raises(ValidationError, match="why"):
        training.reject(hr_admin, r, "   ")
    training.reject(hr_admin, r, "This is last year's certificate.")
    r.refresh_from_db()
    assert r.rejected and r.rejected_note == "This is last year's certificate." and not r.counts
    [msg] = mail.outbox
    assert msg.to == ["sam@example.com"] and "Fire safety" in msg.subject
    assert "This is last year's certificate." in msg.body and "/people/me/" in msg.body
    [row] = [x for x in training.state(e, today) if x.course == fire]
    assert row.status == "missing" and row.rejected == r and row.pending is None
    with pytest.raises(ValidationError):
        training.reject(hr_admin, r, "again")


def test_a_rejected_record_counts_for_nothing_and_a_new_upload_clears_the_note(fire, employee_user, hr_admin):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    first = training.self_record(employee_user, fire, today, upload=_pdf())
    training.reject(hr_admin, first, "Wrong course.")        # no relay configured: no email, no failure row
    from absence.models import EmailFailure
    assert not EmailFailure.objects.exists()
    second = training.self_record(employee_user, fire, today, upload=_pdf())
    [row] = [x for x in training.state(e, today) if x.course == fire]
    assert row.status == "awaiting_verification" and row.pending == second and row.rejected is None
    training.verify(hr_admin, second)
    [row] = [x for x in training.state(e, today) if x.course == fire]
    assert row.status == "current" and row.latest.pk == second.pk and row.rejected is None


def test_summary_counts_and_next_expiry(fire, bls, hr_admin, employee_user):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    training.record(hr_admin, e, fire, today - timedelta(days=350), upload=_pdf())      # due soon (12 months)
    training.self_record(employee_user, bls, today)                                    # awaiting
    s = training.summary(e, today)
    assert (s["current"], s["due_soon"], s["lapsed"], s["missing"], s["awaiting_verification"]) == (0, 1, 0, 0, 1)
    assert s["next_expiry"] == validity.expires_from(today - timedelta(days=350), 12)


def test_set_expiry_is_hrs_one_edit_and_audited(fire, hr_admin, employee_user):
    today = timezone.localdate()
    m = _manager()
    e = _receptionist(user=employee_user, manager=m)
    r = training.record(hr_admin, e, fire, today - timedelta(days=5), upload=_pdf())
    with pytest.raises(PermissionDenied):
        training.set_expiry(m.user, r, today + timedelta(days=10))
    training.set_expiry(hr_admin, r, today + timedelta(days=10))
    r.refresh_from_db()
    assert r.expires_on == today + timedelta(days=10)
    assert AuditEntry.objects.filter(model="training.trainingrecord", object_id=r.pk, field="expires_on").exists()
    p = training.self_record(employee_user, fire, today, upload=_pdf())
    with pytest.raises(ValidationError, match="verified"):
        training.set_expiry(hr_admin, p, today)


def test_record_is_refused_outside_the_managers_team_and_a_file_is_sniffed(fire, hr_admin, employee_user):
    today = timezone.localdate()
    m = _manager()
    e = _receptionist(user=employee_user)                          # nobody's report
    with pytest.raises(PermissionDenied):
        training.record(m.user, e, fire, today)
    with pytest.raises(ValidationError):
        training.record(hr_admin, e, fire, today, upload=SimpleUploadedFile("c.pdf", b"<html>not a pdf</html>"))
    assert not TrainingRecord.objects.exists() and not File.objects.exists()


def test_to_verify_lists_pending_records_of_people_employed_today(fire, hr_admin, employee_user):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    p = training.self_record(employee_user, fire, today, upload=_pdf())
    training.record(hr_admin, e, fire, today - timedelta(days=1), upload=_pdf())
    assert list(training.to_verify(today)) == [p]
    emp = e.employments.get()
    emp.end_date = today - timedelta(days=1)
    emp.save()
    assert list(training.to_verify(today)) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_training_services.py -q`
Expected: FAIL with `ImportError: cannot import name 'training' from 'training.services'`

- [ ] **Step 3: Write the service**

```python
# training/services/training.py
"""The only writer of TrainingRecord rows (sessions.py writes them too,
through the same helpers) and the one reader of a person's training
status. A course is required by the title of the person's current primary
position, or of everyone; state() gives one row per required course, plus
one per other course the person has a record of, each with its counting
record, any pending one, and a status. Pages, the digest, the dashboard
and the matrix all read state() or build_row()."""
from dataclasses import dataclass
from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from absence import mail
from accounts.mail import email_is_configured
from compliance import validity
from compliance.due import active_email, link
from documents.models import File
from documents.services import files
from people.services import access, audit, employments, positions
from training.models import Course, TrainingRecord

LABELS = {"current": "Current", "due_soon": "Due soon", "lapsed": "Lapsed", "missing": "Missing",
          "not_required": "Not required", "awaiting_verification": "Awaiting verification"}
STATUSES = tuple(LABELS)
PROBLEMS = ("due_soon", "lapsed", "missing")


@dataclass
class Row:
    course: Course
    latest: TrainingRecord | None          # the counting record (verified, not rejected), newest done_on
    pending: TrainingRecord | None         # the newest unverified, unrejected record
    rejected: TrainingRecord | None        # the newest rejected record, if newer than `latest`
    status: str
    expires_on: date | None

    @property
    def label(self):
        return LABELS[self.status]


# ---- reading -----------------------------------------------------------------

def required_for(employee, today):
    """Active courses required of everyone, plus those the title of the
    current primary position needs. No current employment: nothing."""
    emp = employments.current(employee, today)
    if emp is None:
        return []
    pos = positions.primary_on(emp, today)
    q = Q(everyone=True)
    if pos is not None:
        q |= Q(positions=pos.title)
    return list(Course.objects.filter(q, active=True).distinct().order_by("display_order", "name"))


def build_row(course, records, required, today, window_days):
    """`records`: this person's records of `course`, newest done_on first."""
    latest = next((r for r in records if r.counts), None)
    pending = next((r for r in records if r.pending), None)
    rejected = next((r for r in records if r.rejected and (latest is None or r.pk > latest.pk)), None)
    expires_on = latest.expires_on if latest is not None else None
    status = validity.status(expires_on, latest is not None, required, today, window_days)
    if pending is not None and status in ("missing", "lapsed"):
        status = "awaiting_verification"
    return Row(course, latest, pending, rejected, status, expires_on)


def _records_by_course(employee):
    out = {}
    for r in (TrainingRecord.objects.filter(employee=employee).select_related("certificate", "session")
              .order_by("-done_on", "-id")):
        out.setdefault(r.course_id, []).append(r)
    return out


def state(employee, today, window_days=validity.WINDOW_DAYS):
    required = required_for(employee, today)
    required_ids = {c.pk for c in required}
    extra = (Course.objects.filter(records__employee=employee).exclude(pk__in=required_ids).distinct()
             .order_by("display_order", "name"))
    by_course = _records_by_course(employee)
    return [build_row(c, by_course.get(c.pk, []), c.pk in required_ids, today, window_days)
            for c in [*required, *extra]]


def summary(employee, today, window_days=validity.WINDOW_DAYS):
    rows = state(employee, today, window_days)
    counts = {k: sum(1 for r in rows if r.status == k) for k in STATUSES}
    expiries = [r.expires_on for r in rows if r.expires_on and r.status in ("current", "due_soon")]
    counts["next_expiry"] = min(expiries) if expiries else None
    return counts


def to_verify(today):
    """Pending records of people employed today, oldest first."""
    employed = employments.active_on(today).values("employee_id")
    return (TrainingRecord.objects.filter(verified_at__isnull=True, rejected_at__isnull=True,
                                          employee_id__in=employed)
            .select_related("employee", "course").order_by("recorded_at", "pk"))


# ---- the rules the writers share ---------------------------------------------

def check_course(course):
    if not course.active:
        raise ValidationError(f"{course} is no longer in use.")


def check_date(done_on, today, what="done"):
    if done_on is None:
        raise ValidationError(f"Enter the date the training was {what}.")
    if done_on > today:
        raise ValidationError(f"The date {what} cannot be after today.")


def attach(actor, record, upload):
    """Store `upload` as the record's certificate: the person's file,
    category Certificate, never HR-only. files.add is the last fallible
    step: its bytes are not rolled back with the transaction, so every
    writer calls this after the row is saved."""
    f = files.add(actor, record.employee, File.Category.CERTIFICATE, f"{record.course} certificate", upload)
    record.certificate = f
    record.save(update_fields=["certificate"])
    audit.record(actor, record, {"certificate": ("", f.pk)})
    return record


def new_record(employee, course, done_on, actor, expires_on=None, note="", verified=False, session=None):
    now = timezone.now()
    r = TrainingRecord(employee=employee, course=course, done_on=done_on, note=note, session=session,
                       expires_on=expires_on or validity.expires_from(done_on, course.validity_months),
                       recorded_by=actor, verified_by=actor if verified else None,
                       verified_at=now if verified else None)
    r.full_clean()
    r.save()
    return r


# ---- writing -----------------------------------------------------------------

@transaction.atomic
def record(actor, employee, course, done_on, upload=None, expires_on=None, note=""):
    """HR, or the person's line manager today, records a completion:
    verified at once. `upload`, a certificate, is stored last."""
    today = timezone.localdate()
    if not access.may_record_training_for(actor, employee, today):
        raise PermissionDenied
    check_course(course)
    check_date(done_on, today)
    if upload is not None:
        files.sniff(upload)
    r = new_record(employee, course, done_on, actor, expires_on=expires_on, note=note, verified=True)
    audit.record(actor, r, {"recorded": ("", f"{course}: done {done_on:%d %b %Y}")})
    if upload is not None:
        attach(actor, r, upload)
    return r


@transaction.atomic
def self_record(actor, course, done_on, upload=None):
    """The person records their own completion: pending until HR or their
    manager verifies it. An online course needs its certificate."""
    me = access.employee_for(actor)
    if me is None:
        raise PermissionDenied
    today = timezone.localdate()
    check_course(course)
    check_date(done_on, today)
    if upload is None and course.delivery == Course.Delivery.ONLINE:
        raise ValidationError("Upload your certificate for this course.")
    if upload is not None:
        files.sniff(upload)
    r = new_record(me, course, done_on, actor)
    audit.record(actor, r, {"self_recorded": ("", f"{course}: done {done_on:%d %b %Y}")})
    if upload is not None:
        attach(actor, r, upload)
    return r


def _pending_only(record):
    if not record.pending:
        raise ValidationError("This record is not waiting to be verified.")


@transaction.atomic
def verify(actor, record):
    if not access.may_verify(actor, record):
        raise PermissionDenied
    _pending_only(record)
    record.verified_by, record.verified_at = actor, timezone.now()
    record.save(update_fields=["verified_by", "verified_at"])
    audit.record(actor, record, {"verified": ("", f"{record.course}: done {record.done_on:%d %b %Y}")})
    return record


@transaction.atomic
def reject(actor, record, note):
    """Turn a pending record down with a note; the person is emailed the
    note and where to record again. The record stays, counting for nothing."""
    if not access.may_verify(actor, record):
        raise PermissionDenied
    _pending_only(record)
    note = (note or "").strip()[:200]
    if not note:
        raise ValidationError("Say why, so the person knows what to put right.")
    record.rejected_at, record.rejected_note = timezone.now(), note
    record.save(update_fields=["rejected_at", "rejected_note"])
    audit.record(actor, record, {"rejected": ("", note)})
    _tell_rejected(record)
    return record


def _tell_rejected(record):
    """Never raises and records no failure when there is no relay: the page
    says the record was turned down either way."""
    to = active_email(record.employee)
    if not to or not email_is_configured():
        return
    body = render_to_string("email/training_rejected.txt",
                            {"record": record, "url": link(reverse("people:me"))})
    mail.send(f"Practice HR: your {record.course} training record", body, [to])


@transaction.atomic
def set_expiry(actor, record, expires_on):
    """HR's one edit after the fact: the expiry of a verified record."""
    if not access.can_view_restricted(actor):
        raise PermissionDenied
    if not record.counts:
        raise ValidationError("Only a verified record has an expiry to change.")
    before = record.expires_on
    record.expires_on = expires_on
    record.full_clean()
    record.save(update_fields=["expires_on"])
    audit.record(actor, record, {"expires_on": (before, expires_on)})
    return record
```

```
{# templates/email/training_rejected.txt #}
{% autoescape off %}Hello {{ record.employee.name }},

Your {{ record.course }} training record (done {{ record.done_on|date:"j M Y" }}) could not be verified:

  {{ record.rejected_note }}

Please record it again on My record, with the right certificate:
{{ url }}

Practice HR{% endautoescape %}
```

- [ ] **Step 4: Run the tests and the lint**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_training_services.py -q && .venv/bin/ruff check .`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /home/user/practice-hr && git add training/services/training.py templates/email/training_rejected.txt tests/test_training_services.py && git commit -q -F - <<'MSG'
Training: required courses, each person's state, recording, verifying and rejecting

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01PkKQLdYCQnRZiVssdedFig
MSG
```

---

### Task 5: Recording a group session

**Files:**
- Create: `training/services/sessions.py`
- Test: `tests/test_training_sessions.py`

**Interfaces:**
- Consumes: `training.check_course`, `training.check_date`, `training.new_record` (Task 4), `access.can_view_restricted`, `access.employee_for`, `access.direct_reports` (existing), `files.add` / `files.sniff`, `audit.record`.
- Produces: `sessions.record_session(actor, course, held_on, attendees, trainer="", note="", upload=None) -> TrainingSession`. One session and one verified record per attendee (`done_on = held_on`, `session` set), in one transaction; the attendance sheet, if any, is a `File` with no employee, category Certificate, stored last.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_training_sessions.py
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from compliance import validity
from documents.models import File
from people.models import AuditEntry
from tests.factories import make_employee, make_employment, make_position
from training.models import Course, TrainingRecord, TrainingSession
from training.services import sessions, training

pytestmark = pytest.mark.django_db
User = get_user_model()
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def bls():
    c = Course.objects.get(code="basic_life_support")
    c.everyone = True
    c.save()
    return c


def _team():
    """A manager with two reports, and a third person on another team."""
    today = timezone.localdate()
    m = make_employee(first="Mo", last="Khan", user=User.objects.create_user(email="mo@example.com", password="pw"))
    make_employment(m, start=today - timedelta(days=800))
    reports = []
    for first in ("Sam", "Ann"):
        e = make_employee(first=first, last="Patel")
        make_position(make_employment(e, start=today - timedelta(days=400)), manager=m)
        reports.append(e)
    other = make_employee(first="Jo", last="Bloggs")
    make_position(make_employment(other, start=today - timedelta(days=400)))
    return m, reports, other


def test_a_session_makes_one_verified_record_per_attendee_sharing_the_sheet(bls, hr_admin):
    today = timezone.localdate()
    m, (sam, ann), other = _team()
    held = today - timedelta(days=3)
    s = sessions.record_session(hr_admin, bls, held, [sam, ann, other, ann], trainer="Resus UK", note="Hall",
                                upload=SimpleUploadedFile("sheet.pdf", PDF))
    assert s.trainer == "Resus UK" and s.recorded_by == hr_admin
    recs = list(TrainingRecord.objects.filter(session=s).order_by("employee__first_name"))
    assert [r.employee for r in recs] == [ann, other, sam]                     # the duplicate is one record
    assert all(r.counts and r.done_on == held and r.recorded_by == hr_admin and r.certificate is None for r in recs)
    assert all(r.expires_on == validity.expires_from(held, 12) for r in recs)
    assert s.attendance_sheet.employee is None and s.attendance_sheet.category == File.Category.CERTIFICATE
    assert s.attendance_sheet.title == f"Basic life support attendance sheet, {held:%d %b %Y}"
    assert AuditEntry.objects.filter(model="training.trainingrecord", field="session_recorded").count() == 3
    [row] = [x for x in training.state(sam, today) if x.course == bls]
    assert row.status == "current" and row.latest.session == s


def test_a_manager_records_a_session_for_their_own_reports(bls):
    today = timezone.localdate()
    m, (sam, ann), other = _team()
    s = sessions.record_session(m.user, bls, today, [sam, ann])            # no sheet: fine
    assert s.attendance_sheet is None and TrainingRecord.objects.filter(session=s).count() == 2


def test_one_outsider_refuses_the_whole_session_and_writes_nothing(bls):
    today = timezone.localdate()
    m, (sam, ann), other = _team()
    with pytest.raises(PermissionDenied):
        sessions.record_session(m.user, bls, today, [sam, other], upload=SimpleUploadedFile("s.pdf", PDF))
    assert not TrainingSession.objects.exists() and not TrainingRecord.objects.exists()
    assert not File.objects.exists()
    with pytest.raises(PermissionDenied):
        sessions.record_session(m.user, bls, today, [m])                      # never yourself
    stranger = User.objects.create_user(email="jo@example.com", password="pw")
    with pytest.raises(PermissionDenied):
        sessions.record_session(stranger, bls, today, [sam])


def test_the_sessions_rules(bls, hr_admin):
    today = timezone.localdate()
    m, (sam, ann), other = _team()
    with pytest.raises(ValidationError, match="at least one"):
        sessions.record_session(hr_admin, bls, today, [])
    with pytest.raises(ValidationError, match="after today"):
        sessions.record_session(hr_admin, bls, today + timedelta(days=1), [sam])
    bls.active = False
    bls.save()
    with pytest.raises(ValidationError, match="no longer"):
        sessions.record_session(hr_admin, bls, today, [sam])
    bls.active = True
    bls.save()
    with pytest.raises(ValidationError):
        sessions.record_session(hr_admin, bls, today, [sam], upload=SimpleUploadedFile("s.pdf", b"<html></html>"))
    assert not TrainingSession.objects.exists()


def test_recording_the_session_again_adds_the_person_left_off(bls, hr_admin):
    today = timezone.localdate()
    m, (sam, ann), other = _team()
    first = sessions.record_session(hr_admin, bls, today, [sam])
    second = sessions.record_session(hr_admin, bls, today, [ann])
    assert first != second and TrainingRecord.objects.filter(course=bls).count() == 2
    assert str(second) == f"Basic life support on {today:%d %b %Y}"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_training_sessions.py -q`
Expected: FAIL with `ImportError: cannot import name 'sessions' from 'training.services'`

- [ ] **Step 3: Write the service**

```python
# training/services/sessions.py
"""A face-to-face group recorded once: one TrainingSession and one verified
TrainingRecord per attendee, in one transaction. HR records anyone; a
manager only their direct reports on the day, and one outsider refuses the
whole call before anything is written. The attendance sheet, if any, is a
file with no person (stored last, as every upload is)."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from documents.models import File
from documents.services import files
from people.services import access, audit
from training.models import TrainingSession
from training.services import training


@transaction.atomic
def record_session(actor, course, held_on, attendees, trainer="", note="", upload=None):
    today = timezone.localdate()
    attendees = list({e.pk: e for e in attendees}.values())           # a name ticked twice is one record
    if not attendees:
        raise ValidationError("Choose at least one person who attended.")
    training.check_course(course)
    training.check_date(held_on, today, what="held")
    if not access.can_view_restricted(actor):
        me = access.employee_for(actor)
        reports = {emp.employee_id for emp in access.direct_reports(me, held_on)} if me is not None else set()
        if any(e.pk not in reports for e in attendees):
            raise PermissionDenied
    if upload is not None:
        files.sniff(upload)
    s = TrainingSession(course=course, held_on=held_on, trainer=trainer, note=note, recorded_by=actor)
    s.full_clean()
    s.save()
    for e in attendees:
        r = training.new_record(e, course, held_on, actor, verified=True, session=s)
        audit.record(actor, r, {"session_recorded": ("", f"{course}: session on {held_on:%d %b %Y}")})
    if upload is not None:
        f = files.add(actor, None, File.Category.CERTIFICATE, f"{course} attendance sheet, {held_on:%d %b %Y}",
                      upload)
        s.attendance_sheet = f
        s.save(update_fields=["attendance_sheet"])
    return s
```

- [ ] **Step 4: Run the tests and the lint**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_training_sessions.py tests/test_training_services.py -q && .venv/bin/ruff check .`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /home/user/practice-hr && git add training/services/sessions.py tests/test_training_sessions.py && git commit -q -F - <<'MSG'
Training: a group session is recorded once, one verified record per attendee

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01PkKQLdYCQnRZiVssdedFig
MSG
```

---

### Task 6: Reminders in the digest, and the retention category

**Files:**
- Create: `training/services/due.py`
- Modify: `compliance/services/digest.py:17-26` (import and `SOURCES`), `compliance/services/digest.py:30-45` (`_when`), `config/settings.py:213-214` (the retention tuple), `people/views.py:120-128` (`CATEGORY_LABELS`)
- Test: `tests/test_training_due.py`

**Interfaces:**
- Consumes: `training.state`, `training.PROBLEMS` (Task 4), `compliance.due.DueItem` / `active_email` / `link` / `state_by_date`, `absence.services.notify.hr_admin_addresses`, `access.line_manager`, `employments.active_on` / `current`. The person page route `training:person` (`/training/<employee pk>/`) is not registered until Task 9: until then `due_items` builds the HR link with `link(f"/training/{e.pk}/")`, and Task 9 swaps it for `reverse`.
- Produces: `due.due_items(today, sched) -> list[DueItem]`, kind `training`; states `due_soon` / `due_today` / `overdue` / `lapsed` / `missing` as checks, plus `to_verify` for HR. Keys `training:<employee pk>:<course code>:<due iso>:<status>` and `training:verify:<record pk>`. `due.WORDS` by delivery. `digest._when` says `uploaded <date>` for `to_verify`. `settings.RETENTION_DAYS["training"]` (default 2190), label *Training records*.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_training_due.py
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from compliance.models import ReminderSchedule
from compliance.services import digest
from people.services import employments, titles
from tests.factories import make_employee, make_employment, make_position
from training.models import Course
from training.services import due, training

pytestmark = pytest.mark.django_db
User = get_user_model()
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def fire():
    c = Course.objects.get(code="fire_safety")
    c.positions.add(titles.get_or_create("Receptionist"))
    return c


@pytest.fixture
def bls():
    c = Course.objects.get(code="basic_life_support")
    c.everyone = True
    c.save()
    return c


def _manager():
    m = make_employee(first="Mo", last="Khan", user=User.objects.create_user(email="mo@example.com", password="pw"))
    make_employment(m, start=timezone.localdate() - timedelta(days=800))
    return m


def _receptionist(user=None, manager=None):
    e = make_employee(user=user)
    emp = make_employment(e, start=timezone.localdate() - timedelta(days=400))
    make_position(emp, title="Receptionist", manager=manager)
    return e


def _items(today=None):
    return due.due_items(today or timezone.localdate(), ReminderSchedule.get())


def test_a_missing_course_goes_to_hr_and_the_person_from_the_start_date(fire, hr_admin, employee_user):
    e = _receptionist(user=employee_user)
    start = employments.current(e, timezone.localdate()).start_date
    items = _items()
    by = {i.recipient: i for i in items}
    assert set(by) == {"hr@example.com", "sam@example.com"}
    hr_item, own = by["hr@example.com"], by["sam@example.com"]
    assert hr_item.kind == "training" and hr_item.label == "Fire safety" and hr_item.state == "missing"
    assert hr_item.due_on == start and hr_item.key == f"training:{e.pk}:fire_safety:{start.isoformat()}:missing"
    assert hr_item.url.endswith(f"/training/{e.pk}/") and hr_item.once is False
    assert own.label == "Fire safety: complete the e-learning and upload your certificate"
    assert own.url.endswith("/people/me/") and own.key == hr_item.key


def test_due_soon_lapsed_and_the_manager_once_naming_the_course(fire, hr_admin, employee_user):
    today = timezone.localdate()
    m = _manager()
    e = _receptionist(user=employee_user, manager=m)
    r = training.record(hr_admin, e, fire, today - timedelta(days=350), upload=SimpleUploadedFile("c.pdf", PDF))
    items = _items()
    assert {i.recipient for i in items} == {"hr@example.com", "sam@example.com"}       # not the manager yet
    assert all(i.state == "due_soon" and i.due_on == r.expires_on for i in items)
    assert all(i.key == f"training:{e.pk}:fire_safety:{r.expires_on.isoformat()}:due_soon" for i in items)
    training.set_expiry(hr_admin, r, today - timedelta(days=1))
    items = _items()
    by = {i.recipient: i for i in items}
    assert set(by) == {"hr@example.com", "sam@example.com", "mo@example.com"}
    assert by["hr@example.com"].state == "lapsed" and by["hr@example.com"].due_on == today - timedelta(days=1)
    mgr = by["mo@example.com"]
    assert mgr.label == "Fire safety has lapsed" and mgr.once is True and mgr.url.endswith("/people/team/")
    assert mgr.key == by["hr@example.com"].key


def test_a_face_to_face_course_asks_about_the_next_session(bls, hr_admin, employee_user):
    _receptionist(user=employee_user)
    [own] = [i for i in _items() if i.recipient == "sam@example.com"]
    assert own.label == "Basic life support: ask your manager about the next session"


def test_a_pending_record_silences_the_person_and_asks_hr_to_verify(fire, hr_admin, employee_user):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    p = training.self_record(employee_user, fire, today - timedelta(days=2), upload=SimpleUploadedFile("c.pdf", PDF))
    [item] = _items()
    assert item.recipient == "hr@example.com" and item.state == "to_verify"
    assert item.label == "Fire safety: to verify" and item.key == f"training:verify:{p.pk}"
    assert item.due_on == timezone.localtime(p.recorded_at).date() and item.url.endswith(f"/training/{e.pk}/")
    assert digest._when(item) == f"uploaded {item.due_on:%-d %b %Y}"
    training.verify(hr_admin, p)
    assert _items() == []                                                 # current: nothing to say


def test_a_leaver_and_a_not_required_course_produce_nothing(fire, hr_admin, employee_user):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    assert len(_items()) == 2
    fire.positions.clear()
    assert _items() == []
    fire.positions.add(titles.get_or_create("Receptionist"))
    emp = employments.current(e, today)
    emp.end_date = today - timedelta(days=1)
    emp.save()
    assert _items() == []


def test_the_window_is_the_schedules_and_the_digest_carries_training_lines(fire, hr_admin, employee_user, configured):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    training.record(hr_admin, e, fire, today - timedelta(days=300), upload=SimpleUploadedFile("c.pdf", PDF))
    sched = ReminderSchedule.get()
    assert due.due_items(today, sched) == []                              # 65 days out, window 60
    sched.start_days_before = 90
    sched.save()
    assert {i.state for i in due.due_items(today, sched)} == {"due_soon"}
    out = digest.run(today)
    assert out["reminders_sent"] == 2
    body = next(m for m in mail.outbox if m.to == ["sam@example.com"]).body
    assert "Fire safety: complete the e-learning and upload your certificate: due" in body


def test_training_has_its_own_retention_category(settings, admin_client, hr_admin):
    assert settings.RETENTION_DAYS["training"] == 2190
    from people.views import CATEGORY_LABELS
    assert CATEGORY_LABELS["training"] == "Training records"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_training_due.py -q`
Expected: FAIL with `ImportError: cannot import name 'due' from 'training.services'`

- [ ] **Step 3: Write the due items**

```python
# training/services/due.py
"""What is due of the training, for the morning digest (compliance.due).

For each currently employed person and each required course that is due
soon, lapsed or missing: a line to every HR admin and one to the person
(always: the person does the course), keyed so the sent log applies the
schedule's cadence; the line manager once, the first time a course
lapses, naming the course (managers see training detail). A course with a
pending record says nothing to the person, who has done their part, and
asks HR to verify, keyed by the record so it repeats on the overdue
cadence until someone acts."""
from django.urls import reverse
from django.utils import timezone

from absence.services.notify import hr_admin_addresses
from compliance.due import DueItem, active_email, link, state_by_date
from people.models import Employee
from people.services import access, employments
from training.services import training

KIND = "training"
WORDS = {"online": "complete the e-learning and upload your certificate",
         "face_to_face": "ask your manager about the next session"}


def _person_url(e):
    return link(f"/training/{e.pk}/")      # training:person, registered in a later task


def due_items(today, sched):
    out = []
    hr = hr_admin_addresses()
    own_url, team_url = link(reverse("people:me")), link(reverse("people:team"))
    employed = employments.active_on(today).values("employee_id")
    for e in Employee.objects.filter(pk__in=employed).select_related("user"):
        emp = employments.current(e, today)
        if emp is None:
            continue
        person = active_email(e)
        hr_url = _person_url(e)
        for row in training.state(e, today, window_days=sched.start_days_before):
            if row.pending is not None:
                uploaded = timezone.localtime(row.pending.recorded_at).date()
                key = f"training:verify:{row.pending.pk}"
                for r in hr:
                    out.append(DueItem(e, r, KIND, f"{row.course.name}: to verify", uploaded, "to_verify", hr_url, key))
                continue
            if row.status not in training.PROBLEMS:
                continue
            # missing has no expiry: it has been owed since the employment started
            due = row.expires_on if row.status != "missing" else emp.start_date
            key = f"training:{e.pk}:{row.course.code}:{due.isoformat()}:{row.status}"
            state = state_by_date(today, due) if row.status == "due_soon" else row.status
            for r in hr:
                out.append(DueItem(e, r, KIND, row.course.name, due, state, hr_url, key))
            if person:
                out.append(DueItem(e, person, KIND, f"{row.course.name}: {WORDS[row.course.delivery]}", due, state,
                                   own_url, key))
            if row.status == "lapsed":
                manager = active_email(access.line_manager(e, today))
                if manager:
                    out.append(DueItem(e, manager, KIND, f"{row.course.name} has lapsed", due, "lapsed", team_url,
                                       key, once=True))
    return out
```

- [ ] **Step 4: Wire the digest and the retention category**

In `compliance/services/digest.py`: add `from training.services import due as training_due` after the registers import, and add it to `SOURCES`:
```python
SOURCES = (checks_due.due_items, documents_due.due_items, onboarding_due.due_items, registers_due.due_items,
           training_due.due_items)
```
In `_when`, before `if item.state == "due_today":`, add:
```python
    if item.state == "to_verify":
        return f"uploaded {item.due_on:%-d %b %Y}"
```

In `config/settings.py` `_retention_days`, add `("training", 2190)` to the tuple after `("signatures", 2190)`, and extend the comment above it: `# ... six years (checks, files, policy signatures and training records included)`.

In `people/views.py` `CATEGORY_LABELS`, add `"training": "Training records",` after the signatures line.

- [ ] **Step 5: Run the tests and the lint**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_training_due.py tests/test_compliance.py tests/test_retention.py tests/test_compliance_admin.py -q && .venv/bin/ruff check .`
Expected: all pass. If `test_retention_report_lists_the_new_categories` in `tests/test_compliance_admin.py` asserts an exact set of categories, add `training` to its expectation: the report now has one more line for a leaver.

- [ ] **Step 6: Commit**

```bash
cd /home/user/practice-hr && git add training/services/due.py compliance/services/digest.py config/settings.py people/views.py tests/test_training_due.py tests/test_compliance_admin.py && git commit -q -F - <<'MSG'
Training: reminders ride the morning digest; a retention category for training records

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01PkKQLdYCQnRZiVssdedFig
MSG
```

---

### Task 7: The matrix and its CSV

**Files:**
- Create: `training/services/matrix.py`
- Test: `tests/test_training_matrix.py`

**Interfaces:**
- Consumes: `training.build_row`, `training.PROBLEMS` (Task 4), the models, `employments.active_on`, `people.models.Position`.
- Produces:
  - `matrix.SHOW = ("all", "problems", "to_verify")`.
  - `matrix.Entry(employee, cells: dict[int, Row])` keyed by course pk; `matrix.Matrix(courses: list[Course], rows: list[Entry])`.
  - `matrix.build(today, course=None, team=None, query="", show="all", window_days=validity.WINDOW_DAYS) -> Matrix`: people employed today (surname, forename order), filtered by primary team, by a name search, and by `show`; columns every course at least one shown person needs or has (or the one course filtered). A bounded number of queries whatever the practice's size.
  - `matrix.to_csv(m) -> str`; `matrix.filename(today, course=None, team=None, query="", show="all") -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_training_matrix.py
import csv
import io
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from people.services import titles
from tests.factories import make_employee, make_employment, make_position, make_team
from training.models import Course
from training.services import matrix, training

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def courses():
    fire = Course.objects.get(code="fire_safety")
    fire.positions.add(titles.get_or_create("Receptionist"))
    bls = Course.objects.get(code="basic_life_support")
    bls.everyone = True
    bls.save()
    return fire, bls


def _people(hr_admin):
    """Two receptionists in Reception, a nurse in Nursing, and a leaver."""
    today = timezone.localdate()
    reception, nursing = make_team(name="Reception"), make_team(name="Nursing")
    out = {}
    for first, last, title, team in (("Sam", "Patel", "Receptionist", reception),
                                     ("Ann", "Brown", "Receptionist", reception),
                                     ("Nia", "Evans", "Practice Nurse", nursing)):
        e = make_employee(first=first, last=last)
        make_position(make_employment(e, start=today - timedelta(days=400)), title=title, team=team)
        out[first] = e
    leaver = make_employee(first="Old", last="Hand")
    make_position(make_employment(leaver, start=today - timedelta(days=900), end_date=today - timedelta(days=1)),
                  title="Receptionist", team=reception)
    return out, reception, nursing


def test_the_matrix_has_people_down_and_needed_or_held_courses_across(courses, hr_admin):
    fire, bls = courses
    people, reception, nursing = _people(hr_admin)
    today = timezone.localdate()
    training.record(hr_admin, people["Nia"], fire, today - timedelta(days=5), upload=SimpleUploadedFile("c.pdf", PDF))
    m = matrix.build(today)
    assert [e.employee.name for e in m.rows] == ["Ann Brown", "Nia Evans", "Sam Patel"]        # no leaver
    assert [c.code for c in m.courses] == ["basic_life_support", "fire_safety"]
    nia = next(e for e in m.rows if e.employee == people["Nia"])
    assert nia.cells[fire.pk].status == "not_required" and nia.cells[bls.pk].status == "missing"
    sam = next(e for e in m.rows if e.employee == people["Sam"])
    assert sam.cells[fire.pk].status == "missing" and bls.pk in sam.cells


def test_filters_by_course_team_and_name(courses, hr_admin):
    fire, bls = courses
    people, reception, nursing = _people(hr_admin)
    today = timezone.localdate()
    m = matrix.build(today, team=nursing)
    assert [e.employee.first_name for e in m.rows] == ["Nia"]
    m = matrix.build(today, course=fire)
    assert [c.code for c in m.courses] == ["fire_safety"]
    assert [e.employee.first_name for e in m.rows] == ["Ann", "Nia", "Sam"]
    assert m.rows[1].cells == {}                                        # Nia neither needs nor has it: an empty cell
    m = matrix.build(today, query="pat")
    assert [e.employee.first_name for e in m.rows] == ["Sam"]
    m = matrix.build(today, query="nobody")
    assert m.rows == [] and m.courses == []
    assert matrix.build(today, query="nobody", course=fire).courses == [fire]


def test_problems_only_and_to_verify(courses, hr_admin):
    fire, bls = courses
    people, reception, nursing = _people(hr_admin)
    today = timezone.localdate()
    from django.contrib.auth import get_user_model
    user = get_user_model().objects.create_user(email="ann@example.com", password="pw")
    people["Ann"].user = user
    people["Ann"].save()
    for e in people.values():
        training.record(hr_admin, e, bls, today - timedelta(days=5))
    training.record(hr_admin, people["Sam"], fire, today - timedelta(days=5), upload=SimpleUploadedFile("c.pdf", PDF))
    pending = training.self_record(user, fire, today, upload=SimpleUploadedFile("c.pdf", PDF))
    m = matrix.build(today, show="problems")
    assert [e.employee.first_name for e in m.rows] == ["Ann"]                 # Sam and Nia have nothing wrong
    assert [c.code for c in m.courses] == ["fire_safety"]
    assert m.rows[0].cells[fire.pk].status == "awaiting_verification" and m.rows[0].cells[fire.pk].pending == pending
    m = matrix.build(today, show="to_verify")
    assert [e.employee.first_name for e in m.rows] == ["Ann"]
    training.verify(hr_admin, pending)
    assert matrix.build(today, show="problems").rows == [] and matrix.build(today, show="to_verify").rows == []


def test_the_query_count_does_not_grow_with_the_practice(courses, hr_admin, django_assert_max_num_queries):
    people, reception, nursing = _people(hr_admin)
    today = timezone.localdate()
    for i in range(12):
        e = make_employee(first=f"P{i}", last="Many")
        make_position(make_employment(e, start=today - timedelta(days=100)), title="Receptionist", team=reception)
    with django_assert_max_num_queries(8):
        m = matrix.build(today)
    assert len(m.rows) == 15


def test_the_csv_quotes_names_and_carries_no_note(courses, hr_admin):
    fire, bls = courses
    people, reception, nursing = _people(hr_admin)
    today = timezone.localdate()
    fire.name = "Fire safety, awareness"
    fire.save()
    r = training.record(hr_admin, people["Sam"], fire, today - timedelta(days=5), note="HR ONLY NOTE",
                        upload=SimpleUploadedFile("c.pdf", PDF))
    text = matrix.to_csv(matrix.build(today))
    assert "HR ONLY NOTE" not in text
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0] == ["Person", "Basic life support", "Fire safety, awareness"]
    sam = next(row for row in rows if row[0] == "Sam Patel")
    assert sam[1] == "Missing" and sam[2] == f"Current, {r.expires_on:%d %b %Y}"
    nia = next(row for row in rows if row[0] == "Nia Evans")
    assert nia[2] == "Not required"
    assert matrix.filename(today) == f"training-matrix-{today.isoformat()}.csv"
    assert matrix.filename(today, course=fire, team=reception, query="Sam P", show="problems") == \
        f"training-matrix-fire_safety-reception-sam-p-problems-{today.isoformat()}.csv"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_training_matrix.py -q`
Expected: FAIL with `ImportError: cannot import name 'matrix' from 'training.services'`

- [ ] **Step 3: Write the module**

```python
# training/services/matrix.py
"""The training matrix: everyone employed today down the side, courses
across, each cell a training.Row. Built from a handful of queries whatever
the practice's size (the people, their primary positions, the courses and
their titles, the records), never one per person or per cell. Read-only;
the CSV is the same grid as text."""
import csv
import io
from collections import defaultdict
from dataclasses import dataclass, field

from django.db.models import Q
from django.utils.text import slugify

from compliance import validity
from people.models import Position
from people.services import employments
from training.models import Course, TrainingRecord
from training.services import training

SHOW = ("all", "problems", "to_verify")


@dataclass
class Entry:
    employee: object
    cells: dict = field(default_factory=dict)       # course pk -> training.Row


@dataclass
class Matrix:
    courses: list
    rows: list


def _wanted(row, show):
    if show == "to_verify":
        return row.pending is not None
    if show == "problems":
        return row.status in training.PROBLEMS or row.status == "awaiting_verification" or row.pending is not None
    return True


def build(today, course=None, team=None, query="", show="all", window_days=validity.WINDOW_DAYS):
    emps = list(employments.active_on(today).select_related("employee")
                .order_by("employee__last_name", "employee__first_name", "employee_id"))
    query = (query or "").strip().lower()
    if query:
        emps = [m for m in emps if query in m.employee.name.lower()]
    primaries = {p.employment_id: p for p in
                 Position.objects.filter(employment_id__in=[m.pk for m in emps], primary=True, from_date__lte=today)
                 .filter(Q(to_date__isnull=True) | Q(to_date__gte=today))}
    if team is not None:
        emps = [m for m in emps if m.pk in primaries and primaries[m.pk].team_id == team.pk]
    by_pk = {c.pk: c for c in Course.objects.all()}
    everyone, by_title = set(), defaultdict(set)
    for c in Course.objects.filter(active=True).prefetch_related("positions"):
        if c.everyone:
            everyone.add(c.pk)
        for t in c.positions.all():
            by_title[t.pk].add(c.pk)
    records = defaultdict(lambda: defaultdict(list))
    for r in (TrainingRecord.objects.filter(employee_id__in=[m.employee_id for m in emps])
              .select_related("certificate", "session").order_by("-done_on", "-id")):
        records[r.employee_id][r.course_id].append(r)
    rows, shown = [], set()
    for m in emps:
        pos = primaries.get(m.pk)
        required = everyone | (by_title.get(pos.title_id, set()) if pos is not None else set())
        wanted = {course.pk} if course is not None else required | set(records[m.employee_id])
        cells = {}
        for pk in wanted:
            recs = records[m.employee_id].get(pk, [])
            if course is not None and pk not in required and not recs:
                continue                      # neither needs nor has the filtered course: an empty cell
            row = training.build_row(by_pk[pk], recs, pk in required, today, window_days)
            if _wanted(row, show):
                cells[pk] = row
        if show != "all" and not cells:
            continue
        rows.append(Entry(m.employee, cells))
        shown |= set(cells)
    if course is not None:
        courses = [course]                    # the filtered course is the column, even with nobody to show
    else:
        courses = sorted((by_pk[pk] for pk in shown), key=lambda c: (c.display_order, c.name))
    return Matrix(courses, rows)


def _cell(row):
    if row is None:
        return ""
    if row.expires_on is not None and row.latest is not None:
        return f"{row.label}, {row.expires_on:%d %b %Y}"
    if row.latest is not None:
        return f"{row.label}, done {row.latest.done_on:%d %b %Y}"
    return row.label


def to_csv(m):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Person", *[c.name for c in m.courses]])
    for entry in m.rows:
        w.writerow([entry.employee.name, *[_cell(entry.cells.get(c.pk)) for c in m.courses]])
    return out.getvalue()


def filename(today, course=None, team=None, query="", show="all"):
    parts = ["training-matrix"]
    if course is not None:
        parts.append(course.code)
    if team is not None:
        parts.append(slugify(team.name))
    if (query or "").strip():
        parts.append(slugify(query))
    if show != "all":
        parts.append(show)
    parts.append(today.isoformat())
    return "-".join(parts) + ".csv"
```

- [ ] **Step 4: Run the tests and the lint**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_training_matrix.py -q && .venv/bin/ruff check .`
Expected: all pass. If the query-count test fails by one or two, count the queries (`django_assert_max_num_queries` prints them) and remove the extra: the budget is the point of the test, not the number 8; raise it only for a query that cannot be folded in.

- [ ] **Step 5: Commit**

```bash
cd /home/user/practice-hr && git add training/services/matrix.py tests/test_training_matrix.py && git commit -q -F - <<'MSG'
Training: the matrix, its filters and its CSV

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01PkKQLdYCQnRZiVssdedFig
MSG
```

---

### Task 8: My record › Training, recording your own, and the starter's Getting started

**Files:**
- Create: `training/forms.py`, `training/views.py` (the first view), `templates/people/_training.html`
- Modify: `training/urls.py`, `people/views.py:51-95` (`me`), `templates/people/me.html`, `onboarding/views.py:57-66` (`getting_started`), `templates/onboarding/getting_started.html`, `onboarding/middleware.py:16` (`ALLOWED_PREFIXES`)
- Test: `tests/test_training_pages.py` (first half)

**Interfaces:**
- Consumes: `training.state`, `training.self_record` (Task 4), `access.is_pre_start`.
- Produces: `training:self_record` at `POST /training/record/` (fields `course`, `done_on`, `file`), redirecting to My record, or Getting started for a pre-start starter. `training.forms.SelfRecordForm`, `training.forms.DateInput`. The My record and Getting started contexts gain `training` (rows) and `training_form`. `/training/` is allowed through the pre-start gate.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_training_pages.py
"""The site's training pages, by role. Task 8: My record and Getting
started; Task 9 adds My team, the person page and sessions below."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone

from documents.models import File
from people.services import titles
from tests.factories import make_employee, make_employment, make_position
from training.models import Course, TrainingRecord
from training.services import training

pytestmark = pytest.mark.django_db
User = get_user_model()
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def fire():
    c = Course.objects.get(code="fire_safety")
    c.positions.add(titles.get_or_create("Receptionist"))
    return c


@pytest.fixture
def bls():
    c = Course.objects.get(code="basic_life_support")
    c.everyone = True
    c.save()
    return c


def _pdf(name="cert.pdf"):
    return SimpleUploadedFile(name, PDF)


def _receptionist(user=None, manager=None, days=400):
    e = make_employee(user=user)
    emp = make_employment(e, start=timezone.localdate() - timedelta(days=days))
    make_position(emp, title="Receptionist", manager=manager)
    return e


def _manager():
    m = make_employee(first="Mo", last="Khan", user=User.objects.create_user(email="mo@example.com", password="pw"))
    make_employment(m, start=timezone.localdate() - timedelta(days=800))
    c = Client()
    c.force_login(m.user)
    return m, c


# ---- Task 8: My record and Getting started -----------------------------------

def test_my_record_lists_training_with_the_record_form_and_no_note(fire, bls, hr_admin, employee_user, employee_client):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    r = training.record(hr_admin, e, fire, today - timedelta(days=5), upload=_pdf(), note="HR ONLY NOTE")
    body = employee_client.get("/people/me/").content.decode()
    assert "<h2>Training</h2>" in body and "Fire safety" in body and "Basic life support" in body
    assert "Current" in body and "Missing" in body and "HR ONLY NOTE" not in body
    assert f'href="/documents/file/{r.certificate_id}/"' in body
    assert 'action="/training/record/"' in body and 'name="course"' in body and 'name="file"' in body


def test_recording_your_own_online_course_needs_the_file_then_shows_awaiting(fire, employee_user, employee_client):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    r = employee_client.post("/training/record/", {"course": fire.pk, "done_on": today.isoformat()})
    assert r.status_code == 302 and r["Location"] == "/people/me/"
    body = employee_client.get("/people/me/").content.decode()
    assert "Upload your certificate for this course." in body and not TrainingRecord.objects.exists()
    r = employee_client.post("/training/record/", {"course": fire.pk, "done_on": today.isoformat(), "file": _pdf()})
    assert r.status_code == 302
    body = employee_client.get("/people/me/").content.decode()
    assert "Awaiting verification" in body and "HR or your manager will verify" in body
    rec = TrainingRecord.objects.get()
    assert rec.pending and rec.employee == e and rec.certificate.employee == e


def test_a_rejected_record_shows_its_note_until_the_next_upload(fire, hr_admin, employee_user, employee_client):
    today = timezone.localdate()
    _receptionist(user=employee_user)
    rec = training.self_record(employee_user, fire, today, upload=_pdf())
    training.reject(hr_admin, rec, "Wrong course entirely.")
    body = employee_client.get("/people/me/").content.decode()
    assert "Wrong course entirely." in body and "Missing" in body
    training.self_record(employee_user, fire, today, upload=_pdf())
    body = employee_client.get("/people/me/").content.decode()
    assert "Wrong course entirely." not in body and "Awaiting verification" in body


def test_the_record_post_is_post_only_login_only_and_validated(fire, employee_user, employee_client, client):
    _receptionist(user=employee_user)
    assert employee_client.get("/training/record/").status_code == 405
    r = client.post("/training/record/", {"course": fire.pk, "done_on": "2030-01-01"})
    assert r.status_code == 302 and "/login/" in r["Location"]
    r = employee_client.post("/training/record/", {"course": fire.pk, "done_on": "not a date", "file": _pdf()})
    assert r.status_code == 302
    body = employee_client.get("/people/me/").content.decode()
    assert "Enter a valid date." in body and not TrainingRecord.objects.exists() and not File.objects.exists()


def test_a_starter_records_training_from_getting_started_before_day_one(fire, employee_user, employee_client):
    today = timezone.localdate()
    e = make_employee(user=employee_user)
    make_position(make_employment(e, start=today + timedelta(days=7)), title="Receptionist")
    body = employee_client.get("/onboarding/").content.decode()
    assert "<h2>Training</h2>" in body and 'action="/training/record/"' in body
    assert "Missing" not in body                         # nothing is required before the start date
    r = employee_client.post("/training/record/", {"course": fire.pk, "done_on": today.isoformat(), "file": _pdf()})
    assert r.status_code == 302 and r["Location"] == "/onboarding/"
    assert TrainingRecord.objects.get().pending
    body = employee_client.get("/onboarding/").content.decode()
    assert "Awaiting verification" in body


def test_a_login_with_no_employee_record_is_told_so(fire, employee_client):
    r = employee_client.post("/training/record/", {"course": fire.pk, "done_on": timezone.localdate().isoformat(),
                                                   "file": _pdf()})
    assert r.status_code == 302
    body = employee_client.get("/people/me/").content.decode()
    assert "no employee record linked to your login" in body
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_training_pages.py -q`
Expected: FAIL (My record has no Training card; `/training/record/` is 404).

- [ ] **Step 3: The form, the view and the route**

```python
# training/forms.py
"""The site's training forms. None saves anything: the views pass cleaned
data to the services, which apply the rules (a certificate for an online
course, who may record for whom) and refuse on the page."""
from django import forms

from people.models import Employee
from training.models import Course

ACCEPT = ".pdf,.jpg,.jpeg,.png,.docx"


class DateInput(forms.DateInput):
    input_type = "date"


def _courses():
    return Course.objects.filter(active=True)


class SelfRecordForm(forms.Form):
    course = forms.ModelChoiceField(queryset=_courses(), label="Course")
    done_on = forms.DateField(label="Date done", widget=DateInput)
    file = forms.FileField(label="Certificate", required=False, widget=forms.ClearableFileInput(attrs={"accept": ACCEPT}),
                           help_text="PDF, JPEG, PNG or DOCX. Needed for an online course.")


class RecordForm(forms.Form):
    """A manager's or HR's record for someone else (Task 9)."""
    course = forms.ModelChoiceField(queryset=_courses(), label="Course")
    done_on = forms.DateField(label="Date done", widget=DateInput)
    file = forms.FileField(label="Certificate", required=False, widget=forms.ClearableFileInput(attrs={"accept": ACCEPT}),
                           help_text="PDF, JPEG, PNG or DOCX, if there is one.")
    note = forms.CharField(label="Note", required=False, widget=forms.Textarea(attrs={"rows": 2}),
                           help_text="Seen by HR and managers, never the person.")


class RejectForm(forms.Form):
    note = forms.CharField(label="Why it is turned down", max_length=200, widget=forms.Textarea(attrs={"rows": 3}),
                           help_text="The person is emailed this, with where to record it again.")


class SessionForm(forms.Form):
    course = forms.ModelChoiceField(queryset=_courses(), label="Course")
    held_on = forms.DateField(label="Date held", widget=DateInput)
    trainer = forms.CharField(label="Trainer", required=False, max_length=120,
                              help_text="An outside provider or a colleague's name.")
    note = forms.CharField(label="Note", required=False, widget=forms.Textarea(attrs={"rows": 2}))
    file = forms.FileField(label="Attendance sheet", required=False,
                           widget=forms.ClearableFileInput(attrs={"accept": ACCEPT}),
                           help_text="PDF, JPEG, PNG or DOCX, if there is one. Shared by everyone's record.")
    attendees = forms.ModelMultipleChoiceField(queryset=Employee.objects.none(), label="Who attended",
                                               widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, attendees_queryset, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["attendees"].queryset = attendees_queryset
```

```python
# training/views.py
"""The site's training pages. Every write is a service's (training,
sessions); a GET writes nothing. Recording your own (self_record) returns
to My record, or to Getting started before your first day."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from people.services import access
from training.forms import SelfRecordForm
from training.services import training


def _own_page(request):
    if access.is_pre_start(request.user, timezone.localdate()):
        return redirect("onboarding:getting_started")
    return redirect("people:me")


def _form_errors(form):
    return " ".join(e for errors in form.errors.values() for e in errors)


@login_required
@require_POST
def self_record(request):
    form = SelfRecordForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, _form_errors(form))
        return _own_page(request)
    d = form.cleaned_data
    try:
        training.self_record(request.user, d["course"], d["done_on"], upload=d.get("file") or None)
    except PermissionDenied:
        messages.error(request, "There is no employee record linked to your login yet. Ask the practice manager.")
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    else:
        messages.success(request, f"Recorded. HR or your manager will verify your {d['course']} training.")
    return _own_page(request)
```

```python
# training/urls.py
from django.urls import path

from . import views

app_name = "training"
urlpatterns = [
    path("record/", views.self_record, name="self_record"),
]
```

In `onboarding/middleware.py`, add `"/training/"` to `ALLOWED_PREFIXES` (after `"/checks/"`), and extend the module docstring's list: "the evidence HR has asked them for, their own training".

- [ ] **Step 4: The card and the two pages' context**

```
{# templates/people/_training.html #}
{% comment %}My record's Training card (and Getting started's): one row per
training.state row with its status, dates and certificate link (the
audited download), then the form to record your own completion
(training:self_record). HR's note is never shown here. Expects training
(rows) and training_form.{% endcomment %}
<section class="card">
  <h2>Training</h2>
  {% if training %}
  <div class="table-scroll">
  <table class="list">
    <thead><tr><th scope="col">Course</th><th scope="col">Status</th><th scope="col">Done</th><th scope="col">Expires</th><th scope="col">Certificate</th></tr></thead>
    <tbody>
    {% for row in training %}
      <tr>
        <th scope="row">{{ row.course.name }}</th>
        <td><span class="badge {% if row.status == 'current' %}badge-ok{% elif row.status == 'due_soon' or row.status == 'lapsed' or row.status == 'missing' %}badge-warning{% else %}badge-muted{% endif %}">{{ row.label }}</span></td>
        {% if row.pending %}
        <td colspan="3">Uploaded {{ row.pending.recorded_at|date:"j M Y" }}; waiting for HR or your manager to verify it.</td>
        {% else %}
        <td>{{ row.latest.done_on|date:"j M Y"|default:"" }}</td>
        <td>{{ row.expires_on|date:"j M Y"|default:"" }}</td>
        <td>{% if row.latest.certificate_id %}<a href="{% url 'documents:download' row.latest.certificate_id %}" download>Download</a>{% endif %}</td>
        {% endif %}
      </tr>
      {% if row.rejected and not row.pending %}
      <tr><td></td><td colspan="4" class="field-error">Your upload of {{ row.rejected.done_on|date:"j M Y" }} was turned down: {{ row.rejected.rejected_note }} Record it again below.</td></tr>
      {% endif %}
    {% endfor %}
    </tbody>
  </table>
  </div>
  {% else %}
  <p class="empty">No training is needed for your position yet. Anything you have already done can be recorded below.</p>
  {% endif %}
  <h3>Record training you have done</h3>
  <form method="post" action="{% url 'training:self_record' %}" enctype="multipart/form-data">{% csrf_token %}
    {{ training_form.as_div }}
    <div class="form-actions"><button type="submit" class="btn btn-primary">Record</button></div>
  </form>
</section>
```

In `people/views.py`:
- add `from training.forms import SelfRecordForm` and `from training.services import training` to the imports;
- in `me`, add to `ctx`: `"training": training.state(employee, today), "training_form": SelfRecordForm(initial={"done_on": today}),`.

In `templates/people/me.html`, add `{% include "people/_training.html" %}` after the `_checks.html` include.

In `onboarding/views.py` `getting_started`: add the same two imports and, inside `if me is not None:`, extend the `ctx.update` with `"training": training.state(me, today), "training_form": SelfRecordForm(initial={"done_on": today}),`. In `templates/onboarding/getting_started.html`, after the `{% if asked %}…{% endif %}` checks section, add `{% include "people/_training.html" %}`.

- [ ] **Step 5: Run the tests and the lint**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_training_pages.py tests/test_people_views.py tests/test_onboarding_pages.py tests/test_private_pages.py -q && .venv/bin/ruff check .`
Expected: all pass. If `test_private_pages.py` enumerates every route and expects a redirect for an anonymous GET, `/training/record/` answers 405 to GET before `login_required` runs (the decorator order is `login_required` outside `require_POST`, so an anonymous GET redirects first: check the order matches the checks upload view).

- [ ] **Step 6: Commit**

```bash
cd /home/user/practice-hr && git add training/forms.py training/views.py training/urls.py templates/people/_training.html people/views.py templates/people/me.html onboarding/views.py templates/onboarding/getting_started.html onboarding/middleware.py tests/test_training_pages.py && git commit -q -F - <<'MSG'
Training: the My record card, recording your own completion, and the starter's view of it

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01PkKQLdYCQnRZiVssdedFig
MSG
```

---

### Task 9: My team › Training, the person page, verifying and rejecting, and the session form

**Files:**
- Create: `templates/people/_team_training.html`, `templates/training/person.html`, `templates/training/reject.html`, `templates/training/session.html`
- Modify: `training/views.py`, `training/urls.py`, `training/services/due.py` (`_person_url` → `reverse`), `people/views.py:98-117` (`team`), `templates/people/team.html`
- Test: `tests/test_training_pages.py` (second half)

**Interfaces:**
- Consumes: `training.state` / `summary` / `record` / `verify` / `reject`, `sessions.record_session`, `access.can_view_training` / `may_record_training_for` / `may_verify` / `direct_reports` / `can_view_restricted`, the forms from Task 8.
- Produces routes: `training:person` `GET /training/<employee pk>/`; `training:record` `POST /training/<employee pk>/record/`; `training:verify` `POST /training/records/<record pk>/verify/`; `training:reject` `GET|POST /training/records/<record pk>/reject/`; `training:session` `GET|POST /training/session/`. My team's context rows gain `training` (summary) and the page a **Record a session** link.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_training_pages.py`)

```python
# ---- Task 9: My team, the person page, verify, reject, sessions --------------

def test_my_team_shows_counts_and_links_to_the_person_page_with_the_note(fire, bls, hr_admin, employee_user):
    today = timezone.localdate()
    m, mc = _manager()
    e = _receptionist(user=employee_user, manager=m)
    r = training.record(hr_admin, e, fire, today - timedelta(days=5), upload=_pdf(), note="Seen the cert")
    body = mc.get("/people/team/").content.decode()
    assert "1 current" in body and "1 missing" in body and f'href="/training/{e.pk}/"' in body
    assert 'href="/training/session/"' in body
    body = mc.get(f"/training/{e.pk}/").content.decode()
    assert "Fire safety" in body and "Seen the cert" in body and f'href="/documents/file/{r.certificate_id}/"' in body
    assert f'action="/training/{e.pk}/record/"' in body
    assert mc.get(f"/documents/file/{r.certificate_id}/").status_code == 200       # the manager opens the certificate


def test_the_person_sees_their_page_without_the_note_or_the_record_form(fire, hr_admin, employee_user, employee_client):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    training.record(hr_admin, e, fire, today - timedelta(days=5), upload=_pdf(), note="Seen the cert")
    body = employee_client.get(f"/training/{e.pk}/").content.decode()
    assert "Fire safety" in body and "Seen the cert" not in body and f'action="/training/{e.pk}/record/"' not in body
    other = _receptionist(user=User.objects.create_user(email="jo@example.com", password="pw"))
    assert employee_client.get(f"/training/{other.pk}/").status_code == 403
    assert employee_client.post(f"/training/{other.pk}/record/", {"course": fire.pk, "done_on": today.isoformat()}).status_code == 403


def test_a_manager_records_for_a_report_and_it_counts_at_once(fire, employee_user):
    today = timezone.localdate()
    m, mc = _manager()
    e = _receptionist(user=employee_user, manager=m)
    r = mc.post(f"/training/{e.pk}/record/", {"course": fire.pk, "done_on": (today - timedelta(days=2)).isoformat(),
                                               "file": _pdf(), "note": "Group session, I was there"})
    assert r.status_code == 302 and r["Location"] == f"/training/{e.pk}/"
    rec = TrainingRecord.objects.get()
    assert rec.counts and rec.verified_by == m.user and rec.note == "Group session, I was there"
    r = mc.post(f"/training/{e.pk}/record/", {"course": fire.pk, "done_on": (today + timedelta(days=1)).isoformat()})
    assert r.status_code == 302 and TrainingRecord.objects.count() == 1
    assert "cannot be after today" in mc.get(f"/training/{e.pk}/").content.decode()


def test_verify_is_a_post_and_reject_confirms_then_emails(fire, employee_user, employee_client, configured):
    from django.core import mail
    today = timezone.localdate()
    m, mc = _manager()
    e = _receptionist(user=employee_user, manager=m)
    first = training.self_record(employee_user, fire, today, upload=_pdf())
    body = mc.get(f"/training/{e.pk}/").content.decode()
    assert f'action="/training/records/{first.pk}/verify/"' in body and f'href="/training/records/{first.pk}/reject/"' in body
    assert mc.get(f"/training/records/{first.pk}/verify/").status_code == 405
    assert employee_client.post(f"/training/records/{first.pk}/verify/").status_code == 403
    r = mc.post(f"/training/records/{first.pk}/verify/")
    assert r.status_code == 302 and TrainingRecord.objects.get(pk=first.pk).counts
    second = training.self_record(employee_user, fire, today, upload=_pdf())
    body = mc.get(f"/training/records/{second.pk}/reject/").content.decode()
    assert 'name="note"' in body and not TrainingRecord.objects.get(pk=second.pk).rejected        # GET writes nothing
    r = mc.post(f"/training/records/{second.pk}/reject/", {"note": ""})
    assert r.status_code == 200 and "required" in r.content.decode().lower()
    r = mc.post(f"/training/records/{second.pk}/reject/", {"note": "Certificate is unreadable."})
    assert r.status_code == 302 and TrainingRecord.objects.get(pk=second.pk).rejected
    assert [msg.to for msg in mail.outbox] == [["sam@example.com"]] and "unreadable" in mail.outbox[0].body
    assert employee_client.get(f"/training/records/{second.pk}/reject/").status_code == 403


def test_the_session_form_lists_only_the_managers_reports_and_records_them(bls, employee_user):
    today = timezone.localdate()
    m, mc = _manager()
    e = _receptionist(user=employee_user, manager=m)
    other = _receptionist(user=User.objects.create_user(email="jo@example.com", password="pw"))
    body = mc.get("/training/session/").content.decode()
    assert f'value="{e.pk}"' in body and f'value="{other.pk}"' not in body
    r = mc.post("/training/session/", {"course": bls.pk, "held_on": today.isoformat(), "trainer": "Resus UK",
                                       "attendees": [e.pk], "file": _pdf("sheet.pdf")})
    assert r.status_code == 302 and r["Location"] == "/people/team/"
    rec = TrainingRecord.objects.get()
    assert rec.counts and rec.session.trainer == "Resus UK" and rec.session.attendance_sheet is not None
    assert mc.get(f"/documents/file/{rec.session.attendance_sheet_id}/").status_code == 200
    r = mc.post("/training/session/", {"course": bls.pk, "held_on": today.isoformat(), "attendees": [other.pk]})
    assert r.status_code == 200 and "valid choice" in r.content.decode()           # not in the manager's list
    # a day the report was not yet theirs: the form offers today's reports, the service checks the day
    r = mc.post("/training/session/", {"course": bls.pk, "held_on": (today - timedelta(days=500)).isoformat(),
                                       "attendees": [e.pk]})
    assert r.status_code == 200 and "report to you on that date" in r.content.decode()
    assert TrainingRecord.objects.count() == 1


def test_hr_records_a_session_for_anyone_and_a_non_manager_cannot_open_the_form(bls, hr_admin, admin_client,
                                                                                 employee_user, employee_client):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    assert employee_client.get("/training/session/").status_code == 403
    body = admin_client.get("/training/session/").content.decode()
    assert f'value="{e.pk}"' in body
    r = admin_client.post("/training/session/", {"course": bls.pk, "held_on": today.isoformat(), "attendees": [e.pk]})
    assert r.status_code == 302 and r["Location"] == "/admin/training/trainingsession/"
    assert TrainingRecord.objects.get().recorded_by == hr_admin


def test_the_digest_link_for_hr_is_the_person_page(fire, hr_admin, employee_user):
    from compliance.models import ReminderSchedule
    from django.urls import reverse

    from training.services import due
    e = _receptionist(user=employee_user)
    [item] = [i for i in due.due_items(timezone.localdate(), ReminderSchedule.get()) if i.recipient == "hr@example.com"]
    assert item.url.endswith(reverse("training:person", args=[e.pk]))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_training_pages.py -q`
Expected: the Task 8 tests pass; the new ones fail with 404s.

- [ ] **Step 3: The views**

Add to `training/views.py` (imports grow to match: `render`, `get_object_or_404`, `reverse`, `require_http_methods`, `require_safe`, `Employee`, `TrainingRecord`, `RecordForm`, `RejectForm`, `SessionForm`, `sessions`, `employments`):

```python
def _person_or_403(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if not access.can_view_training(request.user, employee):
        raise PermissionDenied
    return employee


@login_required
@require_safe
def person(request, pk):
    """One person's training, for HR, the person and their line manager:
    the rows with the note (HR and the manager only), a record form for
    those who may record for them, Verify / Reject on pending rows."""
    employee = _person_or_403(request, pk)
    today = timezone.localdate()
    can_record = access.may_record_training_for(request.user, employee, today)
    me = access.employee_for(request.user)
    return render(request, "training/person.html", {
        "employee": employee, "rows": training.state(employee, today),
        "is_self": me is not None and me.pk == employee.pk,
        "can_record": can_record, "form": RecordForm(initial={"done_on": today}) if can_record else None,
        "back": reverse("admin:people_employee_change", args=[employee.pk])
        if access.can_view_restricted(request.user) else reverse("people:team")})


@login_required
@require_POST
def record(request, pk):
    employee = _person_or_403(request, pk)
    if not access.may_record_training_for(request.user, employee, timezone.localdate()):
        raise PermissionDenied
    form = RecordForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, _form_errors(form))
        return redirect("training:person", employee.pk)
    d = form.cleaned_data
    try:
        training.record(request.user, employee, d["course"], d["done_on"], upload=d.get("file") or None,
                        note=d["note"])
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    else:
        messages.success(request, f"{d['course']} recorded for {employee.name}.")
    return redirect("training:person", employee.pk)


def _record_or_403(request, pk):
    rec = get_object_or_404(TrainingRecord.objects.select_related("employee", "course"), pk=pk)
    if not access.may_verify(request.user, rec):
        raise PermissionDenied
    return rec


@login_required
@require_POST
def verify(request, pk):
    rec = _record_or_403(request, pk)
    try:
        training.verify(request.user, rec)
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    else:
        messages.success(request, f"{rec.course} verified for {rec.employee.name}.")
    return redirect("training:person", rec.employee_id)


@login_required
@require_http_methods(["GET", "POST"])
def reject(request, pk):
    """GET asks why; only the POST rejects (and emails the person)."""
    rec = _record_or_403(request, pk)
    form = RejectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            training.reject(request.user, rec, form.cleaned_data["note"])
        except ValidationError as e:
            form.add_error(None, e.messages)
        else:
            messages.success(request, f"{rec.course} turned down for {rec.employee.name}; they have been told why.")
            return redirect("training:person", rec.employee_id)
    return render(request, "training/reject.html", {"record": rec, "form": form})


@login_required
@require_http_methods(["GET", "POST"])
def session(request):
    """Record a face-to-face group: HR for anyone employed today, a manager
    for their reports today (sessions.record_session checks the day held)."""
    today = timezone.localdate()
    hr = access.can_view_restricted(request.user)
    if hr:
        pks = employments.active_on(today).values("employee_id")
    else:
        me = access.employee_for(request.user)
        reports = access.direct_reports(me, today) if me is not None else []
        if not reports:
            raise PermissionDenied
        pks = [emp.employee_id for emp in reports]
    candidates = Employee.objects.filter(pk__in=pks).order_by("last_name", "first_name")
    form = SessionForm(request.POST or None, request.FILES or None, attendees_queryset=candidates,
                       initial={"held_on": today})
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            s = sessions.record_session(request.user, d["course"], d["held_on"], list(d["attendees"]),
                                        trainer=d["trainer"], note=d["note"], upload=d.get("file") or None)
        except PermissionDenied:
            form.add_error("attendees", "Only people who report to you on that date.")
        except ValidationError as e:
            form.add_error(None, e.messages)
        else:
            n = s.records.count()
            messages.success(request, f"{s.course} on {s.held_on:%-d %b %Y} recorded for {n} "
                                      f"{'person' if n == 1 else 'people'}.")
            return redirect("admin:training_trainingsession_changelist" if hr else "people:team")
    return render(request, "training/session.html", {"form": form, "hr": hr})
```

```python
# training/urls.py
from django.urls import path

from . import views

app_name = "training"
urlpatterns = [
    path("record/", views.self_record, name="self_record"),
    path("session/", views.session, name="session"),
    path("records/<int:pk>/verify/", views.verify, name="verify"),
    path("records/<int:pk>/reject/", views.reject, name="reject"),
    path("<int:pk>/", views.person, name="person"),
    path("<int:pk>/record/", views.record, name="record"),
]
```

In `training/services/due.py`, replace `_person_url`'s body with `return link(reverse("training:person", args=[e.pk]))` and drop the comment.

- [ ] **Step 4: The templates and My team**

```
{# templates/people/_team_training.html #}
{% comment %}My team's per-report training summary (training.summary) as a
link to their training page, where the manager sees the detail and
records. Expects s and employee.{% endcomment %}
<a href="{% url 'training:person' employee.pk %}">{{ s.current }} current, {{ s.due_soon }} due soon, {{ s.lapsed }} lapsed, {{ s.missing }} missing{% if s.awaiting_verification %}, {{ s.awaiting_verification }} to verify{% endif %}</a>{% if s.next_expiry %}; next expiry {{ s.next_expiry|date:"d M Y" }}{% endif %}
```

In `templates/people/team.html`: add a `<th>Training</th>` after `<th>Checks</th>`, a matching `<td>{% include "people/_team_training.html" with s=r.training employee=r.employee %}</td>`, change the empty row's `colspan` to 6, and above the table replace `<h1>My team</h1>` with:
```
<div class="page-head"><h1>My team</h1>{% if rows %}<a href="{% url 'training:session' %}" class="btn btn-quiet">Record a training session</a>{% endif %}</div>
```
In `people/views.py` `team`, add `"training": training.summary(emp.employee, today),` to each row dict.

```
{# templates/training/person.html #}
{% extends "base.html" %}
{% comment %}training:person — one person's training (training.state) for
HR, the person and their line manager. The note column, the record form
and Verify / Reject show only to those who may record for them
(access.may_record_training_for); the person sees their rows and files.
Every POST here is a service's; this page writes nothing.{% endcomment %}
{% block title %}{{ employee.name }}: training{% endblock %}
{% block content %}
<div class="stack">
<div class="page-head"><h1>{{ employee.name }}: training</h1><a href="{{ back }}">Back</a></div>
<section class="card">
  {% if rows %}
  <div class="table-scroll">
  <table class="list">
    <thead><tr><th scope="col">Course</th><th scope="col">Status</th><th scope="col">Done</th><th scope="col">Expires</th><th scope="col">Certificate</th>{% if can_record %}<th scope="col">Note</th><th scope="col"><span class="visually-hidden">Actions</span></th>{% endif %}</tr></thead>
    <tbody>
    {% for row in rows %}
      <tr>
        <th scope="row">{{ row.course.name }}</th>
        <td><span class="badge {% if row.status == 'current' %}badge-ok{% elif row.status == 'due_soon' or row.status == 'lapsed' or row.status == 'missing' %}badge-warning{% else %}badge-muted{% endif %}">{{ row.label }}</span></td>
        <td>{{ row.latest.done_on|date:"j M Y"|default:"" }}</td>
        <td>{{ row.expires_on|date:"j M Y"|default:"" }}</td>
        <td>{% if row.latest.certificate_id %}<a href="{% url 'documents:download' row.latest.certificate_id %}" download>Download</a>{% endif %}</td>
        {% if can_record %}<td>{{ row.latest.note|default:"" }}</td><td></td>{% endif %}
      </tr>
      {% if row.pending %}
      <tr class="pending">
        <td></td><td colspan="{% if can_record %}2{% else %}4{% endif %}">Uploaded {{ row.pending.recorded_at|date:"j M Y" }} (done {{ row.pending.done_on|date:"j M Y" }}){% if row.pending.certificate_id %}: <a href="{% url 'documents:download' row.pending.certificate_id %}" download>certificate</a>{% endif %}</td>
        {% if can_record %}
        <td colspan="3" class="row-actions">
          <form method="post" action="{% url 'training:verify' row.pending.pk %}" class="inline">{% csrf_token %}<button type="submit" class="btn btn-primary">Verify</button></form>
          <a href="{% url 'training:reject' row.pending.pk %}" class="btn btn-quiet">Reject</a>
        </td>
        {% endif %}
      </tr>
      {% endif %}
    {% endfor %}
    </tbody>
  </table>
  </div>
  {% else %}
  <p class="empty">No training is needed for this position, and none is recorded.</p>
  {% endif %}
</section>
{% if can_record %}
<section class="card">
  <h2>Record training for {{ employee.name }}</h2>
  <form method="post" action="{% url 'training:record' employee.pk %}" enctype="multipart/form-data">{% csrf_token %}
    {{ form.as_div }}
    <div class="form-actions"><button type="submit" class="btn btn-primary">Record</button></div>
  </form>
</section>
{% endif %}
</div>
{% endblock %}
```

```
{# templates/training/reject.html #}
{% extends "base.html" %}
{% comment %}training:reject, GET — ask why before the record is turned
down; only the POST writes (training.reject, which emails the person).{% endcomment %}
{% block title %}Turn down {{ record.employee.name }}'s {{ record.course }} record{% endblock %}
{% block content %}
<div class="stack">
<div class="page-head"><h1>Turn down {{ record.employee.name }}'s {{ record.course }} record?</h1></div>
<section class="card">
  <p>Recorded as done on {{ record.done_on|date:"j M Y" }}, uploaded {{ record.recorded_at|date:"j M Y" }}.{% if record.certificate_id %} <a href="{% url 'documents:download' record.certificate_id %}" download>Open the certificate</a>.{% endif %}</p>
  <form method="post">{% csrf_token %}
    {{ form.as_div }}
    <div class="form-actions">
      <button type="submit" class="btn btn-primary">Turn it down</button>
      <a href="{% url 'training:person' record.employee_id %}" class="btn btn-quiet">Back</a>
    </div>
  </form>
</section>
</div>
{% endblock %}
```

```
{# templates/training/session.html #}
{% extends "base.html" %}
{% comment %}training:session — record a face-to-face group once
(sessions.record_session): HR for anyone employed today, a manager for
their reports. GET shows the form; POST records.{% endcomment %}
{% block title %}Record a training session{% endblock %}
{% block content %}
<div class="stack">
<div class="page-head"><h1>Record a training session</h1></div>
<section class="card">
  <p class="muted">One record for everyone who attended, counted from the date held.{% if not hr %} Only people who report to you on that date can be ticked.{% endif %}</p>
  <form method="post" enctype="multipart/form-data">{% csrf_token %}
    {{ form.as_div }}
    <div class="form-actions">
      <button type="submit" class="btn btn-primary">Record the session</button>
      <a href="{% if hr %}{% url 'admin:training_trainingsession_changelist' %}{% else %}{% url 'people:team' %}{% endif %}" class="btn btn-quiet">Back</a>
    </div>
  </form>
</section>
</div>
{% endblock %}
```

- [ ] **Step 5: Run the tests and the lint**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_training_pages.py tests/test_training_due.py tests/test_people_views.py tests/test_navigation.py tests/test_private_pages.py -q && .venv/bin/ruff check .`
Expected: all pass. `tests/test_navigation.py::test_the_mobile_tab_bar_holds_at_most_five_items` is unaffected (no new nav item on the site).

- [ ] **Step 6: Commit**

```bash
cd /home/user/practice-hr && git add training people/views.py templates/people/team.html templates/people/_team_training.html templates/training tests/test_training_pages.py && git commit -q -F - <<'MSG'
Training: the team card, a report's training page, verify and reject, and the session form

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01PkKQLdYCQnRZiVssdedFig
MSG
```

---

### Task 10: The admin: records, sessions, the Compliance tab, the matrix page, the dashboard

**Files:**
- Create: `training/admin_forms.py`, `templates/training/admin/verify.html`, `templates/training/admin/reject.html`, `templates/training/matrix.html`
- Modify: `training/admin.py` (replace the two placeholders), `training/forms.py` (`MatrixFilterForm`), `training/views.py` (`matrix`, `matrix_csv`), `training/urls.py`, `people/admin.py:151-230` (`compliance_summary`), `hr/admin_site.py` (the matrix nav item), `absence/admin_dashboard.py:17-24,69-83` (`COMPLIANCE`, `compliance_people`, `dashboard`), `templates/admin/index.html` (the card's sentence)
- Test: `tests/test_training_admin.py`

**Interfaces:**
- Consumes: everything above; `matrix.build` / `to_csv` / `filename` / `SHOW` (Task 7).
- Produces: `/admin/training/trainingrecord/` (add = `training.record`; change = `training.set_expiry` on a verified record; detail actions `verify/` and `reject/`), `/admin/training/trainingsession/` (add = `sessions.record_session`), `training:matrix` `GET /training/matrix/` and `training:matrix_csv` `GET /training/matrix.csv` (HR only; query parameters `course`, `team`, `q`, `show`), a Training table on the Compliance tab, nav item **Training matrix**, dashboard numbers **Training lapsed or missing** and **Training to verify** linking to the matrix.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_training_admin.py
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from people.models import AuditEntry
from people.services import titles
from tests.factories import make_employee, make_employment, make_position, make_team
from training.models import Course, TrainingRecord, TrainingSession
from training.services import training

pytestmark = pytest.mark.django_db
User = get_user_model()
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def fire():
    c = Course.objects.get(code="fire_safety")
    c.positions.add(titles.get_or_create("Receptionist"))
    return c


@pytest.fixture
def bls():
    c = Course.objects.get(code="basic_life_support")
    c.everyone = True
    c.save()
    return c


def _pdf(name="cert.pdf"):
    return SimpleUploadedFile(name, PDF)


def _receptionist(user=None, team=None, first="Sam", last="Patel"):
    e = make_employee(first=first, last=last, user=user)
    emp = make_employment(e, start=timezone.localdate() - timedelta(days=400))
    make_position(emp, title="Receptionist", team=team)
    return e


def test_the_add_page_records_through_the_service_and_stores_the_certificate(fire, hr_admin, admin_client):
    today = timezone.localdate()
    e = _receptionist()
    r = admin_client.post("/admin/training/trainingrecord/add/", {
        "employee": e.pk, "course": fire.pk, "done_on": (today - timedelta(days=3)).isoformat(), "expires_on": "",
        "note": "Seen it", "upload": _pdf()})
    assert r.status_code == 302
    rec = TrainingRecord.objects.get()
    assert rec.counts and rec.recorded_by == hr_admin and rec.certificate is not None and rec.note == "Seen it"
    assert rec.expires_on == training.validity.expires_from(today - timedelta(days=3), 12)
    r = admin_client.post("/admin/training/trainingrecord/add/", {
        "employee": e.pk, "course": fire.pk, "done_on": (today + timedelta(days=1)).isoformat(), "expires_on": "",
        "note": ""})
    assert r.status_code == 200 and "cannot be after today" in r.content.decode()
    assert TrainingRecord.objects.count() == 1


def test_the_change_page_is_read_only_but_for_the_expiry_of_a_verified_record(fire, hr_admin, admin_client, employee_user):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    rec = training.record(hr_admin, e, fire, today - timedelta(days=3), upload=_pdf())
    body = admin_client.get(f"/admin/training/trainingrecord/{rec.pk}/change/").content.decode()
    assert 'name="expires_on"' in body and 'name="done_on"' not in body and 'name="note"' not in body
    assert f'href="/documents/file/{rec.certificate_id}/"' in body
    r = admin_client.post(f"/admin/training/trainingrecord/{rec.pk}/change/",
                          {"expires_on": (today + timedelta(days=5)).isoformat()})
    assert r.status_code == 302
    rec.refresh_from_db()
    assert rec.expires_on == today + timedelta(days=5)
    assert AuditEntry.objects.filter(model="training.trainingrecord", object_id=rec.pk, field="expires_on").exists()
    pending = training.self_record(employee_user, fire, today, upload=_pdf())
    body = admin_client.get(f"/admin/training/trainingrecord/{pending.pk}/change/").content.decode()
    assert 'name="expires_on"' not in body and "Awaiting verification" in body
    assert admin_client.get(f"/admin/training/trainingrecord/{rec.pk}/delete/").status_code == 403


def test_verify_and_reject_confirm_on_get_and_act_on_post(fire, hr_admin, admin_client, employee_user, configured):
    from django.core import mail
    today = timezone.localdate()
    _receptionist(user=employee_user)
    first = training.self_record(employee_user, fire, today, upload=_pdf())
    body = admin_client.get(f"/admin/training/trainingrecord/{first.pk}/change/").content.decode()
    assert f"/admin/training/trainingrecord/{first.pk}/verify/" in body
    assert admin_client.get(f"/admin/training/trainingrecord/{first.pk}/verify/").status_code == 200
    assert TrainingRecord.objects.get(pk=first.pk).pending                          # GET wrote nothing
    r = admin_client.post(f"/admin/training/trainingrecord/{first.pk}/verify/")
    assert r.status_code == 302 and TrainingRecord.objects.get(pk=first.pk).counts
    assert admin_client.get(f"/admin/training/trainingrecord/{first.pk}/verify/").status_code == 403   # nothing to verify
    second = training.self_record(employee_user, fire, today, upload=_pdf())
    body = admin_client.get(f"/admin/training/trainingrecord/{second.pk}/reject/").content.decode()
    assert 'name="note"' in body
    r = admin_client.post(f"/admin/training/trainingrecord/{second.pk}/reject/", {"note": "Unreadable scan."})
    assert r.status_code == 302 and TrainingRecord.objects.get(pk=second.pk).rejected
    assert [m.to for m in mail.outbox] == [["sam@example.com"]]


def test_the_status_filter_and_the_list(fire, hr_admin, admin_client, employee_user):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    training.record(hr_admin, e, fire, today - timedelta(days=3), upload=_pdf())
    p = training.self_record(employee_user, fire, today, upload=_pdf())
    body = admin_client.get("/admin/training/trainingrecord/?status=pending").content.decode()
    assert f'href="/admin/training/trainingrecord/{p.pk}/change/"' in body and body.count("Fire safety") >= 1
    assert "Awaiting verification" in body
    body = admin_client.get("/admin/training/trainingrecord/?status=verified").content.decode()
    assert f'href="/admin/training/trainingrecord/{p.pk}/change/"' not in body


def test_the_session_add_page_records_everyone_ticked(bls, hr_admin, admin_client):
    today = timezone.localdate()
    a, b = _receptionist(), _receptionist(first="Ann", last="Brown")
    r = admin_client.post("/admin/training/trainingsession/add/", {
        "course": bls.pk, "held_on": today.isoformat(), "trainer": "Resus UK", "note": "",
        "attendees": [a.pk, b.pk], "upload": _pdf("sheet.pdf")})
    assert r.status_code == 302
    s = TrainingSession.objects.get()
    assert s.records.count() == 2 and s.attendance_sheet is not None
    body = admin_client.get(f"/admin/training/trainingsession/{s.pk}/change/").content.decode()
    assert "Ann Brown" in body and "Sam Patel" in body and f'href="/documents/file/{s.attendance_sheet_id}/"' in body
    assert admin_client.get(f"/admin/training/trainingsession/{s.pk}/delete/").status_code == 403


def test_the_compliance_tab_lists_training_with_links(fire, bls, hr_admin, admin_client, employee_user):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    rec = training.record(hr_admin, e, fire, today - timedelta(days=3), upload=_pdf())
    p = training.self_record(employee_user, bls, today)
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert ">Training</h3>" in body
    assert f'href="/admin/training/trainingrecord/{rec.pk}/change/"' in body
    assert f'href="/admin/training/trainingrecord/{p.pk}/change/"' in body and "Verify or reject" in body
    fire.positions.clear()
    bls.everyone = False
    bls.save()
    other = _receptionist(first="Jo", last="Bloggs")
    body = admin_client.get(f"/admin/people/employee/{other.pk}/change/").content.decode()
    assert "needs no training" in body


def test_the_matrix_page_filters_escapes_and_downloads(fire, bls, hr_admin, admin_client, employee_client, employee_user):
    today = timezone.localdate()
    reception, nursing = make_team(name="Reception"), make_team(name="Nursing")
    sam = _receptionist(user=employee_user, team=reception)
    nia = make_employee(first="Nia", last="Evans")
    make_position(make_employment(nia, start=today - timedelta(days=400)), title="Practice Nurse", team=nursing)
    training.record(hr_admin, sam, fire, today - timedelta(days=3), upload=_pdf(), note="HR ONLY NOTE")
    assert employee_client.get("/training/matrix/").status_code == 403
    assert employee_client.get("/training/matrix.csv").status_code == 403
    body = admin_client.get("/training/matrix/").content.decode()
    assert "Sam Patel" in body and "Nia Evans" in body and "Fire safety" in body and "HR ONLY NOTE" not in body
    assert f'href="/training/{sam.pk}/"' in body
    body = admin_client.get(f"/training/matrix/?team={nursing.pk}").content.decode()
    assert "Nia Evans" in body and "Sam Patel" not in body
    body = admin_client.get("/training/matrix/?q=%3Cb%3Epat%3C%2Fb%3E").content.decode()
    assert "<b>pat</b>" not in body and "&lt;b&gt;pat&lt;/b&gt;" in body
    body = admin_client.get("/training/matrix/?show=problems").content.decode()
    assert "Nia Evans" in body and "Sam Patel" in body            # both are missing Basic life support
    r = admin_client.get(f"/training/matrix.csv?course={fire.pk}&show=problems")
    assert r.status_code == 200 and r["Content-Type"].startswith("text/csv")
    assert r["Content-Disposition"] == f'attachment; filename="training-matrix-fire_safety-problems-{today.isoformat()}.csv"'
    assert r.content.decode().splitlines()[0] == "Person,Fire safety"
    body = admin_client.get("/training/matrix/?course=999").content.decode()
    assert "Sam Patel" in body                                   # an unknown filter value is ignored, not a 500


def test_the_filter_text_is_escaped_on_the_page(hr_admin, admin_client):
    body = admin_client.get("/training/matrix/?q=%22%3E%3Cscript%3Ex%3C%2Fscript%3E").content.decode()
    assert "<script>x</script>" not in body


def test_the_dashboard_counts_training_and_links_to_the_matrix(fire, bls, hr_admin, admin_client, employee_user):
    today = timezone.localdate()
    sam = _receptionist(user=employee_user)
    training.record(hr_admin, sam, fire, today - timedelta(days=400), upload=_pdf())      # lapsed
    training.self_record(employee_user, bls, today)                                      # to verify
    from absence.admin_dashboard import compliance_counts
    counts = compliance_counts(today)
    assert counts["training_problems"] == 1 and counts["training_to_verify"] == 1
    body = admin_client.get("/admin/").content.decode()
    assert "Training lapsed or missing" in body and "Training to verify" in body
    assert 'href="/training/matrix/?show=problems"' in body and 'href="/training/matrix/?show=to_verify"' in body
    body = admin_client.get("/admin/people/employee/?compliance=training_problems").content.decode()
    assert "Sam Patel" in body


def test_the_matrix_is_in_the_compliance_sidebar(admin_client):
    from django.test import RequestFactory

    from hr.admin_site import navigation
    request = RequestFactory().get("/admin/")
    request.user = type("U", (), {"is_active": True, "is_hr_admin": True, "is_superuser": False})()
    group = next(g for g in navigation(request) if g["title"] == "Compliance")
    titles_ = [i["title"] for i in group["items"]]
    assert titles_.index("Training sessions") + 1 == titles_.index("Training matrix")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_training_admin.py -q`
Expected: FAIL throughout (the placeholder admins have no add form or actions; `/training/matrix/` is 404).

- [ ] **Step 3: The admin forms**

```python
# training/admin_forms.py
"""The admin's training forms. Each runs the service's date and course
rules and sniffs an upload, so a refusal shows on the form before anything
is written; the admin then writes through training.record,
training.set_expiry, sessions.record_session, training.verify and
training.reject."""
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from unfold.widgets import (UnfoldAdminFileFieldWidget, UnfoldAdminSelectMultipleWidget, UnfoldAdminSelectWidget,
                            UnfoldAdminTextareaWidget, UnfoldAdminTextInputWidget)

from documents.services import files
from people.models import Employee
from people.services import employments
from training.models import Course, TrainingRecord, TrainingSession
from training.services import training


class DateInput(UnfoldAdminTextInputWidget):
    input_type = "date"


class AdminRecordForm(forms.ModelForm):
    upload = forms.FileField(label="Certificate", required=False, widget=UnfoldAdminFileFieldWidget,
                             help_text="PDF, JPEG, PNG or DOCX, if there is one.")

    class Meta:
        model = TrainingRecord
        fields = ["employee", "course", "done_on", "expires_on", "note"]
        labels = {"done_on": "Done on", "expires_on": "Expires on"}
        help_texts = {"expires_on": "Blank: worked out from the course's validity (none for a one-off course).",
                      "note": "Seen by HR and the line manager, never the person."}

    field_order = ["employee", "course", "done_on", "expires_on", "upload", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["course"].queryset = Course.objects.filter(active=True)
        self.fields["done_on"].required = True

    def clean_upload(self):
        upload = self.cleaned_data.get("upload")
        if upload:
            files.sniff(upload)
        return upload

    def clean(self):
        data = super().clean()
        if data.get("done_on") and not self.errors:
            try:
                training.check_date(data["done_on"], timezone.localdate())
            except ValidationError as e:
                self.add_error("done_on", e)
        return data


class AdminSessionForm(forms.ModelForm):
    upload = forms.FileField(label="Attendance sheet", required=False, widget=UnfoldAdminFileFieldWidget,
                             help_text="PDF, JPEG, PNG or DOCX, if there is one. Shared by everyone's record.")
    attendees = forms.ModelMultipleChoiceField(queryset=Employee.objects.none(), label="Who attended",
                                               widget=UnfoldAdminSelectMultipleWidget,
                                               help_text="Everyone employed today. Hold Ctrl or Cmd to pick several.")

    class Meta:
        model = TrainingSession
        fields = ["course", "held_on", "trainer", "note"]
        labels = {"held_on": "Held on"}
        widgets = {"held_on": DateInput, "course": UnfoldAdminSelectWidget, "trainer": UnfoldAdminTextInputWidget,
                   "note": UnfoldAdminTextareaWidget}

    field_order = ["course", "held_on", "trainer", "attendees", "upload", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields["course"].queryset = Course.objects.filter(active=True)
        self.fields["held_on"].required = True
        self.fields["attendees"].queryset = (Employee.objects.filter(pk__in=employments.active_on(today)
                                                                    .values("employee_id"))
                                             .order_by("last_name", "first_name"))

    def clean_upload(self):
        upload = self.cleaned_data.get("upload")
        if upload:
            files.sniff(upload)
        return upload

    def clean(self):
        data = super().clean()
        if data.get("held_on") and not self.errors:
            try:
                training.check_date(data["held_on"], timezone.localdate(), what="held")
            except ValidationError as e:
                self.add_error("held_on", e)
        return data


class AdminRejectForm(forms.Form):
    note = forms.CharField(label="Why it is turned down", max_length=200, widget=UnfoldAdminTextareaWidget,
                           help_text="The person is emailed this, with where to record it again.")
```

- [ ] **Step 4: The admin**

Replace `training/admin.py` wholesale:

```python
# training/admin.py
"""Unfold admin over training. Courses are set up here (the titles that
need each, or everyone). Records are append-only: the add page is the
record form (training.record); an existing row is shown read-only but for
the expiry of a verified record (training.set_expiry), never deleted, and
a pending one has two actions through the service: Verify and Reject.
Sessions: the add page records a group (sessions.record_session); a row is
read-only. Files download through documents:download (files.open, audited)."""
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from unfold.admin import ModelAdmin
from unfold.decorators import action

from people.services import access
from training.admin_forms import AdminRecordForm, AdminRejectForm, AdminSessionForm
from training.models import Course, TrainingRecord, TrainingSession
from training.services import sessions, training

SHOWN = ("employee", "course", "done_on", "expires_on", "note", "session", "recorded_by", "recorded_at",
         "verified_by", "verified_at", "rejected_at", "rejected_note")
SESSION_SHOWN = ("course", "held_on", "trainer", "note", "recorded_by", "recorded_at")


def _file_link(file):
    if file is None:
        return "-"
    return format_html('<a href="{}">{}</a>', reverse("documents:download", args=[file.pk]), file.original_name)


@admin.register(Course)
class CourseAdmin(ModelAdmin):
    list_display = ("name", "delivery", "validity_months", "everyone", "active")
    list_editable = ("active",)
    list_filter = ("delivery", "everyone", "active")
    filter_horizontal = ("positions",)

    def get_readonly_fields(self, request, obj=None):
        fields = tuple(super().get_readonly_fields(request, obj))
        return fields + ("code",) if obj is not None else fields

    def has_delete_permission(self, request, obj=None):
        return False


class StatusFilter(admin.SimpleListFilter):
    title = "status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return [("pending", "Awaiting verification"), ("verified", "Verified"), ("rejected", "Rejected")]

    def queryset(self, request, queryset):
        if self.value() == "pending":
            return queryset.filter(verified_at__isnull=True, rejected_at__isnull=True)
        if self.value() == "verified":
            return queryset.filter(verified_at__isnull=False, rejected_at__isnull=True)
        if self.value() == "rejected":
            return queryset.filter(rejected_at__isnull=False)
        return queryset


class _Refusable:
    """A service refusal at save is a message and a redirect back, not a 500."""

    def log_addition(self, request, obj, message):
        if getattr(request, "_training_not_saved", False):
            return None
        return super().log_addition(request, obj, message)

    def log_change(self, request, obj, message):
        if getattr(request, "_training_not_saved", False):
            return None
        return super().log_change(request, obj, message)

    def response_add(self, request, obj, post_url_continue=None):
        if getattr(request, "_training_not_saved", False):
            return HttpResponseRedirect(request.path)
        return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        if getattr(request, "_training_not_saved", False):
            return HttpResponseRedirect(request.path)
        return super().response_change(request, obj)

    def _refuse(self, request, error):
        request._training_not_saved = True
        messages.error(request, " ".join(error.messages))

    def _page(self, request, template, title, **ctx):
        return render(request, template, {**self.admin_site.each_context(request), "title": title,
                                          "opts": self.model._meta, **ctx})


@admin.register(TrainingRecord)
class TrainingRecordAdmin(_Refusable, ModelAdmin):
    list_display = ("employee", "course", "done_on", "expires_on", "state")
    list_filter = ("course", StatusFilter)
    search_fields = ("employee__first_name", "employee__last_name", "employee__preferred_name")
    list_select_related = ("employee", "course")
    actions_detail = ["verify_record", "reject_record"]

    @admin.display(description="State")
    def state(self, obj):
        return "Awaiting verification" if obj.pending else "Rejected" if obj.rejected else "Verified"

    @admin.display(description="Certificate")
    def certificate_link(self, obj):
        return _file_link(obj.certificate)

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs["form"] = AdminRecordForm
        return super().get_form(request, obj, **kwargs)

    def get_fields(self, request, obj=None):
        if obj is None:
            return list(AdminRecordForm.base_fields)
        return [*SHOWN, "state", "certificate_link"]

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        editable = {"expires_on"} if obj.counts else set()
        return tuple(f for f in (*SHOWN, "state", "certificate_link") if f not in editable)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        # never obj.save(): the service validates, defaults the expiry, audits
        # and stores an upload last
        d = form.cleaned_data
        try:
            with transaction.atomic():
                if change:
                    training.set_expiry(request.user, TrainingRecord.objects.get(pk=obj.pk), d["expires_on"])
                else:
                    r = training.record(request.user, d["employee"], d["course"], d["done_on"],
                                        upload=d.get("upload") or None, expires_on=d["expires_on"], note=d["note"])
                    obj.pk = r.pk
        except ValidationError as e:
            self._refuse(request, e)

    # ---- actions ---------------------------------------------------------

    def has_verify_permission(self, request, object_id=None):
        r = TrainingRecord.objects.filter(pk=object_id).select_related("employee").first()
        return r is not None and r.pending and access.may_verify(request.user, r)

    @action(description="Verify", url_path="verify", permissions=["verify"])
    def verify_record(self, request, object_id):
        """GET asks; only the POST verifies (training.verify)."""
        record = get_object_or_404(TrainingRecord.objects.select_related("employee", "course"), pk=object_id)
        if request.method == "POST":
            try:
                training.verify(request.user, record)
            except ValidationError as e:
                messages.error(request, " ".join(e.messages))
            else:
                messages.success(request, f"{record}: verified.")
            return HttpResponseRedirect(reverse("admin:training_trainingrecord_change", args=[record.pk]))
        return self._page(request, "training/admin/verify.html", f"Verify: {record}", record=record)

    @action(description="Reject", url_path="reject", permissions=["verify"])
    def reject_record(self, request, object_id):
        """GET asks why; the POST rejects (training.reject, which emails the person)."""
        record = get_object_or_404(TrainingRecord.objects.select_related("employee", "course"), pk=object_id)
        form = AdminRejectForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            try:
                training.reject(request.user, record, form.cleaned_data["note"])
            except ValidationError as e:
                form.add_error(None, e.messages)
            else:
                messages.success(request, f"{record}: turned down; {record.employee} has been told why.")
                return HttpResponseRedirect(reverse("admin:training_trainingrecord_change", args=[record.pk]))
        return self._page(request, "training/admin/reject.html", f"Reject: {record}", record=record, form=form)


@admin.register(TrainingSession)
class TrainingSessionAdmin(_Refusable, ModelAdmin):
    list_display = ("course", "held_on", "trainer", "attended")
    list_filter = ("course",)
    list_select_related = ("course",)

    @admin.display(description="Attended")
    def attended(self, obj):
        return obj.records.count()

    @admin.display(description="Who attended")
    def attendees(self, obj):
        rows = obj.records.select_related("employee").order_by("employee__last_name", "employee__first_name")
        if not rows:
            return "-"
        return format_html_join(", ", '<a href="{}">{}</a>',
                                ((reverse("admin:training_trainingrecord_change", args=[r.pk]), r.employee.name)
                                 for r in rows))

    @admin.display(description="Attendance sheet")
    def sheet_link(self, obj):
        return _file_link(obj.attendance_sheet)

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs["form"] = AdminSessionForm
        return super().get_form(request, obj, **kwargs)

    def get_fields(self, request, obj=None):
        if obj is None:
            return list(AdminSessionForm.base_fields)
        return [*SESSION_SHOWN, "attendees", "sheet_link"]

    def get_readonly_fields(self, request, obj=None):
        return () if obj is None else (*SESSION_SHOWN, "attendees", "sheet_link")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        d = form.cleaned_data
        try:
            with transaction.atomic():
                s = sessions.record_session(request.user, d["course"], d["held_on"], list(d["attendees"]),
                                            trainer=d["trainer"], note=d["note"], upload=d.get("upload") or None)
        except ValidationError as e:
            self._refuse(request, e)
            return
        obj.pk = s.pk
```

```
{# templates/training/admin/verify.html #}
{% extends "admin/base_site.html" %}
{% comment %}TrainingRecordAdmin.verify_record: confirm before the record
counts. GET only shows this page; the POST calls training.verify.{% endcomment %}
{% block breadcrumbs %}{% endblock %}
{% block content %}
<div class="flex flex-col gap-6 max-w-2xl">
  <p><a href="{% url 'admin:training_trainingrecord_change' record.pk %}" class="underline">{{ record }}</a></p>
  <form method="post" class="flex flex-col gap-4">{% csrf_token %}
    <p>{{ record.employee }} recorded {{ record.course }} as done on {{ record.done_on|date:"j M Y" }}{% if record.certificate_id %}, with <a href="{% url 'documents:download' record.certificate_id %}" class="underline">this certificate</a>{% endif %}. Verifying makes it count from that date.</p>
    <div class="flex items-center gap-4">
      <button type="submit" class="bg-primary-600 text-white font-semibold px-3 py-2 rounded-default">Verify</button>
      <a href="{% url 'admin:training_trainingrecord_change' record.pk %}" class="underline">Back</a>
    </div>
  </form>
</div>
{% endblock %}
```

```
{# templates/training/admin/reject.html #}
{% extends "admin/base_site.html" %}
{% comment %}TrainingRecordAdmin.reject_record: the note, then training.reject
(which emails the person the note and where to record again).{% endcomment %}
{% block breadcrumbs %}{% endblock %}
{% block content %}
<div class="flex flex-col gap-6 max-w-2xl">
  <p><a href="{% url 'admin:training_trainingrecord_change' record.pk %}" class="underline">{{ record }}</a></p>
  <form method="post" class="flex flex-col gap-4">{% csrf_token %}
    {% if form.non_field_errors %}<div role="alert" class="text-red-600">{% for e in form.non_field_errors %}<p>{{ e }}</p>{% endfor %}</div>{% endif %}
    {% for field in form %}
      <div class="flex flex-col gap-1">
        <label for="{{ field.id_for_label }}" class="font-semibold">{{ field.label }}</label>
        {{ field }}
        {% for e in field.errors %}<p role="alert" class="text-red-600">{{ e }}</p>{% endfor %}
        <p class="text-font-subtle-light dark:text-font-subtle-dark">{{ field.help_text }}</p>
      </div>
    {% endfor %}
    <p>The record stays, counting for nothing; {{ record.employee }} is emailed the note and asked to record it again.</p>
    <div class="flex items-center gap-4">
      <button type="submit" class="bg-primary-600 text-white font-semibold px-3 py-2 rounded-default">Turn it down</button>
      <a href="{% url 'admin:training_trainingrecord_change' record.pk %}" class="underline">Back</a>
    </div>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 5: The Compliance tab**

In `people/admin.py` `compliance_summary`, after the `reg_rows` loop and before `policy_rows`, add:

```python
        from training.services import training as training_svc
        train_rows = []
        for r in training_svc.state(obj, as_of):
            if r.pending is not None:
                link = _link(reverse("admin:training_trainingrecord_change", args=[r.pending.pk]), "Verify or reject")
            elif r.latest is not None:
                link = _link(reverse("admin:training_trainingrecord_change", args=[r.latest.pk]), "Open")
            else:
                link = _link(f"{reverse('admin:training_trainingrecord_add')}?employee={obj.pk}&course={r.course.pk}",
                             "Record")
            train_rows.append((r.course, r.label, _day(r.expires_on), link))
```

and extend the `format_html` call: insert `'<h3 class="font-semibold mb-2">Training</h3>{}'` after the Registrations line of the template string, and the matching argument after the registrations `_table(...)`:

```python
            _table(("Course", "Status", "Expires", ""), train_rows,
                   "Their position needs no training, and none is recorded."),
```

- [ ] **Step 6: The matrix page, its route and the navigation**

Add to `training/forms.py`:

```python
class MatrixFilterForm(forms.Form):
    """The matrix's GET filters. Unknown values are dropped, never an error:
    the page always renders."""
    course = forms.ModelChoiceField(queryset=Course.objects.filter(active=True), required=False, label="Course",
                                    empty_label="Every course")
    team = forms.ModelChoiceField(queryset=Team.objects.all(), required=False, label="Team", empty_label="Every team")
    q = forms.CharField(required=False, max_length=60, label="Name")
    show = forms.ChoiceField(required=False, label="Show", choices=[
        ("all", "Everyone"), ("problems", "Problems only"), ("to_verify", "To verify")])

    def filters(self):
        """Clean what is there; anything invalid is as if it were not given."""
        self.is_valid()
        d = self.cleaned_data if hasattr(self, "cleaned_data") else {}
        return {"course": d.get("course") or None, "team": d.get("team") or None, "query": d.get("q") or "",
                "show": d.get("show") or "all"}
```
with `from people.models import Employee, Team` replacing the Employee import at the top.

Add to `training/views.py`:

```python
def _matrix(request):
    if not access.can_view_restricted(request.user):
        raise PermissionDenied
    form = MatrixFilterForm(request.GET)
    f = form.filters()
    today = timezone.localdate()
    return form, f, today, matrix.build(today, **f)


@login_required
@require_safe
def matrix_page(request):
    """HR's training matrix: people down, courses across, filtered by the
    form (GET; the page writes nothing). Each name opens the person page."""
    form, f, today, m = _matrix(request)
    return render(request, "training/matrix.html", {
        "form": form, "courses": m.courses,
        "grid": [(entry.employee, [entry.cells.get(c.pk) for c in m.courses]) for entry in m.rows], "today": today,
        "csv_url": f"{reverse('training:matrix_csv')}?{request.GET.urlencode()}" if request.GET else
        reverse("training:matrix_csv")})


@login_required
@require_safe
def matrix_csv(request):
    form, f, today, m = _matrix(request)
    response = HttpResponse(matrix.to_csv(m), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{matrix.filename(today, **f)}"'
    return response
```
(imports: `HttpResponse`, `MatrixFilterForm`, `matrix` from `training.services`.)

In `training/urls.py`, add before the `<int:pk>/` routes:
```python
    path("matrix/", views.matrix_page, name="matrix"),
    path("matrix.csv", views.matrix_csv, name="matrix_csv"),
```

```
{# templates/training/matrix.html #}
{% extends "base.html" %}
{% comment %}training:matrix — HR's grid (training.services.matrix.build):
everyone employed today down the side, the courses any of them needs or
has across, each cell its status and expiry. The form's GET filters by
course, team, name and problems only; Download gives the same grid as CSV.
Reads only. Expects form, courses, grid (a list of (employee, cells) with
one cell per course, None where there is nothing), today, csv_url.{% endcomment %}
{% block title %}Training matrix{% endblock %}
{% block content %}
<div class="stack">
<div class="page-head"><h1>Training matrix</h1><a href="{{ csv_url }}" class="btn btn-quiet" download>Download as CSV</a></div>
<section class="card">
  <form method="get" class="filters">
    {{ form.as_div }}
    <div class="form-actions"><button type="submit" class="btn btn-primary">Filter</button> <a href="{% url 'training:matrix' %}" class="btn btn-quiet">Clear</a></div>
  </form>
</section>
<section class="card">
  {% if grid %}
  <div class="table-scroll">
  <table class="list matrix">
    <thead><tr><th scope="col">Person</th>{% for c in courses %}<th scope="col">{{ c.name }}</th>{% endfor %}</tr></thead>
    <tbody>
    {% for employee, cells in grid %}
      <tr>
        <th scope="row"><a href="{% url 'training:person' employee.pk %}">{{ employee.name }}</a></th>
        {% for row in cells %}
          <td>{% if row %}<span class="badge {% if row.status == 'current' %}badge-ok{% elif row.status == 'due_soon' or row.status == 'lapsed' or row.status == 'missing' %}badge-warning{% else %}badge-muted{% endif %}">{% if row.pending %}To verify{% else %}{{ row.label }}{% endif %}</span>{% if row.expires_on %} <span class="muted">{{ row.expires_on|date:"j M Y" }}</span>{% endif %}{% endif %}</td>
        {% endfor %}
      </tr>
    {% endfor %}
    </tbody>
  </table>
  </div>
  {% else %}
  <p class="empty">Nobody matches these filters.</p>
  {% endif %}
  <p class="muted">As of {{ today|date:"j M Y" }}. Each cell is the latest verified record; <em>To verify</em> is an upload waiting for HR or the manager.</p>
</section>
</div>
{% endblock %}
```

The view shapes the grid so the template needs no lookup tag: in `matrix_page`, pass `"courses": m.courses` and `"grid": [(entry.employee, [entry.cells.get(c.pk) for c in m.courses]) for entry in m.rows]` instead of `"matrix": m`.

In `hr/admin_site.py`, after the `Training sessions` item add:
```python
            _nav_item("Training matrix", "grid_on", "training:matrix"),
```

- [ ] **Step 7: The dashboard**

In `absence/admin_dashboard.py`:
- `COMPLIANCE` gains, after the registrations pair: `("training_problems", "Training lapsed or missing"), ("training_to_verify", "Training to verify"),`.
- a module constant after it:
```python
# The two training numbers open the matrix with its filter on, not the Employees list.
MATRIX_SHOW = {"training_problems": "problems", "training_to_verify": "to_verify"}
```
- in `compliance_people`, add `from training.services import training` to the local imports and, inside the per-employee loop after the registrations block:
```python
        for row in training.state(e, today):
            if row.pending is not None:
                out["training_to_verify"].append(e.pk)
            elif row.status in ("lapsed", "missing"):
                out["training_problems"].append(e.pk)
```
- in `dashboard`, build each card entry's URL as:
```python
    matrix_url = reverse("training:matrix")
    context["compliance"] = [
        {"label": label, "count": counts[key],
         "url": f"{matrix_url}?show={MATRIX_SHOW[key]}" if key in MATRIX_SHOW else f"{employees}?compliance={key}"}
        for key, label in COMPLIANCE]
```
- update the module docstring's `COMPLIANCE` comment: "Each opens the Employees list filtered to the people it counts, but the training numbers, which open the matrix."

In `templates/admin/index.html`, change the card's sentence to: `Checks, registrations, training and signatures of the people employed today, and checklist items past their due date. Each number opens the people it counts; the training numbers open the matrix.`

- [ ] **Step 8: Run the tests and the lint**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_training_admin.py tests/test_training_pages.py tests/test_compliance_admin.py tests/test_people_admin.py tests/test_checks.py tests/test_registers_pages.py tests/test_navigation.py -q && .venv/bin/ruff check . && DEBUG=1 .venv/bin/python manage.py makemigrations --check`
Expected: all pass. `tests/test_compliance_admin.py::test_each_number_links_to_the_people_it_counts` may iterate every `COMPLIANCE` key and expect the Employees filter URL: if it does, teach it the two training keys (they link to the matrix) rather than changing the dashboard.

- [ ] **Step 9: Commit**

```bash
cd /home/user/practice-hr && git add training templates/training templates/admin/index.html people/admin.py hr/admin_site.py absence/admin_dashboard.py tests/test_training_admin.py tests/test_compliance_admin.py && git commit -q -F - <<'MSG'
Training: the admin, the Compliance tab's training table, the matrix page and the dashboard numbers

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01PkKQLdYCQnRZiVssdedFig
MSG
```

---

### Task 11: Documentation, the backlog, and the whole suite

**Files:**
- Modify: `docs/admin/compliance.md` (a Training section, the Compliance card and tab paragraphs, Retention), `docs/admin/README.md` (the Compliance row), `docs/admin/people.md:117-150` (The Compliance tab), `docs/guides/hr-administrator.md` (going-live step, a Training section), `docs/guides/manager.md` (a Training section), `docs/guides/README.md`, `README.md` (the first paragraph), `docs/superpowers/backlog.md`
- Test: `tests/test_training_docs.py`

**Interfaces:** none; the docs tests in `tests/test_docs.py` already check every relative link and anchor in these pages.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_training_docs.py
"""The training documentation exists where the other compliance docs are,
names the UI's labels, and the backlog records what was built."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _text(*parts):
    return ROOT.joinpath(*parts).read_text()


def test_the_admin_guide_has_a_training_section_with_every_part():
    text = _text("docs", "admin", "compliance.md")
    for heading in ("## Training", "### Courses", "### Recording training", "### Verifying what someone recorded",
                    "### Sessions", "### The training matrix", "### Who sees what"):
        assert heading in text, heading
    for label in ("Required of everyone", "Awaiting verification", "Record a training session", "Download as CSV",
                  "Training lapsed or missing", "Training to verify", "RETENTION_DAYS_TRAINING"):
        assert label in text, label
    assert "- [Training](#training)" in text                         # the page's own contents list


def test_the_people_page_and_the_index_mention_training():
    assert "Training" in _text("docs", "admin", "people.md").split("### The Compliance tab")[1].split("## ")[0]
    assert "training" in _text("docs", "admin", "README.md").lower()


def test_the_user_guides_cover_training():
    hr = _text("docs", "guides", "hr-administrator.md")
    for heading in ("## Training", "### How to say who needs a course", "### How to verify what someone uploaded",
                    "### How to record a training session", "### How to see the training matrix"):
        assert heading in hr, heading
    assert "training" in hr.split("## Going live: your first month")[1].split("## Finding your way")[0].lower()
    manager = _text("docs", "guides", "manager.md")
    for heading in ("## Your team's training", "### How to record training for someone",
                    "### How to verify or turn down an upload", "### How to record a session"):
        assert heading in manager, heading
    assert "training" in _text("docs", "guides", "README.md").lower()
    assert "training" in _text("README.md").split("## Develop")[0].lower()


def test_the_backlog_closes_the_item_and_parks_the_rest():
    text = _text("docs", "superpowers", "backlog.md")
    assert "Training compliance (spec 4)" not in text.split("## Smaller items")[0] or "built" in text
    for parked in ("level", "import", "certificate pack", "booking"):
        assert parked in text.lower(), parked
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_training_docs.py -q`
Expected: FAIL on the first assertion of each test.

- [ ] **Step 3: The admin reference (`docs/admin/compliance.md`)**

Add `- [Training](#training)` to the contents list after `- [Professional registrations](#professional-registrations)`, and add `Courses / Training records / Training sessions / Training matrix` to the **Where** line. Insert the section below after the Professional registrations section (before `## Files`):

```markdown
## Training

The courses each role must keep current: basic life support, safeguarding,
fire safety, information governance and the like. Which courses a person
needs follows the **title of their current primary position**, or a course
is **required of everyone**; what they have is a list of training records,
one row per completion.

### The mental model

**A course says who needs it and how long it lasts.** A training record is
one completion of a course by one person. **Records are append-only:** a
renewal is a new row, and the latest verified one by date done is the one
that counts. Nothing is edited or deleted; the one change allowed after
the fact is the expiry date of a verified record.

**Three kinds of record.** One HR or a line manager enters is *verified*
at once. One the person enters themselves is *awaiting verification*
until HR or their manager verifies it: it counts for nothing yet, but the
person is not reminded while it waits. One turned down is *rejected*: it
stays in the history with its note, counts for nothing, and the person is
emailed the note and asked to record it again.

**Changing someone's position changes what they need, on the next read.**
A record for a course their title no longer needs stays, shown as *Not
required*, and nobody is chased for it.

### Courses

`/admin/training/course/`

Ten are set up when the app is installed, **with no titles assigned and
none required of everyone**: until you set that up, nobody owes anything.

| Course | Delivery | Valid for |
|---|---|---|
| Basic life support | Face to face | 12 months |
| Fire safety | Online | 12 months |
| Information governance | Online | 12 months |
| Infection prevention and control | Online | 12 months |
| Safeguarding children | Online | 36 months |
| Safeguarding adults | Online | 36 months |
| Equality and diversity | Online | 36 months |
| Health and safety | Online | 36 months |
| Conflict resolution | Online | 36 months |
| Chaperone | Online | One-off |

- **Name** and **Code**: the code names the course in the reminder keys
  and is fixed once added. Rename freely; add a course with a new code.
- **Validity months**: blank is a one-off that never renews.
- **Required of everyone**: every currently employed person needs it,
  whatever their title. With it off, **Positions** says which titles do.
  A course with neither is optional: recorded when someone has done it,
  required of nobody.
- **Delivery**: *Online* or *Face to face*. A label with two effects: a
  completion the person records themselves needs a certificate file for
  an online course and not for a face-to-face one, and the reminder
  wording differs ("complete the e-learning and upload your certificate"
  against "ask your manager about the next session").
- **Active**: a course cannot be deleted (records point at it); make it
  inactive and it is required of nobody and offered on no form.

### Recording training

`/admin/training/trainingrecord/add/`, or a person's training page at
`/training/<their id>/` (HR and their line manager), or **My record** (the
person themselves).

- **Done on** cannot be after today. **Expires on** is worked out from the
  course's validity when left blank.
- **Certificate**: PDF, JPEG, PNG or DOCX, up to the usual size, stored as
  the person's file (category *Certificate*, never HR-only) so it also
  appears in their Documents.
- **Note**: seen by HR and the line manager, never the person, never in a
  reminder, never in the matrix download.

A record HR or a manager enters is verified at once. A manager records
only for their direct reports on the day, never for themselves. HR
records anyone, themselves included (as with checks).

### Verifying what someone recorded

A person records their own completion from **My record** (or **Getting
started** before their first day): course, date done, and the certificate
(required for an online course). It shows as **Awaiting verification** on
their page, in the **Training to verify** number on the admin home page,
as *To verify* in the matrix, and in the morning digest to HR ("Fire
safety: to verify, uploaded 3 Oct 2026") on the overdue cadence until
someone acts.

**Verify** (a button on the person's training page, or the record's
**Verify** action in the admin) makes it count from its date done.
**Reject** asks for a note of up to 200 characters, then emails the person
the note with a link to My record to record it again. Both are HR's or the
line manager's; both confirm before writing.

### Sessions

`/training/session/` (**Record a training session** on **My team**, or
**Training sessions › Add** in the admin).

A face-to-face group recorded once: course, date held, trainer (free
text), an optional attendance sheet, and who attended. Recording it makes
one verified record per attendee, dated the day held, all pointing at the
session, so each person's history reads normally. The sheet is one file
with no person, shared by every record from that session; HR and any
manager with a report on the session can open it.

A manager ticks only their own reports; HR anyone employed today. One name
outside the manager's team refuses the whole session and writes nothing.
Someone left off is added by recording the session again with just them.

### The training matrix

`/training/matrix/` (**Training matrix** in the Compliance sidebar).

Everyone employed today down the side, the courses any of them needs or
has across, each cell the status and expiry from the latest verified
record; *To verify* marks an upload waiting. Filter by **Course**,
**Team**, **Name** and **Show** (*Everyone*, *Problems only*: lapsed,
missing or to verify; *To verify*). Each name opens the person's training
page. **Download as CSV** gives the filtered grid as
`training-matrix-<filters>-<date>.csv`, one row per person, one column
per course, each cell "Status, date": what an inspector asks for. The
note is never in it.

### Who sees what

| Who | Sees | Does |
|---|---|---|
| The person | their own courses, statuses, dates and certificates on My record (never the note) | records their own completions |
| Their line manager | everything about their reports' training, certificates included, on My team and the person page | records for a report, verifies or rejects, records a session for their reports |
| HR | everyone, the matrix, the admin lists | everything, and the one edit: a verified record's expiry |

Managers see training detail because training is not health or identity
material and they chase and record it; they still see nothing of a
report's checks beyond the counts.

### What each status means

| Status | Meaning |
|---|---|
| **Current** | A verified record whose expiry is more than the reminder window away, or a one-off. |
| **Due soon** | Expires within the reminder window (**Start days before**, 60 by default). |
| **Lapsed** | The latest verified record has expired. |
| **Missing** | Required, and no verified record. Owed from the employment start date. |
| **Awaiting verification** | Missing or lapsed, but the person has recorded a completion that waits for HR or the manager. |
| **Not required** | Has a record, but the title no longer needs the course. |

### Reminders

Each required course that is due soon, lapsed or missing goes to every HR
admin and to the person (always: the person does the course), on the
schedule's cadence, with the line manager told once, the first time it
lapses, naming the course. A course with an upload waiting says nothing to
the person and asks HR to verify. See [Reminders](#reminders).
```

Then in **Seeing where everyone stands › The Compliance card**, add two rows to the table:

```markdown
| **Training lapsed or missing** | Courses with the status *Lapsed* or *Missing*, across everyone employed today. Opens the matrix with *Problems only* on. |
| **Training to verify** | Completions people recorded themselves that nobody has verified or rejected yet. Opens the matrix with *To verify* on. |
```
and change "shows five numbers" to "shows seven numbers", and the sentence "Choose a number to open **Employees** filtered…" to say the two training numbers open the matrix instead. In **The Compliance tab**, after "their professional registrations first", add "then their training (each course with its status and a link to open, verify or record)". In **Retention**, add *Training records* and `RETENTION_DAYS_TRAINING` to the list.

- [ ] **Step 4: The other admin pages and the index**

`docs/admin/README.md`: in the Compliance row of the table, after "professional registrations and the register lookups," add "training courses, records, sessions and the matrix,".

`docs/admin/people.md`, **The Compliance tab**: add a paragraph after the registrations one:

```markdown
**Training** lists each course their title needs (or everyone does), plus
any other course they have a record of, with its status, the expiry of the
counting record, and a link: **Open** the record, **Verify or reject** an
upload that waits, or **Record** one (the add page with the person and the
course filled in). See [Training](compliance.md#training).
```

- [ ] **Step 5: The user guides and the README**

`docs/guides/hr-administrator.md`: in **Going live**, add a step after step 7:

```markdown
8. **Set up training the same way round.** Under **Compliance**,
   **Courses**, tick **Required of everyone** on the practice-wide courses
   and add the titles that need the rest (see [How to say who needs a
   course](#how-to-say-who-needs-a-course)). Then ask staff to record the
   training they already hold from **My record**, with their
   certificates, and verify each one (see [How to verify what someone
   uploaded](#how-to-verify-what-someone-uploaded)). Until a course has
   titles or the everyone tick, nobody is reminded of it.
```
(renumber the later steps.) Add a section after **Professional registrations**:

```markdown
## Training

Every member of staff must keep a set of courses current, and an inspector
asks to see the matrix. Staff record their own completions with the
certificate; you or their manager verify them. Face-to-face sessions are
recorded once for everyone who attended.

### How to say who needs a course

1. Under **Compliance**, choose **Courses** and open the course.
2. For a practice-wide course, tick **Required of everyone**.
3. Otherwise, move the titles that need it into **Positions**.
4. Check **Validity months** and **Delivery**, then **Save**.

What you will see: the next morning's reminder email tells each person
with the course missing, and HR, that it is owed. Set up the courses after
recording what people already hold, or everyone is told their training is
missing.

### How to record training for someone

1. Open **Employees**, the person, then the **Compliance** tab, and choose
   **Record** beside the course (or **Compliance**, **Training records**,
   **Add**).
2. Enter the **Done on** date and attach the certificate if there is one.
   **Expires on** is worked out from the course if you leave it blank.
3. Add a **Note** if you want one. The person never sees it.
4. **Save**.

What you will see: the record is verified straight away, and the matrix
shows **Current** with the expiry date.

### How to verify what someone uploaded

1. On the admin home page, choose **Training to verify**, or open the
   person's training page from the matrix.
2. Open the certificate and check it is the right course, the right
   person and the right date.
3. Choose **Verify**, or **Reject** and say why in a sentence.

What you will see: a verified record counts from its date done. A rejected
one stays in the history, counts for nothing, and the person is emailed
your note with a link to record it again.

### How to record a training session

1. Under **Compliance**, choose **Training sessions**, then **Add** (or
   **Record a training session** on **My team**).
2. Choose the course and the date held, name the trainer, tick everyone
   who attended, and attach the attendance sheet if there is one.
3. **Save**.

What you will see: one verified record per person, dated the day held,
sharing the one sheet. Someone left off is added by recording the session
again with just them.

### How to see the training matrix

1. Under **Compliance**, choose **Training matrix**.
2. Filter by course, team or name, or choose **Problems only** to see
   just the people with something lapsed, missing or waiting to be
   verified.
3. Choose **Download as CSV** to hand the filtered grid over.

What you will see: people down the side, courses across, each cell the
status and expiry. The file is named with the filters and the date.
```

`docs/guides/manager.md`: add a section after **What you can see of a report's checks**:

```markdown
## Your team's training

Unlike checks, you see your team's training in full: each course, its
status, the dates and the certificates. You can record training for
someone, verify what they uploaded, and record a session for your team.

### How to see how someone's training stands

1. Choose **My team**.
2. Look in the **Training** column beside the person, and choose it to
   open their training page.

The words are the same as for checks, with one more: **to verify** means
they have recorded a completion and uploaded a certificate that is
waiting for you or HR to check.

### How to record training for someone

1. Open their training page from **My team**.
2. Under **Record training**, choose the course and the date done, attach
   the certificate if there is one, and choose **Record**.

What you will see: the record counts straight away. You can only record
for people who report to you; your own training you record from **My
record**, for HR or your own manager to verify.

### How to verify or turn down an upload

1. Open their training page. A row marked **Awaiting verification** shows
   the date uploaded and a link to the certificate.
2. Open the certificate and check it is the right course, person and date.
3. Choose **Verify**, or **Reject** and write a sentence saying why.

What you will see: a verified record counts from its date done. A rejected
one stays in their history, counts for nothing, and they are emailed your
note with a link to record it again.

### How to record a session

1. Choose **My team**, then **Record a training session**.
2. Choose the course and the date held, name the trainer, tick everyone
   who attended, and attach the attendance sheet if there is one.
3. Choose **Record the session**.

What you will see: one record per person, dated the day held. You can only
tick your own reports, and only people who reported to you on that date:
if someone else attended, ask HR to add them.

If one of your team's training lapses, you are told once, in a "Practice
HR: things due" email, with the course named: "Fire safety has lapsed".
```

`docs/guides/README.md`: in the managers' sentence add "and your team's training"; in HR's add "training".

`README.md`: in the first paragraph, after "professional registrations (…)", add "training compliance (courses by role, staff-recorded certificates verified by HR or the manager, group sessions, and the matrix an inspector asks for),".

- [ ] **Step 6: The backlog**

In `docs/superpowers/backlog.md`: remove item 3 from **Next** (renumber **Later** to 3) and add to the go-live item a sentence: "For spec 4 (training), set courses' titles and the everyone tick only after staff have recorded what they hold." Under **Smaller items**, add:

```markdown
- Course levels and equivalence (safeguarding level 3 satisfying level 2):
  the training app models each level as its own course for now.
- Importing an e-learning platform's completion export (Blue Stream
  Academy, e-LfH) as training records.
- A certificate pack download: every certificate for one person, or one
  course, as a zip, for an inspection.
- Bookings and a training calendar, and reminding a manager to run the
  next session when a face-to-face course is due for several people.
```

- [ ] **Step 7: Run the docs tests, then the whole suite**

Run: `cd /home/user/practice-hr && .venv/bin/pytest tests/test_training_docs.py tests/test_docs.py -q`
Expected: all pass (every link and anchor added resolves: the anchors are the headings' slugs).

Run: `cd /home/user/practice-hr && .venv/bin/ruff check . && DEBUG=1 .venv/bin/python manage.py makemigrations --check && .venv/bin/pytest -q`
Expected: ruff clean, no migration drift, the whole suite green (about seven minutes).

- [ ] **Step 8: Commit**

```bash
cd /home/user/practice-hr && git add docs README.md tests/test_training_docs.py && git commit -q -F - <<'MSG'
Docs: training compliance in the admin reference and both guides; the backlog closes spec 4

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01PkKQLdYCQnRZiVssdedFig
MSG
```

---

## Self-review notes (written with the spec open)

- **Spec §1 models**: Task 2, every field. `TrainingRecord.rejected` is a property, not a field; the spec's `rejected_at` / `rejected_note` are the fields.
- **Spec §2 helpers**: Task 1. The spec's `status(latest_expires_on, has_latest, required, today, window_days)` is `validity.status(expires_on, has_latest, required, today, window_days)`.
- **Spec §3 services**: Tasks 4, 5, 7. Two rulings: `may_record_training_for` lets HR record their own training (the spec says "never yourself" for everyone; HR records their own checks today and an HR admin's own training would otherwise be verifiable only by their manager). `matrix` takes a name search (`query`) rather than an `employee`; the person filter in the spec is a type-ahead on name, which this is.
- **Spec §4 pages**: Tasks 8, 9, 10. Rulings: the matrix is a site page at `/training/matrix/` linked from the Compliance sidebar and the dashboard, as **Starters and leavers** is, not an admin-site URL. The My record card has one record form with a course select (which also covers a course the person did that is not required) rather than a button per row; the person page keeps a `Reject` link to a confirm page as the spec says. The admin's record change page edits `expires_on` in place through `set_expiry`.
- **Spec §5 reminders**: Task 6. The digest template groups lines by person, not by kind, so there is no "Training heading"; the labels name the course. `to_verify` repeats on the overdue cadence because its `due_on` is the upload date, already past.
- **Spec §6 errors, audit, privacy**: audit fields `recorded`, `self_recorded`, `verified`, `rejected`, `session_recorded`, `expires_on` (the spec's `expiry_changed`), `certificate`; `file.viewed` through `files.open`. The note is excluded from the person's page (Task 9 template), the digest (Task 6 labels) and the CSV (Task 7 test).
- **Spec §7 testing**: each line maps to a test above; the Review Focus items are pinned where stated.
- **Placeholder scan**: none. **Type consistency**: `Row` fields, `build_row`'s arguments, the route names and the `show` values are the same in every task.

## Execution notes (2026-10-25)

Built subagent-driven on `feature/training-compliance` from main 1011fd3: one implementer per task, a task review after each, a whole-branch review at the end, one fix wave and one re-review. Tasks 4, 9, 10 and 11 each took one fix round (a stale rejection beside a current record; the person page's Back link; a 500 on Save from a pending record's admin page; duplicate headings hijacking `#reminders`); Tasks 7 and 8 were corrected before review (an empty matrix cell; where the awaiting-verification rule lives). Whole suite at the end: 1596 passed, 1 skipped.

Rulings made against this plan's text, each recorded in the ledger as it was made:

- `_Refusable` in `training/admin.py` repeats CheckAdmin's refusal guard rather than sharing a cross-app base class (a tidy-up candidate).
- `build_row`: `rejected` is None when a newer pending record exists, and is decided by position in the done_on-ordered list, not by pk; a pending record with no counting record is `awaiting_verification` whatever `required` is.
- A matrix cell for a course the person neither needs nor has stays empty in every view; the page's footnote says so. "Problems only" means lapsed, missing or an upload waiting (not due soon), as the dashboard label says.
- The person page's Back link goes to My record, My team or the employee admin page by viewer.
- Going live is record-first: staff upload what they hold and HR verifies, then titles and the everyone tick.
- The admin record list's status filter is pending / verified / rejected with a name search; the matrix carries the date-driven statuses.
- `training.to_verify` feeds the dashboard count; `matrix.SHOW` was dropped as unused.
- `set_expiry` and `record` refuse an expiry before the date done; `set_expiry` refuses a blank expiry on a course with a validity.
- A former or not-yet-started manager named on a position keeps the existing `can_view` behaviour; the backlog records it.
