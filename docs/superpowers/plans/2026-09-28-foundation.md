# Practice HR Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the `practice-hr` Django project with the rota's accounts app moved in, the `people` app (employees, employments, positions, contracts, working patterns, pay, audit), role-based access, an OpenID Connect provider, and the rota's *Sign in with the practice account* path.

**Architecture:** A separate Django project mirroring the rota's conventions (SQLite WAL, unfold admin, no build step, secrets from the environment). `accounts` is copied from the rota at commit `f1cdc4d` with its rota-specific names changed. `people` holds effective-dated rows and a service layer that is the only writer; the admin and views call services. `django-oauth-toolkit` serves OpenID Connect; the rota gains a `mozilla-django-oidc` client.

**Tech Stack:** Python 3.13, Django 5.2 LTS, SQLite, django-unfold, django-axes, webauthn, whitenoise, gunicorn, django-oauth-toolkit, pytest-django, ruff (pyflakes only).

**Spec:** `docs/superpowers/specs/2026-09-27-practice-hr-foundation-and-absence-design.md` (sections 1, 2, 3 and the deployment paragraph of section 1). Plans 2 and 3 implement sections 4 to 7.

## Global Constraints

- Django 5.2 LTS, Python 3.13, SQLite WAL. Unfold for the admin. No build step, no node. Every colour from `tokens.css`.
- Secrets from the environment only. No key, token or password in any file in the repository or in any log line.
- All writes to `people` and `absence` go through `*/services/`, never a view, a form's `save()` or the admin directly.
- The test suite makes no network calls.
- New dependencies allowed by the spec: `django-oauth-toolkit` (here), `openpyxl` (plan 3). Nothing else without a spec change.
- The rota's own constraints continue to apply to the rota; the one rota change in this release is sign-in through OpenID Connect with one client library (Task 14).
- Nothing in `people` is ever deleted; rows end.
- Effective dating: employments, positions, contracts, patterns, pay records carry a from-date and an optional to-date.
- Commit messages follow the rota's style: `feat:`, `fix:`, `docs:`, `test:` prefixes, one line of what changed and why.

## Review Focus

Inputs the spec implies but no section spells out, each pinned by a test in the task that owns the code:

1. **A returner whose new employment starts the day after the old one ended** must be accepted (no overlap), and `current(employee, day)` must pick the right spell on the boundary days. Test in Task 6.
2. **Two contracts whose date ranges touch but do not overlap** (permanent ends 31 March, fixed term starts 1 April) must not trip the unit rule, and the contracted amount on 31 March and 1 April must be each contract's own amount. Test in Task 8.
3. **A working pattern saved with a weekly total that differs from the contracted amount** must save with a warning, never refuse, because part-timers' patterns and contracts drift by design. Test in Task 9.
4. **An employee who is their own line manager, or a cycle A manages B manages A**, must be refused at the service layer, not only in the form. Test in Task 7.
5. **An email that matches an existing rota user only by case** must sign in as that user, not create a second; and a leaver whose employment ended yesterday must have `is_active` false after the nightly job, while a returner with a later spell keeps their login. Tests in Task 14 and Task 12.

---

## File structure

Created in `devachnid/practice-hr` (all paths relative to the repository root):

| Path | Responsibility |
|---|---|
| `manage.py`, `config/settings.py`, `config/urls.py`, `config/wsgi.py`, `config/asgi.py`, `config/apps.py` | Project wiring. `settings.py` is the rota's with the rota-specific blocks removed and the OIDC provider added. |
| `config/views.py` | The one non-app view: the front page redirect. |
| `hr/admin_site.py`, `hr/admin_theme.py` | The unfold site subclass with the access rule and navigation, and the colour callbacks. Copied from the rota's `rota/admin_site.py` and `rota/admin_theme.py`, trimmed. |
| `accounts/` | Moved from the rota. Login, invitations, passkeys, lockout, the `User` model with `is_hr_admin`. |
| `accounts/oidc.py` | The OpenID Connect claims validator. |
| `accounts/management/commands/register_oidc_client.py` | Registers a relying party and prints its credentials once. |
| `people/models/employee.py` | `Employee`, `EmergencyContact`. |
| `people/models/employment.py` | `Employment`, `Team`, `Position`. |
| `people/models/contract.py` | `ContractType`, `Contract`, `PayRecord`. |
| `people/models/pattern.py` | `WorkingPattern`, `PatternDay`. |
| `people/models/audit.py` | `AuditEntry`. |
| `people/services/audit.py` | `record`, `viewed`. |
| `people/services/employees.py` | `create`, `update`. |
| `people/services/employments.py` | `current`, `start`, `end`, `service_years`. |
| `people/services/positions.py` | `add`, `end`, cycle check. |
| `people/services/contracts.py` | `add`, `end`, `contracted_amount`, `unit`, `fte`. |
| `people/services/patterns.py` | `set_pattern`, `pattern_on`, `units_on`, `weekly_total`. |
| `people/services/access.py` | `line_manager`, `direct_reports`, `is_approver`, `can_view`, `route_for`. |
| `people/services/nightly.py` | `run(today)`: disable leavers' logins. |
| `people/management/commands/hr_nightly.py` | Runs every app's nightly job. |
| `people/admin.py` | Unfold admin for the hub and its inlines, posting through services. |
| `people/views.py`, `people/urls.py`, `templates/people/*.html` | The employee's own record page and the approver's team page. |
| `templates/base.html`, `static/css/*`, `static/js/passkeys.js`, `static/js/theme.js`, `static/fonts/*` | The design system, copied from the rota. |
| `deploy/*` | gunicorn unit, backup script and timers, nightly timer. |
| `docs/admin/people.md`, `docs/admin/sign-in.md` | Admin guide pages. |
| `tests/` | `conftest.py`, `factories.py`, one `test_*.py` per task. |

Modified in `devachnid/rota` (Task 14 only): `requirements.txt`, `config/settings.py`, `config/urls.py`, `accounts/oidc.py` (new), `templates/registration/login.html`, `docs/admin/sign-in.md` (new), `tests/test_oidc_signin.py` (new).

The rota checkout is available at the path the executor is given; this plan calls it `$ROTA`. Every copy below reads from commit `f1cdc4d` of `devachnid/rota`.

---

### Task 1: Project scaffold, settings, CI

**Files:**
- Create: `manage.py`, `config/__init__.py`, `config/settings.py`, `config/urls.py`, `config/wsgi.py`, `config/asgi.py`, `config/apps.py`, `config/views.py`, `hr/__init__.py`, `hr/admin_site.py`, `hr/admin_theme.py`, `requirements.txt`, `ruff.toml`, `pytest.ini`, `.gitignore`, `.github/workflows/tests.yml`, `tests/__init__.py`, `tests/conftest.py`, `tests/test_settings.py`
- Copy from `$ROTA`: `static/css/tokens.css`, `static/css/components.css`, `static/css/screens.css`, `static/css/fonts.css`, `static/fonts/*`, `static/js/theme.js`, `templates/offline.html` is **not** copied (no service worker in this release).

**Interfaces:**
- Produces: `config.settings` with `INSTALLED_APPS = [unfold…, "config.apps.HrAdminConfig", auth, contenttypes, sessions, messages, staticfiles, "axes", "oauth2_provider", "accounts", "people"]`, `AUTH_USER_MODEL = "accounts.User"`, `LOGIN_REDIRECT_URL = "/"`, `_TESTING` flag, `TRUSTED_PROXY_IPS`, the email settings, the axes settings; `hr.admin_site.HrAdminSite` whose `has_permission` is `is_hr_admin(request)`.

- [ ] **Step 1: Create the Python environment and pin dependencies**

```bash
cd practice-hr
python3.13 -m venv .venv && source .venv/bin/activate
pip install Django==5.2.16 django-unfold==0.104.1 django-axes==8.3.1 webauthn==3.0.0 whitenoise==6.12.0 gunicorn==26.0.0 pytest==9.1.1 pytest-django==4.12.0 "django-oauth-toolkit>=3.0,<4" ruff==0.16.6
pip freeze | grep -v ruff > requirements.txt
```

`requirements.txt` must list `django-oauth-toolkit` at the exact version installed.

- [ ] **Step 2: Write the settings test**

`tests/test_settings.py`:

```python
from django.conf import settings


def test_project_apps_present():
    for app in ("accounts", "people", "axes", "oauth2_provider"):
        assert app in settings.INSTALLED_APPS


def test_user_model_and_redirects():
    assert settings.AUTH_USER_MODEL == "accounts.User"
    assert settings.LOGIN_URL == "/accounts/login/"
    assert settings.LOGIN_REDIRECT_URL == "/"


def test_no_breathe_settings_survived():
    assert not hasattr(settings, "BREATHE_API_KEY")
```

- [ ] **Step 3: Copy the project wiring from the rota and edit it**

```bash
cp $ROTA/manage.py $ROTA/pytest.ini $ROTA/ruff.toml .
mkdir -p config hr static templates tests
cp $ROTA/config/__init__.py $ROTA/config/settings.py $ROTA/config/wsgi.py $ROTA/config/asgi.py config/
cp -r $ROTA/static/css $ROTA/static/fonts static/
mkdir -p static/js && cp $ROTA/static/js/theme.js static/js/
```

Edit `config/settings.py`:

1. `INSTALLED_APPS` becomes:

```python
INSTALLED_APPS = [
    "unfold.apps.BasicAppConfig",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "config.apps.HrAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "axes",
    "oauth2_provider",
    "accounts",
    "people",
]
```

2. Delete the `BREATHE_API_KEY` and `BREATHE_API_URL` lines and their comment.
3. `LOGIN_REDIRECT_URL = "/"`.
4. In `UNFOLD`: `SITE_TITLE = "HR"`, `SITE_HEADER = "Practice HR"`, `SITE_URL = "/"`, `SITE_SYMBOL = "badge"`; every `rota.admin_site.` becomes `hr.admin_site.` and `rota.admin_theme.` becomes `hr.admin_theme.`; delete the `DASHBOARD_CALLBACK` line and the `SITE_FAVICONS` block.
5. `AUTHENTICATION_BACKENDS` third entry becomes `"accounts.backends.HrAdminBackend"`.
6. Append:

```python
# OpenID Connect provider for the practice's other apps (the rota). The RSA
# key comes from the environment like SECRET_KEY; with no key the provider
# is off and /o/ answers 404 (config/urls.py).
OIDC_RSA_PRIVATE_KEY = os.environ.get("OIDC_RSA_PRIVATE_KEY", "").replace("\\n", "\n")
OAUTH2_PROVIDER = {
    "OIDC_ENABLED": bool(OIDC_RSA_PRIVATE_KEY) or _TESTING,
    "OIDC_RSA_PRIVATE_KEY": OIDC_RSA_PRIVATE_KEY,
    "SCOPES": {"openid": "Sign in", "email": "Your email address"},
    "OAUTH2_VALIDATOR_CLASS": "accounts.oidc.Validator",
    "PKCE_REQUIRED": True,
    "ACCESS_TOKEN_EXPIRE_SECONDS": 600,
    "ID_TOKEN_EXPIRE_SECONDS": 600,
}
```

Create `config/apps.py`:

```python
from django.contrib.admin.apps import AdminConfig


class HrAdminConfig(AdminConfig):
    """admin.site is our HrAdminSite (unfold, with the is_hr_admin rule)."""
    default_site = "hr.admin_site.HrAdminSite"
```

Create `config/urls.py`:

```python
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from config.views import home

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("people/", include("people.urls")),
    path("", home, name="home"),
]

if settings.OAUTH2_PROVIDER["OIDC_ENABLED"]:
    urlpatterns.insert(
        1, path("o/", include("oauth2_provider.urls", namespace="oauth2_provider")))
```

Create `config/views.py`:

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


@login_required
def home(request):
    return redirect("people:me")
```

Create `hr/admin_site.py` by copying `$ROTA/rota/admin_site.py` and editing: rename `is_rota_admin` to `is_hr_admin` everywhere and read `user.is_hr_admin`; rename the class `RotaAdminSite` to `HrAdminSite`; delete `favicon_32`, `apple_touch_icon`, `settings_link` and `script_theme_bridge`; replace the body of `navigation(request)` with:

```python
def navigation(request):
    return [
        {"title": "People", "separator": False, "items": [
            _item("Employees", "badge", reverse("admin:people_employee_changelist")),
            _item("Teams", "groups", reverse("admin:people_team_changelist")),
            _item("Contract types", "description", reverse("admin:people_contracttype_changelist")),
            _item("Audit log", "history", reverse("admin:people_auditentry_changelist")),
        ]},
        {"title": "Access", "separator": True, "items": [
            _item("Login accounts", "key", reverse("admin:accounts_user_changelist")),
            _item("Sign-in clients", "link", reverse("admin:oauth2_provider_application_changelist"),
                  permission=is_superuser),
        ]},
    ]
```

Keep `style_fonts` and `style_admin` (they point at `static/css/fonts.css` and `static/admin/admin.css`; copy `$ROTA/static/admin/admin.css` too). `hr/admin_theme.py` is `$ROTA/rota/admin_theme.py` unchanged.

Create `tests/conftest.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

User = get_user_model()


@pytest.fixture
def hr_admin(db):
    return User.objects.create_user(email="hr@example.com", password="pw", is_hr_admin=True)


@pytest.fixture
def employee_user(db):
    return User.objects.create_user(email="sam@example.com", password="pw")


@pytest.fixture
def admin_client(hr_admin):
    c = Client()
    c.force_login(hr_admin)
    return c


@pytest.fixture
def employee_client(employee_user):
    c = Client()
    c.force_login(employee_user)
    return c


@pytest.fixture
def superuser_client(db):
    u = User.objects.create_superuser(email="root@example.com", password="pw")
    c = Client()
    c.force_login(u)
    return c


@pytest.fixture
def configured(settings):
    settings.EMAIL_HOST = "smtp.example"
    settings.DEFAULT_FROM_EMAIL = "Practice HR <hr@example.org>"
```

`.gitignore`:

```
.venv/
db.sqlite3*
staticfiles/
media/
__pycache__/
*.pyc
.pytest_cache/
```

`.github/workflows/tests.yml` is `$ROTA/.github/workflows/tests.yml` with `master` replaced by `main`, the Breathe sentence removed from the comment, `DEFAULT_FROM_EMAIL: HR <hr@example.org>`, and one extra env line in the deploy-check step: `OIDC_RSA_PRIVATE_KEY: ""`.

- [ ] **Step 4: Run the settings test; it fails until accounts and people exist**

Run: `python -m pytest tests/test_settings.py -q`
Expected: errors importing `accounts`/`people` (created in Tasks 2 and 4). Leave it red; Task 4 turns it green.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: project scaffold, settings, admin site and CI, from the rota's conventions"
```

---

### Task 2: Move the accounts app

**Files:**
- Copy then edit: `accounts/__init__.py`, `apps.py`, `models.py`, `admin.py`, `views.py`, `urls.py`, `backends.py`, `mail.py`, `passkeys.py`, `axes_username.py`, `client_ip.py` from `$ROTA/accounts/`; `templates/registration/*`, `templates/accounts/account.html`, `templates/base.html`, `static/js/passkeys.js` from `$ROTA`; tests `tests/test_accounts.py`, `tests/test_account_mail.py`, `tests/test_axes_lockout.py`, `tests/test_email_case.py`, `tests/test_client_ip.py`, `tests/soft_authenticator.py` from `$ROTA/tests/`.
- Create: `accounts/migrations/0001_initial.py` (generated).

**Interfaces:**
- Produces: `accounts.models.User(email, is_hr_admin, is_active, password_link_sent_at)`, `User.objects.create_user(email, password=None, **extra)`, `accounts.backends.HrAdminBackend` answering every permission on `{"accounts", "people", "absence"}` for an active `is_hr_admin` user, `accounts.mail.send_password_link(request, user, *, invite, throttle=False)`, `accounts.mail.email_is_configured()`, the URL names `login`, `logout`, `account`, `password_change`, `password_reset`, `password_reset_confirm`, `passkey_*`.

- [ ] **Step 1: Copy and rename**

```bash
mkdir -p accounts templates/registration templates/accounts static/js
cp $ROTA/accounts/*.py accounts/
cp $ROTA/templates/registration/* templates/registration/
cp $ROTA/templates/accounts/account.html templates/accounts/
cp $ROTA/templates/base.html templates/
cp $ROTA/static/js/passkeys.js static/js/
cp $ROTA/tests/test_accounts.py $ROTA/tests/test_account_mail.py $ROTA/tests/test_axes_lockout.py \
   $ROTA/tests/test_email_case.py $ROTA/tests/test_client_ip.py $ROTA/tests/soft_authenticator.py tests/
grep -rl "is_rota_admin" accounts tests templates | xargs sed -i 's/is_rota_admin/is_hr_admin/g'
grep -rl "RotaAdminBackend" accounts | xargs sed -i 's/RotaAdminBackend/HrAdminBackend/g'
sed -i 's/ROTA_APPS = {"rota", "accounts", "feedback"}/HR_APPS = {"accounts", "people", "absence"}/; s/ROTA_APPS/HR_APPS/g; s/_is_rota_admin/_is_hr_admin/g' accounts/backends.py
```

Then by hand:

- `accounts/models.py`: the `is_hr_admin` help text becomes `"Can use this admin, decide any request, and see pay and health records."`; the `verbose_name` strings stay.
- `accounts/admin.py`: delete `clinician_name`, remove it from `list_display`, `readonly_fields`, `list_select_related` and the fieldset; the fieldset description becomes `"An HR admin can use this admin, decide any leave request, and see pay and health records."`. Every docstring's "rota admin" becomes "HR admin".
- `accounts/mail.py`: the invitation and reset copy names "Practice HR" instead of the rota; `email_is_configured`'s docstring says `/etc/practice-hr.env`.
- `templates/base.html`: replace the nav links with `My record` (`{% url 'people:me' %}`), `My team` (`{% url 'people:team' %}`, wrapped in `{% if is_approver %}`), and `Admin` (`{% url 'admin:index' %}`, wrapped in `{% if user.is_hr_admin or user.is_superuser %}`); delete the feedback button, the install card and the service-worker script tag; keep the account link, the theme script and the passkey prompt.
- `templates/registration/login.html`: the heading reads `Practice HR`.
- `tests/test_accounts.py`, `tests/test_email_case.py`, `tests/test_account_mail.py`: fixtures `admin_user`→`hr_admin`, `gp_user`→`employee_user`, `gp_client`→`employee_client`, `staff_client`→`superuser_client`; delete any test that asserts on a clinician link or on `/rota/` as the landing page, and change landing-page assertions to `/people/me/`.
- `tests/test_axes_lockout.py`, `tests/test_client_ip.py`, `tests/soft_authenticator.py`: fixture renames only.

- [ ] **Step 2: Add the `is_approver` context processor stub**

`base.html` reads `is_approver`; Task 10 makes it real. For now create `people/context_processors.py`:

```python
def roles(request):
    return {"is_approver": False}
```

and add `"people.context_processors.roles"` to `TEMPLATES[0]["OPTIONS"]["context_processors"]` in `config/settings.py`. Create `people/__init__.py`, `people/apps.py` (`name = "people"`), `people/urls.py`:

```python
from django.urls import path

app_name = "people"
urlpatterns = []
```

- [ ] **Step 3: Generate the migration and run the moved tests**

Run: `DEBUG=1 python manage.py makemigrations accounts && python -m pytest tests/test_accounts.py tests/test_account_mail.py tests/test_axes_lockout.py tests/test_email_case.py tests/test_client_ip.py -q`
Expected: all pass. A failure naming `people:me` or `people:team` means a template still references a URL that Task 11 adds; register placeholder views in `people/urls.py` now:

```python
from django.http import HttpResponse
from django.urls import path

app_name = "people"
urlpatterns = [
    path("me/", lambda r: HttpResponse("me"), name="me"),
    path("team/", lambda r: HttpResponse("team"), name="team"),
]
```

Task 11 replaces them.

- [ ] **Step 4: Lint and commit**

Run: `ruff check .`
Expected: clean.

```bash
git add -A
git commit -m "feat: move the accounts app from the rota; is_hr_admin replaces is_rota_admin"
```

---

### Task 3: The people models, part one: Employee, EmergencyContact, AuditEntry

**Files:**
- Create: `people/models/__init__.py`, `people/models/employee.py`, `people/models/audit.py`, `people/services/__init__.py`, `people/services/audit.py`, `tests/factories.py`, `tests/test_employee.py`, `tests/test_audit.py`

**Interfaces:**
- Produces: `Employee(first_name, last_name, preferred_name, work_email, personal_email, phone, date_of_birth, address_line1, address_line2, town, postcode, ni_number, user)`, `Employee.name` property; `EmergencyContact(employee, name, relationship, phone, priority)`; `AuditEntry(actor, at, kind, model, object_id, field, before, after, note)` with `Kind.CHANGE`/`Kind.VIEWED`; `services.audit.record(actor, obj, changes, note="") -> list[AuditEntry]` where `changes` is `{field: (before, after)}`; `services.audit.viewed(actor, obj, section) -> AuditEntry`; `tests.factories.make_employee(**kw)`.

- [ ] **Step 1: Write the failing tests**

`tests/factories.py`:

```python
from datetime import date

from people.models import Employee

MON = date(2026, 4, 6)  # a Monday, in the 2026/27 leave year


def make_employee(first="Sam", last="Patel", email=None, **kw):
    """Default emails carry a counter so two default employees never collide."""
    email = email or f"{first}.{last}.{Employee.objects.count() + 1}@example.org".lower()
    return Employee.objects.create(first_name=first, last_name=last, work_email=email, **kw)
```

`tests/test_employee.py`:

```python
import pytest
from django.db import IntegrityError

from people.models import Employee
from tests.factories import make_employee


def test_name_prefers_preferred_name(db):
    e = make_employee(preferred_name="Sammy")
    assert e.name == "Sammy Patel"
    e.preferred_name = ""
    assert e.name == "Sam Patel"


def test_work_email_unique_case_insensitive(db):
    make_employee(email="a@example.org")
    with pytest.raises(IntegrityError):
        make_employee(first="Other", email="A@example.org")


def test_str_is_name(db):
    assert str(make_employee()) == "Sam Patel"
```

`tests/test_audit.py`:

```python
from people.models import AuditEntry
from people.services import audit
from tests.factories import make_employee


def test_record_writes_one_row_per_field(hr_admin):
    e = make_employee()
    rows = audit.record(hr_admin, e, {"phone": ("", "0113"), "town": ("", "Leeds")}, note="edit")
    assert len(rows) == 2
    row = AuditEntry.objects.get(field="phone")
    assert row.kind == AuditEntry.Kind.CHANGE
    assert (row.model, row.object_id, row.before, row.after, row.note) == ("people.employee", e.pk, "", "0113", "edit")
    assert row.actor == hr_admin


def test_record_skips_unchanged_fields(hr_admin):
    e = make_employee()
    assert audit.record(hr_admin, e, {"phone": ("x", "x")}) == []


def test_viewed_writes_a_viewed_row(hr_admin):
    e = make_employee()
    row = audit.viewed(hr_admin, e, "pay")
    assert row.kind == AuditEntry.Kind.VIEWED and row.field == "pay"
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest tests/test_employee.py tests/test_audit.py -q`
Expected: ImportError on `people.models`.

- [ ] **Step 3: Write the models and the audit service**

`people/models/employee.py`:

```python
from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class Employee(models.Model):
    """The person, created once and never deleted. Employment spells,
    contracts and everything dated hang off Employment, not here."""
    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)
    preferred_name = models.CharField(max_length=60, blank=True, default="")
    work_email = models.EmailField(
        help_text="The login identity. Matched case-insensitively to the login account.")
    personal_email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=30, blank=True, default="")
    date_of_birth = models.DateField(null=True, blank=True)
    address_line1 = models.CharField(max_length=120, blank=True, default="")
    address_line2 = models.CharField(max_length=120, blank=True, default="")
    town = models.CharField(max_length=60, blank=True, default="")
    postcode = models.CharField(max_length=10, blank=True, default="")
    ni_number = models.CharField("NI number", max_length=9, blank=True, default="")
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="employee")

    class Meta:
        ordering = ["last_name", "first_name"]
        constraints = [
            models.UniqueConstraint(Lower("work_email"), name="employee_work_email_ci_unique"),
        ]

    @property
    def name(self):
        return f"{self.preferred_name or self.first_name} {self.last_name}"

    def __str__(self):
        return self.name


class EmergencyContact(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="emergency_contacts")
    name = models.CharField(max_length=120)
    relationship = models.CharField(max_length=60, blank=True, default="")
    phone = models.CharField(max_length=30)
    priority = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["priority", "name"]

    def __str__(self):
        return f"{self.name} ({self.relationship})"
```

`people/models/audit.py`:

```python
from django.conf import settings
from django.db import models


class AuditEntry(models.Model):
    """One row per field changed by a service, and one per view of a
    restricted section. Never edited, never deleted."""
    class Kind(models.TextChoices):
        CHANGE = "change", "Change"
        VIEWED = "viewed", "Viewed"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    at = models.DateTimeField(auto_now_add=True)
    kind = models.CharField(max_length=6, choices=Kind.choices)
    model = models.CharField(max_length=60)       # "people.employee"
    object_id = models.PositiveBigIntegerField()
    field = models.CharField(max_length=60)       # field name, or the section viewed
    before = models.TextField(blank=True, default="")
    after = models.TextField(blank=True, default="")
    note = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["-at", "-id"]
        verbose_name_plural = "audit entries"
        indexes = [models.Index(fields=["model", "object_id"])]

    def __str__(self):
        return f"{self.at:%Y-%m-%d %H:%M} {self.kind} {self.model}#{self.object_id} {self.field}"
```

`people/models/__init__.py`:

```python
from .audit import AuditEntry
from .employee import EmergencyContact, Employee

__all__ = ["AuditEntry", "EmergencyContact", "Employee"]
```

`people/services/audit.py`:

```python
"""The one writer of AuditEntry. Every service in people and absence calls
record() after a change and viewed() when a restricted section is shown."""

from people.models import AuditEntry


def _label(obj):
    return f"{obj._meta.app_label}.{obj._meta.model_name}"


def record(actor, obj, changes, note=""):
    rows = [
        AuditEntry(actor=actor, kind=AuditEntry.Kind.CHANGE, model=_label(obj),
                   object_id=obj.pk, field=field, before=str(before), after=str(after), note=note)
        for field, (before, after) in changes.items() if before != after
    ]
    return AuditEntry.objects.bulk_create(rows)


def viewed(actor, obj, section):
    return AuditEntry.objects.create(
        actor=actor, kind=AuditEntry.Kind.VIEWED, model=_label(obj), object_id=obj.pk,
        field=section)
```

`people/services/__init__.py` is empty.

- [ ] **Step 4: Migrate and run**

Run: `DEBUG=1 python manage.py makemigrations people && python -m pytest tests/test_employee.py tests/test_audit.py tests/test_settings.py -q`
Expected: all pass, including Task 1's settings test.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: Employee, EmergencyContact and the audit log with its service"
```

---

### Task 4: Employee service and the changes helper

**Files:**
- Create: `people/services/employees.py`, `tests/test_employees_service.py`

**Interfaces:**
- Produces: `services.employees.create(actor, **fields) -> Employee`, `services.employees.update(actor, employee, **fields) -> Employee` (audits every changed field), `services.employees.diff(obj, fields) -> dict` used by every later service.

- [ ] **Step 1: Write the failing tests**

`tests/test_employees_service.py`:

```python
from people.models import AuditEntry
from people.services import employees
from tests.factories import make_employee


def test_create_audits_creation(hr_admin):
    e = employees.create(hr_admin, first_name="Ada", last_name="Lovelace", work_email="ada@example.org")
    assert e.pk
    row = AuditEntry.objects.get(model="people.employee", object_id=e.pk)
    assert row.field == "created" and row.after == "Ada Lovelace"


def test_update_audits_only_changed_fields(hr_admin):
    e = make_employee()
    employees.update(hr_admin, e, phone="0113", town="")
    rows = AuditEntry.objects.filter(model="people.employee", object_id=e.pk, kind="change")
    assert [r.field for r in rows] == ["phone"]
    e.refresh_from_db()
    assert e.phone == "0113"


def test_update_refuses_unknown_field(hr_admin):
    e = make_employee()
    import pytest
    with pytest.raises(ValueError):
        employees.update(hr_admin, e, salary=1)
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_employees_service.py -q`
Expected: ImportError `people.services.employees`.

- [ ] **Step 3: Implement**

`people/services/employees.py`:

```python
from django.db import transaction

from people.models import Employee
from people.services import audit

EDITABLE = {
    "first_name", "last_name", "preferred_name", "work_email", "personal_email", "phone",
    "date_of_birth", "address_line1", "address_line2", "town", "postcode", "ni_number", "user",
}


def diff(obj, fields):
    """{field: (before, after)} for the fields whose value would change."""
    out = {}
    for field, new in fields.items():
        old = getattr(obj, field)
        if old != new:
            out[field] = (old, new)
    return out


@transaction.atomic
def create(actor, **fields):
    unknown = set(fields) - EDITABLE
    if unknown:
        raise ValueError(f"not editable: {sorted(unknown)}")
    employee = Employee(**fields)
    employee.full_clean()
    employee.save()
    audit.record(actor, employee, {"created": ("", employee.name)})
    return employee


@transaction.atomic
def update(actor, employee, **fields):
    unknown = set(fields) - EDITABLE
    if unknown:
        raise ValueError(f"not editable: {sorted(unknown)}")
    changes = diff(employee, fields)
    for field, (_, new) in changes.items():
        setattr(employee, field, new)
    employee.full_clean()
    employee.save()
    audit.record(actor, employee, changes)
    return employee
```

- [ ] **Step 4: Run and commit**

Run: `python -m pytest tests/test_employees_service.py -q`
Expected: 3 passed.

```bash
git add -A
git commit -m "feat: employee service with audited create and update"
```

---

### Task 5: Employment and Team models

**Files:**
- Create: `people/models/employment.py`; Modify: `people/models/__init__.py`, `tests/factories.py`; Create `tests/test_employment_model.py`

**Interfaces:**
- Produces: `Employment(employee, start_date, end_date, leaving_reason, continuous_service_date)` with `LeavingReason` choices, `Employment.is_active_on(day) -> bool`, `Employment.clean()` refusing an end before the start; `Team(name, display_order, min_present)`; `tests.factories.make_employment(employee=None, start=MON, **kw)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/factories.py`:

```python
from people.models import Employment, Team  # noqa: E402


def make_employment(employee=None, start=MON, **kw):
    employee = employee or make_employee()
    kw.setdefault("continuous_service_date", start)
    return Employment.objects.create(employee=employee, start_date=start, **kw)


def make_team(name="Reception", **kw):
    return Team.objects.create(name=name, **kw)
```

`tests/test_employment_model.py`:

```python
from datetime import date

import pytest
from django.core.exceptions import ValidationError

from tests.factories import make_employment


def test_active_on_respects_both_bounds(db):
    emp = make_employment(start=date(2026, 4, 6), end_date=date(2026, 9, 30))
    assert not emp.is_active_on(date(2026, 4, 5))
    assert emp.is_active_on(date(2026, 4, 6))
    assert emp.is_active_on(date(2026, 9, 30))
    assert not emp.is_active_on(date(2026, 10, 1))


def test_open_ended_is_active_forever(db):
    emp = make_employment()
    assert emp.is_active_on(date(2099, 1, 1))


def test_end_before_start_refused(db):
    emp = make_employment()
    emp.end_date = emp.start_date.replace(day=1)
    with pytest.raises(ValidationError):
        emp.full_clean()


def test_service_date_defaults_to_start(db):
    emp = make_employment()
    assert emp.continuous_service_date == emp.start_date
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_employment_model.py -q`
Expected: ImportError `Employment`.

- [ ] **Step 3: Implement**

`people/models/employment.py`:

```python
from django.core.exceptions import ValidationError
from django.db import models

from .employee import Employee


class Team(models.Model):
    name = models.CharField(max_length=60, unique=True)
    display_order = models.PositiveIntegerField(default=100)
    min_present = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Warn an approver when agreeing a request would leave fewer "
                  "of this team present on a day. Blank means never warn.")

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class Employment(models.Model):
    """One dated spell of employment. A returner gets a new row; history
    stays on the old one. Spells for one employee never overlap
    (people.services.employments.start enforces it)."""
    class LeavingReason(models.TextChoices):
        RESIGNED = "resigned", "Resigned"
        RETIRED = "retired", "Retired"
        END_OF_FIXED_TERM = "fixed_term", "End of fixed term"
        DISMISSED = "dismissed", "Dismissed"
        REDUNDANCY = "redundancy", "Redundancy"
        DEATH = "death", "Death in service"
        OTHER = "other", "Other"

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="employments")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    leaving_reason = models.CharField(
        max_length=12, choices=LeavingReason.choices, blank=True, default="")
    continuous_service_date = models.DateField(
        help_text="Defaults to the start date. Earlier when reckonable service "
                  "carries over from elsewhere in the NHS or an earlier spell. "
                  "Service tiers read this, never the start date.")

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        end = f"{self.end_date:%d %b %Y}" if self.end_date else "present"
        return f"{self.employee} {self.start_date:%d %b %Y} to {end}"

    def clean(self):
        super().clean()
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date is before the start date."})
        if self.end_date and not self.leaving_reason:
            raise ValidationError({"leaving_reason": "Say why the employment ended."})

    def save(self, *args, **kwargs):
        if not self.continuous_service_date:
            self.continuous_service_date = self.start_date
        super().save(*args, **kwargs)

    def is_active_on(self, day):
        if day < self.start_date:
            return False
        return self.end_date is None or day <= self.end_date
```

Add both to `people/models/__init__.py` and `__all__`.

- [ ] **Step 4: Migrate, run, commit**

Run: `DEBUG=1 python manage.py makemigrations people && python -m pytest tests/test_employment_model.py -q`
Expected: 4 passed.

```bash
git add -A
git commit -m "feat: Employment spells with their own continuous-service date, and Team"
```

---

### Task 6: Employments service: start, end, current, service years

> **Execution note (2026-09-28):** the days/365.25 formula below was replaced during execution by a calendar-anniversary computation (whole years by anniversary plus the fraction of the current year, rounded down), because 1826 days is 4.99 on a fifth anniversary and a tier would never start on the day the spec implies. The test expectations changed with it. The ledger for this plan records the ruling.

**Files:**
- Create: `people/services/employments.py`, `tests/test_employments_service.py`

**Interfaces:**
- Produces: `employments.current(employee, day) -> Employment | None`, `employments.start(actor, employee, start_date, continuous_service_date=None) -> Employment` (refuses overlap), `employments.end(actor, employment, end_date, leaving_reason) -> Employment`, `employments.service_years(employment, day) -> Decimal` (whole years and fraction, from `continuous_service_date`), `employments.active_on(day) -> QuerySet[Employment]`.

- [ ] **Step 1: Write the failing tests**

`tests/test_employments_service.py`:

```python
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from people.models import AuditEntry, Employment
from people.services import employments
from tests.factories import make_employee, make_employment


def test_start_and_current(hr_admin):
    e = make_employee()
    emp = employments.start(hr_admin, e, date(2026, 4, 6))
    assert employments.current(e, date(2026, 4, 6)) == emp
    assert employments.current(e, date(2026, 4, 5)) is None
    assert AuditEntry.objects.filter(model="people.employment", object_id=emp.pk).exists()


def test_end_then_return_the_next_day(hr_admin):
    e = make_employee()
    first = employments.start(hr_admin, e, date(2024, 1, 1))
    employments.end(hr_admin, first, date(2026, 3, 31), Employment.LeavingReason.RESIGNED)
    second = employments.start(hr_admin, e, date(2026, 4, 1))
    assert employments.current(e, date(2026, 3, 31)) == first
    assert employments.current(e, date(2026, 4, 1)) == second


def test_overlapping_spell_refused(hr_admin):
    e = make_employee()
    employments.start(hr_admin, e, date(2026, 1, 1))
    with pytest.raises(ValidationError):
        employments.start(hr_admin, e, date(2026, 6, 1))


def test_service_years_reads_service_date(db):
    emp = make_employment(start=date(2026, 4, 6), continuous_service_date=date(2020, 10, 6))
    assert employments.service_years(emp, date(2026, 4, 6)) == Decimal("5.5")
    assert employments.service_years(emp, date(2025, 10, 5)) == Decimal("4.99")


def test_active_on_filters_by_day(db):
    a = make_employment(start=date(2026, 1, 1), end_date=date(2026, 6, 30),
                        leaving_reason="resigned")
    b = make_employment(employee=make_employee(first="Bo"), start=date(2026, 7, 1))
    assert list(employments.active_on(date(2026, 3, 1))) == [a]
    assert list(employments.active_on(date(2026, 8, 1))) == [b]
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_employments_service.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement**

`people/services/employments.py`:

```python
from decimal import ROUND_DOWN, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from people.models import Employment
from people.services import audit


def active_on(day):
    return Employment.objects.filter(
        Q(start_date__lte=day) & (Q(end_date__isnull=True) | Q(end_date__gte=day)))


def current(employee, day):
    return active_on(day).filter(employee=employee).first()


def _overlaps(employee, start, end, exclude_pk=None):
    qs = Employment.objects.filter(employee=employee)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    qs = qs.filter(Q(end_date__isnull=True) | Q(end_date__gte=start))
    if end is not None:
        qs = qs.filter(start_date__lte=end)
    return qs.exists()


@transaction.atomic
def start(actor, employee, start_date, continuous_service_date=None):
    if _overlaps(employee, start_date, None):
        raise ValidationError("This person already has an employment covering that date.")
    emp = Employment(employee=employee, start_date=start_date,
                     continuous_service_date=continuous_service_date or start_date)
    emp.full_clean()
    emp.save()
    audit.record(actor, emp, {"start_date": ("", start_date),
                              "continuous_service_date": ("", emp.continuous_service_date)})
    return emp


@transaction.atomic
def end(actor, employment, end_date, leaving_reason):
    before = (employment.end_date, employment.leaving_reason)
    employment.end_date = end_date
    employment.leaving_reason = leaving_reason
    employment.full_clean()
    employment.save()
    audit.record(actor, employment, {"end_date": (before[0], end_date),
                                     "leaving_reason": (before[1], leaving_reason)})
    return employment


def service_years(employment, day):
    """Continuous service on `day`, in years to two places, rounded down so
    a tier is never reached a day early."""
    delta = day - employment.continuous_service_date
    return (Decimal(delta.days) / Decimal("365.25")).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
```

- [ ] **Step 4: Run and commit**

Run: `python -m pytest tests/test_employments_service.py -q`
Expected: 5 passed.

```bash
git add -A
git commit -m "feat: employments service: start, end, current, service years"
```

---

### Task 7: Positions and the reporting line

**Files:**
- Modify: `people/models/employment.py`, `people/models/__init__.py`, `tests/factories.py`; Create: `people/services/positions.py`, `tests/test_positions.py`

**Interfaces:**
- Produces: `Position(employment, title, team, line_manager, primary, from_date, to_date)`; `positions.add(actor, employment, title, team, line_manager, from_date, primary=True, to_date=None) -> Position` (refuses self-management and cycles, refuses a second primary on overlapping dates); `positions.end(actor, position, to_date)`; `positions.on(employment, day) -> QuerySet[Position]`; `positions.primary_on(employment, day) -> Position | None`; `tests.factories.make_position(employment, manager=None, **kw)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/factories.py`:

```python
from people.models import Position  # noqa: E402


def make_position(employment, manager=None, title="Receptionist", team=None, start=None, **kw):
    team = team or Team.objects.first() or make_team()
    return Position.objects.create(
        employment=employment, title=title, team=team, line_manager=manager,
        from_date=start or employment.start_date, **kw)
```

`tests/test_positions.py`:

```python
from datetime import date

import pytest
from django.core.exceptions import ValidationError

from people.services import positions
from tests.factories import make_employee, make_employment, make_team


def _two():
    a = make_employment(employee=make_employee(first="Ann"))
    b = make_employment(employee=make_employee(first="Ben"))
    return a, b


def test_add_and_primary_on(hr_admin):
    a, b = _two()
    team = make_team()
    p = positions.add(hr_admin, b, "Receptionist", team, a.employee, b.start_date)
    assert positions.primary_on(b, b.start_date) == p
    assert positions.primary_on(b, date(2020, 1, 1)) is None


def test_self_management_refused(hr_admin):
    a, _ = _two()
    with pytest.raises(ValidationError):
        positions.add(hr_admin, a, "Manager", make_team(), a.employee, a.start_date)


def test_cycle_refused(hr_admin):
    a, b = _two()
    team = make_team()
    positions.add(hr_admin, b, "Receptionist", team, a.employee, b.start_date)
    with pytest.raises(ValidationError):
        positions.add(hr_admin, a, "Lead", team, b.employee, a.start_date)


def test_second_primary_on_same_dates_refused(hr_admin):
    a, b = _two()
    team = make_team()
    positions.add(hr_admin, b, "Receptionist", team, a.employee, b.start_date)
    with pytest.raises(ValidationError):
        positions.add(hr_admin, b, "Admin", team, a.employee, b.start_date)
    positions.add(hr_admin, b, "Admin", team, a.employee, b.start_date, primary=False)
    assert positions.on(b, b.start_date).count() == 2


def test_end_position(hr_admin):
    a, b = _two()
    p = positions.add(hr_admin, b, "Receptionist", make_team(), a.employee, b.start_date)
    positions.end(hr_admin, p, date(2026, 12, 31))
    assert positions.primary_on(b, date(2027, 1, 1)) is None
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_positions.py -q`
Expected: ImportError `Position`.

- [ ] **Step 3: Implement**

Append to `people/models/employment.py`:

```python
class Position(models.Model):
    """A dated job. The current primary position's line manager is the
    reporting line, which routes approvals."""
    employment = models.ForeignKey(Employment, on_delete=models.PROTECT, related_name="positions")
    title = models.CharField(max_length=80)
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="positions")
    line_manager = models.ForeignKey(
        Employee, null=True, blank=True, on_delete=models.PROTECT, related_name="reports")
    primary = models.BooleanField(default=True)
    from_date = models.DateField()
    to_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-primary", "from_date"]

    def __str__(self):
        return f"{self.title} ({self.team})"

    def clean(self):
        super().clean()
        if self.to_date and self.to_date < self.from_date:
            raise ValidationError({"to_date": "End date is before the start date."})

    def is_active_on(self, day):
        return self.from_date <= day and (self.to_date is None or day <= self.to_date)
```

Export `Position` from `people/models/__init__.py`.

`people/services/positions.py`:

```python
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from people.models import Position
from people.services import audit


def on(employment, day):
    return Position.objects.filter(
        employment=employment, from_date__lte=day
    ).filter(Q(to_date__isnull=True) | Q(to_date__gte=day)).select_related("team", "line_manager")


def primary_on(employment, day):
    return on(employment, day).filter(primary=True).first()


def manager_of(employee, day):
    """The line manager of the employee's current primary position, or None."""
    from people.services import employments
    emp = employments.current(employee, day)
    if emp is None:
        return None
    pos = primary_on(emp, day)
    return pos.line_manager if pos else None


def _would_cycle(employee, manager, day):
    """Walking up from `manager` must never reach `employee`."""
    seen = set()
    cur = manager
    while cur is not None:
        if cur == employee:
            return True
        if cur.pk in seen:
            return True
        seen.add(cur.pk)
        cur = manager_of(cur, day)
    return False


@transaction.atomic
def add(actor, employment, title, team, line_manager, from_date, primary=True, to_date=None):
    if line_manager is not None:
        if line_manager == employment.employee:
            raise ValidationError({"line_manager": "A person cannot be their own manager."})
        if _would_cycle(employment.employee, line_manager, from_date):
            raise ValidationError({"line_manager": "That would make the reporting line a loop."})
    if primary:
        clash = Position.objects.filter(employment=employment, primary=True).filter(
            Q(to_date__isnull=True) | Q(to_date__gte=from_date))
        if to_date is not None:
            clash = clash.filter(from_date__lte=to_date)
        if clash.exists():
            raise ValidationError({"primary": "There is already a primary position on those dates."})
    pos = Position(employment=employment, title=title, team=team, line_manager=line_manager,
                   primary=primary, from_date=from_date, to_date=to_date)
    pos.full_clean()
    pos.save()
    audit.record(actor, pos, {"created": ("", f"{title}, {team}, reports to {line_manager or 'nobody'}")})
    return pos


@transaction.atomic
def end(actor, position, to_date):
    before = position.to_date
    position.to_date = to_date
    position.full_clean()
    position.save()
    audit.record(actor, position, {"to_date": (before, to_date)})
    return position
```

- [ ] **Step 4: Migrate, run, commit**

Run: `DEBUG=1 python manage.py makemigrations people && python -m pytest tests/test_positions.py -q`
Expected: 5 passed.

```bash
git add -A
git commit -m "feat: positions with a cycle-checked reporting line"
```

---

### Task 8: Contract types and contracts

> **Execution note (2026-09-28):** `fte()` now sums each active contract's own `weekly_amount / full_time_weekly` (the code below divided the total by the first contract's figure, incoherent when two same-unit types coexist); `end()` re-runs the unit-clash check for the new range; `Contract` orders by `from_date, id`; and two boundary tests were added because the ones below never reached the date logic. The ledger records the rulings.

**Files:**
- Create: `people/models/contract.py`, `people/services/contracts.py`, `tests/test_contracts.py`; Modify: `people/models/__init__.py`, `tests/factories.py`

**Interfaces:**
- Produces: `ContractType(name, unit, full_time_weekly, display_order)` with `Unit.SESSIONS = "sessions"`, `Unit.HOURS = "hours"`; `Contract(employment, contract_type, basis, from_date, to_date, weekly_amount, notes)` with `Basis.PERMANENT`/`Basis.FIXED_TERM`; `contracts.add(actor, employment, contract_type, weekly_amount, from_date, basis="permanent", to_date=None, notes="") -> Contract`; `contracts.end(actor, contract, to_date)`; `contracts.active_on(employment, day) -> QuerySet[Contract]`; `contracts.contracted_amount(employment, day) -> Decimal`; `contracts.unit(employment, day) -> str | None`; `contracts.fte(employment, day) -> Decimal`; `tests.factories.make_contract_type(name="Reception", unit="hours", full_time=Decimal("37.5"))`, `make_contract(employment, ctype=None, amount=..., start=None, **kw)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/factories.py`:

```python
from decimal import Decimal  # noqa: E402

from people.models import Contract, ContractType  # noqa: E402


def make_contract_type(name="Reception", unit="hours", full_time=Decimal("37.5")):
    ct, _ = ContractType.objects.get_or_create(
        name=name, defaults={"unit": unit, "full_time_weekly": full_time})
    return ct


def make_contract(employment, ctype=None, amount=Decimal("37.5"), start=None, **kw):
    ctype = ctype or make_contract_type()
    return Contract.objects.create(
        employment=employment, contract_type=ctype, weekly_amount=amount,
        from_date=start or employment.start_date, **kw)
```

`tests/test_contracts.py`:

```python
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from people.services import contracts
from tests.factories import make_contract_type, make_employment


def test_sum_of_concurrent_contracts(hr_admin):
    emp = make_employment(start=date(2026, 4, 1))
    ct = make_contract_type()
    contracts.add(hr_admin, emp, ct, Decimal("18.75"), date(2026, 4, 1))
    contracts.add(hr_admin, emp, ct, Decimal("18.75"), date(2026, 4, 1),
                  basis="fixed_term", to_date=date(2027, 3, 31))
    assert contracts.contracted_amount(emp, date(2026, 10, 1)) == Decimal("37.5")
    assert contracts.contracted_amount(emp, date(2027, 4, 1)) == Decimal("18.75")
    assert contracts.fte(emp, date(2026, 10, 1)) == Decimal("1")
    assert contracts.fte(emp, date(2027, 4, 1)) == Decimal("0.5")


def test_touching_contracts_do_not_clash(hr_admin):
    emp = make_employment(start=date(2026, 1, 1))
    ct = make_contract_type()
    a = contracts.add(hr_admin, emp, ct, Decimal("30"), date(2026, 1, 1), to_date=date(2026, 3, 31))
    contracts.add(hr_admin, emp, ct, Decimal("20"), date(2026, 4, 1))
    assert contracts.contracted_amount(emp, date(2026, 3, 31)) == Decimal("30")
    assert contracts.contracted_amount(emp, date(2026, 4, 1)) == Decimal("20")
    assert a.to_date == date(2026, 3, 31)


def test_mixed_units_refused(hr_admin):
    emp = make_employment()
    hours = make_contract_type()
    sessions = make_contract_type("Salaried GP", "sessions", Decimal("9"))
    contracts.add(hr_admin, emp, hours, Decimal("15"), emp.start_date)
    with pytest.raises(ValidationError):
        contracts.add(hr_admin, emp, sessions, Decimal("2"), emp.start_date)


def test_fixed_term_needs_end(hr_admin):
    emp = make_employment()
    with pytest.raises(ValidationError):
        contracts.add(hr_admin, emp, make_contract_type(), Decimal("10"), emp.start_date, basis="fixed_term")


def test_unit_and_zero_when_no_contract(db):
    emp = make_employment()
    assert contracts.unit(emp, emp.start_date) is None
    assert contracts.contracted_amount(emp, emp.start_date) == Decimal("0")
    assert contracts.fte(emp, emp.start_date) == Decimal("0")


def test_contract_outside_employment_refused(hr_admin):
    emp = make_employment(start=date(2026, 4, 6))
    with pytest.raises(ValidationError):
        contracts.add(hr_admin, emp, make_contract_type(), Decimal("10"), date(2026, 4, 1))
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_contracts.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement**

`people/models/contract.py`:

```python
from django.core.exceptions import ValidationError
from django.db import models

from .employment import Employment


class ContractType(models.Model):
    """Configurable: adding a kind of staff is a row, not a release."""
    class Unit(models.TextChoices):
        SESSIONS = "sessions", "Sessions"
        HOURS = "hours", "Hours"

    name = models.CharField(max_length=60, unique=True)
    unit = models.CharField(max_length=8, choices=Unit.choices)
    full_time_weekly = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text="What full time is in this unit: 9 sessions, 37.5 hours. FTE is derived from it.")
    display_order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class Contract(models.Model):
    """A dated contractual arrangement. Rows may overlap; the contracted
    amount on a day is their sum (people.services.contracts)."""
    class Basis(models.TextChoices):
        PERMANENT = "permanent", "Permanent"
        FIXED_TERM = "fixed_term", "Fixed term"

    employment = models.ForeignKey(Employment, on_delete=models.PROTECT, related_name="contracts")
    contract_type = models.ForeignKey(ContractType, on_delete=models.PROTECT, related_name="contracts")
    basis = models.CharField(max_length=10, choices=Basis.choices, default=Basis.PERMANENT)
    from_date = models.DateField()
    to_date = models.DateField(null=True, blank=True)
    weekly_amount = models.DecimalField(max_digits=5, decimal_places=2)
    notes = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["from_date"]

    def __str__(self):
        return f"{self.weekly_amount} {self.contract_type.unit}/week {self.get_basis_display().lower()}"

    def clean(self):
        super().clean()
        if self.basis == self.Basis.FIXED_TERM and not self.to_date:
            raise ValidationError({"to_date": "A fixed-term contract needs an end date."})
        if self.to_date and self.to_date < self.from_date:
            raise ValidationError({"to_date": "End date is before the start date."})
        if self.employment_id:
            emp = self.employment
            if self.from_date < emp.start_date or (emp.end_date and self.from_date > emp.end_date):
                raise ValidationError({"from_date": "Outside the employment's dates."})

    def is_active_on(self, day):
        return self.from_date <= day and (self.to_date is None or day <= self.to_date)


class PayRecord(models.Model):
    """Dated pay, for the payroll changes report only. No arithmetic."""
    class Basis(models.TextChoices):
        ANNUAL = "annual", "Annual salary"
        HOURLY = "hourly", "Hourly rate"
        PER_SESSION = "session", "Per session"

    employment = models.ForeignKey(Employment, on_delete=models.PROTECT, related_name="pay_records")
    from_date = models.DateField()
    to_date = models.DateField(null=True, blank=True)
    basis = models.CharField(max_length=8, choices=Basis.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        ordering = ["from_date"]

    def __str__(self):
        return f"{self.get_basis_display()} {self.amount} from {self.from_date:%d %b %Y}"
```

Export `Contract`, `ContractType`, `PayRecord`.

`people/services/contracts.py`:

```python
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from people.models import Contract
from people.services import audit


def active_on(employment, day):
    return Contract.objects.filter(
        employment=employment, from_date__lte=day
    ).filter(Q(to_date__isnull=True) | Q(to_date__gte=day)).select_related("contract_type")


def contracted_amount(employment, day):
    return sum((c.weekly_amount for c in active_on(employment, day)), Decimal("0"))


def unit(employment, day):
    c = active_on(employment, day).first()
    return c.contract_type.unit if c else None


def fte(employment, day):
    rows = list(active_on(employment, day))
    if not rows:
        return Decimal("0")
    full = rows[0].contract_type.full_time_weekly
    return (sum((r.weekly_amount for r in rows), Decimal("0")) / full).quantize(Decimal("0.01"))


def _unit_clash(employment, contract_type, from_date, to_date):
    others = Contract.objects.filter(employment=employment).exclude(
        contract_type__unit=contract_type.unit
    ).filter(Q(to_date__isnull=True) | Q(to_date__gte=from_date))
    if to_date is not None:
        others = others.filter(from_date__lte=to_date)
    return others.exists()


@transaction.atomic
def add(actor, employment, contract_type, weekly_amount, from_date, basis="permanent",
        to_date=None, notes=""):
    if _unit_clash(employment, contract_type, from_date, to_date):
        raise ValidationError({"contract_type": "Concurrent contracts must share a unit "
                                                "(sessions or hours)."})
    c = Contract(employment=employment, contract_type=contract_type, basis=basis,
                 from_date=from_date, to_date=to_date, weekly_amount=weekly_amount, notes=notes)
    c.full_clean()
    c.save()
    audit.record(actor, c, {"created": ("", str(c))})
    return c


@transaction.atomic
def end(actor, contract, to_date):
    before = contract.to_date
    contract.to_date = to_date
    contract.full_clean()
    contract.save()
    audit.record(actor, contract, {"to_date": (before, to_date)})
    return contract
```

- [ ] **Step 4: Migrate, run, commit**

Run: `DEBUG=1 python manage.py makemigrations people && python -m pytest tests/test_contracts.py -q`
Expected: 6 passed.

```bash
git add -A
git commit -m "feat: contract types, overlapping contracts, pay records, and the contracted amount on a day"
```

---

### Task 9: Working patterns

**Files:**
- Create: `people/models/pattern.py`, `people/services/patterns.py`, `tests/test_patterns.py`; Modify: `people/models/__init__.py`, `tests/factories.py`

**Interfaces:**
- Produces: `WorkingPattern(employment, effective_from, cycle_weeks=1)`, `PatternDay(pattern, weekday, week_in_cycle=0, am_units, pm_units)`; `patterns.set_pattern(actor, employment, effective_from, days) -> (WorkingPattern, warning | None)` where `days` is `{weekday: (am, pm)}` for weekdays 0 to 6, missing weekdays meaning 0 and 0; `patterns.pattern_on(employment, day) -> WorkingPattern | None`; `patterns.units_on(employment, day, half) -> Decimal` with `half` in `"AM"`, `"PM"`; `patterns.weekly_total(pattern) -> Decimal`; `tests.factories.make_pattern(employment, days=None, effective_from=None)` where the default is Monday to Friday, hours 3.75 and 3.75.

- [ ] **Step 1: Write the failing tests**

Append to `tests/factories.py`:

```python
from people.models import PatternDay, WorkingPattern  # noqa: E402


def make_pattern(employment, days=None, effective_from=None):
    days = days if days is not None else {d: (Decimal("3.75"), Decimal("3.75")) for d in range(5)}
    pattern = WorkingPattern.objects.create(
        employment=employment, effective_from=effective_from or employment.start_date)
    for weekday in range(7):
        am, pm = days.get(weekday, (Decimal("0"), Decimal("0")))
        PatternDay.objects.create(pattern=pattern, weekday=weekday, am_units=am, pm_units=pm)
    return pattern
```

`tests/test_patterns.py`:

```python
from datetime import date
from decimal import Decimal

from people.services import contracts, patterns
from tests.factories import make_contract, make_employment

D = Decimal


def test_set_pattern_and_units_on(hr_admin):
    emp = make_employment(start=date(2026, 4, 6))
    pattern, warning = patterns.set_pattern(
        hr_admin, emp, date(2026, 4, 6), {0: (D("3.75"), D("3.75")), 2: (D("4"), D("0"))})
    assert warning is None or "contracted" in warning
    assert patterns.units_on(emp, date(2026, 4, 6), "AM") == D("3.75")   # Monday
    assert patterns.units_on(emp, date(2026, 4, 8), "PM") == D("0")      # Wednesday
    assert patterns.units_on(emp, date(2026, 4, 7), "AM") == D("0")      # Tuesday, absent from dict
    assert patterns.weekly_total(pattern) == D("11.5")


def test_latest_version_on_or_before_wins(hr_admin):
    emp = make_employment(start=date(2026, 1, 5))
    patterns.set_pattern(hr_admin, emp, date(2026, 1, 5), {0: (D("1"), D("1"))})
    patterns.set_pattern(hr_admin, emp, date(2026, 6, 1), {0: (D("1"), D("0"))})
    assert patterns.units_on(emp, date(2026, 5, 25), "PM") == D("1")
    assert patterns.units_on(emp, date(2026, 6, 1), "PM") == D("0")
    assert patterns.pattern_on(emp, date(2025, 12, 1)) is None


def test_total_differs_from_contract_warns_but_saves(hr_admin):
    emp = make_employment(start=date(2026, 4, 6))
    make_contract(emp, amount=D("20"))
    pattern, warning = patterns.set_pattern(hr_admin, emp, date(2026, 4, 6), {0: (D("3"), D("3"))})
    assert pattern.pk
    assert warning == "Pattern totals 6 a week; contracts total 20."


def test_same_effective_from_replaces_days(hr_admin):
    emp = make_employment(start=date(2026, 4, 6))
    patterns.set_pattern(hr_admin, emp, date(2026, 4, 6), {0: (D("1"), D("1"))})
    pattern, _ = patterns.set_pattern(hr_admin, emp, date(2026, 4, 6), {1: (D("1"), D("1"))})
    assert pattern.days.count() == 7
    assert patterns.units_on(emp, date(2026, 4, 6), "AM") == D("0")
    assert patterns.units_on(emp, date(2026, 4, 7), "AM") == D("1")
    assert contracts.unit(emp, date(2026, 4, 6)) is None
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_patterns.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement**

`people/models/pattern.py`:

```python
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .employment import Employment


class WorkingPattern(models.Model):
    """A dated version of the whole working week, in the employment's unit.
    The master; the rota reads it. cycle_weeks is always 1 in this release."""
    employment = models.ForeignKey(Employment, on_delete=models.PROTECT, related_name="patterns")
    effective_from = models.DateField()
    cycle_weeks = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["-effective_from"]
        constraints = [models.UniqueConstraint(
            fields=["employment", "effective_from"], name="one_pattern_per_employment_per_date")]

    def __str__(self):
        return f"Pattern from {self.effective_from:%d %b %Y}"


class PatternDay(models.Model):
    pattern = models.ForeignKey(WorkingPattern, on_delete=models.CASCADE, related_name="days")
    weekday = models.PositiveSmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(6)])
    week_in_cycle = models.PositiveSmallIntegerField(default=0)
    am_units = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    pm_units = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        ordering = ["week_in_cycle", "weekday"]
        constraints = [models.UniqueConstraint(
            fields=["pattern", "weekday", "week_in_cycle"], name="one_day_per_pattern")]

    def units(self, half):
        return self.am_units if half == "AM" else self.pm_units
```

Export both.

`people/services/patterns.py`:

```python
from decimal import Decimal

from django.db import transaction

from people.models import PatternDay, WorkingPattern
from people.services import audit, contracts


def pattern_on(employment, day):
    return (WorkingPattern.objects.filter(employment=employment, effective_from__lte=day)
            .order_by("-effective_from").prefetch_related("days").first())


def units_on(employment, day, half):
    pattern = pattern_on(employment, day)
    if pattern is None:
        return Decimal("0")
    for d in pattern.days.all():
        if d.weekday == day.weekday():
            return d.units(half)
    return Decimal("0")


def weekly_total(pattern):
    return sum((d.am_units + d.pm_units for d in pattern.days.all()), Decimal("0"))


@transaction.atomic
def set_pattern(actor, employment, effective_from, days):
    """Create or replace the version dated effective_from. Returns the
    pattern and a warning string when its total differs from the
    contracted amount that day, which is allowed."""
    pattern, created = WorkingPattern.objects.get_or_create(
        employment=employment, effective_from=effective_from)
    before = "" if created else ", ".join(
        f"{d.weekday}:{d.am_units}/{d.pm_units}" for d in pattern.days.all())
    pattern.days.all().delete()
    for weekday in range(7):
        am, pm = days.get(weekday, (Decimal("0"), Decimal("0")))
        PatternDay.objects.create(pattern=pattern, weekday=weekday, am_units=am, pm_units=pm)
    after = ", ".join(f"{d.weekday}:{d.am_units}/{d.pm_units}" for d in pattern.days.all())
    audit.record(actor, pattern, {"days": (before, after)})
    total = weekly_total(pattern)
    contracted = contracts.contracted_amount(employment, effective_from)
    warning = None
    if contracted and total != contracted:
        warning = f"Pattern totals {total.normalize()} a week; contracts total {contracted.normalize()}."
    return pattern, warning
```

- [ ] **Step 4: Migrate, run, commit**

Run: `DEBUG=1 python manage.py makemigrations people && python -m pytest tests/test_patterns.py -q`
Expected: 4 passed.

```bash
git add -A
git commit -m "feat: working patterns as dated versions, the master the rota will read"
```

---

### Task 10: Access rules and the approver context

**Files:**
- Create: `people/services/access.py`, `tests/test_access.py`; Modify: `people/context_processors.py`

**Interfaces:**
- Produces: `access.line_manager(employee, day) -> Employee | None`; `access.direct_reports(manager, day) -> list[Employment]`; `access.is_approver(user, day) -> bool`; `access.can_view(user, employee) -> bool` (self, current manager, HR admin, superuser); `access.can_view_restricted(user) -> bool` (HR admin or superuser); `access.route_for(employment, day) -> Employee | None` (None means the HR admin group); `access.employee_for(user) -> Employee | None`.

- [ ] **Step 1: Write the failing tests**

`tests/test_access.py`:

```python
from datetime import date

from django.contrib.auth import get_user_model

from people.services import access, positions
from tests.factories import make_employee, make_employment, make_team

User = get_user_model()
DAY = date(2026, 6, 1)


def _person(first, user=None):
    e = make_employee(first=first, user=user)
    return e, make_employment(employee=e, start=date(2026, 1, 1))


def test_route_and_reports(hr_admin, employee_user):
    boss, boss_emp = _person("Boss", user=hr_admin)
    sam, sam_emp = _person("Sam", user=employee_user)
    positions.add(None, sam_emp, "Receptionist", make_team(), boss, DAY)
    assert access.line_manager(sam, DAY) == boss
    assert access.route_for(sam_emp, DAY) == boss
    assert access.direct_reports(boss, DAY) == [sam_emp]
    assert access.is_approver(hr_admin, DAY)
    assert not access.is_approver(employee_user, DAY)


def test_route_without_manager_goes_to_admin_group(db):
    sam, sam_emp = _person("Sam")
    positions.add(None, sam_emp, "Manager", make_team(), None, DAY)
    assert access.route_for(sam_emp, DAY) is None


def test_can_view(hr_admin, employee_user):
    other_user = User.objects.create_user(email="o@example.org", password="pw")
    boss, boss_emp = _person("Boss", user=other_user)
    sam, sam_emp = _person("Sam", user=employee_user)
    stranger, _ = _person("Stranger")
    positions.add(None, sam_emp, "Receptionist", make_team(), boss, DAY)
    assert access.can_view(employee_user, sam)
    assert access.can_view(other_user, sam)
    assert not access.can_view(employee_user, boss)
    assert not access.can_view(employee_user, stranger)
    assert access.can_view(hr_admin, stranger)
    assert access.can_view_restricted(hr_admin)
    assert not access.can_view_restricted(other_user)


def test_employee_for(employee_user):
    assert access.employee_for(employee_user) is None
    sam, _ = _person("Sam", user=employee_user)
    assert access.employee_for(employee_user) == sam
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_access.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement**

`people/services/access.py`:

```python
"""Who may see and decide what. Read by views, templates and the admin;
every rule about relationship-based access lives here."""

from django.db.models import Q

from people.models import Employee, Position
from people.services import employments, positions


def employee_for(user):
    if user is None or not user.is_authenticated:
        return None
    return Employee.objects.filter(user=user).first()


def line_manager(employee, day):
    return positions.manager_of(employee, day)


def direct_reports(manager, day):
    rows = (Position.objects.filter(line_manager=manager, primary=True, from_date__lte=day)
            .filter(Q(to_date__isnull=True) | Q(to_date__gte=day))
            .select_related("employment__employee"))
    return [p.employment for p in rows if p.employment.is_active_on(day)]


def is_approver(user, day):
    me = employee_for(user)
    return bool(me) and bool(direct_reports(me, day))


def can_view_restricted(user):
    return bool(user and user.is_authenticated and (user.is_hr_admin or user.is_superuser))


def can_view(user, employee, day=None):
    from datetime import date
    day = day or date.today()
    if can_view_restricted(user):
        return True
    me = employee_for(user)
    if me is None:
        return False
    if me == employee:
        return True
    return line_manager(employee, day) == me


def route_for(employment, day):
    """The approver for a request from this employment, or None for the
    HR admin group: no manager, or the requester tops their own chain."""
    manager = line_manager(employment.employee, day)
    if manager is None:
        return None
    if employments.current(manager, day) is None:
        return None
    return manager
```

`people/context_processors.py`:

```python
from datetime import date

from people.services import access


def roles(request):
    user = getattr(request, "user", None)
    return {"is_approver": access.is_approver(user, date.today()) if user else False}
```

- [ ] **Step 4: Run and commit**

Run: `python -m pytest tests/test_access.py tests/test_accounts.py -q`
Expected: all pass.

```bash
git add -A
git commit -m "feat: access rules: line manager, direct reports, approver, routing"
```

---

### Task 11: The employee's own record page and the team page

**Files:**
- Create: `people/views.py`, `templates/people/me.html`, `templates/people/team.html`, `tests/test_people_views.py`; Modify: `people/urls.py`

**Interfaces:**
- Produces: URL names `people:me` and `people:team`; `me` shows the record and lets the employee edit personal details through `services.employees.update`; `team` lists an approver's direct reports with title, team and pattern total. Pay and NI are never rendered here.

- [ ] **Step 1: Write the failing tests**

`tests/test_people_views.py`:

```python
from datetime import date

from people.models import Employee
from people.services import positions
from tests.factories import make_employee, make_employment, make_team


def test_me_shows_record_and_hides_ni(employee_client, employee_user):
    e = make_employee(user=employee_user, ni_number="AB123456C")
    make_employment(employee=e)
    r = employee_client.get("/people/me/")
    assert r.status_code == 200
    body = r.content.decode()
    assert "Sam Patel" in body and "AB123456C" not in body


def test_me_without_employee_record_is_polite(employee_client):
    r = employee_client.get("/people/me/")
    assert r.status_code == 200
    assert "no employee record" in r.content.decode().lower()


def test_me_post_updates_personal_details(employee_client, employee_user):
    e = make_employee(user=employee_user)
    r = employee_client.post("/people/me/", {"phone": "0113", "personal_email": "s@x.org",
                                             "address_line1": "", "address_line2": "",
                                             "town": "Leeds", "postcode": ""})
    assert r.status_code == 302
    assert Employee.objects.get(pk=e.pk).phone == "0113"


def test_team_lists_reports_only_for_approver(employee_client, employee_user, admin_client, hr_admin):
    boss = make_employee(first="Boss", user=hr_admin)
    make_employment(employee=boss, start=date(2026, 1, 1))
    sam = make_employee(user=employee_user)
    sam_emp = make_employment(employee=sam, start=date(2026, 1, 1))
    positions.add(None, sam_emp, "Receptionist", make_team(), boss, date(2026, 1, 1))
    assert employee_client.get("/people/team/").status_code == 403
    r = admin_client.get("/people/team/")
    assert r.status_code == 200 and "Sam Patel" in r.content.decode()
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_people_views.py -q`
Expected: failures (placeholder views answer 200 "me"; the assertions fail).

- [ ] **Step 3: Implement**

`people/views.py`:

```python
from datetime import date

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from people.models import Employee
from people.services import access, contracts, employees, employments, patterns, positions


class PersonalDetailsForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["personal_email", "phone", "address_line1", "address_line2", "town", "postcode"]


@login_required
def me(request):
    employee = access.employee_for(request.user)
    if employee is None:
        return render(request, "people/me.html", {"employee": None})
    today = date.today()
    if request.method == "POST":
        form = PersonalDetailsForm(request.POST, instance=employee)
        if form.is_valid():
            employees.update(request.user, employee, **form.cleaned_data)
            messages.success(request, "Saved.")
            return redirect("people:me")
    else:
        form = PersonalDetailsForm(instance=employee)
    emp = employments.current(employee, today)
    ctx = {"employee": employee, "employment": emp, "form": form}
    if emp:
        ctx.update({
            "position": positions.primary_on(emp, today),
            "contracts": list(contracts.active_on(emp, today)),
            "contracted": contracts.contracted_amount(emp, today),
            "unit": contracts.unit(emp, today),
            "pattern": patterns.pattern_on(emp, today),
        })
    return render(request, "people/me.html", ctx)


@login_required
def team(request):
    me_ = access.employee_for(request.user)
    today = date.today()
    if not (me_ and access.is_approver(request.user, today)):
        raise PermissionDenied
    rows = []
    for emp in access.direct_reports(me_, today):
        pattern = patterns.pattern_on(emp, today)
        rows.append({
            "employee": emp.employee,
            "position": positions.primary_on(emp, today),
            "contracted": contracts.contracted_amount(emp, today),
            "unit": contracts.unit(emp, today),
            "pattern_total": patterns.weekly_total(pattern) if pattern else None,
        })
    return render(request, "people/team.html", {"rows": rows})
```

`people/urls.py`:

```python
from django.urls import path

from . import views

app_name = "people"
urlpatterns = [
    path("me/", views.me, name="me"),
    path("team/", views.team, name="team"),
]
```

`templates/people/me.html`:

```html
{% extends "base.html" %}
{% block title %}My record{% endblock %}
{% block content %}
<h1>My record</h1>
{% if not employee %}
  <p class="notice">There is no employee record linked to your login yet. Ask the practice manager.</p>
{% else %}
  <section class="card">
    <h2>{{ employee.name }}</h2>
    {% if employment %}
      <dl class="facts">
        <dt>Employed since</dt><dd>{{ employment.start_date|date:"j M Y" }}</dd>
        <dt>Continuous service from</dt><dd>{{ employment.continuous_service_date|date:"j M Y" }}</dd>
        {% if position %}<dt>Position</dt><dd>{{ position.title }}, {{ position.team }}{% if position.line_manager %}, reports to {{ position.line_manager.name }}{% endif %}</dd>{% endif %}
        <dt>Contracted</dt><dd>{{ contracted|floatformat:"-2" }} {{ unit|default:"" }} a week</dd>
      </dl>
      {% if pattern %}
      <table class="pattern"><thead><tr><th></th><th>Mon</th><th>Tue</th><th>Wed</th><th>Thu</th><th>Fri</th><th>Sat</th><th>Sun</th></tr></thead>
        <tbody>
          <tr><th>AM</th>{% for d in pattern.days.all %}<td>{{ d.am_units|floatformat:"-2" }}</td>{% endfor %}</tr>
          <tr><th>PM</th>{% for d in pattern.days.all %}<td>{{ d.pm_units|floatformat:"-2" }}</td>{% endfor %}</tr>
        </tbody></table>
      {% endif %}
    {% else %}
      <p>No current employment.</p>
    {% endif %}
  </section>
  <section class="card">
    <h2>Personal details</h2>
    <form method="post">{% csrf_token %}{{ form.as_div }}<button type="submit" class="btn">Save</button></form>
  </section>
{% endif %}
{% endblock %}
```

`templates/people/team.html`:

```html
{% extends "base.html" %}
{% block title %}My team{% endblock %}
{% block content %}
<h1>My team</h1>
<table class="list">
  <thead><tr><th>Name</th><th>Position</th><th>Contracted</th><th>Pattern</th></tr></thead>
  <tbody>
  {% for r in rows %}
    <tr><td>{{ r.employee.name }}</td><td>{% if r.position %}{{ r.position.title }}, {{ r.position.team }}{% endif %}</td>
        <td>{{ r.contracted|floatformat:"-2" }} {{ r.unit|default:"" }}</td>
        <td>{% if r.pattern_total is not None %}{{ r.pattern_total|floatformat:"-2" }}{% else %}none{% endif %}</td></tr>
  {% empty %}<tr><td colspan="4">Nobody reports to you today.</td></tr>{% endfor %}
  </tbody>
</table>
{% endblock %}
```

Add `.facts`, `.pattern` and `.list` rules to `static/css/screens.css` using only `var(--…)` tokens from `tokens.css`.

- [ ] **Step 4: Run and commit**

Run: `python -m pytest tests/test_people_views.py tests/test_accounts.py -q`
Expected: all pass.

```bash
git add -A
git commit -m "feat: my record and my team pages"
```

---

### Task 12: The admin, the nightly job, and the audit of restricted views

**Files:**
- Create: `people/admin.py`, `people/admin_forms.py`, `people/services/nightly.py`, `people/management/__init__.py`, `people/management/commands/__init__.py`, `people/management/commands/hr_nightly.py`, `tests/test_people_admin.py`, `tests/test_nightly.py`

**Interfaces:**
- Produces: admin registrations for `Employee` (hub, with inlines for `EmergencyContact` and `Employment`), `Employment` (with inlines `Position`, `Contract`, `WorkingPattern`, and `PayRecord` for HR admins only), `Team`, `ContractType`, `AuditEntry` (read-only); `nightly.run(today) -> dict` returning `{"logins_disabled": n}`; `manage.py hr_nightly`.

- [ ] **Step 1: Write the failing tests**

`tests/test_nightly.py`:

```python
from datetime import date

from django.contrib.auth import get_user_model

from people.services import nightly
from tests.factories import make_employee, make_employment

User = get_user_model()


def test_leaver_login_disabled_returner_kept(db):
    u1 = User.objects.create_user(email="left@example.org", password="pw")
    u2 = User.objects.create_user(email="back@example.org", password="pw")
    left = make_employee(first="Lee", user=u1)
    make_employment(employee=left, start=date(2025, 1, 1), end_date=date(2026, 5, 31), leaving_reason="resigned")
    back = make_employee(first="Bea", user=u2)
    make_employment(employee=back, start=date(2025, 1, 1), end_date=date(2026, 5, 31), leaving_reason="resigned")
    make_employment(employee=back, start=date(2026, 7, 1))
    result = nightly.run(date(2026, 6, 1))
    assert result == {"logins_disabled": 1}
    assert not User.objects.get(pk=u1.pk).is_active
    assert User.objects.get(pk=u2.pk).is_active


def test_command_runs(db, capsys):
    from django.core.management import call_command
    call_command("hr_nightly")
    assert "logins_disabled" in capsys.readouterr().out
```

`tests/test_people_admin.py`:

```python
from datetime import date

from people.models import AuditEntry, PayRecord
from tests.factories import make_employee, make_employment


def test_changelists_render(admin_client):
    for url in ("/admin/people/employee/", "/admin/people/employment/", "/admin/people/team/",
                "/admin/people/contracttype/", "/admin/people/auditentry/"):
        assert admin_client.get(url).status_code == 200, url


def test_employment_change_page_shows_pay_to_admin_and_audits(admin_client, hr_admin):
    emp = make_employment()
    PayRecord.objects.create(employment=emp, from_date=date(2026, 4, 6), basis="annual", amount=25000)
    r = admin_client.get(f"/admin/people/employment/{emp.pk}/change/")
    assert r.status_code == 200 and "25000" in r.content.decode()
    assert AuditEntry.objects.filter(kind="viewed", field="pay", object_id=emp.pk).exists()


def test_employee_add_goes_through_service(admin_client):
    r = admin_client.post("/admin/people/employee/add/", {
        "first_name": "Ada", "last_name": "Lovelace", "work_email": "ada@example.org",
        "preferred_name": "", "personal_email": "", "phone": "", "address_line1": "",
        "address_line2": "", "town": "", "postcode": "", "ni_number": "",
        "emergency_contacts-TOTAL_FORMS": 0, "emergency_contacts-INITIAL_FORMS": 0,
        "employments-TOTAL_FORMS": 0, "employments-INITIAL_FORMS": 0,
    })
    assert r.status_code == 302
    assert AuditEntry.objects.filter(model="people.employee", field="created").exists()


def test_audit_log_is_read_only(admin_client):
    e = make_employee()
    assert admin_client.get("/admin/people/auditentry/add/").status_code == 403
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_nightly.py tests/test_people_admin.py -q`
Expected: ImportError / 404s.

- [ ] **Step 3: Implement**

`people/services/nightly.py`:

```python
from django.contrib.auth import get_user_model

from people.models import Employee
from people.services import employments


def run(today):
    """Disable the login of anyone whose employment has ended and who has
    no spell on or after today. Idempotent."""
    User = get_user_model()
    disabled = 0
    for employee in Employee.objects.filter(user__isnull=False, user__is_active=True).select_related("user"):
        if employments.current(employee, today) is not None:
            continue
        if employee.employments.filter(start_date__gt=today).exists():
            continue
        if not employee.employments.exists():
            continue
        User.objects.filter(pk=employee.user_id).update(is_active=False)
        disabled += 1
    return {"logins_disabled": disabled}
```

`people/management/commands/hr_nightly.py`:

```python
from datetime import date

from django.core.management.base import BaseCommand

from people.services import nightly as people_nightly


class Command(BaseCommand):
    help = "Nightly housekeeping. Each app's services.nightly.run(today) is called in turn."

    def handle(self, *args, **options):
        today = date.today()
        results = {"people": people_nightly.run(today)}
        for app, result in results.items():
            self.stdout.write(f"{app}: {result}")
```

`people/admin_forms.py`:

```python
from django import forms

from people.models import Contract, Employee, Employment, Position


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["first_name", "last_name", "preferred_name", "work_email", "personal_email",
                  "phone", "date_of_birth", "address_line1", "address_line2", "town", "postcode",
                  "ni_number", "user"]


class EmploymentForm(forms.ModelForm):
    class Meta:
        model = Employment
        fields = ["employee", "start_date", "end_date", "leaving_reason", "continuous_service_date"]


class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = ["title", "team", "line_manager", "primary", "from_date", "to_date"]


class ContractForm(forms.ModelForm):
    class Meta:
        model = Contract
        fields = ["contract_type", "basis", "from_date", "to_date", "weekly_amount", "notes"]
```

`people/admin.py`:

```python
"""Unfold admin over the people models. Every save posts through a
service so the audit log and the rules hold whether a change comes from
here or from a page."""

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from unfold.admin import ModelAdmin, StackedInline, TabularInline

from people import admin_forms
from people.models import (AuditEntry, Contract, ContractType, EmergencyContact, Employee,
                           Employment, PatternDay, PayRecord, Position, Team, WorkingPattern)
from people.services import access, audit, contracts, employees, employments, positions


class EmergencyContactInline(TabularInline):
    model = EmergencyContact
    extra = 0


class EmploymentInline(TabularInline):
    model = Employment
    extra = 0
    fields = ("start_date", "end_date", "leaving_reason", "continuous_service_date")
    show_change_link = True


@admin.register(Employee)
class EmployeeAdmin(ModelAdmin):
    form = admin_forms.EmployeeForm
    list_display = ("name", "work_email", "current_position")
    search_fields = ("first_name", "last_name", "preferred_name", "work_email")
    inlines = [EmergencyContactInline, EmploymentInline]

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if not access.can_view_restricted(request.user):
            fields.remove("ni_number")
        return fields

    @admin.display(description="Position")
    def current_position(self, obj):
        from datetime import date
        emp = employments.current(obj, date.today())
        pos = positions.primary_on(emp, date.today()) if emp else None
        return f"{pos.title}, {pos.team}" if pos else ""

    def save_model(self, request, obj, form, change):
        data = {k: form.cleaned_data[k] for k in form.changed_data}
        if change:
            employees.update(request.user, obj, **data)
        else:
            new = employees.create(request.user, **form.cleaned_data)
            obj.pk = new.pk

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for inst in instances:
            if isinstance(inst, Employment):
                if inst.pk is None:
                    try:
                        employments.start(request.user, form.instance, inst.start_date,
                                          inst.continuous_service_date)
                    except ValidationError as e:
                        messages.error(request, "; ".join(e.messages))
                    continue
                inst.full_clean()
                inst.save()
                audit.record(request.user, inst, {"end_date": ("", inst.end_date)})
            else:
                inst.save()
        for inst in formset.deleted_objects:
            if not isinstance(inst, Employment):
                inst.delete()


class PositionInline(TabularInline):
    model = Position
    form = admin_forms.PositionForm
    extra = 0


class ContractInline(TabularInline):
    model = Contract
    form = admin_forms.ContractForm
    extra = 0


class PatternDayInline(TabularInline):
    model = PatternDay
    extra = 0
    fields = ("weekday", "am_units", "pm_units")


class WorkingPatternInline(StackedInline):
    model = WorkingPattern
    extra = 0
    fields = ("effective_from",)
    show_change_link = True


class PayRecordInline(TabularInline):
    model = PayRecord
    extra = 0


@admin.register(Employment)
class EmploymentAdmin(ModelAdmin):
    form = admin_forms.EmploymentForm
    list_display = ("employee", "start_date", "end_date", "leaving_reason")
    list_select_related = ("employee",)
    search_fields = ("employee__first_name", "employee__last_name")

    def get_inlines(self, request, obj):
        inlines = [PositionInline, ContractInline, WorkingPatternInline]
        if access.can_view_restricted(request.user):
            inlines.append(PayRecordInline)
        return inlines

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if access.can_view_restricted(request.user) and request.method == "GET":
            obj = self.get_object(request, object_id)
            if obj is not None and obj.pay_records.exists():
                audit.viewed(request.user, obj, "pay")
        return super().change_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        if change:
            changes = {k: (form.initial.get(k), form.cleaned_data[k]) for k in form.changed_data}
            obj.full_clean()
            obj.save()
            audit.record(request.user, obj, changes)
        else:
            new = employments.start(request.user, obj.employee, obj.start_date,
                                    obj.continuous_service_date)
            obj.pk = new.pk

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for inst in instances:
            try:
                if isinstance(inst, Position) and inst.pk is None:
                    positions.add(request.user, form.instance, inst.title, inst.team,
                                  inst.line_manager, inst.from_date, inst.primary, inst.to_date)
                elif isinstance(inst, Contract) and inst.pk is None:
                    contracts.add(request.user, form.instance, inst.contract_type, inst.weekly_amount,
                                  inst.from_date, inst.basis, inst.to_date, inst.notes)
                elif isinstance(inst, PayRecord):
                    inst.save()
                    audit.record(request.user, inst, {"amount": ("", inst.amount)})
                else:
                    inst.full_clean()
                    inst.save()
                    audit.record(request.user, inst, {"saved": ("", str(inst))})
            except ValidationError as e:
                messages.error(request, "; ".join(e.messages))
        for inst in formset.deleted_objects:
            messages.error(request, f"{inst} was not deleted: rows here end, they are not removed.")


@admin.register(WorkingPattern)
class WorkingPatternAdmin(ModelAdmin):
    list_display = ("employment", "effective_from")
    inlines = [PatternDayInline]

    def save_formset(self, request, form, formset, change):
        from decimal import Decimal
        from people.services import patterns
        formset.save(commit=False)
        days = {}
        for f in formset.forms:
            if f.cleaned_data and not f.cleaned_data.get("DELETE"):
                d = f.cleaned_data
                days[d["weekday"]] = (d.get("am_units") or Decimal("0"), d.get("pm_units") or Decimal("0"))
        _, warning = patterns.set_pattern(request.user, form.instance.employment,
                                          form.instance.effective_from, days)
        if warning:
            messages.warning(request, warning)


@admin.register(Team)
class TeamAdmin(ModelAdmin):
    list_display = ("name", "display_order", "min_present")


@admin.register(ContractType)
class ContractTypeAdmin(ModelAdmin):
    list_display = ("name", "unit", "full_time_weekly", "display_order")


@admin.register(AuditEntry)
class AuditEntryAdmin(ModelAdmin):
    list_display = ("at", "actor", "kind", "model", "object_id", "field", "before", "after")
    list_filter = ("kind", "model")
    search_fields = ("field", "before", "after", "note")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
```

Also a data migration seeding the contract types. Generate an empty one with `DEBUG=1 python manage.py makemigrations people --empty -n seed_contract_types` and give it this body:

```python
from decimal import Decimal

from django.db import migrations

SEED = [
    ("Partner", "sessions", "9"), ("Salaried GP", "sessions", "9"), ("GP trainee", "sessions", "9"),
    ("Practice nurse", "hours", "37.5"), ("HCA", "hours", "37.5"), ("Reception", "hours", "37.5"),
    ("Administration", "hours", "37.5"), ("Management", "hours", "37.5"),
]


def seed(apps, schema_editor):
    ContractType = apps.get_model("people", "ContractType")
    for order, (name, unit, full) in enumerate(SEED, start=1):
        ContractType.objects.get_or_create(
            name=name, defaults={"unit": unit, "full_time_weekly": Decimal(full),
                                 "display_order": order * 10})


class Migration(migrations.Migration):
    dependencies = [("people", "<the previous migration's name>")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
```

The `dependencies` entry is whatever `makemigrations --empty` wrote; keep it.

- [ ] **Step 4: Run and commit**

Run: `python -m pytest tests/test_nightly.py tests/test_people_admin.py -q`
Expected: all pass.

```bash
git add -A
git commit -m "feat: people admin through the services, nightly job, seeded contract types"
```

---

### Task 13: The OpenID Connect provider

**Files:**
- Create: `accounts/oidc.py`, `accounts/management/__init__.py`, `accounts/management/commands/__init__.py`, `accounts/management/commands/register_oidc_client.py`, `tests/test_oidc_provider.py`; Modify: `tests/conftest.py`

**Interfaces:**
- Produces: `accounts.oidc.Validator` adding `email` and `employee_id` claims; `manage.py register_oidc_client --name rota --redirect-uri URL` which creates an `oauth2_provider.Application` (confidential, authorization-code, `skip_authorization=True`, `algorithm="RS256"`) and prints `client_id` and `client_secret` once; the discovery document at `/o/.well-known/openid-configuration/`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/conftest.py`:

```python
@pytest.fixture(scope="session", autouse=True)
def _oidc_test_key():
    """The suite signs ID tokens with a throwaway key generated per run.
    Nothing here reaches the environment."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from django.conf import settings
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    settings.OAUTH2_PROVIDER["OIDC_RSA_PRIVATE_KEY"] = pem
    from oauth2_provider import settings as oauth2_settings
    oauth2_settings.oauth2_settings.OIDC_RSA_PRIVATE_KEY = pem
```

`tests/test_oidc_provider.py`:

```python
import json

from django.core.management import call_command
from oauth2_provider.models import Application

from accounts.oidc import Validator
from tests.factories import make_employee


def test_discovery_document(client):
    r = client.get("/o/.well-known/openid-configuration/")
    assert r.status_code == 200
    doc = r.json()
    assert "authorization_endpoint" in doc and "jwks_uri" in doc


def test_register_client_prints_credentials_once(db, capsys):
    call_command("register_oidc_client", name="rota", redirect_uri="https://rota.example/oidc/callback/")
    out = capsys.readouterr().out
    app = Application.objects.get(name="rota")
    assert app.client_id in out and "client_secret=" in out
    assert app.skip_authorization and app.algorithm == "RS256"
    assert app.client_type == Application.CLIENT_CONFIDENTIAL
    assert app.authorization_grant_type == Application.GRANT_AUTHORIZATION_CODE


def test_claims_carry_email_and_employee_id(employee_user):
    e = make_employee(user=employee_user)
    request = type("R", (), {"user": employee_user})()
    claims = Validator().get_additional_claims(request)
    assert claims == {"email": "sam@example.com", "employee_id": e.pk}


def test_claims_without_employee(employee_user):
    request = type("R", (), {"user": employee_user})()
    assert Validator().get_additional_claims(request) == {"email": "sam@example.com", "employee_id": None}
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_oidc_provider.py -q`
Expected: ImportError `accounts.oidc`.

- [ ] **Step 3: Implement**

`accounts/oidc.py`:

```python
"""What the ID token and userinfo say about a person: their email and
their employee id. Nothing else leaves this system through sign-in."""

from oauth2_provider.oauth2_validators import OAuth2Validator


class Validator(OAuth2Validator):
    oidc_claim_scope = None  # every claim below is returned for the openid scope

    def get_additional_claims(self, request):
        user = request.user
        employee = getattr(user, "employee", None)
        return {"email": user.email, "employee_id": employee.pk if employee else None}
```

`accounts/management/commands/register_oidc_client.py`:

```python
from django.core.management.base import BaseCommand
from oauth2_provider.generators import generate_client_secret
from oauth2_provider.models import Application


class Command(BaseCommand):
    help = ("Register a relying party (the rota). Prints the client id and the "
            "secret once; the secret is stored hashed and cannot be shown again.")

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)
        parser.add_argument("--redirect-uri", required=True)

    def handle(self, *args, **options):
        secret = generate_client_secret()
        app, created = Application.objects.update_or_create(
            name=options["name"],
            defaults={
                "redirect_uris": options["redirect_uri"],
                "client_type": Application.CLIENT_CONFIDENTIAL,
                "authorization_grant_type": Application.GRANT_AUTHORIZATION_CODE,
                "skip_authorization": True,
                "algorithm": "RS256",
                "client_secret": secret,
            },
        )
        self.stdout.write(f"client_id={app.client_id}")
        self.stdout.write(f"client_secret={secret}")
        self.stdout.write("Put both in the relying party's environment file now; "
                          "the secret is not shown again.")
```

- [ ] **Step 4: Run migrations for oauth2_provider, run the tests, commit**

Run: `DEBUG=1 python manage.py migrate --check || true; python -m pytest tests/test_oidc_provider.py -q`
Expected: 4 passed.

```bash
git add -A
git commit -m "feat: OpenID Connect provider with email and employee_id claims; register_oidc_client"
```

---

### Task 14: The rota signs in with the practice account

This task runs in `$ROTA` on a new branch `feature/practice-account-signin`, following the rota's own CLAUDE.md and README. It is the one rota change in this release.

**Files:**
- Modify: `requirements.txt` (add `mozilla-django-oidc==4.0.1`), `config/settings.py`, `config/urls.py`, `templates/registration/login.html`; Create: `accounts/oidc.py`, `tests/test_oidc_signin.py`, `docs/admin/sign-in.md`.

**Interfaces:**
- Consumes: the HR system's discovery document, `email` and `employee_id` claims.
- Produces: `accounts.oidc.PracticeAccountBackend`, URL names `oidc_authentication_init` and `oidc_authentication_callback`, settings `OIDC_RP_CLIENT_ID`, `OIDC_RP_CLIENT_SECRET`, `OIDC_OP_*` from the environment, and `PRACTICE_HR_URL`.

- [ ] **Step 1: Write the failing tests**

`$ROTA/tests/test_oidc_signin.py`:

```python
import pytest
from django.contrib.auth import get_user_model

from accounts.oidc import PracticeAccountBackend

User = get_user_model()


@pytest.fixture
def oidc_on(settings):
    settings.PRACTICE_HR_URL = "https://hr.example"
    settings.OIDC_RP_CLIENT_ID = "abc"


def test_login_page_offers_practice_account_when_configured(client, oidc_on):
    body = client.get("/accounts/login/").content.decode()
    assert "Sign in with the practice account" in body
    assert "/oidc/authenticate/" in body


def test_login_page_silent_when_not_configured(client, settings):
    settings.PRACTICE_HR_URL = ""
    assert "practice account" not in client.get("/accounts/login/").content.decode()


def test_existing_user_matched_by_case_insensitive_email(db):
    u = User.objects.create_user(email="Tom@Example.org", password="pw")
    found = PracticeAccountBackend().filter_users_by_claims({"email": "tom@example.org"})
    assert list(found) == [u]


def test_new_user_created_without_password_and_not_admin(db):
    b = PracticeAccountBackend()
    u = b.create_user({"email": "new@example.org", "employee_id": 7})
    assert not u.has_usable_password() and not u.is_rota_admin and u.is_active


def test_no_email_claim_matches_nobody(db):
    assert list(PracticeAccountBackend().filter_users_by_claims({})) == []
```

- [ ] **Step 2: Run to see them fail**

Run (in `$ROTA`): `python -m pytest tests/test_oidc_signin.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement**

Install and pin: `pip install mozilla-django-oidc==4.0.1` and add that line to `requirements.txt`.

`$ROTA/accounts/oidc.py`:

```python
"""Sign in with the practice account: the HR system is the OpenID Connect
provider. On first sign-in the email claim is matched to an existing rota
user, case-insensitively, or a user is created with no usable password.
is_rota_admin stays local to the rota."""

from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from .models import User


class PracticeAccountBackend(OIDCAuthenticationBackend):
    def filter_users_by_claims(self, claims):
        email = claims.get("email")
        if not email:
            return User.objects.none()
        return User.objects.filter(email__iexact=email)

    def create_user(self, claims):
        user = User(email=claims["email"])
        user.set_unusable_password()
        user.save()
        return user

    def update_user(self, user, claims):
        return user
```

`$ROTA/config/settings.py`, appended:

```python
# Sign in with the practice account: the HR system is the OpenID Connect
# provider. Every value comes from /etc/rota.env; with no PRACTICE_HR_URL the
# login page shows only the local form.
PRACTICE_HR_URL = os.environ.get("PRACTICE_HR_URL", "").rstrip("/")
OIDC_RP_CLIENT_ID = os.environ.get("OIDC_RP_CLIENT_ID", "")
OIDC_RP_CLIENT_SECRET = os.environ.get("OIDC_RP_CLIENT_SECRET", "")
OIDC_RP_SIGN_ALGO = "RS256"
OIDC_RP_SCOPES = "openid email"
OIDC_OP_AUTHORIZATION_ENDPOINT = f"{PRACTICE_HR_URL}/o/authorize/"
OIDC_OP_TOKEN_ENDPOINT = f"{PRACTICE_HR_URL}/o/token/"
OIDC_OP_USER_ENDPOINT = f"{PRACTICE_HR_URL}/o/userinfo/"
OIDC_OP_JWKS_ENDPOINT = f"{PRACTICE_HR_URL}/o/.well-known/jwks.json"
OIDC_USE_PKCE = True
OIDC_CREATE_USER = True
```

Add `"mozilla_django_oidc"` to `INSTALLED_APPS` after `"axes"`, and `"accounts.oidc.PracticeAccountBackend"` to `AUTHENTICATION_BACKENDS` after `ModelBackend`. In `config/urls.py` add `path("oidc/", include("mozilla_django_oidc.urls")),` before the accounts include. In `templates/registration/login.html`, above the local form:

```html
{% if settings_practice_hr_url %}
<p><a class="btn btn-primary" href="{% url 'oidc_authentication_init' %}">Sign in with the practice account</a></p>
<p class="field-help">Or use your rota password below.</p>
{% endif %}
```

with a context processor `rota.context_processors.practice_hr` returning `{"settings_practice_hr_url": settings.PRACTICE_HR_URL}` added to the rota's context processors list.

`$ROTA/docs/admin/sign-in.md`: one page: what the practice account is, the four environment variables, how to run `register_oidc_client` on the HR box and paste its output into `/etc/rota.env`, that the local password form stays for the superuser, and that `is_rota_admin` is still set in the rota's admin.

- [ ] **Step 4: Run the whole rota suite, lint, commit**

Run (in `$ROTA`): `ruff check . && DEBUG=1 python manage.py makemigrations --check --dry-run && python -m pytest -q`
Expected: all pass; no pre-existing assertion changed.

```bash
git add -A
git commit -m "feat: sign in with the practice account through OpenID Connect"
```

Push the branch and open a pull request against `master` in `devachnid/rota` once the HR system is deployed to staging; until then the branch waits.

---

### Task 15: Deployment files and the admin guide

**Files:**
- Create: `deploy/gunicorn.service`, `deploy/backup.sh`, `deploy/hr-backup.service`, `deploy/hr-backup.timer`, `deploy/hr-clearsessions.service`, `deploy/hr-clearsessions.timer`, `deploy/hr-nightly.service`, `deploy/hr-nightly.timer`, `docs/admin/README.md`, `docs/admin/people.md`, `docs/admin/sign-in.md`, `README.md` (extend), `tests/test_deploy.py`

- [ ] **Step 1: Write the failing test**

`tests/test_deploy.py`:

```python
from pathlib import Path

DEPLOY = Path(__file__).resolve().parent.parent / "deploy"


def test_units_use_env_file_and_loopback():
    unit = (DEPLOY / "gunicorn.service").read_text()
    assert "EnvironmentFile=/etc/practice-hr.env" in unit
    assert "--bind 127.0.0.1:" in unit
    assert "SECRET_KEY" not in unit.split("EnvironmentFile")[1]


def test_nightly_timer_exists():
    assert "hr_nightly" in (DEPLOY / "hr-nightly.service").read_text()
    assert "OnCalendar" in (DEPLOY / "hr-nightly.timer").read_text()


def test_backup_copies_media_too():
    assert "media" in (DEPLOY / "backup.sh").read_text()
```

- [ ] **Step 2: Run to see it fail**

Run: `python -m pytest tests/test_deploy.py -q`
Expected: FileNotFoundError.

- [ ] **Step 3: Write the files**

`deploy/gunicorn.service` is `$ROTA/deploy/gunicorn.service` with `/root/rota` → `/root/practice-hr`, `/etc/rota.env` → `/etc/practice-hr.env`, the Breathe lines in the comment replaced by `OIDC_RSA_PRIVATE_KEY=…  # one line, \n for newlines; generate with openssl genrsa 2048`, the description `Practice HR gunicorn`, and the bind port `8322`.

`deploy/backup.sh`:

```sh
#!/bin/sh
set -eu
mkdir -p /root/practice-hr/backups
sqlite3 /root/practice-hr/db.sqlite3 ".backup /root/practice-hr/backups/db-$(date +%F).sqlite3"
tar -czf "/root/practice-hr/backups/media-$(date +%F).tgz" -C /root/practice-hr media
find /root/practice-hr/backups -name 'db-*.sqlite3' -mtime +30 -delete
find /root/practice-hr/backups -name 'media-*.tgz' -mtime +30 -delete
```

`hr-backup.*` and `hr-clearsessions.*` are the rota's `rota-backup.*` and `rota-clearsessions.*` with paths and names changed. `hr-nightly.service` runs `manage.py hr_nightly` with `EnvironmentFile=/etc/practice-hr.env`; `hr-nightly.timer` is `OnCalendar=*-*-* 01:30:00`, `Persistent=true`.

`docs/admin/README.md` lists the pages. `docs/admin/people.md` documents every field of Employee, Employment, Position, ContractType, Contract, WorkingPattern, PayRecord and Team in the rota's style: what it is, what depends on it, what goes wrong if it is set wrong. `docs/admin/sign-in.md` documents login accounts, `is_hr_admin`, passkeys, invitations, the OIDC provider, `register_oidc_client`, and `OIDC_RSA_PRIVATE_KEY`. `README.md` gains Develop, First-time setup and Deploy sections mirroring the rota's with the names changed and the OIDC key step added.

- [ ] **Step 4: Run everything, lint, check migrations, commit**

Run: `ruff check . && DEBUG=1 python manage.py makemigrations --check --dry-run && python -m pytest -q`
Expected: all green.

```bash
git add -A
git commit -m "docs: deploy units, backup, nightly timer, and the admin guide for people and sign-in"
```

---

## Self-review

**Spec coverage (sections 1 to 3 and deployment):** architecture and apps (Task 1, 2); Employee and EmergencyContact (3); Employment with service date (5, 6); Team and Position with cycle check and primary (7); ContractType, overlapping Contract, unit rule, contracted amount, FTE, PayRecord (8); WorkingPattern and PatternDay with the warning (9); AuditEntry with change and viewed rows (3, 12); roles, what each sees, routing (10, 11, 12); OIDC provider, claims, consent skipped, client registration (13); the rota change (14); nightly login disabling (12); deployment and docs (15). **Not in this plan, by design:** retention report (spec section 3 "Housekeeping", second sentence) is deferred to plan 3 with the other reports, and is recorded there.

**Placeholders:** none; every step names its code or the exact edit.

**Type consistency:** `employments.current(employee, day)`, `positions.primary_on(employment, day)`, `contracts.contracted_amount(employment, day)`, `contracts.unit(employment, day)`, `patterns.units_on(employment, day, half)`, `access.route_for(employment, day)` are used with those signatures in Tasks 10 to 12 and are the names plans 2 and 3 consume.

**Review Focus:** returner boundary (Task 6 `test_end_then_return_the_next_day`), touching contracts (Task 8 `test_touching_contracts_do_not_clash`), pattern warning (Task 9 `test_total_differs_from_contract_warns_but_saves`), self and cycle (Task 7), case-only email match and leaver versus returner (Tasks 14 and 12).
