# Onboarding, offboarding and documents — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Starter and leaver checklists with owners, dated compliance checks by position title, a per-person document store, policies signed with re-authentication, and one configurable morning reminder digest.

**Architecture:** Three new Django apps (`checks`, `documents`, `onboarding`) plus a small `compliance` app holding the "what is due" contract, the reminder schedule, the sent log and the digest. Services are the only writers; every file download goes through one audited view; the nightly job gains one more step. Position titles become a table so the three apps can target them.

**Tech Stack:** Django 5.2, SQLite WAL, django-unfold admin, pytest-django, openpyxl (payroll), the existing `accounts` re-authentication (password via `authenticate`, passkeys via `accounts.passkeys.verify_login`), `MEDIA_ROOT` file storage.

**Spec:** `docs/superpowers/specs/2026-10-04-onboarding-documents-design.md`. The plan argues from it; executors read both.

## Global Constraints

- Services are the only writers (`<app>/services/*.py`); views, admin and management commands call them. Pages never write on GET.
- `timezone.localdate()` for today, never `date.today()`.
- Every file download goes through `documents.services.files.open(actor, file)`, which applies the access rule and writes an audit "viewed" row. Nothing under `MEDIA_ROOT` is served by the web server directly (`MEDIA_URL` is never mapped in `config/urls.py`).
- Uploads: PDF, JPEG, PNG, DOCX only; `DOCUMENT_MAX_BYTES = 10 * 1024 * 1024`; the content is sniffed and a mismatch is refused; files are stored as `MEDIA_ROOT/<app>/<yyyy>/<uuid4 hex>.<ext>`.
- Nothing is deleted automatically. Checks and signatures are append-only; files are superseded, never removed.
- No PII, no secrets, no plaintext credential, no file content and no model identifier in any file, log or commit message.
- Tests: pytest-django, no network, no literal calendar year that will pass (use `timezone.localdate()` offsets or `tests/factories.py` helpers; `MON = date(2026, 4, 6)` in factories is a fixed past date and is fine), every new page and download tested for employee-own, other employee, manager, HR, pre-start and anonymous.
- Ruff clean; `DEBUG=1 python manage.py makemigrations --check` clean; full suite green (945 at `main` 58e15be).
- Every commit message ends with exactly:
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_01PkKQLdYCQnRZiVssdedFig`
- Docs: `docs/admin/compliance.md` (new), `docs/admin/people.md`, `docs/admin/README.md` index, the nightly keys in the existing nightly section, and plain-language sections in `docs/guides/hr-administrator.md` and `docs/guides/manager.md`. `tests/test_docs.py` pins wording and link targets; keep it green.
- Reminder cadence defaults: start 60 days before, every 30 days before due, every 7 days overdue. A manager is told once when a report's check lapses.
- Confirmation sentence for a signature, exactly: `I confirm I have read and understood {policy title} ({version label}).`

## Review Focus

Five conditions the spec implies but no happy-path test exercises, each pinned to a test in the task that owns it:

1. **A file whose bytes do not match its extension** (an HTML page saved as `.pdf`): refused with "This file is not a PDF" and nothing written. Task 3.
2. **A starter whose primary position has no line manager**: the checklist is still created, manager-owned items get no owner, and the Starters and leavers page lists the gap. Task 6.
3. **A policy reissued while a starter has not yet signed the previous version**: the owed list shows only the current version; the older one is never owed. Task 5.
4. **A reminder schedule where `every_days_before` is larger than `start_days_before`**: a single reminder at the start of the window, then the due-date one; no crash, no skipped due-date reminder. Task 8.
5. **A position title renamed in the admin after checks and templates point at it**: nothing changes for the people (the FK holds), and the new name shows everywhere. Task 1.

---

## File structure

```
people/models/employment.py          PositionTitle; Position.title FK
people/models/employee.py            bank_* fields
people/services/titles.py            get_or_create(name)
people/services/access.py            can_view_file, can_view_checks, is_pre_start
people/migrations/0013_positiontitle.py, 0014_employee_bank.py
documents/{models.py,admin.py,urls.py,views.py,apps.py}
documents/services/{files.py,policies.py,due.py}
documents/migrations/0001_initial.py
checks/{models.py,admin.py,apps.py}
checks/services/{checks.py,due.py}
checks/migrations/{0001_initial.py,0002_seed_types.py}
onboarding/{models.py,admin.py,urls.py,views.py,forms.py,middleware.py,apps.py}
onboarding/services/{checklists.py,due.py}
onboarding/migrations/{0001_initial.py,0002_seed_templates.py}
compliance/{models.py,admin.py,apps.py,due.py}
compliance/services/{schedule.py,digest.py,nightly.py}
compliance/migrations/0001_initial.py
templates/documents/{policies.html,sign.html}
templates/onboarding/{getting_started.html,_checklist.html,_todo_card.html,hr_list.html,hr_detail.html,details_form.html}
templates/people/me.html (sections), templates/people/team.html (card), templates/base.html (nav)
templates/email/compliance_digest.txt
templates/admin/index.html (card)
hr/admin_site.py (Compliance group), absence/admin_dashboard.py (counts)
people/management/commands/hr_nightly.py (compliance step)
config/settings.py (INSTALLED_APPS, DOCUMENT_MAX_BYTES, RETENTION_DAYS categories)
config/urls.py
docs/admin/compliance.md, docs/admin/people.md, docs/guides/*.md
tests/test_titles.py, test_bank_details.py, test_documents_files.py, test_checks.py,
tests/test_policies.py, test_onboarding.py, test_onboarding_pages.py, test_compliance.py,
tests/test_compliance_admin.py
```

Conventions to copy from the existing code (read these first): `absence/services/toil.py` (service shape, `_lock`, `check` functions, ValidationError messages), `absence/views/toil.py` (view shape, `messages`, POST-only writes), `absence/admin.py` (`ModelAdmin`, `has_*_permission`, detail actions, read-only admins), `people/services/audit.py`, `templates/absence/toil_claim.html` (page markup, `form.as_div`), `tests/test_toil_views.py` (role fixtures, `admin_client`, `employee_client`), `tests/factories.py`.

## Task 1: Position titles become a table

**Files:**
- Modify: `people/models/employment.py` (add `PositionTitle`; `Position.title` → FK)
- Create: `people/services/titles.py`, `people/migrations/0013_positiontitle.py`
- Modify: `people/services/positions.py:78` (`add` takes a `PositionTitle`), `people/admin.py` (PositionTitle admin; the Position inline's title field is now a select), `people/models/__init__.py` (export), `api/views.py` (`p.title.name`), `tests/factories.py:27` (`make_position` resolves a name to a title), `hr/admin_site.py` (People group gains "Position titles"), `docs/admin/people.md`
- Test: `tests/test_titles.py`

**Interfaces:**
- Produces: `people.models.PositionTitle(name: str unique, display_order: int)`; `Position.title: FK PositionTitle` (so `position.title.name`); `people.services.titles.get_or_create(name) -> PositionTitle`; `make_position(employment, title="Receptionist")` still takes a name.
- Every later task that targets positions uses `PositionTitle` rows and `positions.primary_on(employment, day).title`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_titles.py
import pytest
from django.db import IntegrityError

from people.models import Position, PositionTitle
from people.services import titles
from tests.factories import make_employment, make_position

pytestmark = pytest.mark.django_db


def test_a_title_is_a_row_and_a_position_points_at_it():
    pos = make_position(make_employment(), title="Practice Nurse")
    assert isinstance(pos.title, PositionTitle)
    assert pos.title.name == "Practice Nurse"
    assert PositionTitle.objects.filter(name="Practice Nurse").count() == 1


def test_get_or_create_is_case_sensitive_and_unique():
    t1 = titles.get_or_create("Receptionist")
    t2 = titles.get_or_create("Receptionist")
    assert t1.pk == t2.pk
    with pytest.raises(IntegrityError):
        PositionTitle.objects.create(name="Receptionist")


def test_renaming_a_title_moves_every_position_with_it():
    pos = make_position(make_employment(), title="Receptionist")
    title = pos.title
    title.name = "Patient Services Advisor"
    title.save()
    pos.refresh_from_db()
    assert pos.title.name == "Patient Services Advisor"
    assert Position.objects.filter(title=title).count() == 1


def test_the_api_still_sends_the_title_as_text(client, settings):
    settings.HR_API_TOKENS = ["t"]
    pos = make_position(make_employment(), title="Receptionist")
    r = client.get("/api/v1/people", HTTP_AUTHORIZATION="Bearer t")
    assert r.status_code == 200
    assert r.json()["people"][0]["positions"][0]["title"] == "Receptionist"
    assert pos.title.name == "Receptionist"
```

- [ ] **Step 2: Run them to see them fail**

Run: `source .venv/bin/activate && pytest -q tests/test_titles.py`
Expected: ImportError on `PositionTitle` / `titles`.

- [ ] **Step 3: Model, service, migration**

```python
# people/models/employment.py — add above Position
class PositionTitle(models.Model):
    """A job title the practice uses. Check types, policies and checklist
    templates target titles, so they are rows rather than free text."""
    name = models.CharField(max_length=80, unique=True)
    display_order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


# Position.title becomes:
    title = models.ForeignKey(PositionTitle, on_delete=models.PROTECT, related_name="positions")
```

```python
# people/services/titles.py
from people.models import PositionTitle


def get_or_create(name):
    """The title row for `name`, exact match, created if missing."""
    name = (name or "").strip()
    if not name:
        raise ValueError("a title needs a name")
    title, _ = PositionTitle.objects.get_or_create(name=name)
    return title
```

Migration `people/migrations/0013_positiontitle.py`, written by hand (not `makemigrations` alone), in this order: `CreateModel PositionTitle`; `AddField Position.title_ref` (FK, null=True); `RunPython` that creates one `PositionTitle` per distinct existing `title` string (ordered by name, `display_order` 100) and sets `title_ref` on every position; `RemoveField Position.title`; `RenameField title_ref → title`; `AlterField` to `null=False`. The reverse of the RunPython copies `title.name` back; make the migration reversible end to end.

```python
def forwards(apps, schema_editor):
    Position = apps.get_model("people", "Position")
    PositionTitle = apps.get_model("people", "PositionTitle")
    for name in sorted(set(Position.objects.values_list("title", flat=True))):
        row, _ = PositionTitle.objects.get_or_create(name=name)
        Position.objects.filter(title=name).update(title_ref=row)
```

- [ ] **Step 4: Callers**

`people/services/positions.py:add` takes `title` as a `PositionTitle` (a str is accepted and passed through `titles.get_or_create` for convenience). `tests/factories.py:make_position` passes `titles.get_or_create(title)`. `api/views.py` sends `p.title.name`. Grep `\.title\b` and `title=` across `people/`, `absence/`, `api/`, `templates/`, `tests/` and adapt each use (`str(position.title)` already gives the name). `people/admin.py`: register `PositionTitleAdmin(ModelAdmin)` with `list_display = ("name", "display_order")`, `search_fields = ("name",)`; the Position inline shows `title` as a select. `hr/admin_site.py`: People group gains `_nav_item("Position titles", "work_outline", "admin:people_positiontitle_changelist")`.

- [ ] **Step 5: Run the suite**

Run: `pytest -q` and `ruff check .` and `DEBUG=1 python manage.py makemigrations --check`
Expected: all green; the migration test in `tests/test_titles.py` plus every existing test touching positions.

- [ ] **Step 6: Docs and commit**

`docs/admin/people.md`: under Position, "Title is chosen from **People › Position titles**; add a new title there first. Renaming a title renames it on every position." Commit: `People: position titles become a table`.

---

## Task 2: Bank details on the employee, and the payroll Starters sheet

**Files:**
- Modify: `people/models/employee.py` (three fields), `people/services/employees.py:6` (EDITABLE), `people/admin.py` (fields shown; viewed audit "bank" alongside "ni_number"), `absence/services/payroll.py:57,94` (Starters headers and rows), `docs/admin/people.md`, `docs/admin/payroll.md`
- Create: `people/migrations/0014_employee_bank.py`
- Test: `tests/test_bank_details.py`

**Interfaces:**
- Produces: `Employee.bank_account_name` (char 60), `Employee.bank_sort_code` (char 8, stored `NN-NN-NN`), `Employee.bank_account_number` (char 8, digits); all `blank=True, default=""`; `employees.update(actor, employee, bank_sort_code=...)` validates; the payroll Starters sheet gains the three columns after "Unit".

- [ ] **Step 1: Failing tests**

```python
# tests/test_bank_details.py
import pytest
from django.core.exceptions import ValidationError

from people.models import AuditEntry
from people.services import employees
from tests.factories import make_employee

pytestmark = pytest.mark.django_db


def test_bank_details_are_editable_through_the_service_and_audited(hr_admin):
    e = make_employee()
    employees.update(hr_admin, e, bank_account_name="S Patel", bank_sort_code="12-34-56",
                     bank_account_number="12345678")
    e.refresh_from_db()
    assert (e.bank_sort_code, e.bank_account_number) == ("12-34-56", "12345678")
    fields = set(AuditEntry.objects.filter(object_id=e.pk).values_list("field", flat=True))
    assert {"bank_account_name", "bank_sort_code", "bank_account_number"} <= fields


@pytest.mark.parametrize("field,value", [("bank_sort_code", "123456"), ("bank_sort_code", "12-34-5x"),
                                         ("bank_account_number", "1234567"), ("bank_account_number", "1234567a")])
def test_malformed_bank_details_are_refused(hr_admin, field, value):
    e = make_employee()
    with pytest.raises(ValidationError):
        employees.update(hr_admin, e, **{field: value})


def test_opening_an_employee_with_bank_details_is_audited_as_viewed(admin_client, hr_admin):
    e = make_employee(bank_account_number="12345678", bank_sort_code="12-34-56")
    admin_client.get(f"/admin/people/employee/{e.pk}/change/")
    assert AuditEntry.objects.filter(object_id=e.pk, kind="viewed", field="bank").exists()


def test_the_payroll_starters_sheet_carries_bank_details(hr_admin, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    from openpyxl import load_workbook
    from absence.services import payroll
    from tests.factories import hours_employee
    emp = hours_employee()
    employees.update(hr_admin, emp.employee, bank_account_name="S Patel", bank_sort_code="12-34-56",
                     bank_account_number="12345678")
    run = payroll.generate(hr_admin, emp.start_date.year, emp.start_date.month)
    ws = load_workbook(tmp_path / run.path)["Starters"]
    headers = [c.value for c in ws[1]]
    row = [c.value for c in ws[2]]
    assert headers[-3:] == ["Account name", "Sort code", "Account number"]
    assert row[-3:] == ["S Patel", "12-34-56", "12345678"]
```

(Read `absence/services/payroll.py` for the real `generate` signature and `PayrollRun.path` before pinning the last test; adapt the call, not the assertion.)

- [ ] **Step 2: Run, see them fail.** `pytest -q tests/test_bank_details.py`

- [ ] **Step 3: Implement**

```python
# people/models/employee.py — after ni_number
    bank_account_name = models.CharField(max_length=60, blank=True, default="")
    bank_sort_code = models.CharField(
        max_length=8, blank=True, default="",
        validators=[RegexValidator(r"^\d{2}-\d{2}-\d{2}$", "Enter the sort code as NN-NN-NN.")])
    bank_account_number = models.CharField(
        max_length=8, blank=True, default="",
        validators=[RegexValidator(r"^\d{8}$", "An account number is eight digits.")])
```

`EDITABLE` gains the three names. `people/admin.py` `change_view`: alongside the `ni_number` audit, `if obj and (obj.bank_account_number or obj.bank_sort_code): audit.viewed(request.user, obj, "bank")`; `get_fields` keeps the three fields for HR admins (the admin is HR-only already). Payroll: `HEADERS["Starters"]` gains the three names; `_starters` yields `e.employee.bank_account_name, e.employee.bank_sort_code, e.employee.bank_account_number` at the end.

- [ ] **Step 4: Suite, ruff, migrations check; docs; commit** `Employee bank details, HR-only and audited; on the payroll Starters sheet`. Docs: `people.md` (Bank details: HR-only, viewed-audited, entered by the starter in self-service or by HR), `payroll.md` (Starters sheet columns).

---

## Task 3: The document store: `documents.File`, the files service, the audited download

**Files:**
- Create: `documents/__init__.py`, `documents/apps.py`, `documents/models.py`, `documents/services/__init__.py`, `documents/services/files.py`, `documents/views.py`, `documents/urls.py`, `documents/admin.py`, `documents/forms.py`, `documents/migrations/0001_initial.py`, `templates/people/_documents.html`
- Modify: `config/settings.py` (INSTALLED_APPS `documents`; `DOCUMENT_MAX_BYTES`; `DOCUMENT_TYPES`), `config/urls.py` (`path("documents/", include("documents.urls"))`), `people/services/access.py` (`can_view_file`), `people/views.py:32` and `templates/people/me.html` (Documents section), `hr/admin_site.py` (Compliance group starts here with "Files")
- Test: `tests/test_documents_files.py`

**Interfaces:**
- Produces: `documents.models.File` (fields below); `files.add(actor, employee, category, title, upload, hr_only=False) -> File`; `files.supersede(actor, file, by, note) -> File`; `files.open(actor, file) -> FileResponse` (raises `PermissionDenied`); `files.sniff(upload) -> str` (one of `pdf`, `jpeg`, `png`, `docx`; raises `ValidationError`); URL name `documents:download` (`/documents/file/<pk>/`); `access.can_view_file(user, file) -> bool`.
- Consumed by: Task 4 (check evidence), Task 5 (policy version files), Task 6/7 (upload items).

- [ ] **Step 1: Failing tests**

```python
# tests/test_documents_files.py
import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from documents.models import File
from documents.services import files
from people.models import AuditEntry
from tests.factories import make_employee, make_employment, make_position

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def _upload(name="contract.pdf", content=PDF, content_type="application/pdf"):
    return SimpleUploadedFile(name, content, content_type=content_type)


def test_add_stores_the_file_under_an_opaque_name_and_audits(hr_admin, media):
    e = make_employee()
    f = files.add(hr_admin, e, File.Category.CONTRACT, "Contract 2026", _upload())
    assert f.original_name == "contract.pdf" and f.content_type == "application/pdf"
    assert f.size == len(PDF) and len(f.sha256) == 64
    assert f.path.startswith("documents/") and f.path.endswith(".pdf") and "contract" not in f.path
    assert (media / f.path).read_bytes() == PDF
    assert AuditEntry.objects.filter(model="documents.file", object_id=f.pk, kind="change").exists()


def test_a_pdf_that_is_really_html_is_refused_and_nothing_written(hr_admin, media):
    e = make_employee()
    with pytest.raises(ValidationError, match="not a PDF"):
        files.add(hr_admin, e, File.Category.OTHER, "x", _upload(content=b"<html><body>hi</body></html>"))
    assert File.objects.count() == 0 and not any(media.rglob("*.pdf"))


def test_too_large_and_wrong_type_are_refused(hr_admin, settings):
    settings.DOCUMENT_MAX_BYTES = 100
    e = make_employee()
    with pytest.raises(ValidationError, match="10 MB|100 bytes"):
        files.add(hr_admin, e, File.Category.OTHER, "x", _upload(content=PDF + b"0" * 200))
    with pytest.raises(ValidationError, match="PDF, JPEG, PNG or DOCX"):
        files.add(hr_admin, e, File.Category.OTHER, "x", _upload(name="x.exe", content=b"MZ", content_type="x"))


def test_who_may_open(hr_admin, employee_user):
    e = make_employee(user=employee_user)
    other = make_employee(first="Jo", last="Bloggs")
    mgr = make_employee(first="Mo", last="Khan")
    make_position(make_employment(e), manager=mgr)
    f = files.add(hr_admin, e, File.Category.CONTRACT, "Contract", _upload())
    secret = files.add(hr_admin, e, File.Category.OCCUPATIONAL_HEALTH, "OH letter", _upload(), hr_only=True)
    assert files.open(employee_user, f).status_code == 200
    assert AuditEntry.objects.filter(model="documents.file", object_id=f.pk, kind="viewed").count() == 1
    with pytest.raises(PermissionDenied):
        files.open(employee_user, secret)
    from django.contrib.auth import get_user_model
    U = get_user_model()
    for who in (U.objects.create_user(email="jo@example.com", password="pw"),
                U.objects.create_user(email="mo@example.com", password="pw")):
        with pytest.raises(PermissionDenied):
            files.open(who, f)
    other.user = U.objects.get(email="jo@example.com"); other.save()
    mgr.user = U.objects.get(email="mo@example.com"); mgr.save()
    for who in (other.user, mgr.user):
        with pytest.raises(PermissionDenied):
            files.open(who, f)
    assert files.open(hr_admin, secret).status_code == 200


def test_download_view_streams_for_the_owner_and_404s_for_others(employee_client, admin_client, hr_admin, employee_user, client):
    e = make_employee(user=employee_user)
    f = files.add(hr_admin, e, File.Category.CONTRACT, "Contract", _upload())
    r = employee_client.get(f"/documents/file/{f.pk}/")
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    assert r["Content-Disposition"].startswith("attachment") and "contract.pdf" in r["Content-Disposition"]
    assert b"".join(r.streaming_content) == PDF
    assert client.get(f"/documents/file/{f.pk}/").status_code in (302, 403)
    assert admin_client.get(f"/documents/file/{f.pk}/").status_code == 200


def test_supersede_links_and_keeps_both(hr_admin):
    e = make_employee()
    old = files.add(hr_admin, e, File.Category.CONTRACT, "Contract", _upload())
    new = files.add(hr_admin, e, File.Category.CONTRACT, "Contract v2", _upload())
    files.supersede(hr_admin, old, new, "reissued with the new hours")
    old.refresh_from_db()
    assert old.superseded_by_id == new.pk and old.superseded_note == "reissued with the new hours"
    assert File.objects.count() == 2


def test_my_record_lists_own_files_but_not_hr_only_ones(employee_client, hr_admin, employee_user):
    e = make_employee(user=employee_user)
    files.add(hr_admin, e, File.Category.CONTRACT, "Contract 2026", _upload())
    files.add(hr_admin, e, File.Category.OCCUPATIONAL_HEALTH, "OH letter", _upload(), hr_only=True)
    body = employee_client.get("/people/me/").content.decode()
    assert "Contract 2026" in body and "OH letter" not in body
```

- [ ] **Step 2: Run, see them fail.**

- [ ] **Step 3: Model**

```python
# documents/models.py
from django.conf import settings
from django.db import models


class File(models.Model):
    """One stored document. `path` is opaque under MEDIA_ROOT; the original
    name is kept for the download. Never edited, only superseded."""
    class Category(models.TextChoices):
        CONTRACT = "contract", "Contract"
        OFFER = "offer", "Offer letter"
        IDENTITY = "identity", "Identity"
        CERTIFICATE = "certificate", "Certificate"
        OCCUPATIONAL_HEALTH = "occupational_health", "Occupational health"
        CORRESPONDENCE = "correspondence", "Correspondence"
        POLICY = "policy", "Policy"
        OTHER = "other", "Other"

    employee = models.ForeignKey("people.Employee", null=True, blank=True, on_delete=models.PROTECT,
                                 related_name="files")
    category = models.CharField(max_length=20, choices=Category.choices)
    title = models.CharField(max_length=120)
    path = models.CharField(max_length=200, unique=True)
    original_name = models.CharField(max_length=200)
    content_type = models.CharField(max_length=80)
    size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    hr_only = models.BooleanField(default=False)
    superseded_by = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="supersedes")
    superseded_note = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["-uploaded_at", "-id"]

    def __str__(self):
        return self.title
```

- [ ] **Step 4: Service**

```python
# documents/services/files.py
"""The only writer of File rows and the only reader of their bytes."""
import hashlib
import uuid
import zipfile
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import FileResponse
from django.utils import timezone

from documents.models import File
from people.services import access, audit

TYPES = {  # sniffed kind -> (extension, content type)
    "pdf": ("pdf", "application/pdf"),
    "jpeg": ("jpg", "image/jpeg"),
    "png": ("png", "image/png"),
    "docx": ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
}
BY_EXTENSION = {"pdf": "pdf", "jpg": "jpeg", "jpeg": "jpeg", "png": "png", "docx": "docx"}
LABEL = {"pdf": "PDF", "jpeg": "JPEG", "png": "PNG", "docx": "DOCX"}


def sniff(upload):
    """What the bytes are, or ValidationError. The extension says what the
    file claims to be; the bytes must agree."""
    ext = Path(upload.name).suffix.lower().lstrip(".")
    claimed = BY_EXTENSION.get(ext)
    if claimed is None:
        raise ValidationError("Upload a PDF, JPEG, PNG or DOCX file.")
    if upload.size > settings.DOCUMENT_MAX_BYTES:
        raise ValidationError(f"That file is bigger than {settings.DOCUMENT_MAX_BYTES // (1024 * 1024)} MB.")
    upload.seek(0)
    head = upload.read(8)
    upload.seek(0)
    actual = None
    if head.startswith(b"%PDF-"):
        actual = "pdf"
    elif head.startswith(b"\xff\xd8\xff"):
        actual = "jpeg"
    elif head.startswith(b"\x89PNG\r\n\x1a\n"):
        actual = "png"
    elif head.startswith(b"PK"):
        try:
            with zipfile.ZipFile(upload) as z:
                if "[Content_Types].xml" in z.namelist() and any(n.startswith("word/") for n in z.namelist()):
                    actual = "docx"
        except zipfile.BadZipFile:
            actual = None
        upload.seek(0)
    if actual != claimed:
        raise ValidationError(f"This file is not a {LABEL[claimed]}.")
    return actual


def _store(upload, kind):
    ext, _ = TYPES[kind]
    rel = Path("documents") / str(timezone.localdate().year) / f"{uuid.uuid4().hex}.{ext}"
    target = Path(settings.MEDIA_ROOT) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with open(target, "wb") as out:
        for chunk in upload.chunks():
            digest.update(chunk)
            out.write(chunk)
    return str(rel), digest.hexdigest()


@transaction.atomic
def add(actor, employee, category, title, upload, hr_only=False):
    kind = sniff(upload)
    path, sha = _store(upload, kind)
    f = File(employee=employee, category=category, title=title, path=path, original_name=upload.name[:200],
             content_type=TYPES[kind][1], size=upload.size, sha256=sha, uploaded_by=actor, hr_only=hr_only)
    f.full_clean()
    f.save()
    audit.record(actor, f, {"added": ("", f"{f.get_category_display()}: {title}")})
    return f


@transaction.atomic
def supersede(actor, file, by, note):
    if file.superseded_by_id:
        raise ValidationError("Already superseded.")
    file.superseded_by = by
    file.superseded_note = note[:200]
    file.save(update_fields=["superseded_by", "superseded_note"])
    audit.record(actor, file, {"superseded_by": ("", by.pk)}, note=note[:200])
    return file


def open(actor, file):
    """The access rule, the audit row, the bytes. Every download uses this."""
    if not access.can_view_file(actor, file):
        raise PermissionDenied
    audit.viewed(actor, file, "file")
    response = FileResponse(open_bytes(file), content_type=file.content_type, as_attachment=True,
                            filename=file.original_name)
    return response


def open_bytes(file):
    return (Path(settings.MEDIA_ROOT) / file.path).open("rb")
```

`people/services/access.py`:

```python
def can_view_file(user, file):
    """HR always; the person their own unless HR-only; nobody else (managers
    never see documents)."""
    if can_view_restricted(user):
        return True
    me = employee_for(user)
    return me is not None and file.employee_id == me.pk and not file.hr_only
```

- [ ] **Step 5: View, URL, My record section, admin**

`documents/views.py`: `download(request, pk)` with `@login_required`, `get_object_or_404(File, pk=pk)`, `return files.open(request.user, f)` (PermissionDenied → 403 as Django does). `documents/urls.py` `app_name = "documents"`, `path("file/<int:pk>/", views.download, name="download")`. `people/views.py:me` adds `"files": e.files.filter(hr_only=False, superseded_by__isnull=True)` when the employee exists; `templates/people/_documents.html` lists title, category, date, a download link; included in `me.html` as a **Documents** card. Admin `documents/admin.py`: `FileAdmin(ModelAdmin)` with `list_display = ("title", "employee", "category", "uploaded_at", "hr_only")`, `list_filter = ("category", "hr_only")`, `search_fields` on employee names and title, `readonly_fields` everything but a `download` link; add page is a custom form (`documents/forms.py: UploadForm(employee, category, title, upload, hr_only)`) whose `save_model` calls `files.add`; change and delete refused. Settings: `DOCUMENT_MAX_BYTES = 10 * 1024 * 1024`. `hr/admin_site.py`: new group `{"title": "Compliance", "separator": True, "items": [_nav_item("Files", "folder", "admin:documents_file_changelist")]}` (later tasks add to it).

- [ ] **Step 6: Suite, ruff, migrations check; commit** `Documents: the file store, the files service, the audited download`.

---
## Task 4: Checks: types, records, status, pages

**Files:**
- Create: `checks/__init__.py`, `checks/apps.py`, `checks/models.py`, `checks/services/__init__.py`, `checks/services/checks.py`, `checks/admin.py`, `checks/forms.py`, `checks/views.py`, `checks/urls.py`, `checks/migrations/0001_initial.py`, `checks/migrations/0002_seed_types.py`, `templates/people/_checks.html`, `templates/people/_team_checks.html`
- Modify: `config/settings.py` (INSTALLED_APPS `checks`), `config/urls.py` (`path("checks/", include("checks.urls"))`), `people/services/access.py` (`can_view_checks`), `people/views.py` (`me`: checks rows; `team`: per-report summary), `templates/people/me.html`, `templates/people/team.html`, `hr/admin_site.py` (Compliance: "Check types", "Checks"), `docs/admin/compliance.md` (new; the checks part)
- Test: `tests/test_checks.py`

**Interfaces:**
- Consumes: `PositionTitle` (Task 1), `files.add` / `files.open` (Task 3).
- Produces: models `CheckType`, `Check`; `checks.required_for(employee, today) -> list[CheckType]`; `checks.state(employee, today, window_days=60) -> list[Row]` where `Row = dataclass(check_type, latest: Check|None, status: str, expires_on: date|None)` and `status ∈ {"current","due_soon","lapsed","missing","not_required","awaiting"}`; `checks.record(actor, employee, check_type, done_on, outcome, expires_on=None, reference="", note="", evidence=None, dbs_level="", dbs_update_service=False) -> Check`; `checks.ask(actor, employee, check_type) -> Check`; `checks.complete(actor, check, done_on, outcome, **fields) -> Check`; `checks.upload_evidence(actor, check, upload) -> Check`; `checks.summary(employee, today) -> dict(current, due_soon, lapsed, missing, next_expiry)`; a hook point `on_recorded(check)` that Task 6 wires to close linked checklist items (a module-level list `RECORDED_HOOKS` of callables; `record` and `complete` call each with the check when `outcome` is clear).
- URL names: `checks:upload` (`/checks/<pk>/upload/`, POST by the person on an awaiting check).

- [ ] **Step 1: Failing tests**

```python
# tests/test_checks.py
from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from checks.models import Check, CheckType
from checks.services import checks
from people.services import titles
from tests.factories import make_employee, make_employment, make_position

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def dbs():
    t = CheckType.objects.get(code="dbs")          # seeded
    t.positions.add(titles.get_or_create("Receptionist"))
    return t


def _receptionist(user=None):
    e = make_employee(user=user)
    emp = make_employment(e, start=timezone.localdate() - timedelta(days=400))
    make_position(emp, title="Receptionist")
    return e


def test_seeded_types_exist_with_the_spec_defaults():
    by = {t.code: t for t in CheckType.objects.all()}
    assert set(by) >= {"right_to_work", "dbs", "references", "occupational_health", "hep_b", "indemnity",
                       "professional_registration"}
    assert by["dbs"].validity_months == 36 and by["dbs"].remind_person and by["dbs"].evidence == "reference"
    assert by["right_to_work"].validity_months is None and by["right_to_work"].evidence == "file"
    assert by["references"].validity_months is None and by["references"].evidence == "none"


def test_required_follows_the_primary_position_title(dbs):
    e = _receptionist()
    assert [t.code for t in checks.required_for(e, timezone.localdate())] == ["dbs"]
    other = make_employee(first="Jo", last="Bloggs")
    make_position(make_employment(other, start=timezone.localdate() - timedelta(days=10)), title="Practice Nurse")
    assert checks.required_for(other, timezone.localdate()) == []


def test_status_missing_current_due_soon_lapsed(dbs, hr_admin):
    today = timezone.localdate()
    e = _receptionist()
    assert checks.state(e, today)[0].status == "missing"
    c = checks.record(hr_admin, e, dbs, today - timedelta(days=30), Check.Outcome.CLEAR, reference="001234567890",
                      dbs_level=Check.DbsLevel.ENHANCED)
    assert c.expires_on == today - timedelta(days=30) + timedelta(days=36 * 30)   # see expires_from
    assert checks.state(e, today)[0].status == "current"
    c.expires_on = today + timedelta(days=10); c.save()
    assert checks.state(e, today, window_days=60)[0].status == "due_soon"
    c.expires_on = today - timedelta(days=1); c.save()
    assert checks.state(e, today)[0].status == "lapsed"


def test_a_renewal_is_a_new_row_and_the_latest_wins(dbs, hr_admin):
    today = timezone.localdate()
    e = _receptionist()
    checks.record(hr_admin, e, dbs, today - timedelta(days=1200), Check.Outcome.CLEAR, reference="1", dbs_level="enhanced")
    checks.record(hr_admin, e, dbs, today - timedelta(days=5), Check.Outcome.CLEAR, reference="2", dbs_level="enhanced")
    assert Check.objects.filter(employee=e).count() == 2
    assert checks.state(e, today)[0].latest.reference == "2"


def test_dbs_needs_its_level_and_a_future_done_on_is_refused(dbs, hr_admin):
    today = timezone.localdate()
    e = _receptionist()
    with pytest.raises(ValidationError, match="disclosure level"):
        checks.record(hr_admin, e, dbs, today, Check.Outcome.CLEAR, reference="1")
    with pytest.raises(ValidationError, match="after today"):
        checks.record(hr_admin, e, dbs, today + timedelta(days=1), Check.Outcome.CLEAR, reference="1", dbs_level="basic")


def test_ask_then_the_person_uploads_then_hr_completes(hr_admin, employee_user):
    rtw = CheckType.objects.get(code="right_to_work")
    rtw.positions.add(titles.get_or_create("Receptionist"))
    e = _receptionist(user=employee_user)
    today = timezone.localdate()
    c = checks.ask(hr_admin, e, rtw)
    assert c.awaiting and checks.state(e, today)[0].status == "awaiting"
    checks.upload_evidence(employee_user, c, SimpleUploadedFile("passport.pdf", PDF, content_type="application/pdf"))
    c.refresh_from_db()
    assert c.evidence is not None and c.evidence.category == "identity"
    with pytest.raises(PermissionDenied):
        checks.upload_evidence(employee_user, Check.objects.create(employee=make_employee(first="Jo", last="B"),
                                                                   check_type=rtw, awaiting=True), SimpleUploadedFile("p.pdf", PDF))
    done = checks.complete(hr_admin, c, today, Check.Outcome.CLEAR)
    assert not done.awaiting and checks.state(e, today)[0].status == "current"


def test_a_type_no_longer_required_is_kept_but_not_chased(dbs, hr_admin):
    today = timezone.localdate()
    e = _receptionist()
    checks.record(hr_admin, e, dbs, today - timedelta(days=5), Check.Outcome.CLEAR, reference="1", dbs_level="basic")
    dbs.positions.clear()
    rows = checks.state(e, today)
    assert [r.status for r in rows] == ["not_required"]


def test_pages_by_role(dbs, hr_admin, employee_user, employee_client, admin_client, client):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    checks.record(hr_admin, e, dbs, today - timedelta(days=5), Check.Outcome.CLEAR, reference="9", dbs_level="basic",
                  note="HR only note")
    body = employee_client.get("/people/me/").content.decode()
    assert "DBS" in body and "Current" in body and "HR only note" not in body
    mgr_user = type(employee_user).objects.create_user(email="mo@example.com", password="pw")
    mgr = make_employee(first="Mo", last="Khan", user=mgr_user)
    pos = e.employments.first().positions.first(); pos.line_manager = mgr; pos.save()
    client.force_login(mgr_user)
    body = client.get("/people/team/").content.decode()
    assert "1 current" in body and "9" not in body
```

- [ ] **Step 2: Run, see them fail.**

- [ ] **Step 3: Models and seed**

```python
# checks/models.py
from django.conf import settings
from django.db import models


class CheckType(models.Model):
    class Evidence(models.TextChoices):
        NONE = "none", "Nothing to attach"
        FILE = "file", "A file"
        REFERENCE = "reference", "A reference number"

    name = models.CharField(max_length=60, unique=True)
    code = models.SlugField(max_length=40, unique=True)
    validity_months = models.PositiveSmallIntegerField(null=True, blank=True,
                                                       help_text="Blank: a one-off check that never expires.")
    evidence = models.CharField(max_length=9, choices=Evidence.choices, default=Evidence.NONE)
    remind_person = models.BooleanField(default=False, help_text="Remind the person as well as HR.")
    positions = models.ManyToManyField("people.PositionTitle", blank=True, related_name="check_types",
                                       help_text="The titles that need this check.")
    display_order = models.PositiveIntegerField(default=100)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class Check(models.Model):
    class Outcome(models.TextChoices):
        CLEAR = "clear", "Clear"
        CLEAR_WITH_NOTES = "clear_with_notes", "Clear with notes"
        NOT_CLEAR = "not_clear", "Not clear"

    class DbsLevel(models.TextChoices):
        BASIC = "basic", "Basic"
        STANDARD = "standard", "Standard"
        ENHANCED = "enhanced", "Enhanced"
        ENHANCED_BARRED = "enhanced_barred", "Enhanced with barred lists"

    employee = models.ForeignKey("people.Employee", on_delete=models.PROTECT, related_name="checks")
    check_type = models.ForeignKey(CheckType, on_delete=models.PROTECT, related_name="checks")
    done_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    outcome = models.CharField(max_length=16, choices=Outcome.choices, blank=True, default="")
    reference = models.CharField(max_length=60, blank=True, default="")
    note = models.TextField(blank=True, default="")
    evidence = models.ForeignKey("documents.File", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    dbs_level = models.CharField(max_length=15, choices=DbsLevel.choices, blank=True, default="")
    dbs_update_service = models.BooleanField(default=False)
    awaiting = models.BooleanField(default=False, help_text="Asked of the person; not yet a recorded check.")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-done_on", "-id"]

    def __str__(self):
        return f"{self.check_type} for {self.employee}"
```

Seed migration `0002_seed_types.py` (`RunPython`, reverse deletes by code): Right to work (`right_to_work`, file, remind, 10), DBS (`dbs`, reference, 36 months, remind, 20), References (`references`, none, 30), Occupational health (`occupational_health`, file, 40), Hep B immunity (`hep_b`, file, 50), Indemnity (`indemnity`, file, 12 months, 60), Professional registration (`professional_registration`, reference, 12 months, 70). No positions assigned: HR assigns them in the admin (documented).

- [ ] **Step 4: Service**

```python
# checks/services/checks.py
from dataclasses import dataclass
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from checks.models import Check, CheckType
from documents.models import File
from documents.services import files
from people.services import access, audit, employments, positions

RECORDED_HOOKS = []          # callables(check) run after a clear check is recorded or completed
CLEAR = (Check.Outcome.CLEAR, Check.Outcome.CLEAR_WITH_NOTES)


@dataclass
class Row:
    check_type: CheckType
    latest: Check | None
    status: str
    expires_on: object


def expires_from(done_on, check_type):
    """done_on plus validity_months, month arithmetic clipped to the month's end; None for one-off."""
    if check_type.validity_months is None:
        return None
    month = done_on.month - 1 + check_type.validity_months
    year = done_on.year + month // 12
    month = month % 12 + 1
    import calendar
    day = min(done_on.day, calendar.monthrange(year, month)[1])
    return done_on.replace(year=year, month=month, day=day)


def required_for(employee, today):
    emp = employments.current(employee, today)
    if emp is None:
        return []
    pos = positions.primary_on(emp, today)
    if pos is None:
        return []
    return list(CheckType.objects.filter(active=True, positions=pos.title).order_by("display_order", "name"))


def _status(latest, required, today, window_days):
    if not required:
        return "not_required"
    if latest is None:
        return "missing"
    if latest.awaiting:
        return "awaiting"
    if latest.outcome not in CLEAR:
        return "missing"
    if latest.expires_on is None:
        return "current"
    if latest.expires_on < today:
        return "lapsed"
    if latest.expires_on <= today + timedelta(days=window_days):
        return "due_soon"
    return "current"


def state(employee, today, window_days=60):
    required = required_for(employee, today)
    seen = {t.pk: t for t in required}
    rows = []
    for t in required + [c.check_type for c in Check.objects.filter(employee=employee).select_related("check_type")
                         if c.check_type_id not in seen and not seen.setdefault(c.check_type_id, c.check_type)]:
        latest = (Check.objects.filter(employee=employee, check_type=t)
                  .order_by("awaiting", "-done_on", "-id").first())
        rows.append(Row(t, latest, _status(latest, t in required, today, window_days),
                        latest.expires_on if latest else None))
    return rows


def summary(employee, today, window_days=60):
    rows = state(employee, today, window_days)
    counts = {k: sum(1 for r in rows if r.status == k) for k in ("current", "due_soon", "lapsed", "missing")}
    expiries = [r.expires_on for r in rows if r.expires_on and r.status in ("current", "due_soon")]
    counts["next_expiry"] = min(expiries) if expiries else None
    return counts


def _validate(check_type, done_on, outcome, fields, today):
    if done_on > today:
        raise ValidationError("The date done cannot be after today.")
    if outcome not in Check.Outcome.values:
        raise ValidationError("Choose an outcome.")
    if check_type.code == "dbs" and outcome in CLEAR and not fields.get("dbs_level"):
        raise ValidationError("A DBS check needs its disclosure level.")
    if check_type.evidence == CheckType.Evidence.REFERENCE and outcome in CLEAR and not fields.get("reference"):
        raise ValidationError(f"{check_type} needs its reference number.")


def _after(check):
    if check.outcome in CLEAR:
        for hook in RECORDED_HOOKS:
            hook(check)


@transaction.atomic
def record(actor, employee, check_type, done_on, outcome, expires_on=None, **fields):
    today = timezone.localdate()
    _validate(check_type, done_on, outcome, fields, today)
    c = Check(employee=employee, check_type=check_type, done_on=done_on, outcome=outcome,
              expires_on=expires_on or expires_from(done_on, check_type), recorded_by=actor, **fields)
    c.full_clean()
    c.save()
    audit.record(actor, c, {"recorded": ("", f"{check_type}: {c.get_outcome_display()}, done {done_on:%d %b %Y}")})
    _after(c)
    return c


@transaction.atomic
def ask(actor, employee, check_type):
    if Check.objects.filter(employee=employee, check_type=check_type, awaiting=True).exists():
        raise ValidationError("Already asked.")
    c = Check.objects.create(employee=employee, check_type=check_type, awaiting=True, recorded_by=actor)
    audit.record(actor, c, {"asked": ("", str(check_type))})
    return c


@transaction.atomic
def upload_evidence(actor, check, upload):
    me = access.employee_for(actor)
    own = me is not None and me.pk == check.employee_id
    if not (own or access.can_view_restricted(actor)):
        raise PermissionDenied
    if own and not check.awaiting:
        raise ValidationError("This check is not waiting for anything from you.")
    category = File.Category.IDENTITY if check.check_type.code == "right_to_work" else File.Category.CERTIFICATE
    f = files.add(actor, check.employee, category, f"{check.check_type} evidence", upload)
    check.evidence = f
    check.save(update_fields=["evidence"])
    audit.record(actor, check, {"evidence": ("", f.pk)})
    return check


@transaction.atomic
def complete(actor, check, done_on, outcome, expires_on=None, **fields):
    if not check.awaiting:
        raise ValidationError("Only a check still waiting can be completed.")
    today = timezone.localdate()
    _validate(check.check_type, done_on, outcome, fields, today)
    for k, v in fields.items():
        setattr(check, k, v)
    check.done_on, check.outcome = done_on, outcome
    check.expires_on = expires_on or expires_from(done_on, check.check_type)
    check.awaiting, check.recorded_by = False, actor
    check.full_clean()
    check.save()
    audit.record(actor, check, {"completed": ("", f"{check.check_type}: {check.get_outcome_display()}")})
    _after(check)
    return check
```

`access.can_view_checks(user, employee)`: HR always; the person themselves; managers only through `summary` (the view, not the detail).

- [ ] **Step 5: Pages and admin**

`people/views.py:me` adds `"checks": checks.state(employee, today)` and `templates/people/_checks.html` renders a **Checks** card: type, status badge (Current / Due soon / Lapsed / Missing / Awaiting), done and expiry dates, outcome; for an awaiting row a one-field upload form posting to `checks:upload`. HR's `note` is never rendered on this page. `people/views.py:team` adds per report `checks.summary(report.employee, today)` and `templates/people/_team_checks.html` shows "N current, N due soon, N lapsed, N missing; next expiry dd Mon yyyy" (no type names). `checks/views.py:upload` (`@login_required`, `@require_POST`): `checks.upload_evidence(request.user, check, request.FILES["file"])`, `messages`, redirect to My record; ValidationError → `messages.error`.

Admin (`checks/admin.py`): `CheckTypeAdmin` (list name, validity, evidence, remind_person, positions filter_horizontal, active); `CheckAdmin`: list employee, type, done_on, expires_on, outcome, awaiting; filters type, outcome, awaiting; search employee names; the add page is `checks/forms.py: RecordForm` (employee, check_type, done_on, outcome, expires_on, reference, note, evidence upload, dbs_level, dbs_update_service) whose `save_model` calls `checks.record` (with `files.add` for the upload); a detail action **Ask the person for evidence** calling `checks.ask`; existing rows are read-only (append-only), delete refused; evidence shown as a `documents:download` link. `hr/admin_site.py` Compliance group: "Check types" (`admin:checks_checktype_changelist`), "Checks" (`admin:checks_check_changelist`).

- [ ] **Step 6: Suite, ruff, migrations; docs; commit** `Checks: types by position title, append-only checks, status, pages`. Docs: start `docs/admin/compliance.md` with a "Checks" section (types, fields, what each status means, asking for evidence, the DBS rule on not storing certificates) and add the page to `docs/admin/README.md`.

---

## Task 5: Policies, versions and signatures with re-authentication

**Files:**
- Create: `documents/services/policies.py`, `templates/documents/policies.html`, `templates/documents/sign.html`, `documents/forms.py` (add `SignForm`), `documents/migrations/0002_policies.py`
- Modify: `documents/models.py` (Policy, PolicyVersion, Signature), `documents/views.py`, `documents/urls.py`, `documents/admin.py`, `templates/base.html` (nav **Policies**, desktop and More sheet), `hr/admin_site.py` (Compliance: "Policies", "Signatures"), `docs/admin/compliance.md`
- Test: `tests/test_policies.py`

**Interfaces:**
- Consumes: `files.add(actor, None, File.Category.POLICY, title, upload)`; `accounts.recent_auth.confirm_password(request, password)`; `accounts.passkeys.verify_login(request, credential)` and `login_options(request)`.
- Produces: `policies.issue(actor, policy, label, upload, issued_on, sign_within_days) -> PolicyVersion`; `policies.applies_to(employee, today) -> list[Policy]`; `policies.owed(employee, today) -> list[Owed]` (`Owed = dataclass(version, due_on, state)` with state `awaiting`/`overdue`); `policies.sign(actor, version, method, ip) -> Signature` (the view does the re-authentication; the service asserts `method in ("password", "passkey")` and that the actor is the person); `policies.state(employee, today) -> list[dict(policy, version, signature|None, due_on, status)]`; hook list `SIGNED_HOOKS` of callables(employee) run after every signature. URL names `documents:policies` (`/documents/policies/`), `documents:sign` (`/documents/policies/<version pk>/sign/`), `documents:passkey_options` (`/documents/policies/passkey-options/`, GET JSON for the sign page's passkey button).

- [ ] **Step 1: Failing tests**

```python
# tests/test_policies.py
from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from documents.models import Policy, Signature
from documents.services import policies
from people.services import titles
from tests.factories import make_employee, make_employment, make_position

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


def _policy(hr_admin, title="Information governance", positions=(), label="v1", days=14):
    p = Policy.objects.create(title=title)
    for name in positions:
        p.positions.add(titles.get_or_create(name))
    policies.issue(hr_admin, p, label, SimpleUploadedFile("ig.pdf", PDF, content_type="application/pdf"),
                   timezone.localdate(), days)
    return p


def _staff(user=None, title="Receptionist", start_offset=-100):
    e = make_employee(user=user)
    make_position(make_employment(e, start=timezone.localdate() + timedelta(days=start_offset)), title=title)
    return e


def test_a_policy_with_no_positions_applies_to_everyone_and_is_owed(hr_admin):
    p = _policy(hr_admin)
    e = _staff()
    today = timezone.localdate()
    assert policies.applies_to(e, today) == [p]
    owed = policies.owed(e, today)
    assert len(owed) == 1 and owed[0].state == "awaiting" and owed[0].due_on == today + timedelta(days=14)


def test_a_policy_by_title_applies_only_to_that_title(hr_admin):
    _policy(hr_admin, positions=["Practice Nurse"])
    assert policies.owed(_staff(title="Receptionist"), timezone.localdate()) == []
    assert len(policies.owed(_staff(title="Practice Nurse"), timezone.localdate())) == 1


def test_signing_records_the_exact_sentence_and_closes_the_debt(hr_admin, employee_user):
    p = _policy(hr_admin)
    e = _staff(user=employee_user)
    v = p.versions.get()
    s = policies.sign(employee_user, v, "password", "203.0.113.5")
    assert s.confirmation_text == "I confirm I have read and understood Information governance (v1)."
    assert s.method == "password" and policies.owed(e, timezone.localdate()) == []
    with pytest.raises(ValidationError, match="already signed"):
        policies.sign(employee_user, v, "password", "")
    s.confirmation_text = "x"
    with pytest.raises(ValidationError):
        s.save()


def test_only_the_person_signs_for_themselves(hr_admin, employee_user):
    p = _policy(hr_admin)
    _staff(user=employee_user)
    with pytest.raises(PermissionDenied):
        policies.sign(hr_admin, p.versions.get(), "password", "")


def test_a_new_version_is_owed_again_and_the_old_one_never_is(hr_admin, employee_user):
    p = _policy(hr_admin)
    e = _staff(user=employee_user)
    v1 = p.versions.get()
    policies.sign(employee_user, v1, "password", "")
    policies.issue(hr_admin, p, "v2", SimpleUploadedFile("ig2.pdf", PDF, content_type="application/pdf"),
                   timezone.localdate(), 14)
    owed = policies.owed(e, timezone.localdate())
    assert [o.version.label for o in owed] == ["v2"]
    unsigned = make_employee(first="Jo", last="Bloggs")
    make_position(make_employment(unsigned, start=timezone.localdate() - timedelta(days=5)), title="Receptionist")
    assert [o.version.label for o in policies.owed(unsigned, timezone.localdate())] == ["v2"]


def test_overdue_after_the_sign_by_period_and_a_starter_counts_from_their_start(hr_admin):
    today = timezone.localdate()
    p = _policy(hr_admin, days=7)
    v = p.versions.get(); v.issued_on = today - timedelta(days=10); v.save()
    assert policies.owed(_staff(), today)[0].state == "overdue"
    starter = _staff(start_offset=5)
    o = policies.owed(starter, today)[0]
    assert o.state == "awaiting" and o.due_on == today + timedelta(days=5 + 7)


def test_sign_page_needs_the_password_and_a_wrong_one_writes_nothing(hr_admin, employee_user, employee_client):
    p = _policy(hr_admin)
    _staff(user=employee_user)
    v = p.versions.get()
    body = employee_client.get(f"/documents/policies/{v.pk}/sign/").content.decode()
    assert "I confirm I have read and understood" in body and 'name="password"' in body
    r = employee_client.post(f"/documents/policies/{v.pk}/sign/", {"confirm": "on", "password": "wrong"})
    assert r.status_code == 200 and Signature.objects.count() == 0
    r = employee_client.post(f"/documents/policies/{v.pk}/sign/", {"confirm": "on", "password": "pw"})
    assert r.status_code == 302 and Signature.objects.get().method == "password"


def test_policies_page_lists_state(hr_admin, employee_user, employee_client):
    p = _policy(hr_admin)
    _staff(user=employee_user)
    body = employee_client.get("/documents/policies/").content.decode()
    assert "Information governance" in body and "Awaiting signature" in body and "Sign" in body
```

- [ ] **Step 2: Run, see them fail.**

- [ ] **Step 3: Models** (append to `documents/models.py`; migration `0002_policies.py`)

```python
class Policy(models.Model):
    title = models.CharField(max_length=120, unique=True)
    positions = models.ManyToManyField("people.PositionTitle", blank=True, related_name="policies",
                                       help_text="Leave empty for everyone.")
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "policies"
        ordering = ["title"]

    def __str__(self):
        return self.title


class PolicyVersion(models.Model):
    policy = models.ForeignKey(Policy, on_delete=models.PROTECT, related_name="versions")
    label = models.CharField(max_length=40)
    file = models.ForeignKey(File, on_delete=models.PROTECT, related_name="+")
    issued_on = models.DateField()
    sign_within_days = models.PositiveSmallIntegerField(default=14)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-issued_on", "-id"]
        constraints = [models.UniqueConstraint(fields=["policy", "label"], name="one_label_per_policy")]

    def __str__(self):
        return f"{self.policy} ({self.label})"


class Signature(models.Model):
    class Method(models.TextChoices):
        PASSWORD = "password", "Password"
        PASSKEY = "passkey", "Passkey"

    employee = models.ForeignKey("people.Employee", on_delete=models.PROTECT, related_name="signatures")
    version = models.ForeignKey(PolicyVersion, on_delete=models.PROTECT, related_name="signatures")
    signed_at = models.DateTimeField(auto_now_add=True)
    method = models.CharField(max_length=8, choices=Method.choices)
    confirmation_text = models.CharField(max_length=300)
    ip_address = models.CharField(max_length=45, blank=True, default="")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["employee", "version"], name="one_signature_per_version")]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("A signature is never changed.")
        super().save(*args, **kwargs)
```

- [ ] **Step 4: Service**

```python
# documents/services/policies.py
from dataclasses import dataclass
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from documents.models import File, Policy, PolicyVersion, Signature
from documents.services import files
from people.services import access, audit, employments, positions

SIGNED_HOOKS = []
SENTENCE = "I confirm I have read and understood {title} ({label})."


@dataclass
class Owed:
    version: PolicyVersion
    due_on: object
    state: str


def confirmation(version):
    return SENTENCE.format(title=version.policy.title, label=version.label)


@transaction.atomic
def issue(actor, policy, label, upload, issued_on, sign_within_days):
    f = files.add(actor, None, File.Category.POLICY, f"{policy.title} {label}", upload)
    v = PolicyVersion(policy=policy, label=label, file=f, issued_on=issued_on,
                      sign_within_days=sign_within_days, issued_by=actor)
    v.full_clean()
    v.save()
    audit.record(actor, policy, {"issued": ("", label)})
    return v


def current(policy):
    return policy.versions.order_by("-issued_on", "-id").first()


def applies_to(employee, today):
    emp = employments.current(employee, today) or employee.employments.filter(start_date__gt=today).order_by("start_date").first()
    if emp is None:
        return []
    pos = positions.primary_on(emp, emp.start_date if emp.start_date > today else today)
    qs = Policy.objects.filter(active=True)
    out = []
    for p in qs.prefetch_related("positions"):
        titles = list(p.positions.all())
        if not titles or (pos is not None and pos.title in titles):
            out.append(p)
    return out


def _due(version, employee, today):
    emp = employments.current(employee, today) or employee.employments.filter(start_date__gt=today).order_by("start_date").first()
    base = max(version.issued_on, emp.start_date) if emp and emp.start_date > version.issued_on else version.issued_on
    return base + timedelta(days=version.sign_within_days)


def owed(employee, today):
    out = []
    for p in applies_to(employee, today):
        v = current(p)
        if v is None or Signature.objects.filter(employee=employee, version=v).exists():
            continue
        due = _due(v, employee, today)
        out.append(Owed(v, due, "overdue" if today > due else "awaiting"))
    return out


def state(employee, today):
    rows = []
    for p in applies_to(employee, today):
        v = current(p)
        if v is None:
            continue
        s = Signature.objects.filter(employee=employee, version=v).first()
        due = _due(v, employee, today)
        status = "signed" if s else ("overdue" if today > due else "awaiting")
        rows.append({"policy": p, "version": v, "signature": s, "due_on": due, "status": status})
    return rows


@transaction.atomic
def sign(actor, version, method, ip):
    me = access.employee_for(actor)
    if me is None:
        raise PermissionDenied
    if method not in Signature.Method.values:
        raise ValueError(method)
    if Signature.objects.filter(employee=me, version=version).exists():
        raise ValidationError("You have already signed this version.")
    s = Signature(employee=me, version=version, method=method, confirmation_text=confirmation(version), ip_address=ip or "")
    s.full_clean()
    s.save()
    audit.record(actor, s, {"signed": ("", str(version))})
    for hook in SIGNED_HOOKS:
        hook(me)
    return s
```

- [ ] **Step 5: Views, templates, nav, admin**

`documents/views.py`:
- `policies_page` (`@login_required`, GET): `policies.state(me, today)` → `templates/documents/policies.html`: a table of policy, version, status badge (Signed on …, Awaiting signature, Overdue), a **Read** link to `documents:download` for the version's file (allowed for anyone the policy applies to: extend `access.can_view_file` so a `File` with `category == POLICY` is viewable by any signed-in employee), and **Sign** for unsigned ones.
- `sign` (`@login_required`): GET renders `templates/documents/sign.html`: the Read link, the confirmation sentence as the label of a required checkbox `confirm`, a `password` field, and a **Sign with a passkey** button (hidden by JS when the browser has no `PublicKeyCredential`, exactly as the account page does, posting the assertion JSON in a hidden `credential` field). POST: require `confirm`; if `credential` present → `accounts.passkeys.verify_login(request, credential)` must return the signed-in user, method `passkey`; else `recent_auth.confirm_password(request, password)` must be True, method `password`; on failure re-render with the error "That password is not right." (or the passkey error) and status 200, nothing written; on success `policies.sign(request.user, version, method, client_ip(request))`, `messages.success`, redirect to `documents:policies`. Refuse (404) a version that does not apply to the person.
- `passkey_options` (GET JSON): `accounts.passkeys.login_options(request)` for the sign page's button (reuse the existing `static/js/passkeys.js` flow; add a small `static/documents/sign.js` that wires the button, allowed by the CSP as a static script).

`templates/base.html`: **Policies** link (`documents:policies`) after Balances on desktop and in the More sheet on phones. Admin: `PolicyAdmin` (title, positions filter_horizontal, active; `PolicyVersionInline` read-only listing label, issued_on, sign_within_days, download link; a detail action **Issue new version** opening a form (label, issued_on, sign_within_days, upload) that calls `policies.issue`); `SignatureAdmin` read-only (employee, version, signed_at, method). `hr/admin_site.py` Compliance: "Policies" (`admin:documents_policy_changelist`), "Signatures" (`admin:documents_signature_changelist`).

- [ ] **Step 6: Suite, ruff, migrations; docs; commit** `Policies: versions, re-signing, signatures with re-authentication`. Docs: `compliance.md` "Policies" section (who must sign, issuing a version, what a signature records, re-authentication); the plain-language "How to issue a policy" goes in Task 9.

---
## Task 6: Checklists: templates, instances, owners, linked items, hooks from employments

**Files:**
- Create: `onboarding/__init__.py`, `onboarding/apps.py`, `onboarding/models.py`, `onboarding/services/__init__.py`, `onboarding/services/checklists.py`, `onboarding/migrations/0001_initial.py`, `onboarding/migrations/0002_seed_templates.py`, `onboarding/admin.py`
- Modify: `config/settings.py` (INSTALLED_APPS `onboarding`), `people/services/employments.py:55,110` (`start` and `end` call the checklist service inside the same transaction), `checks/services/checks.py` and `documents/services/policies.py` and `documents/services/files.py` (register the hooks in `onboarding/apps.py:ready`), `hr/admin_site.py` (Compliance: "Checklist templates", "Checklists"), `docs/admin/compliance.md`
- Test: `tests/test_onboarding.py`

**Interfaces:**
- Consumes: `PositionTitle`; `positions.primary_on`, `access.line_manager`; `checks.RECORDED_HOOKS`, `policies.SIGNED_HOOKS`; `files.add` (Task 7 wires an upload hook by calling `checklists.linked_done` from its view; Task 6 registers `FILE_HOOKS` in `files.add` — add a `ADDED_HOOKS` list to `documents/services/files.py` called with the file after `add`).
- Produces: models `ChecklistTemplate`, `TemplateItem`, `Checklist`, `ChecklistItem`; `checklists.start(actor, employment) -> Checklist|None` (None when the start is more than 30 days ago); `checklists.leave(actor, employment) -> Checklist`; `checklists.complete(actor, item, note="")`; `checklists.not_needed(actor, item, note)`; `checklists.add_item(actor, checklist, title, instruction, owner, due_on, link="")`; `checklists.remove_item(actor, item)`; `checklists.linked_done(employee, link_prefix, *, category=None, check_code=None)`; `checklists.open_items(employee, today)`; `checklists.items_owned_by(manager_employee, today)`; `checklists.summary(checklist) -> dict(total, done, open, overdue, oldest_overdue: ChecklistItem|None)`; `checklists.gaps(checklist) -> list[str]`; `checklists.may_complete(user, item) -> bool`.
- Link strings: `""`, `"details"`, `"upload:<category>"`, `"sign_policies"`, `"check:<check type code>"`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_onboarding.py
from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from checks.models import Check, CheckType
from checks.services import checks
from documents.models import File, Policy
from documents.services import files, policies
from onboarding.models import Checklist, ChecklistItem, ChecklistTemplate
from onboarding.services import checklists
from people.services import employments, positions, titles
from tests.factories import make_employee, make_team

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


def _starter(hr_admin, days_ahead=10, manager=None, title="Receptionist"):
    e = make_employee()
    start = timezone.localdate() + timedelta(days=days_ahead)
    emp = employments.start(hr_admin, e, start)
    positions.add(hr_admin, emp, titles.get_or_create(title), make_team(), manager, start)
    return emp


def test_seeded_default_templates_exist():
    kinds = {t.kind: t for t in ChecklistTemplate.objects.filter(positions=None)}
    assert set(kinds) == {"starter", "leaver"}
    starter = list(kinds["starter"].items.order_by("order"))
    assert [i.link for i in starter[:3]] == ["details", "sign_policies", "upload:identity"]
    assert {i.owner for i in starter} == {"hr", "manager", "person"}


def test_a_new_employment_gets_a_starter_checklist_with_owners_and_dates(hr_admin):
    mgr = make_employee(first="Mo", last="Khan")
    emp = _starter(hr_admin, manager=mgr)
    cl = Checklist.objects.get(employment=emp, kind="starter")
    items = list(cl.items.order_by("order"))
    assert len(items) == ChecklistTemplate.objects.get(kind="starter", positions=None).items.count()
    first = items[0]
    assert first.owner == "person" and first.owner_employee == emp.employee
    manager_item = next(i for i in items if i.owner == "manager")
    assert manager_item.owner_employee == mgr
    assert all(i.due_on is not None for i in items)
    assert checklists.gaps(cl) == []


def test_a_starter_without_a_manager_is_a_gap_not_a_failure(hr_admin):
    emp = _starter(hr_admin, manager=None)
    cl = Checklist.objects.get(employment=emp)
    assert any(i.owner == "manager" and i.owner_employee is None for i in cl.items.all())
    assert "no line manager" in " ".join(checklists.gaps(cl))


def test_a_title_template_beats_the_default_and_an_old_start_gets_none(hr_admin):
    t = ChecklistTemplate.objects.create(kind="starter", name="Nurse starter")
    t.positions.add(titles.get_or_create("Practice Nurse"))
    t.items.create(order=1, title="Hep B status", owner="hr", due_rule="after_start", due_days=7, link="check:hep_b")
    emp = _starter(hr_admin, title="Practice Nurse")
    assert Checklist.objects.get(employment=emp).template == t
    old = _starter(hr_admin, days_ahead=-60)
    assert not Checklist.objects.filter(employment=old).exists()


def test_leaving_makes_a_leaver_checklist(hr_admin):
    emp = _starter(hr_admin, days_ahead=-200)
    employments.end(hr_admin, emp, timezone.localdate() + timedelta(days=20), "resigned")
    cl = Checklist.objects.get(employment=emp, kind="leaver")
    assert cl.items.filter(due_rule="before_end").exists() or cl.items.exists()


def test_who_completes_what(hr_admin, employee_user):
    mgr_user = type(employee_user).objects.create_user(email="mo@example.com", password="pw")
    mgr = make_employee(first="Mo", last="Khan", user=mgr_user)
    emp = _starter(hr_admin, manager=mgr)
    emp.employee.user = employee_user; emp.employee.save()
    cl = Checklist.objects.get(employment=emp)
    mine = cl.items.filter(owner="person").first()
    theirs = cl.items.filter(owner="manager").first()
    hrs = cl.items.filter(owner="hr").first()
    assert checklists.may_complete(employee_user, mine) and not checklists.may_complete(employee_user, theirs)
    assert checklists.may_complete(mgr_user, theirs) and not checklists.may_complete(mgr_user, hrs)
    assert checklists.may_complete(hr_admin, hrs) and checklists.may_complete(hr_admin, theirs)
    checklists.complete(mgr_user, theirs, "done at induction")
    theirs.refresh_from_db()
    assert theirs.state == "done" and theirs.done_by == mgr_user and theirs.done_at
    with pytest.raises(PermissionDenied):
        checklists.complete(employee_user, hrs)
    with pytest.raises(ValidationError):
        checklists.not_needed(hr_admin, hrs, "")
    checklists.not_needed(hr_admin, hrs, "covered by agency")
    hrs.refresh_from_db(); assert hrs.state == "not_needed"


def test_linked_items_close_themselves(hr_admin, employee_user):
    emp = _starter(hr_admin)
    e = emp.employee; e.user = employee_user; e.save()
    cl = Checklist.objects.get(employment=emp)
    rtw = CheckType.objects.get(code="right_to_work"); rtw.positions.add(titles.get_or_create("Receptionist"))
    upload = cl.items.get(link="upload:identity")
    files.add(hr_admin, e, File.Category.IDENTITY, "Passport", SimpleUploadedFile("p.pdf", PDF, content_type="application/pdf"))
    upload.refresh_from_db(); assert upload.state == "done"
    sign = cl.items.get(link="sign_policies")
    checklists.linked_done(e, "sign_policies")          # no policies owed → closes
    sign.refresh_from_db(); assert sign.state == "done"
    dbs = cl.items.get(link="check:dbs")
    t = CheckType.objects.get(code="dbs"); t.positions.add(titles.get_or_create("Receptionist"))
    checks.record(hr_admin, e, t, timezone.localdate(), Check.Outcome.CLEAR, reference="1", dbs_level="basic")
    dbs.refresh_from_db(); assert dbs.state == "done"


def test_summary_and_completion(hr_admin):
    emp = _starter(hr_admin)
    cl = Checklist.objects.get(employment=emp)
    for item in cl.items.all():
        checklists.complete(hr_admin, item)
    cl.refresh_from_db()
    assert cl.completed_at is not None and checklists.summary(cl)["open"] == 0
```

- [ ] **Step 2: Run, see them fail.**

- [ ] **Step 3: Models and seed**

```python
# onboarding/models.py
from django.conf import settings
from django.db import models


class Kind(models.TextChoices):
    STARTER = "starter", "Starter"
    LEAVER = "leaver", "Leaver"


class Owner(models.TextChoices):
    HR = "hr", "HR"
    MANAGER = "manager", "Line manager"
    PERSON = "person", "The person"


class DueRule(models.TextChoices):
    BEFORE_START = "before_start", "Days before the start date"
    AFTER_START = "after_start", "Days after the start date"
    BEFORE_END = "before_end", "Days before the leaving date"
    AFTER_END = "after_end", "Days after the leaving date"


class ChecklistTemplate(models.Model):
    kind = models.CharField(max_length=7, choices=Kind.choices)
    name = models.CharField(max_length=80)
    positions = models.ManyToManyField("people.PositionTitle", blank=True, related_name="checklist_templates",
                                       help_text="Leave empty for the default of its kind.")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["kind", "name"]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.name}"


class TemplateItem(models.Model):
    template = models.ForeignKey(ChecklistTemplate, on_delete=models.CASCADE, related_name="items")
    order = models.PositiveSmallIntegerField(default=10)
    title = models.CharField(max_length=120)
    instruction = models.TextField(blank=True, default="")
    owner = models.CharField(max_length=7, choices=Owner.choices)
    due_rule = models.CharField(max_length=12, choices=DueRule.choices)
    due_days = models.PositiveSmallIntegerField(default=0)
    link = models.CharField(max_length=40, blank=True, default="",
                            help_text='"details", "upload:<category>", "sign_policies", "check:<check code>" or blank.')

    class Meta:
        ordering = ["order", "id"]


class Checklist(models.Model):
    employment = models.ForeignKey("people.Employment", on_delete=models.PROTECT, related_name="checklists")
    kind = models.CharField(max_length=7, choices=Kind.choices)
    template = models.ForeignKey(ChecklistTemplate, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    completed_at = models.DateTimeField(null=True, blank=True)
    gaps = models.TextField(blank=True, default="", help_text="One line per set-up problem found when created.")

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["employment", "kind"], name="one_checklist_per_kind")]


class ChecklistItem(models.Model):
    class State(models.TextChoices):
        OPEN = "open", "Open"
        DONE = "done", "Done"
        NOT_NEEDED = "not_needed", "Not needed"

    checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name="items")
    order = models.PositiveSmallIntegerField(default=10)
    title = models.CharField(max_length=120)
    instruction = models.TextField(blank=True, default="")
    owner = models.CharField(max_length=7, choices=Owner.choices)
    owner_employee = models.ForeignKey("people.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    due_on = models.DateField()
    due_rule = models.CharField(max_length=12, choices=DueRule.choices, blank=True, default="")
    link = models.CharField(max_length=40, blank=True, default="")
    state = models.CharField(max_length=10, choices=State.choices, default=State.OPEN)
    done_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    done_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["due_on", "order", "id"]
```

Seed `0002_seed_templates.py` (RunPython, reverse deletes the two default templates). Starter, default, items in order: 1 "Complete your details" person, before_start 7, `details`; 2 "Read and sign the practice policies" person, after_start 14, `sign_policies`; 3 "Upload your right-to-work document" person, before_start 7, `upload:identity`; 4 "References received" hr, before_start 7; 5 "DBS check recorded" hr, after_start 0, `check:dbs`; 6 "Occupational health clearance" hr, before_start 0, `check:occupational_health`; 7 "Contract issued" hr, before_start 14, `upload:contract`; 8 "Induction completed" manager, after_start 5; 9 "Clinical and practice systems access set up" manager, before_start 1; 10 "Buddy named" manager, after_start 1. Leaver, default: 1 "Handover completed" manager, before_end 5; 2 "Equipment returned" manager, after_end 0; 3 "Systems access removed" manager, after_end 0; 4 "Smartcard returned" manager, after_end 0; 5 "Final pay and leave balance to payroll" hr, after_end 7; 6 "File closed and retention date noted" hr, after_end 14.

- [ ] **Step 4: Service**

```python
# onboarding/services/checklists.py
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from onboarding.models import Checklist, ChecklistItem, ChecklistTemplate, DueRule, Kind, Owner
from people.services import access, audit, positions

RECENT_DAYS = 30


def _template(kind, title):
    qs = ChecklistTemplate.objects.filter(kind=kind, active=True)
    if title is not None:
        hit = qs.filter(positions=title).first()
        if hit:
            return hit
    return qs.filter(positions=None).first()


def _due(rule, days, start, end):
    if rule == DueRule.BEFORE_START:
        return start - timedelta(days=days)
    if rule == DueRule.AFTER_START:
        return start + timedelta(days=days)
    if rule == DueRule.BEFORE_END:
        return end - timedelta(days=days)
    return end + timedelta(days=days)


def _build(actor, employment, kind, anchor_day):
    pos = positions.primary_on(employment, anchor_day)
    title = pos.title if pos else None
    template = _template(kind, title)
    manager = pos.line_manager if pos else None
    gaps = []
    if pos is None:
        gaps.append("no position on the anchor date, so no title to match a template")
    if template is None:
        gaps.append(f"no {kind} checklist template (add one in Admin › Compliance › Checklist templates)")
    if manager is None:
        gaps.append("no line manager on the primary position: manager items have no owner")
    cl = Checklist.objects.create(employment=employment, kind=kind, template=template, created_by=actor,
                                  gaps="\n".join(gaps))
    for it in (template.items.all() if template else []):
        owner_employee = {Owner.MANAGER: manager, Owner.PERSON: employment.employee, Owner.HR: None}[it.owner]
        ChecklistItem.objects.create(
            checklist=cl, order=it.order, title=it.title, instruction=it.instruction, owner=it.owner,
            owner_employee=owner_employee, due_rule=it.due_rule, link=it.link,
            due_on=_due(it.due_rule, it.due_days, employment.start_date, employment.end_date or employment.start_date))
    audit.record(actor, cl, {"created": ("", f"{kind} checklist, {cl.items.count()} items")})
    return cl


@transaction.atomic
def start(actor, employment):
    """Called by employments.start. None for a spell that began more than
    RECENT_DAYS ago (a past spell entered after the fact)."""
    today = timezone.localdate()
    if employment.start_date < today - timedelta(days=RECENT_DAYS):
        return None
    if Checklist.objects.filter(employment=employment, kind=Kind.STARTER).exists():
        return Checklist.objects.get(employment=employment, kind=Kind.STARTER)
    return _build(actor, employment, Kind.STARTER, employment.start_date)


@transaction.atomic
def leave(actor, employment):
    """Called by employments.end when an end date is set."""
    if employment.end_date is None:
        return None
    existing = Checklist.objects.filter(employment=employment, kind=Kind.LEAVER).first()
    if existing:
        return existing
    return _build(actor, employment, Kind.LEAVER, employment.end_date)


def gaps(checklist):
    return [g for g in checklist.gaps.splitlines() if g]


def may_complete(user, item):
    if access.can_view_restricted(user):
        return True
    me = access.employee_for(user)
    return me is not None and item.owner_employee_id == me.pk


def _finish_if_done(checklist):
    if not checklist.items.filter(state=ChecklistItem.State.OPEN).exists() and checklist.completed_at is None:
        checklist.completed_at = timezone.now()
        checklist.save(update_fields=["completed_at"])


@transaction.atomic
def complete(actor, item, note=""):
    if not may_complete(actor, item):
        raise PermissionDenied
    if item.state != ChecklistItem.State.OPEN:
        raise ValidationError("Already closed.")
    item.state, item.done_by, item.done_at, item.note = ChecklistItem.State.DONE, actor, timezone.now(), note[:200]
    item.save()
    audit.record(actor, item, {"state": ("open", "done")}, note=note[:200])
    _finish_if_done(item.checklist)
    return item


@transaction.atomic
def not_needed(actor, item, note):
    if not access.can_view_restricted(actor):
        raise PermissionDenied
    if not (note or "").strip():
        raise ValidationError("Say why it is not needed.")
    if item.state != ChecklistItem.State.OPEN:
        raise ValidationError("Already closed.")
    item.state, item.done_by, item.done_at, item.note = ChecklistItem.State.NOT_NEEDED, actor, timezone.now(), note[:200]
    item.save()
    audit.record(actor, item, {"state": ("open", "not_needed")}, note=note[:200])
    _finish_if_done(item.checklist)
    return item


@transaction.atomic
def add_item(actor, checklist, title, instruction, owner, due_on, link=""):
    if not access.can_view_restricted(actor):
        raise PermissionDenied
    emp = checklist.employment
    owner_employee = {Owner.MANAGER: access.line_manager(emp.employee, due_on), Owner.PERSON: emp.employee, Owner.HR: None}[owner]
    item = ChecklistItem.objects.create(checklist=checklist, order=(checklist.items.count() + 1) * 10, title=title,
                                        instruction=instruction, owner=owner, owner_employee=owner_employee,
                                        due_on=due_on, link=link)
    audit.record(actor, item, {"added": ("", title)})
    return item


@transaction.atomic
def remove_item(actor, item):
    if not access.can_view_restricted(actor):
        raise PermissionDenied
    audit.record(actor, item.checklist, {"removed": (item.title, "")})
    item.delete()


def _system_close(items, note):
    for item in items:
        item.state, item.done_at, item.note = ChecklistItem.State.DONE, timezone.now(), note
        item.save()
        _finish_if_done(item.checklist)


@transaction.atomic
def linked_done(employee, link):
    """Close every open item of `employee` whose link is exactly `link`
    (e.g. "upload:identity", "check:dbs", "sign_policies", "details")."""
    items = ChecklistItem.objects.filter(checklist__employment__employee=employee, link=link,
                                         state=ChecklistItem.State.OPEN).select_related("checklist")
    _system_close(list(items), "done automatically")


def open_items(employee, today):
    return list(ChecklistItem.objects.filter(checklist__employment__employee=employee, state=ChecklistItem.State.OPEN,
                                             owner=Owner.PERSON).order_by("due_on", "order"))


def items_owned_by(manager, today):
    return list(ChecklistItem.objects.filter(owner_employee=manager, owner=Owner.MANAGER, state=ChecklistItem.State.OPEN)
                .select_related("checklist__employment__employee").order_by("due_on", "order"))


def summary(checklist):
    items = list(checklist.items.all())
    today = timezone.localdate()
    open_ = [i for i in items if i.state == ChecklistItem.State.OPEN]
    overdue = sorted((i for i in open_ if i.due_on < today), key=lambda i: i.due_on)
    return {"total": len(items), "done": len(items) - len(open_), "open": len(open_), "overdue": len(overdue),
            "oldest_overdue": overdue[0] if overdue else None}
```

Hooks, registered in `onboarding/apps.py:OnboardingConfig.ready`:

```python
from checks.services import checks
from documents.services import files, policies
from onboarding.services import checklists

checks.RECORDED_HOOKS.append(lambda check: checklists.linked_done(check.employee, f"check:{check.check_type.code}"))
policies.SIGNED_HOOKS.append(lambda employee: not policies.owed(employee, timezone.localdate())
                             and checklists.linked_done(employee, "sign_policies"))
files.ADDED_HOOKS.append(lambda f: f.employee_id and checklists.linked_done(f.employee, f"upload:{f.category}"))
```

(`files.add` gains `ADDED_HOOKS = []` and calls each with the file after saving; `linked_done(e, "sign_policies")` is also safe to call when nothing is owed, which the test relies on.)

`people/services/employments.py`: `start` ends with `from onboarding.services import checklists; checklists.start(actor, emp)` before `return emp` (inside the atomic block; `start` is not yet atomic, so wrap it with `@transaction.atomic`); `end` calls `checklists.leave(actor, employment)` after the audit when `end_date` is not None.

- [ ] **Step 5: Admin** `onboarding/admin.py`: `ChecklistTemplateAdmin` (kind, name, positions filter_horizontal, active; `TemplateItemInline` tabular with order, title, owner, due_rule, due_days, link, instruction); `ChecklistAdmin` read-only list (employment, kind, created, completed, gaps) with an inline of items read-only; actions are done on the HR page (Task 7). Sidebar: "Checklist templates", "Checklists".

- [ ] **Step 6: Suite, ruff, migrations; docs; commit** `Onboarding: checklist templates, instances with owners, linked items, hooks from employments`. Docs: `compliance.md` "Checklists" section (templates, owners, due rules, links, gaps, what closes an item automatically).

---

## Task 7: Checklist pages, self-service details, the pre-start gate

**Files:**
- Create: `onboarding/views.py`, `onboarding/urls.py`, `onboarding/forms.py` (`DetailsForm`, `EmergencyContactFormSet`), `onboarding/middleware.py`, `templates/onboarding/getting_started.html`, `templates/onboarding/_checklist.html`, `templates/onboarding/_todo_card.html`, `templates/onboarding/hr_list.html`, `templates/onboarding/hr_detail.html`, `templates/onboarding/details_form.html`
- Modify: `config/settings.py` (MIDDLEWARE after `AuthenticationMiddleware`), `config/urls.py` (`path("onboarding/", include("onboarding.urls"))`), `people/services/access.py` (`is_pre_start(user, today)`), `people/views.py` (`me`: "Your checklist"; `team`: To do card), `templates/people/me.html`, `templates/people/team.html`, `hr/admin_site.py` (Compliance: "Starters and leavers" → `onboarding:hr_list`)
- Test: `tests/test_onboarding_pages.py`

**Interfaces:**
- Consumes: Task 6 services; `employees.update`; the emergency-contact model and whatever service `people` has for it (read `people/services/employees.py`; if there is none, add `employees.set_emergency_contacts(actor, employee, rows)` there, audited).
- Produces: URL names `onboarding:getting_started` (`/onboarding/`), `onboarding:details` (`/onboarding/details/`), `onboarding:complete` (`/onboarding/item/<pk>/done/`, POST), `onboarding:not_needed` (`/onboarding/item/<pk>/not-needed/`, POST, HR), `onboarding:hr_list` (`/onboarding/all/`), `onboarding:hr_detail` (`/onboarding/all/<checklist pk>/`), `onboarding:add_item` (POST, HR), `onboarding:remove_item` (POST, HR); `access.is_pre_start(user, today) -> bool`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_onboarding_pages.py
from datetime import timedelta

import pytest
from django.utils import timezone

from onboarding.models import Checklist, ChecklistItem
from people.models import AuditEntry, EmergencyContact
from people.services import employments, positions, titles
from tests.factories import make_employee, make_team

pytestmark = pytest.mark.django_db


def _starter(hr_admin, user, days_ahead=10, manager=None):
    e = make_employee(user=user)
    start = timezone.localdate() + timedelta(days=days_ahead)
    emp = employments.start(hr_admin, e, start)
    positions.add(hr_admin, emp, titles.get_or_create("Receptionist"), make_team(), manager, start)
    return emp


def test_a_pre_start_starter_is_sent_to_getting_started_from_every_page(hr_admin, employee_user, employee_client):
    _starter(hr_admin, employee_user)
    for path in ("/people/me/", "/absence/mine/", "/absence/calendar/", "/"):
        r = employee_client.get(path)
        assert r.status_code == 302 and r["Location"].startswith("/onboarding/")
    assert employee_client.get("/onboarding/").status_code == 200
    assert employee_client.get("/accounts/account/").status_code == 200


def test_on_the_start_date_the_normal_pages_open(hr_admin, employee_user, employee_client):
    _starter(hr_admin, employee_user, days_ahead=0)
    assert employee_client.get("/people/me/").status_code == 200
    assert employee_client.get("/onboarding/").status_code == 200    # still reachable until complete


def test_getting_started_lists_my_items_in_due_order_with_their_forms(hr_admin, employee_user, employee_client):
    _starter(hr_admin, employee_user)
    body = employee_client.get("/onboarding/").content.decode()
    assert "Complete your details" in body and "Upload your right-to-work document" in body
    assert body.index("Complete your details") < body.index("Read and sign the practice policies")
    assert "/onboarding/details/" in body and "/documents/policies/" in body


def test_details_form_writes_through_the_service_and_closes_the_item(hr_admin, employee_user, employee_client):
    emp = _starter(hr_admin, employee_user)
    r = employee_client.post("/onboarding/details/", {
        "preferred_name": "Sam", "personal_email": "sam@home.example", "phone": "07700 900000",
        "address_line1": "1 High St", "town": "Town", "postcode": "AB1 2CD", "ni_number": "QQ123456C",
        "bank_account_name": "S Patel", "bank_sort_code": "12-34-56", "bank_account_number": "12345678",
        "contacts-TOTAL_FORMS": "1", "contacts-INITIAL_FORMS": "0", "contacts-MIN_NUM_FORMS": "0", "contacts-MAX_NUM_FORMS": "3",
        "contacts-0-name": "Jo Patel", "contacts-0-relationship": "Partner", "contacts-0-phone": "07700 900001",
    })
    assert r.status_code == 302
    e = emp.employee; e.refresh_from_db()
    assert e.bank_sort_code == "12-34-56" and EmergencyContact.objects.filter(employee=e).count() == 1
    assert AuditEntry.objects.filter(object_id=e.pk, field="bank_sort_code").exists()
    item = ChecklistItem.objects.get(checklist__employment=emp, link="details")
    assert item.state == "open"           # HR verifies; see next test
    assert employee_client.get("/onboarding/details/").status_code == 200   # can return to it


def test_hr_marks_details_verified_which_closes_the_item(hr_admin, employee_user, admin_client):
    emp = _starter(hr_admin, employee_user)
    item = ChecklistItem.objects.get(checklist__employment=emp, link="details")
    r = admin_client.post(f"/onboarding/item/{item.pk}/done/", {"note": "verified against passport"})
    assert r.status_code == 302
    item.refresh_from_db(); assert item.state == "done"


def test_manager_to_do_card_and_done(hr_admin, employee_user, client):
    mgr_user = type(employee_user).objects.create_user(email="mo@example.com", password="pw")
    mgr = make_employee(first="Mo", last="Khan", user=mgr_user)
    employments.start(hr_admin, mgr, timezone.localdate() - timedelta(days=400))
    emp = _starter(hr_admin, employee_user, manager=mgr)
    client.force_login(mgr_user)
    body = client.get("/people/team/").content.decode()
    assert "Induction completed" in body and emp.employee.name in body
    item = ChecklistItem.objects.get(checklist__employment=emp, title="Induction completed")
    assert client.post(f"/onboarding/item/{item.pk}/done/", {}).status_code == 302
    item.refresh_from_db(); assert item.state == "done"
    hr_item = ChecklistItem.objects.filter(checklist__employment=emp, owner="hr").first()
    assert client.post(f"/onboarding/item/{hr_item.pk}/done/", {}).status_code == 403


def test_hr_list_and_detail(hr_admin, employee_user, admin_client, employee_client):
    emp = _starter(hr_admin, employee_user, manager=None)
    body = admin_client.get("/onboarding/all/").content.decode()
    assert emp.employee.name in body and "no line manager" in body
    cl = Checklist.objects.get(employment=emp)
    body = admin_client.get(f"/onboarding/all/{cl.pk}/").content.decode()
    assert "Contract issued" in body and "Not needed" in body
    assert employee_client.get("/onboarding/all/").status_code == 403
    r = admin_client.post(f"/onboarding/all/{cl.pk}/add/", {"title": "Uniform ordered", "instruction": "", "owner": "hr",
                                                             "due_on": timezone.localdate().isoformat()})
    assert r.status_code == 302 and cl.items.filter(title="Uniform ordered").exists()
```

- [ ] **Step 2: Run, see them fail.**

- [ ] **Step 3: Pre-start gate**

```python
# people/services/access.py
def is_pre_start(user, day):
    """A starter before their first day: a login linked to an employee with
    no current employment and one that starts after `day`."""
    me = employee_for(user)
    if me is None:
        return False
    return (employments.current(me, day) is None
            and me.employments.filter(start_date__gt=day).exists())
```

```python
# onboarding/middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from people.services import access

ALLOWED_PREFIXES = ("/onboarding/", "/documents/", "/accounts/", "/static/", "/admin/login/")


class PreStartGate:
    """Before their start date a starter sees Getting started (and the pages
    it links to) and nothing else."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (user is not None and user.is_authenticated and not request.path.startswith(ALLOWED_PREFIXES)
                and access.is_pre_start(user, timezone.localdate())):
            return redirect(reverse("onboarding:getting_started"))
        return self.get_response(request)
```

Add to `MIDDLEWARE` after `AuthenticationMiddleware` (and after axes'). HR admins and superusers are never pre-start starters unless they have such an employee record; that is correct.

- [ ] **Step 4: Views and templates**

`onboarding/views.py`:
- `getting_started` (`@login_required`): `checklists.open_items(me, today)` plus the done ones of the same checklist, the person's `policies.owed`, and for each item the control its link needs: `details` → link to `onboarding:details`; `upload:<cat>` → an inline upload form posting to a view `upload(request, pk)` that calls `files.add(request.user, me, category, item.title, request.FILES["file"])` (the `ADDED_HOOKS` close the item); `sign_policies` → link to `documents:policies`; `check:<code>` → "HR will record this" (no control); blank → a **Done** button (POST `onboarding:complete`). Template `getting_started.html` extends base; before the start date the nav is hidden (`{% if not pre_start %}` around the nav blocks in `base.html`, with `pre_start` from a tiny context processor in `onboarding`).
- `details` (`@login_required`): `DetailsForm` (ModelForm on Employee: preferred_name, personal_email, phone, address_line1, address_line2, town, postcode, ni_number, bank_account_name, bank_sort_code, bank_account_number) plus an inline formset `contacts` for EmergencyContact (max 3). POST: `employees.update(request.user, Employee.objects.get(pk=me.pk), **form.cleaned_data)` and the emergency-contact service; `messages.success`; redirect to Getting started. Does not close the item: HR does, by **Done** on the HR detail page, after verifying.
- `complete` (POST): `checklists.complete(request.user, item, request.POST.get("note", ""))`; PermissionDenied → 403; redirect to `next` (Getting started, My team or the HR detail).
- `not_needed`, `add_item`, `remove_item` (POST, HR via `access.can_view_restricted` else 403).
- `hr_list` (HR only): open checklists with `summary` and `gaps`; `hr_detail`: every item, owner, state, Done / Not needed (with note) / Remove controls, Add item form.

`people/views.py:me`: `"checklist_items"` for the current employment's incomplete checklist, rendered by `templates/onboarding/_checklist.html` as **Your checklist**. `people/views.py:team`: `"todo": checklists.items_owned_by(me, today)` rendered by `_todo_card.html` with a Done form per item. Sidebar: "Starters and leavers" → `onboarding:hr_list`.

- [ ] **Step 5: Suite, ruff; commit** `Onboarding: Getting started, self-service details, manager To do, HR Starters and leavers, the pre-start gate`.

---
## Task 8: The compliance contract, the reminder schedule, the sent log, the digest, the nightly step

**Files:**
- Create: `compliance/__init__.py`, `compliance/apps.py`, `compliance/models.py`, `compliance/due.py`, `compliance/services/__init__.py`, `compliance/services/schedule.py`, `compliance/services/digest.py`, `compliance/services/nightly.py`, `compliance/admin.py`, `compliance/migrations/0001_initial.py`, `checks/services/due.py`, `documents/services/due.py`, `onboarding/services/due.py`, `templates/email/compliance_digest.txt`
- Modify: `config/settings.py` (INSTALLED_APPS `compliance`), `people/management/commands/hr_nightly.py` (third step), `hr/admin_site.py` (Compliance: "Reminder settings"), `docs/admin/compliance.md`, the nightly doc section
- Test: `tests/test_compliance.py`

**A deviation from the spec, recorded here:** the spec calls `compliance` "a Python package, not a Django app" and then gives it two models. It needs the models, so it is a small Django app. Nothing else changes.

**Interfaces:**
- Consumes: `checks.state`, `checks.CheckType.remind_person`, `access.line_manager`, `policies.owed`, `ChecklistItem` rows, `absence.services.notify._deliver`-style sending (`accounts.mail.send(subject, body, to, reply_to=None)`), `notify.hr_admin_addresses()`.
- Produces: `compliance.due.DueItem` (frozen dataclass: `employee`, `recipient` (an email address), `kind` ∈ {`check`, `policy`, `item`}, `label`, `due_on`, `state` ∈ {`due_soon`, `due_today`, `overdue`, `lapsed`, `missing`}, `url`, `key` (stable string like `check:<employee pk>:<type code>:<expires iso>`), `once` (bool: send a single time, used for the manager's lapsed notice)); `ReminderSchedule.get()` (singleton: `start_days_before=60`, `every_days_before=30`, `every_days_overdue=7`); `schedule.should_send(today, due_on, state, last_sent, sched) -> bool`; each app's `due_items(today, sched) -> list[DueItem]`; `digest.run(today) -> dict(reminders_sent, reminders_failed, items)`; `nightly.run(today)` wraps it; the nightly result dict gains `compliance: {...}`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_compliance.py
from datetime import date, timedelta

import pytest
from django.core import mail
from django.utils import timezone

from checks.models import Check, CheckType
from checks.services import checks
from compliance.models import ReminderSchedule, ReminderSent
from compliance.services import digest, schedule
from onboarding.models import ChecklistItem
from people.services import employments, positions, titles
from tests.factories import make_employee, make_team

pytestmark = pytest.mark.django_db
D = date(2026, 1, 1)   # schedule arithmetic is pure; a fixed date is fine


def S(x=60, y=30, z=7):
    return ReminderSchedule(start_days_before=x, every_days_before=y, every_days_overdue=z)


def test_defaults_and_singleton():
    s = ReminderSchedule.get()
    assert (s.start_days_before, s.every_days_before, s.every_days_overdue) == (60, 30, 7)
    assert ReminderSchedule.get().pk == s.pk


@pytest.mark.parametrize("days_to_due,last,expected", [
    (61, None, False),      # outside the window
    (60, None, True),       # first day of the window
    (59, D, False),         # sent yesterday
    (30, D, True),          # 30 days after the first send: every Y
    (0, D + timedelta(days=30), True),   # the due date always sends
    (-1, D + timedelta(days=60), False), # day after due: the due-date send was yesterday
    (-7, D + timedelta(days=60), True),  # every Z overdue
])
def test_should_send_follows_the_cadence(days_to_due, last, expected):
    today = D + timedelta(days=60 - days_to_due)
    due = today + timedelta(days=days_to_due)
    assert schedule.should_send(today, due, "overdue" if days_to_due < 0 else "due_soon", last, S()) is expected


def test_y_bigger_than_x_still_sends_at_window_start_and_on_the_day():
    s = S(x=10, y=30, z=7)
    today = D
    assert schedule.should_send(today, today + timedelta(days=10), "due_soon", None, s)
    assert not schedule.should_send(today + timedelta(days=5), today + timedelta(days=10), "due_soon", today, s)
    assert schedule.should_send(today + timedelta(days=10), today + timedelta(days=10), "due_today", today, s)


def _receptionist(hr_admin, user=None, manager=None):
    e = make_employee(user=user)
    emp = employments.start(hr_admin, e, timezone.localdate() - timedelta(days=400))
    positions.add(hr_admin, emp, titles.get_or_create("Receptionist"), make_team(), manager, emp.start_date)
    return e


def test_digest_groups_by_recipient_and_logs_sends(hr_admin, configured, employee_user):
    today = timezone.localdate()
    dbs = CheckType.objects.get(code="dbs"); dbs.positions.add(titles.get_or_create("Receptionist"))
    e = _receptionist(hr_admin, user=employee_user)
    checks.record(hr_admin, e, dbs, today - timedelta(days=5), Check.Outcome.CLEAR, reference="1", dbs_level="basic",
                  expires_on=today + timedelta(days=30))
    out = digest.run(today)
    assert out["reminders_sent"] == 2            # the person (remind_person) and HR
    to = sorted(m.to[0] for m in mail.outbox)
    assert to == ["hr@example.com", "sam@example.com"]
    assert "DBS" in mail.outbox[0].body and e.name in mail.outbox[0].body
    assert ReminderSent.objects.count() == 2
    mail.outbox.clear()
    assert digest.run(today + timedelta(days=1))["reminders_sent"] == 0   # not again tomorrow


def test_manager_told_once_when_a_check_lapses(hr_admin, configured, employee_user):
    today = timezone.localdate()
    mgr_user = type(employee_user).objects.create_user(email="mo@example.com", password="pw")
    mgr = make_employee(first="Mo", last="Khan", user=mgr_user)
    employments.start(hr_admin, mgr, today - timedelta(days=500))
    dbs = CheckType.objects.get(code="dbs"); dbs.positions.add(titles.get_or_create("Receptionist"))
    e = _receptionist(hr_admin, user=employee_user, manager=mgr)
    checks.record(hr_admin, e, dbs, today - timedelta(days=1200), Check.Outcome.CLEAR, reference="1", dbs_level="basic")
    digest.run(today)
    assert any(m.to == ["mo@example.com"] for m in mail.outbox)
    mail.outbox.clear()
    digest.run(today + timedelta(days=7))
    assert not any(m.to == ["mo@example.com"] for m in mail.outbox)      # once
    assert any(m.to == ["hr@example.com"] for m in mail.outbox)          # HR every Z days


def test_checklist_items_remind_their_owner(hr_admin, configured, employee_user):
    today = timezone.localdate()
    e = make_employee(user=employee_user)
    emp = employments.start(hr_admin, e, today + timedelta(days=3))
    positions.add(hr_admin, emp, titles.get_or_create("Receptionist"), make_team(), None, emp.start_date)
    ChecklistItem.objects.filter(checklist__employment=emp, owner="person").update(due_on=today)
    digest.run(today)
    me = [m for m in mail.outbox if m.to == ["sam@example.com"]]
    assert me and "Complete your details" in me[0].body


def test_no_email_without_a_relay_and_nothing_logged(hr_admin, employee_user):
    today = timezone.localdate()
    dbs = CheckType.objects.get(code="dbs"); dbs.positions.add(titles.get_or_create("Receptionist"))
    e = _receptionist(hr_admin, user=employee_user)
    checks.record(hr_admin, e, dbs, today - timedelta(days=5), Check.Outcome.CLEAR, reference="1", dbs_level="basic",
                  expires_on=today + timedelta(days=30))
    out = digest.run(today)
    assert out["reminders_sent"] == 0 and ReminderSent.objects.count() == 0
```

- [ ] **Step 2: Run, see them fail.**

- [ ] **Step 3: Models, contract, schedule**

```python
# compliance/models.py
from django.db import models


class ReminderSchedule(models.Model):
    """One row. Start X days before due, every Y days until due, every Z days overdue."""
    start_days_before = models.PositiveSmallIntegerField(default=60)
    every_days_before = models.PositiveSmallIntegerField(default=30)
    every_days_overdue = models.PositiveSmallIntegerField(default=7)

    class Meta:
        verbose_name = "reminder settings"
        verbose_name_plural = "reminder settings"

    @classmethod
    def get(cls):
        row, _ = cls.objects.get_or_create(pk=1)
        return row


class ReminderSent(models.Model):
    recipient = models.EmailField()
    key = models.CharField(max_length=120)
    sent_on = models.DateField()

    class Meta:
        indexes = [models.Index(fields=["recipient", "key"])]
```

```python
# compliance/due.py
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DueItem:
    employee: object
    recipient: str
    kind: str          # check | policy | item
    label: str
    due_on: date
    state: str         # due_soon | due_today | overdue | lapsed | missing
    url: str
    key: str
    once: bool = False
```

```python
# compliance/services/schedule.py
from datetime import timedelta


def should_send(today, due_on, state, last_sent, sched):
    """The cadence: first day inside the window, every Y days before due,
    the due date itself, then every Z days after. `last_sent` is the day
    this recipient last had this key, or None."""
    days = (due_on - today).days
    if days > sched.start_days_before:
        return False
    if days == 0:
        return last_sent != today
    if last_sent is None:
        return True
    gap = (today - last_sent).days
    if days > 0:
        return gap >= max(sched.every_days_before, 1)
    return gap >= max(sched.every_days_overdue, 1)
```

- [ ] **Step 4: Each app's `due_items`**

```python
# checks/services/due.py
from datetime import timedelta
from urllib.parse import urljoin

from django.conf import settings
from django.utils import timezone

from checks.services import checks
from compliance.due import DueItem
from people.models import Employee
from people.services import access, employments


def _hr():
    from absence.services.notify import hr_admin_addresses
    return hr_admin_addresses()


def due_items(today, sched):
    out = []
    url = urljoin(settings.SITE_URL, "/people/me/")
    for e in Employee.objects.filter(user__isnull=False).select_related("user"):
        if employments.current(e, today) is None:
            continue
        for row in checks.state(e, today, window_days=sched.start_days_before):
            if row.status not in ("due_soon", "lapsed", "missing"):
                continue
            due = row.expires_on or today
            key = f"check:{e.pk}:{row.check_type.code}:{due.isoformat()}:{row.status}"
            label = f"{row.check_type.name}: {row.status.replace('_', ' ')}"
            recipients = list(_hr())
            if row.check_type.remind_person and e.user and e.user.is_active:
                recipients.append(e.user.email)
            for r in recipients:
                out.append(DueItem(e, r, "check", label, due, row.status, url, key))
            if row.status == "lapsed":
                m = access.line_manager(e, today)
                if m is not None and m.user and m.user.is_active:
                    out.append(DueItem(e, m.user.email, "check", label, due, "lapsed", url, key, once=True))
    return out
```

`documents/services/due.py`: for each employee with an active login, `policies.owed(e, today)`; state `overdue` or `due_soon` (if within the window; a policy awaiting outside the window is not listed); recipient the person; HR too when overdue; key `policy:<e.pk>:<version pk>`; url `/documents/policies/`. `onboarding/services/due.py`: every open `ChecklistItem` whose checklist's employment is not more than 90 days past its end: state by `due_on` (`due_soon` within window, `due_today`, `overdue`); recipient by owner: `person` → the employee's login email, `manager` → `owner_employee.user.email`, `hr` → each HR admin; key `item:<item pk>`; url `/onboarding/` for the person, `/people/team/` for a manager, `/onboarding/all/<checklist pk>/` for HR.

- [ ] **Step 5: Digest and nightly**

```python
# compliance/services/digest.py
import logging
from collections import defaultdict

from django.template.loader import render_to_string

from accounts import mail
from checks.services import due as checks_due
from compliance.models import ReminderSchedule, ReminderSent
from compliance.services import schedule
from documents.services import due as documents_due
from onboarding.services import due as onboarding_due

log = logging.getLogger("hr.compliance")
SOURCES = (checks_due.due_items, documents_due.due_items, onboarding_due.due_items)


def pending(today):
    """The items that should go today, by recipient, after the schedule and the sent log."""
    sched = ReminderSchedule.get()
    by_recipient = defaultdict(list)
    for source in SOURCES:
        for item in source(today, sched):
            last = (ReminderSent.objects.filter(recipient=item.recipient, key=item.key)
                    .order_by("-sent_on").values_list("sent_on", flat=True).first())
            if item.once and last is not None:
                continue
            if schedule.should_send(today, item.due_on, item.state, last, sched):
                by_recipient[item.recipient].append(item)
    return by_recipient


def run(today):
    if not mail.email_is_configured():
        return {"reminders_sent": 0, "reminders_failed": 0, "items": 0}
    sent = failed = items = 0
    for recipient, rows in pending(today).items():
        rows.sort(key=lambda i: (i.employee.last_name, i.employee.first_name, i.due_on))
        body = render_to_string("email/compliance_digest.txt", {"rows": rows, "today": today})
        if mail.send("Practice HR: things due", body, [recipient]):
            sent += 1
            ReminderSent.objects.bulk_create([ReminderSent(recipient=recipient, key=i.key, sent_on=today) for i in rows])
            items += len(rows)
        else:
            failed += 1
    return {"reminders_sent": sent, "reminders_failed": failed, "items": items}
```

(Check `accounts.mail.send`'s real signature and return value and adapt; it must record failures in `EmailFailure` as the absence emails do.) `compliance/services/nightly.py: run(today) = digest.run(today)`; `hr_nightly.py` adds `"compliance": compliance_nightly.run(today)` after absence. `templates/email/compliance_digest.txt`: a greeting, then per person a heading and one line per item: label, state, due date, url. Admin: `ReminderScheduleAdmin` on the singleton (no add, no delete; the changelist redirects to the one row); sidebar "Reminder settings".

- [ ] **Step 6: Suite, ruff, migrations; docs; commit** `Compliance: the due-items contract, the reminder schedule, the morning digest`. Docs: `compliance.md` "Reminders" (the three numbers, what each app reminds whom, the once rule for managers, the sent log, no email without a relay); the nightly keys.

---

## Task 9: Admin tab and dashboard card, retention categories, docs and guides

**Files:**
- Modify: `people/admin.py` (Employee **Compliance** tab: read-only summary built from `checks.state`, `policies.state`, open checklist items, with links), `absence/admin_dashboard.py` and `templates/admin/index.html` (Compliance card: lapsed checks, missing checks, overdue signatures, overdue checklist items, each linking to the filtered list), `config/settings.py:195` (RETENTION categories `checks`, `files`, `signatures`, default 2190), `people/services/retention.py` (unchanged logic; the categories come from settings), `templates/people/retention.html` (no change unless it enumerates categories), `docs/admin/compliance.md` (complete), `docs/admin/people.md`, `docs/admin/README.md`, `docs/guides/hr-administrator.md`, `docs/guides/manager.md`, `README.md` (one line in the features list), `tests/test_docs.py` (new doc page in its list)
- Test: `tests/test_compliance_admin.py`

**Interfaces:** consumes everything above; produces nothing new.

- [ ] **Step 1: Failing tests**

```python
# tests/test_compliance_admin.py
from datetime import timedelta

import pytest
from django.utils import timezone

from checks.models import Check, CheckType
from checks.services import checks
from people.services import employments, positions, titles
from tests.factories import make_employee, make_team

pytestmark = pytest.mark.django_db


def _receptionist(hr_admin):
    e = make_employee()
    emp = employments.start(hr_admin, e, timezone.localdate() - timedelta(days=400))
    positions.add(hr_admin, emp, titles.get_or_create("Receptionist"), make_team(), None, emp.start_date)
    return e


def test_employee_admin_has_a_compliance_tab(admin_client, hr_admin):
    dbs = CheckType.objects.get(code="dbs"); dbs.positions.add(titles.get_or_create("Receptionist"))
    e = _receptionist(hr_admin)
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert "Compliance" in body and "DBS" in body and "Missing" in body


def test_dashboard_card_counts(admin_client, hr_admin):
    dbs = CheckType.objects.get(code="dbs"); dbs.positions.add(titles.get_or_create("Receptionist"))
    e = _receptionist(hr_admin)
    checks.record(hr_admin, e, dbs, timezone.localdate() - timedelta(days=1200), Check.Outcome.CLEAR, reference="1", dbs_level="basic")
    body = admin_client.get("/admin/").content.decode()
    assert "Lapsed checks" in body and ">1<" in body


def test_retention_report_lists_the_new_categories(admin_client, hr_admin, settings):
    e = make_employee()
    emp = employments.start(hr_admin, e, timezone.localdate() - timedelta(days=4000))
    employments.end(hr_admin, emp, timezone.localdate() - timedelta(days=3000), "resigned")
    body = admin_client.get("/people/retention/").content.decode()
    for category in ("checks", "files", "signatures"):
        assert category in body
```

- [ ] **Step 2: Run, see them fail.**

- [ ] **Step 3: Implement** the tab (unfold supports tabs via `fieldsets` with `"classes": ["tab"]`; follow how the Employee admin already lays out sections; render the summary through a `readonly_fields` method returning safe HTML built with `format_html`), the dashboard counts (`absence/admin_dashboard.py` gains `compliance_counts(today)` computing the four numbers from `checks.state` over current employees, `policies.owed`, and `ChecklistItem` rows; the card in `templates/admin/index.html` beside the existing ones), the retention categories (settings tuple gains `("checks", 2190), ("files", 2190), ("signatures", 2190)`; `docs/admin/people.md` retention table).

- [ ] **Step 4: Docs** `docs/admin/compliance.md` complete (checks, files, policies, checklists, reminders, retention, the admin pages, the nightly keys); `people.md` (position titles, bank details, retention categories); `README.md` features line; `docs/guides/hr-administrator.md` new sections in the guide's voice: "Setting someone up before day one" (create the login and employee, employment with position and manager; what the starter sees; verify their details; record checks; what closes by itself), "Recording a check", "Asking someone for evidence", "Issuing a policy", "Working the leaver list", "Reminder settings"; `docs/guides/manager.md`: "Your To do list" and "What you can see of a report's checks". `tests/test_docs.py`: add the new page to the list it enumerates.

- [ ] **Step 5: Suite, ruff, migrations; commit** `Compliance: the admin tab, the dashboard card, retention categories, docs and guides`.

---

## Self-review notes (written with the spec open)

- **Spec coverage.** §1 architecture/files/access/sensitive/retention → Tasks 3, 2, 9; position titles → Task 1; §2 checks → Task 4; §3 files → Task 3, policies and signatures → Task 5; §4 templates, instances, services, self-service, pages, leaving → Tasks 6, 7; §5 contract, schedule, digest → Task 8; §6 admin, nav, dashboard → Tasks 3–5 (sidebar), 9 (tab, card), 5 (nav); §7 errors (upload refusal Task 3, signing fails closed Task 5, gaps Task 6), audit (every service), retention Task 9; §8 testing: each task; docs: Task 9 plus per-task sections.
- **Type consistency.** `checks.state` returns `Row` objects (`.status`, `.latest`, `.check_type`, `.expires_on`) everywhere; `policies.owed` returns `Owed` (`.version`, `.due_on`, `.state`); link strings are exact in Tasks 6 and 7; `DueItem` fields match between Task 8's contract and each app's producer; `ReminderSchedule.get()` is the only way to read the cadence.
- **Review Focus pins:** 1 → `test_a_pdf_that_is_really_html_is_refused_and_nothing_written` (Task 3); 2 → `test_a_starter_without_a_manager_is_a_gap_not_a_failure` (Task 6); 3 → `test_a_new_version_is_owed_again_and_the_old_one_never_is` (Task 5); 4 → `test_y_bigger_than_x_still_sends_at_window_start_and_on_the_day` (Task 8); 5 → `test_renaming_a_title_moves_every_position_with_it` (Task 1).
- **Known judgement calls for the executor:** `RECENT_DAYS = 30` for "recent start"; the manager's lapsed notice uses `once=True`; policy files are readable by any signed-in employee the policy applies to (extend `can_view_file` for `category == POLICY`); the self-service `details` item is closed by HR's Done, not by the form submit.

## Execution notes (2026-10-04)

Executed as nine subagent-driven tasks in sequence on branch `feature/onboarding-documents`, each with its own review and fix rounds, then a whole-branch review, one fix wave and one scoped re-review. The whole-branch review found the Task 7 "must fix" (NI-number normalisation) had been queued but never executed, so the fix wave carried it; the wave also added evidence requests before day one, the details item routing to HR once submitted, unanswered requests counting as missing, gapped and empty checklists staying visible, the required evidence file on a clear outcome, guarded checklist building, and the Supersede action. Suite: 1272 tests (52 added by the fix wave, 1220 before it); ruff and makemigrations --check clean.

**Rulings made while executing:**

- `compliance` is a Django app (models for the schedule and the sent log) rather than the plain package the spec named.
- Occupational-health and Hep B evidence is filed under the person's own occupational-health category, not as a certificate, so it is not HR-only; managers never see files and HR views are audited.
- Clearing a leaving date closes the leaver checklist (open items become not needed with the note "leaving date cleared"); a later leaving date keeps those items and appends fresh ones, nothing is deleted.
- A checklist built after its conditions are already met starts with those linked items done; a `check:` item counts as met, at build or by hook, only by a clear check that has not expired.
- The self-service details form is reachable only while the person has an open details item; after it is sent the item shows "Sent – HR will check it" and the reminder goes to HR, who closes it with Done. Contact details stay editable on My record.
- A pre-start starter cannot sign in to the rota; before day one they see Getting started, the details form and any evidence HR has asked for.
- An unanswered evidence request on a required check, once the employment has started, is chased as missing by the digest and the dashboard; the pages keep the Awaiting label.
- A clear outcome on a file-evidence check needs its file; DBS never stores one. HR cannot repoint evidence already recorded.
- A checklist is never auto-completed while it has no items; empty and gapped checklists stay on Starters and leavers until HR completes them. Templates are deactivated, never deleted.
- Checklist building runs inside a savepoint: a failure is logged by class and recorded as a gap, and never fails the employment save.
- Any signed-in employee may read any policy version file (policies are staff-facing documents).
- HR's view of a person's checks on the Compliance tab is audited as "checks"; the Checks changelist is not.
- Retention keeps listing checks, files and signatures per category; deletion has no path yet (backlog).
- Stored NI numbers are normalised by a data migration (strip, uppercase); rows that still fail the format are left and reported by pk; typed values are normalised on both forms; a stale value shows as a form error on My record.

**Deferred (recorded, not blocking):** whitespace and case variants of existing position titles become separate rows (de-duplicate on live data before deploy); `checks.state` and `policies.state` run a query per row; a renewal request on a due-soon or lapsed type is outside the manager's awaiting count; a password signature also opens the passkey-enrolment window; Signature and File rows protect their employee, so deleting someone under retention needs its own path; leaver and starter manager items keep an owner who has since left; a historical end date builds an overdue leaver checklist; the gate and nav flag cost a few queries per page; Remove on the HR checklist page has no confirmation; employees past the recent-start window with no checklist cannot self-edit bank details (HR does it); `ReminderSchedule.get()` bootstraps the singleton on an admin GET; `ReminderSent` is never pruned; the pages use a fixed 60-day window for "due soon" while reminders use the setting; the dashboard card recomputes on every load.
