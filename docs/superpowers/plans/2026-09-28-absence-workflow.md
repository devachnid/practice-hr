# Absence Workflow, Payroll and API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put the ledger to work: request and decide pages, the calendar, balances, emails and the chase, year end with carry-over and expiries, TOIL earned, the payroll changes report, the retention report, and the read API the rota will consume.

**Architecture:** Pages are thin: forms validate shape, `absence/services/bookings.py` (plan 2) decides and writes. New services: `notify` (emails through one door that never raises), `calendar`, `year_end`, `toil`, `chase`, `payroll`, and `people/services/retention`. The API is three read-only JSON views behind a bearer token from the environment. Everything runs on plan 1's `hr_nightly`.

**Tech Stack:** As plans 1 and 2, plus `openpyxl` for the payroll spreadsheet.

**Spec:** `docs/superpowers/specs/2026-09-27-practice-hr-foundation-and-absence-design.md`, sections 5, 6 and 7, plus "Housekeeping" in section 3 (retention report) and the year-end and TOIL expiry rules in section 5.

## Global Constraints

- As plans 1 and 2. One new dependency: `openpyxl` (pin the version installed in `requirements.txt`).
- Emails never raise into a page; a failure is logged and shown on the dashboard.
- Calendar and team pages show `calendar_label` only; a sickness category is never rendered outside the employee's own page, their manager's view of them, and the admin.
- The payroll report never includes a sickness category, only dates.
- The read API is read-only and never includes a sickness category; `/absences` returns `"Sick"` as the label.
- Every automatic ledger line (carry-in, expiry) is reversible by an adjustment and idempotent under re-runs.

## Review Focus

1. **A request submitted by someone whose employment ends before the dates** must be refused at the form with a clear message, not costed as zero and approved. Task 2.
2. **Year end run twice**, or run for a pot closed by hand, must not double the carry-in or expiry. Task 6.
3. **A negative balance at year end** carries in full as a negative carry-in, and is shown as such, not silently zeroed. Task 6.
4. **The API's `/absences` window** must include an absence that starts before `from` and ends after `to` (overlap, not containment), because that is the Breathe bug the rota's spec recorded. Task 9.
5. **An approver whose report's request lands on a day the approver is themselves off** still sees and can decide it; and an HR admin deciding a request routed to a manager is recorded as the decider. Task 3.

---

## File structure

| Path | Responsibility |
|---|---|
| `absence/mail.py` | `send(subject, body, to)`, never raises. |
| `absence/services/notify.py` | Which email goes to whom for each event. |
| `absence/forms.py` | `RequestForm`, `DecisionForm`, `KitDayForm`, `PayrollPeriodForm`. |
| `absence/views/requests.py`, `templates/absence/request.html`, `mine.html` | Requesting, listing, cancelling own absences; KIT days. |
| `absence/views/approvals.py`, `templates/absence/queue.html`, `decide.html` | The approver's queue and decision page. |
| `absence/services/calendar.py`, `absence/views/calendar.py`, `templates/absence/calendar.html` | Month view and the min-present warning. |
| `absence/views/balances.py`, `templates/absence/balances.html`, `ledger.html` | Balances and the lines behind them. |
| `absence/services/year_end.py`, `absence/services/toil.py`, `absence/management/commands/absence_year_end.py` | Carry-over, expiries, TOIL earned. |
| `absence/services/chase.py`, `absence/admin_dashboard.py`, `templates/admin/index.html` | Waiting requests, dashboard card. |
| `absence/models/payroll.py`, `absence/services/payroll.py`, `absence/views/payroll.py`, `absence/management/commands/payroll_report.py`, `templates/absence/payroll.html` | The changes report. |
| `people/services/retention.py`, `people/views.py` (add `retention`), `templates/people/retention.html` | What is past its retention period. |
| `api/__init__.py`, `api/auth.py`, `api/views.py`, `api/urls.py` | The read API. |
| `absence/urls.py`, `config/urls.py`, `hr/admin_site.py`, `templates/base.html` | Wiring and navigation. |
| `docs/admin/absence.md`, `year-end.md`, `payroll.md`, `api.md`, `README.md` | Guide pages. |

---

### Task 1: The email door and notifications

**Files:**
- Create: `absence/mail.py`, `absence/services/notify.py`, `templates/absence/email/*.txt`, `tests/test_absence_notify.py`

**Interfaces:**
- Produces: `absence.mail.send(subject, body, to: list[str], reply_to=None) -> bool`; `notify.request_submitted(absence) -> bool`, `notify.request_decided(absence) -> bool`, `notify.absence_cancelled(absence) -> bool`, `notify.requests_waiting(absences) -> bool`, `notify.approver_addresses(absence) -> list[str]` (the routed manager's work email, or every active HR admin's).

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_notify.py`:

```python
from datetime import date

from django.core import mail

from absence.services import bookings, notify
from people.services import positions
from tests.factories import absence_type, hours_employee, make_employee, make_employment, make_team


def _pair(employee_user, hr_admin):
    boss = make_employee(first="Boss", email="boss@example.org", user=hr_admin)
    make_employment(employee=boss, start=date(2026, 1, 1))
    emp = hours_employee(employee=make_employee(user=employee_user))
    positions.add(None, emp, "Receptionist", make_team(), boss, emp.start_date)
    return emp


def test_submitted_goes_to_manager(configured, employee_user, hr_admin):
    emp = _pair(employee_user, hr_admin)
    a = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, 1))
    assert notify.request_submitted(a) is True
    assert mail.outbox[-1].to == ["boss@example.org"]
    assert "Sam Patel" in mail.outbox[-1].body and "1 Jun 2026" in mail.outbox[-1].body


def test_submitted_without_manager_goes_to_hr_admins(configured, employee_user, hr_admin):
    emp = hours_employee(employee=make_employee(user=employee_user))
    a = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, 1))
    notify.request_submitted(a)
    assert mail.outbox[-1].to == [hr_admin.email]


def test_unconfigured_returns_false_and_sends_nothing(db, employee_user):
    emp = hours_employee(employee=make_employee(user=employee_user))
    a = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, 1))
    assert notify.request_submitted(a) is False
    assert mail.outbox == []


def test_decided_goes_to_requester(configured, employee_user, hr_admin):
    emp = _pair(employee_user, hr_admin)
    a = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, 1))
    bookings.decline(hr_admin, a, "short staffed")
    notify.request_decided(a)
    m = mail.outbox[-1]
    assert m.to == [employee_user.email] and "declined" in m.subject.lower() and "short staffed" in m.body
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_absence_notify.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement**

`absence/mail.py`:

```python
"""One door for every email the absence app sends. Never raises into a
page: a failure is logged and reported by the return value."""

import logging

from django.conf import settings
from django.core.mail import EmailMessage

from accounts.mail import email_is_configured

log = logging.getLogger(__name__)


def send(subject, body, to, reply_to=None):
    if not email_is_configured() or not to:
        return False
    try:
        EmailMessage(subject=subject, body=body, to=list(to),
                     from_email=settings.DEFAULT_FROM_EMAIL,
                     reply_to=[reply_to] if reply_to else None).send()
        return True
    except Exception:            # noqa: BLE001 - a relay fault must not surface in a page
        log.exception("absence email failed: %s", subject)
        return False
```

`absence/services/notify.py`:

```python
from datetime import date

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string

from absence import mail
from people.services import access


def approver_addresses(absence):
    manager = access.route_for(absence.employment, date.today())
    if manager is not None and manager.work_email:
        return [manager.work_email]
    User = get_user_model()
    return list(User.objects.filter(is_hr_admin=True, is_active=True).values_list("email", flat=True))


def _requester_address(absence):
    return absence.employment.employee.work_email


def _render(name, absence, **extra):
    return render_to_string(f"absence/email/{name}.txt", {"a": absence, **extra})


def request_submitted(absence):
    return mail.send(f"Leave request from {absence.employment.employee.name}",
                     _render("submitted", absence), approver_addresses(absence),
                     reply_to=_requester_address(absence))


def request_decided(absence):
    return mail.send(f"Your {absence.absence_type} request was {absence.get_status_display().lower()}",
                     _render("decided", absence), [_requester_address(absence)])


def absence_cancelled(absence):
    return mail.send(f"{absence.employment.employee.name} cancelled {absence.absence_type}",
                     _render("cancelled", absence), approver_addresses(absence))


def requests_waiting(absences):
    User = get_user_model()
    to = list(User.objects.filter(is_hr_admin=True, is_active=True).values_list("email", flat=True))
    return mail.send(f"{len(absences)} leave request(s) waiting", _render("waiting", None, rows=absences), to)
```

Templates, plain text. `templates/absence/email/submitted.txt`:

```
{{ a.employment.employee.name }} has requested {{ a.absence_type }}:
{{ a.start_date|date:"j M Y" }}{% if a.end_date != a.start_date %} to {{ a.end_date|date:"j M Y" }}{% endif %}{% if a.is_partial %} ({{ a.hours }} hours){% endif %}.
Cost: {{ a.cost_units }}.

Decide it here: {{ a.decide_url }}
```

`decided.txt`, `cancelled.txt` and `waiting.txt` follow the same shape with the decision comment, the cancellation, and a line per waiting row. `a.decide_url` is a property added to `Absence` in this task: `reverse("absence:decide", args=[self.pk])` prefixed with `settings.SITE_URL` (a new setting from the environment, default `""`).

- [ ] **Step 4: Run and commit**

Run: `python -m pytest tests/test_absence_notify.py -q`
Expected: 4 passed.

```bash
git add -A
git commit -m "feat: absence emails through one door that never raises"
```

---

### Task 2: Requesting, my absences, cancelling, KIT days

**Files:**
- Create: `absence/forms.py`, `absence/views/__init__.py`, `absence/views/requests.py`, `absence/urls.py`, `templates/absence/request.html`, `templates/absence/mine.html`, `tests/test_absence_request_views.py`; Modify: `config/urls.py` (add `path("absence/", include("absence.urls"))`), `templates/base.html` (nav: Leave → `absence:mine`).

**Interfaces:**
- Produces: URL names `absence:request`, `absence:mine`, `absence:cancel` (POST, pk), `absence:kit_day` (POST, pk); `RequestForm` with fields `absence_type, start_date, end_date, start_half, end_half, partial, start_time, end_time, hours, category, expected_return`.

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_request_views.py`:

```python
from datetime import date
from decimal import Decimal

from absence.models import Absence
from tests.factories import absence_type, hours_employee, make_employee


def _me(employee_user, **kw):
    return hours_employee(employee=make_employee(user=employee_user), **kw)


def test_request_page_shows_balance_and_submits(employee_client, employee_user):
    _me(employee_user)
    r = employee_client.get("/absence/request/")
    assert r.status_code == 200 and "remaining" in r.content.decode().lower()
    r = employee_client.post("/absence/request/", {
        "absence_type": absence_type("AL").pk, "start_date": "2026-06-01", "end_date": "2026-06-03",
        "start_half": "", "end_half": "", "hours": "", "category": "", "expected_return": ""})
    assert r.status_code == 302
    a = Absence.objects.get()
    assert a.status == "requested" and a.cost_units == Decimal("22.50")


def test_negative_balance_warns_on_page(employee_client, employee_user):
    _me(employee_user, amount=Decimal("7.5"))
    r = employee_client.post("/absence/request/", {
        "absence_type": absence_type("AL").pk, "start_date": "2026-06-01", "end_date": "2026-06-30",
        "start_half": "", "end_half": "", "hours": "", "category": "", "expected_return": ""})
    assert r.status_code == 302
    r = employee_client.get("/absence/mine/")
    assert "more than your balance" in r.content.decode().lower()


def test_partial_day_request(employee_client, employee_user):
    _me(employee_user)
    r = employee_client.post("/absence/request/", {
        "absence_type": absence_type("DEP").pk, "start_date": "2026-06-01", "end_date": "2026-06-01",
        "partial": "on", "start_time": "09:00", "end_time": "10:30", "hours": "1.5",
        "start_half": "", "end_half": "", "category": "", "expected_return": ""})
    assert r.status_code == 302
    assert Absence.objects.get().cost_units == Decimal("1.50")


def test_dates_after_employment_end_refused(employee_client, employee_user):
    _me(employee_user, end_date=date(2026, 5, 31), leaving_reason="resigned")
    r = employee_client.post("/absence/request/", {
        "absence_type": absence_type("AL").pk, "start_date": "2026-06-01", "end_date": "2026-06-01",
        "start_half": "", "end_half": "", "hours": "", "category": "", "expected_return": ""})
    assert r.status_code == 200 and "employment" in r.content.decode().lower()
    assert not Absence.objects.exists()


def test_overlap_message_shown(employee_client, employee_user):
    _me(employee_user)
    data = {"absence_type": absence_type("AL").pk, "start_date": "2026-06-01", "end_date": "2026-06-01",
            "start_half": "", "end_half": "", "hours": "", "category": "", "expected_return": ""}
    employee_client.post("/absence/request/", data)
    r = employee_client.post("/absence/request/", data)
    assert r.status_code == 200 and "already an absence" in r.content.decode()


def test_cancel_own_future_only(employee_client, employee_user, hr_admin):
    from absence.services import bookings
    emp = _me(employee_user)
    a = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, 1))
    bookings.approve(hr_admin, a)
    past = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 4, 6))
    bookings.approve(hr_admin, past)
    assert employee_client.post(f"/absence/{a.pk}/cancel/").status_code == 302
    assert Absence.objects.get(pk=a.pk).status == "cancelled"
    import datetime
    if datetime.date.today() > date(2026, 4, 6):
        assert employee_client.post(f"/absence/{past.pk}/cancel/").status_code == 403


def test_kit_day_added_to_family_leave(employee_client, employee_user):
    from absence.services import bookings
    emp = _me(employee_user)
    a = bookings.request(employee_user, emp, absence_type("MAT"), date(2026, 7, 1), date(2027, 3, 31))
    r = employee_client.post(f"/absence/{a.pk}/kit-day/", {"date": "2026-09-15"})
    assert r.status_code == 302 and a.kit_days.count() == 1
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_absence_request_views.py -q`
Expected: 404s.

- [ ] **Step 3: Implement**

`absence/forms.py`:

```python
from django import forms

from absence.models import Absence, AbsenceType

HALF_START = [("", "All day"), ("PM", "Afternoon only")]
HALF_END = [("", "All day"), ("AM", "Morning only")]


class RequestForm(forms.Form):
    absence_type = forms.ModelChoiceField(
        queryset=AbsenceType.objects.filter(active=True).exclude(code="BH"))
    start_date = forms.DateField()
    end_date = forms.DateField(required=False)
    start_half = forms.ChoiceField(choices=HALF_START, required=False)
    end_half = forms.ChoiceField(choices=HALF_END, required=False)
    partial = forms.BooleanField(required=False, label="Part of a day, in hours")
    start_time = forms.TimeField(required=False)
    end_time = forms.TimeField(required=False)
    hours = forms.DecimalField(required=False, min_value=0, decimal_places=2)
    category = forms.ChoiceField(choices=[("", "—")] + Absence.Category.choices, required=False)
    expected_return = forms.DateField(required=False)

    def clean(self):
        d = super().clean()
        d["end_date"] = d.get("end_date") or d.get("start_date")
        if d.get("partial"):
            if not (d.get("start_time") and d.get("end_time") and d.get("hours")):
                raise forms.ValidationError("A part day needs a start time, an end time and the hours.")
            d["end_date"] = d["start_date"]
        else:
            d["start_time"] = d["end_time"] = d["hours"] = None
        t = d.get("absence_type")
        if t and t.code == "SICK" and not d.get("category"):
            self.add_error("category", "Say which kind, in broad terms.")
        return d


class DecisionForm(forms.Form):
    action = forms.ChoiceField(choices=[("approve", "Approve"), ("decline", "Decline")])
    comment = forms.CharField(required=False, max_length=300)


class KitDayForm(forms.Form):
    date = forms.DateField()


class PayrollPeriodForm(forms.Form):
    period = forms.RegexField(regex=r"^\d{4}-\d{2}$", label="Month (YYYY-MM)")
```

`absence/views/requests.py`:

```python
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from absence.forms import KitDayForm, RequestForm
from absence.models import Absence, AbsenceType, KitDay
from absence.services import balances, bookings, notify, pots
from people.services import access, employments


def _my_employment(request):
    employee = access.employee_for(request.user)
    return employee, (employments.current(employee, date.today()) if employee else None)


def _balance_rows(employment, today):
    rows = []
    for t in AbsenceType.objects.filter(active=True, uses_pot=True).exclude(code="BH"):
        try:
            pot = pots.for_day(employment, t, today)
        except ValidationError:
            continue
        rows.append((t, balances.summary(pot, today)))
    return rows


@login_required
def request_leave(request):
    employee, employment = _my_employment(request)
    if employment is None:
        return render(request, "absence/request.html", {"no_employment": True})
    today = date.today()
    form = RequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        if not employment.is_active_on(d["start_date"]) or not employment.is_active_on(d["end_date"]):
            form.add_error(None, "Those dates are outside your employment.")
        else:
            try:
                a = bookings.request(
                    request.user, employment, d["absence_type"], d["start_date"], d["end_date"],
                    d["start_half"], d["end_half"], d["start_time"], d["end_time"], d["hours"],
                    d["category"])
                if d["expected_return"]:
                    a.expected_return = d["expected_return"]
                    a.save()
                if a.status == Absence.Status.REQUESTED:
                    notify.request_submitted(a)
                    messages.success(request, "Sent for approval.")
                else:
                    messages.success(request, "Recorded.")
                return redirect("absence:mine")
            except ValidationError as e:
                form.add_error(None, e)
    return render(request, "absence/request.html",
                  {"form": form, "balances": _balance_rows(employment, today)})


@login_required
def mine(request):
    employee, employment = _my_employment(request)
    rows = []
    today = date.today()
    if employment:
        for a in Absence.objects.filter(employment__employee=employee).select_related("absence_type"):
            over = False
            if a.absence_type.uses_pot and a.status == Absence.Status.REQUESTED:
                pot = pots.for_day(a.employment, a.absence_type, a.start_date)
                over = balances.summary(pot, today)["remaining"] - a.cost_units < 0
            rows.append({"a": a, "over": over,
                         "can_cancel": a.status == "requested" or (a.status == "approved" and a.start_date > today)})
    return render(request, "absence/mine.html",
                  {"rows": rows, "balances": _balance_rows(employment, today) if employment else []})


@login_required
@require_POST
def cancel(request, pk):
    a = get_object_or_404(Absence, pk=pk)
    mine_ = a.employment.employee.user_id == request.user.pk
    admin = access.can_view_restricted(request.user)
    future = a.start_date > date.today()
    if not (admin or (mine_ and (a.status == "requested" or (a.status == "approved" and future)))):
        raise PermissionDenied
    bookings.cancel(request.user, a)
    notify.absence_cancelled(a)
    messages.success(request, "Cancelled.")
    return redirect("absence:mine")


@login_required
@require_POST
def kit_day(request, pk):
    a = get_object_or_404(Absence, pk=pk)
    if a.employment.employee.user_id != request.user.pk and not access.can_view_restricted(request.user):
        raise PermissionDenied
    form = KitDayForm(request.POST)
    if form.is_valid():
        KitDay.objects.get_or_create(absence=a, date=form.cleaned_data["date"])
    return redirect("absence:mine")
```

Family-leave dates are set by an HR admin in the admin, which plan 2 made read-only. In `absence/admin.py`, change `AbsenceAdmin` so that `has_change_permission` returns `access.can_view_restricted(request.user)` and add:

```python
    def get_readonly_fields(self, request, obj=None):
        editable = {"expected_start", "actual_start", "expected_return"}
        return [f.name for f in Absence._meta.fields if f.name not in editable]
```

with `from people.services import access` at the top of the file.

`absence/urls.py`:

```python
from django.urls import path

from absence.views import requests

app_name = "absence"
urlpatterns = [
    path("request/", requests.request_leave, name="request"),
    path("mine/", requests.mine, name="mine"),
    path("<int:pk>/cancel/", requests.cancel, name="cancel"),
    path("<int:pk>/kit-day/", requests.kit_day, name="kit_day"),
]
```

`templates/absence/request.html` renders `form.as_div` with a small script that shows the time and hours fields when `partial` is ticked and the `category` field when the type's code is `SICK` (the type select carries `data-code` attributes via a template filter `type_codes` in `absence/templatetags/absence_extras.py` returning `{pk: code}` as JSON), and a balances table with the `remaining` column. `templates/absence/mine.html` lists rows with status, dates, cost, the message "This is more than your balance" when `over`, a Cancel button when `can_cancel`, and a KIT-day form for family-leave types.

- [ ] **Step 4: Run and commit**

Run: `python -m pytest tests/test_absence_request_views.py -q`
Expected: 7 passed.

```bash
git add -A
git commit -m "feat: request, list and cancel absences; KIT days"
```

---

### Task 3: The approver's queue and decision page

**Files:**
- Create: `absence/views/approvals.py`, `templates/absence/queue.html`, `templates/absence/decide.html`, `tests/test_absence_approval_views.py`; Modify: `absence/urls.py`, `templates/base.html` (nav: Approvals with a count when any wait), `people/context_processors.py` (add `waiting_count`)

**Interfaces:**
- Produces: URL names `absence:queue`, `absence:decide` (pk); `approvals.queue_for(user, today) -> QuerySet[Absence]` (routed to this user's employee, or all when HR admin).

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_approval_views.py`:

```python
from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client

from absence.models import Absence
from absence.services import bookings
from people.services import positions
from tests.factories import absence_type, hours_employee, make_employee, make_employment, make_team

User = get_user_model()


def _setup(employee_user):
    boss_user = User.objects.create_user(email="boss@example.org", password="pw")
    boss = make_employee(first="Boss", user=boss_user)
    make_employment(employee=boss, start=date(2026, 1, 1))
    emp = hours_employee(employee=make_employee(user=employee_user))
    positions.add(None, emp, "Receptionist", make_team(), boss, emp.start_date)
    c = Client()
    c.force_login(boss_user)
    a = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, 1), date(2026, 6, 3))
    return c, a, boss_user


def test_queue_lists_routed_requests_only(employee_user, employee_client):
    c, a, _ = _setup(employee_user)
    assert str(a.pk) in c.get("/absence/queue/").content.decode()
    assert employee_client.get("/absence/queue/").status_code == 403


def test_decide_approves_and_records_decider(employee_user, admin_client, hr_admin):
    c, a, boss_user = _setup(employee_user)
    r = c.post(f"/absence/{a.pk}/decide/", {"action": "approve", "comment": "ok"})
    assert r.status_code == 302
    a.refresh_from_db()
    assert a.status == "approved" and a.decided_by == boss_user


def test_hr_admin_can_decide_anything(employee_user, admin_client, hr_admin):
    _, a, _ = _setup(employee_user)
    r = admin_client.post(f"/absence/{a.pk}/decide/", {"action": "decline", "comment": "no"})
    assert r.status_code == 302
    a.refresh_from_db()
    assert a.status == "declined" and a.decided_by == hr_admin


def test_stranger_cannot_decide(employee_user):
    _, a, _ = _setup(employee_user)
    other = User.objects.create_user(email="x@example.org", password="pw")
    c = Client()
    c.force_login(other)
    assert c.post(f"/absence/{a.pk}/decide/", {"action": "approve"}).status_code == 403


def test_decide_page_shows_calendar_and_min_present_warning(employee_user):
    c, a, _ = _setup(employee_user)
    team = a.employment.positions.first().team
    team.min_present = 2
    team.save()
    body = c.get(f"/absence/{a.pk}/decide/").content.decode()
    assert "1 Jun" in body and "fewer than 2" in body


def test_approver_off_that_day_still_decides(employee_user, hr_admin):
    c, a, boss_user = _setup(employee_user)
    boss_emp = boss_user.employee.employments.first()
    from tests.factories import make_contract, make_pattern
    make_contract(boss_emp)
    make_pattern(boss_emp)
    off = bookings.request(boss_user, boss_emp, absence_type("AL"), date(2026, 6, 1))
    bookings.approve(hr_admin, off)
    assert c.post(f"/absence/{a.pk}/decide/", {"action": "approve", "comment": ""}).status_code == 302
    assert Absence.objects.get(pk=a.pk).status == "approved"
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_absence_approval_views.py -q`
Expected: 404s.

- [ ] **Step 3: Implement**

`absence/views/approvals.py`:

```python
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from absence.forms import DecisionForm
from absence.models import Absence
from absence.services import balances, bookings, calendar, notify, pots
from people.services import access, positions


def queue_for(user, today):
    qs = Absence.objects.filter(status=Absence.Status.REQUESTED).select_related(
        "employment__employee", "absence_type")
    if access.can_view_restricted(user):
        return qs
    me = access.employee_for(user)
    if me is None:
        return qs.none()
    return qs.filter(pk__in=[a.pk for a in qs if access.route_for(a.employment, today) == me])


def _may_decide(user, absence, today):
    if access.can_view_restricted(user):
        return True
    me = access.employee_for(user)
    return me is not None and access.route_for(absence.employment, today) == me


@login_required
def queue(request):
    today = date.today()
    if not (access.is_approver(request.user, today) or access.can_view_restricted(request.user)):
        raise PermissionDenied
    return render(request, "absence/queue.html", {"rows": queue_for(request.user, today)})


@login_required
def decide(request, pk):
    a = get_object_or_404(Absence, pk=pk)
    today = date.today()
    if not _may_decide(request.user, a, today):
        raise PermissionDenied
    form = DecisionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            if form.cleaned_data["action"] == "approve":
                bookings.approve(request.user, a, form.cleaned_data["comment"])
            else:
                bookings.decline(request.user, a, form.cleaned_data["comment"])
            notify.request_decided(a)
            messages.success(request, f"{a.get_status_display()}.")
            return redirect("absence:queue")
        except ValidationError as e:
            form.add_error(None, e)
    summary = None
    if a.absence_type.uses_pot:
        summary = balances.summary(pots.for_day(a.employment, a.absence_type, a.start_date), today)
    pos = positions.primary_on(a.employment, a.start_date)
    team = pos.team if pos else None
    return render(request, "absence/decide.html", {
        "a": a, "form": form, "summary": summary, "team": team,
        "days": calendar.days_for(a.start_date, a.end_date, team),
        "warning": calendar.warning_if_approved(a, team) if team else None,
    })
```

Add to `absence/urls.py`: `path("queue/", approvals.queue, name="queue")`, `path("<int:pk>/decide/", approvals.decide, name="decide")`. In `people/context_processors.py` add `"waiting_count": queue_for(user, today).count() if user.is_authenticated else 0` (import inside the function to avoid a cycle). `base.html`'s nav shows `Approvals (N)` when `waiting_count`.

`calendar.days_for` and `calendar.warning_if_approved` are Task 4's; write Task 4's service file first if executing tasks in order is not possible, otherwise proceed to Task 4 and run both tasks' tests together at its end.

`templates/absence/decide.html` shows the request, the requester's balance summary, one row per day in `days` (who else is off, count present), the warning if any, and the decision form.

- [ ] **Step 4: Run (together with Task 4) and commit**

Run: `python -m pytest tests/test_absence_approval_views.py -q` after Task 4's service exists.
Expected: 6 passed.

```bash
git add -A
git commit -m "feat: the approver's queue and decision page"
```

---

### Task 4: The calendar

**Files:**
- Create: `absence/services/calendar.py`, `absence/views/calendar.py`, `templates/absence/calendar.html`, `tests/test_absence_calendar.py`; Modify: `absence/urls.py`, `templates/base.html` (nav: Calendar)

**Interfaces:**
- Produces: `calendar.off_on(day, team=None) -> list[dict]` with `employee, label, partial_hours, halves`; `calendar.present(team, day) -> tuple[int, int]` (present, headcount); `calendar.days_for(start, end, team) -> list[dict]` with `day, off, present, headcount`; `calendar.warning_if_approved(absence, team) -> str | None` ("Approving leaves fewer than N of Reception present on 1 Jun"); `calendar.month(year, month, team=None) -> list[list[dict]]` weeks of days; URL name `absence:calendar` with `?team=&month=YYYY-MM`.

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_calendar.py`:

```python
from datetime import date

from absence.services import bookings, calendar
from people.services import positions
from tests.factories import absence_type, hours_employee, make_employee, make_team


def _team_of(n, team, boss=None):
    emps = []
    for i in range(n):
        e = hours_employee(employee=make_employee(first=f"P{i}"))
        positions.add(None, e, "Receptionist", team, boss, e.start_date)
        emps.append(e)
    return emps


def test_off_on_shows_label_not_reason(db, hr_admin):
    team = make_team()
    a, b, c = _team_of(3, team)
    sick = bookings.request(hr_admin, a, absence_type("SICK"), date(2026, 6, 1), category="mental")
    leave = bookings.request(hr_admin, b, absence_type("AL"), date(2026, 6, 1), start_half="PM")
    bookings.approve(hr_admin, leave)
    rows = calendar.off_on(date(2026, 6, 1), team)
    labels = {r["employee"].pk: r["label"] for r in rows}
    assert labels == {a.employee.pk: "Sick", b.employee.pk: "Leave"}
    assert "mental" not in str(rows)
    assert calendar.present(team, date(2026, 6, 1)) == (1, 3)


def test_pending_not_on_calendar(db, hr_admin):
    team = make_team()
    (a,) = _team_of(1, team)
    bookings.request(hr_admin, a, absence_type("AL"), date(2026, 6, 1))
    assert calendar.off_on(date(2026, 6, 1), team) == []


def test_warning_if_approved(db, hr_admin):
    team = make_team(min_present=2)
    a, b, c = _team_of(3, team)
    first = bookings.request(hr_admin, a, absence_type("AL"), date(2026, 6, 1))
    bookings.approve(hr_admin, first)
    second = bookings.request(hr_admin, b, absence_type("AL"), date(2026, 6, 1))
    assert calendar.warning_if_approved(second, team) == "Approving leaves fewer than 2 of Reception present on 1 Jun 2026."
    third = bookings.request(hr_admin, c, absence_type("AL"), date(2026, 6, 2))
    assert calendar.warning_if_approved(third, team) is None


def test_month_grid_and_view(db, admin_client):
    weeks = calendar.month(2026, 6)
    assert weeks[0][0]["day"] == date(2026, 6, 1) and len(weeks[-1]) == 7
    assert admin_client.get("/absence/calendar/?month=2026-06").status_code == 200
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_absence_calendar.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement**

`absence/services/calendar.py`:

```python
import calendar as cal
from datetime import date, timedelta

from django.db.models import Q

from absence.models import Absence
from people.models import Position
from people.services import employments


def _team_employments(team, day):
    rows = (Position.objects.filter(team=team, primary=True, from_date__lte=day)
            .filter(Q(to_date__isnull=True) | Q(to_date__gte=day)).select_related("employment__employee"))
    return [p.employment for p in rows if p.employment.is_active_on(day)]


def _approved_on(day, team=None):
    qs = Absence.objects.filter(status=Absence.Status.APPROVED, start_date__lte=day, end_date__gte=day
                                ).select_related("employment__employee", "absence_type")
    if team is not None:
        ids = [e.pk for e in _team_employments(team, day)]
        qs = qs.filter(employment_id__in=ids)
    return qs


def off_on(day, team=None):
    out = []
    for a in _approved_on(day, team):
        halves = ["AM", "PM"]
        if day == a.start_date and a.start_half == "PM":
            halves.remove("AM")
        if day == a.end_date and a.end_half == "AM":
            halves.remove("PM")
        out.append({"employee": a.employment.employee, "label": a.absence_type.calendar_label,
                    "partial_hours": a.hours if a.is_partial else None, "halves": halves})
    return out


def present(team, day):
    members = _team_employments(team, day)
    off = {a.employment_id for a in _approved_on(day, team) if not a.is_partial}
    return len(members) - len(off), len(members)


def days_for(start, end, team):
    out = []
    day = start
    while day <= end:
        p, n = present(team, day) if team else (None, None)
        out.append({"day": day, "off": off_on(day, team), "present": p, "headcount": n})
        day += timedelta(days=1)
    return out


def warning_if_approved(absence, team):
    if not team or not team.min_present or absence.is_partial:
        return None
    day = absence.start_date
    while day <= absence.end_date:
        p, _ = present(team, day)
        if p - 1 < team.min_present:
            return f"Approving leaves fewer than {team.min_present} of {team} present on {day:%-d %b %Y}."
        day += timedelta(days=1)
    return None


def month(year, month_, team=None):
    weeks = []
    for week in cal.Calendar(firstweekday=0).monthdatescalendar(year, month_):
        weeks.append([{"day": d, "in_month": d.month == month_, "off": off_on(d, team) if d.month == month_ else []}
                      for d in week])
    return weeks
```

`absence/views/calendar.py`: `@login_required def calendar_view(request)` parsing `month` (default this month) and `team` (a `Team` pk or blank for the practice), rendering `absence/calendar.html` with `weeks`, the team list for a selector, and previous/next month links. URL `path("calendar/", calendar.calendar_view, name="calendar")`.

- [ ] **Step 4: Run Tasks 3 and 4 together, commit**

Run: `python -m pytest tests/test_absence_calendar.py tests/test_absence_approval_views.py -q`
Expected: 10 passed.

```bash
git add -A
git commit -m "feat: the who's-off calendar and the min-present warning"
```

---

### Task 5: Balances and the ledger page

**Files:**
- Create: `absence/views/balances.py`, `templates/absence/balances.html`, `templates/absence/ledger.html`, `tests/test_absence_balance_views.py`; Modify: `absence/urls.py`, `templates/base.html` (nav: Balances)

**Interfaces:**
- Produces: URL names `absence:balances` (own), `absence:balances_for` (employee pk; manager, HR admin), `absence:ledger` (pot pk); each row shows the current and the next leave year.

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_balance_views.py`:

```python
from datetime import date

from absence.services import ledger, pots
from tests.factories import absence_type, hours_employee, make_employee


def test_own_balances_two_years_and_ledger_link(employee_client, employee_user):
    emp = hours_employee(employee=make_employee(user=employee_user))
    pot = pots.for_day(emp, absence_type("AL"), date.today())
    ledger.sync_entitlement(pot)
    body = employee_client.get("/absence/balances/").content.decode()
    assert "210" in body and f"/absence/ledger/{pot.pk}/" in body
    assert body.count("Annual leave") >= 2          # this year and next
    r = employee_client.get(f"/absence/ledger/{pot.pk}/")
    assert r.status_code == 200 and "Entitlement" in r.content.decode()


def test_other_persons_balances_need_relationship(employee_client, employee_user, admin_client):
    other = hours_employee(employee=make_employee(first="Other"))
    assert employee_client.get(f"/absence/balances/{other.employee.pk}/").status_code == 403
    assert admin_client.get(f"/absence/balances/{other.employee.pk}/").status_code == 200
    pot = pots.for_day(other, absence_type("AL"), date.today())
    assert employee_client.get(f"/absence/ledger/{pot.pk}/").status_code == 403
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_absence_balance_views.py -q`
Expected: 404s.

- [ ] **Step 3: Implement**

`absence/views/balances.py`:

```python
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, render

from absence.models import AbsenceType, Pot
from absence.services import balances, ledger, pots
from people.models import Employee
from people.services import access, employments


def _rows(employment, today):
    rows = []
    for t in AbsenceType.objects.filter(active=True, uses_pot=True):
        try:
            this = pots.for_day(employment, t, today)
        except ValidationError:
            continue
        ledger.sync_entitlement(this)
        years = [(this, balances.summary(this, today))]
        try:
            nxt = pots.for_day(employment, t, this.year_end + timedelta(days=1))
            ledger.sync_entitlement(nxt)
            years.append((nxt, balances.summary(nxt, today)))
        except ValidationError:
            pass
        rows.append((t, years))
    return rows


def _render(request, employee):
    today = date.today()
    employment = employments.current(employee, today)
    return render(request, "absence/balances.html",
                  {"employee": employee, "rows": _rows(employment, today) if employment else []})


@login_required
def balances_view(request):
    employee = access.employee_for(request.user)
    if employee is None:
        return render(request, "absence/balances.html", {"employee": None, "rows": []})
    return _render(request, employee)


@login_required
def balances_for(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if not access.can_view(request.user, employee):
        raise PermissionDenied
    return _render(request, employee)


@login_required
def ledger_view(request, pk):
    pot = get_object_or_404(Pot.objects.select_related("employment__employee", "absence_type"), pk=pk)
    if not access.can_view(request.user, pot.employment.employee):
        raise PermissionDenied
    return render(request, "absence/ledger.html",
                  {"pot": pot, "entries": pot.entries.select_related("absence", "actor"),
                   "balance": ledger.balance(pot)})
```

URLs: `balances/`, `balances/<int:pk>/`, `ledger/<int:pk>/`. `balances.html` shows, per type, one row per year with the eight summary figures and a link to the ledger. `ledger.html` lists date, kind, units, absence, note, actor, and the running balance.

- [ ] **Step 4: Run and commit**

Run: `python -m pytest tests/test_absence_balance_views.py -q`
Expected: 2 passed.

```bash
git add -A
git commit -m "feat: balances for this year and next, with the ledger behind each figure"
```

---

### Task 6: Year end, carry-over, expiries, TOIL earned

**Files:**
- Create: `absence/services/year_end.py`, `absence/services/toil.py`, `absence/management/__init__.py`, `absence/management/commands/__init__.py`, `absence/management/commands/absence_year_end.py`, `tests/test_absence_year_end.py`; Modify: `absence/services/nightly.py`

**Interfaces:**
- Produces: `year_end.close(pot, actor=None) -> dict` with `carried, expired` (idempotent: a pot with an `EXPIRY` or `CARRY_IN`-to-next line noted `year end` is skipped); `year_end.expire_carry_in(pot, today, actor=None) -> LedgerEntry | None`; `year_end.expire_toil(pot, today, actor=None) -> list[LedgerEntry]`; `year_end.run(today) -> dict`; `toil.earn(actor, employment, units, day, note) -> LedgerEntry`; command `absence_year_end [--today YYYY-MM-DD]`.

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_year_end.py`:

```python
from datetime import date
from decimal import Decimal

from absence.models import LedgerEntry, Policy
from absence.services import bookings, ledger, pots, toil, year_end
from tests.factories import absence_type, hours_employee, make_policy

D = Decimal
K = LedgerEntry.Kind


def _pot_2026(emp):
    pot = pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    ledger.sync_entitlement(pot)
    return pot


def test_close_carries_up_to_cap_and_expires_rest(db):
    emp = hours_employee(start=date(2025, 4, 1))
    Policy.objects.update(carry_over_max_weeks=D("1"))           # 37.5 hours
    pot = _pot_2026(emp)                                          # 210, nothing taken
    result = year_end.close(pot)
    assert result == {"carried": D("37.50"), "expired": D("172.50")}
    nxt = pots.for_day(emp, absence_type("AL"), date(2027, 4, 1))
    assert nxt.entries.get(kind=K.CARRY_IN).units == D("37.50")
    assert pot.entries.get(kind=K.EXPIRY).units == D("-172.50")
    assert ledger.balance(pot) == D("0")


def test_close_twice_is_a_no_op(db):
    emp = hours_employee(start=date(2025, 4, 1))
    Policy.objects.update(carry_over_max_weeks=D("1"))
    pot = _pot_2026(emp)
    year_end.close(pot)
    assert year_end.close(pot) == {"carried": D("0"), "expired": D("0")}
    assert pot.entries.filter(kind=K.EXPIRY).count() == 1


def test_no_cap_means_no_carry(db):
    emp = hours_employee(start=date(2025, 4, 1))
    pot = _pot_2026(emp)
    assert year_end.close(pot)["carried"] == D("0")


def test_negative_balance_carries_in_full(db, hr_admin, employee_user):
    emp = hours_employee(start=date(2025, 4, 1), amount=D("7.5"))
    from tests.factories import make_pattern
    make_pattern(emp, {0: (D("3.75"), D("3.75"))})
    pot = _pot_2026(emp)                                          # 42 hours
    for week in range(7):
        a = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, 1 + 7 * week))
        bookings.approve(hr_admin, a)
    assert ledger.balance(pot) == D("-10.50")
    result = year_end.close(pot)
    assert result == {"carried": D("-10.50"), "expired": D("0")}
    nxt = pots.for_day(emp, absence_type("AL"), date(2027, 4, 1))
    assert nxt.entries.get(kind=K.CARRY_IN).units == D("-10.50")


def test_carry_in_expires_after_days(db):
    emp = hours_employee(start=date(2025, 4, 1))
    Policy.objects.update(carry_over_max_weeks=D("1"), carry_over_expires_after_days=90)
    pot = _pot_2026(emp)
    year_end.close(pot)
    nxt = pots.for_day(emp, absence_type("AL"), date(2027, 4, 1))
    assert year_end.expire_carry_in(nxt, date(2027, 6, 29)) is None
    row = year_end.expire_carry_in(nxt, date(2027, 6, 30))
    assert row.kind == K.EXPIRY and row.units == D("-37.50")
    assert year_end.expire_carry_in(nxt, date(2027, 7, 1)) is None


def test_toil_earned_and_expired(db, hr_admin):
    emp = hours_employee()
    ct = emp.contracts.first().contract_type
    make_policy(ct, "TOIL", toil_expires_after_days=90)
    row = toil.earn(hr_admin, emp, D("3"), date(2026, 6, 1), "late clinic")
    assert row.kind == K.TOIL_EARNED and row.units == D("3")
    pot = row.pot
    assert year_end.expire_toil(pot, date(2026, 8, 29)) == []
    expired = year_end.expire_toil(pot, date(2026, 8, 31))
    assert [e.units for e in expired] == [D("-3")]
    assert year_end.expire_toil(pot, date(2026, 9, 1)) == []


def test_run_and_command(db):
    emp = hours_employee(start=date(2025, 4, 1))
    _pot_2026(emp)
    result = year_end.run(date(2027, 4, 1))
    assert result["closed"] == 1
    from django.core.management import call_command
    call_command("absence_year_end", today="2027-04-02")
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_absence_year_end.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement**

`absence/services/toil.py`:

```python
from django.db import transaction

from absence.models import AbsenceType, LedgerEntry
from absence.services import ledger, pots


@transaction.atomic
def earn(actor, employment, units, day, note):
    pot = pots.for_day(employment, AbsenceType.objects.get(code="TOIL"), day)
    return ledger.write(pot, LedgerEntry.Kind.TOIL_EARNED, units, actor, note=note, date=day)
```

`absence/services/year_end.py`:

```python
"""Closing a pot, and the expiries that run from dates."""

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from absence.models import LedgerEntry, Pot
from absence.services import ledger, policies, pots, rounding
from people.services import contracts

K = LedgerEntry.Kind
YEAR_END = "year end"


def _closed(pot):
    return pot.entries.filter(note__startswith=YEAR_END).exists()


@transaction.atomic
def close(pot, actor=None):
    """Carry the balance forward up to the policy cap; expire the rest.
    A negative balance carries in full. Idempotent."""
    zero = {"carried": Decimal("0"), "expired": Decimal("0")}
    if _closed(pot):
        return zero
    balance = ledger.balance(pot)
    policy = policies.policy_for(pot.employment, pot.absence_type, pot.year_end)
    if balance < 0:
        carry = balance
    elif policy.carry_over_max_weeks is None:
        carry = Decimal("0")
    else:
        cap = rounding.round_to(policy.carry_over_max_weeks * contracts.contracted_amount(pot.employment, pot.year_end),
                                policy.rounding)
        carry = min(balance, cap)
    expire = balance - carry
    next_day = pot.year_end + timedelta(days=1)
    if carry:
        if pot.employment.is_active_on(next_day):
            nxt = pots.for_day(pot.employment, pot.absence_type, next_day)
            ledger.write(nxt, K.CARRY_IN, carry, actor, note=f"{YEAR_END}: carried in from {pot.year_start:%Y}/{pot.year_end:%y}",
                         date=nxt.year_start)
        else:
            expire = balance
            carry = Decimal("0")
    if expire:
        ledger.write(pot, K.EXPIRY, -expire, actor, note=f"{YEAR_END}: not carried over", date=pot.year_end)
    elif carry and not pot.entries.filter(note__startswith=YEAR_END).exists():
        ledger.write(pot, K.EXPIRY, Decimal("0"), actor, note=f"{YEAR_END}: closed", date=pot.year_end)
    return {"carried": carry, "expired": expire}


def expire_carry_in(pot, today, actor=None):
    policy = policies.policy_for(pot.employment, pot.absence_type, pot.year_start)
    days = policy.carry_over_expires_after_days
    if not days:
        return None
    deadline = pot.year_start + timedelta(days=days)
    if today <= deadline or pot.entries.filter(note="carry-over expired").exists():
        return None
    carried = pot.entries.filter(kind=K.CARRY_IN).aggregate(t=Sum("units"))["t"] or Decimal("0")
    unused = min(carried, ledger.balance(pot))
    if unused <= 0:
        return None
    return ledger.write(pot, K.EXPIRY, -unused, actor, note="carry-over expired", date=deadline)


def expire_toil(pot, today, actor=None):
    policy = policies.policy_for(pot.employment, pot.absence_type, pot.year_start)
    days = policy.toil_expires_after_days
    if not days:
        return []
    out = []
    for earned in pot.entries.filter(kind=K.TOIL_EARNED).order_by("date", "id"):
        deadline = earned.date + timedelta(days=days)
        marker = f"toil earned {earned.date:%Y-%m-%d} expired"
        if today <= deadline or pot.entries.filter(note=marker).exists():
            continue
        unused = min(earned.units, ledger.balance(pot))
        if unused <= 0:
            continue
        out.append(ledger.write(pot, K.EXPIRY, -unused, actor, note=marker, date=deadline))
    return out


def run(today):
    closed = expired = 0
    for pot in Pot.objects.filter(year_end__lt=today):
        if not _closed(pot):
            close(pot)
            closed += 1
    for pot in pots.open_pots(today):
        if pot.absence_type.code == "TOIL":
            expired += len(expire_toil(pot, today))
        elif expire_carry_in(pot, today) is not None:
            expired += 1
    return {"closed": closed, "expired": expired}
```

`absence/management/commands/absence_year_end.py`:

```python
from datetime import date

from django.core.management.base import BaseCommand

from absence.services import year_end


class Command(BaseCommand):
    help = "Close pots whose leave year has ended and run the date-based expiries."

    def add_arguments(self, parser):
        parser.add_argument("--today", default=None)

    def handle(self, *args, **options):
        today = date.fromisoformat(options["today"]) if options["today"] else date.today()
        self.stdout.write(str(year_end.run(today)))
```

In `absence/services/nightly.py`, call `year_end.run(today)` first and merge its keys into the result.

- [ ] **Step 4: Run and commit**

Run: `python -m pytest tests/test_absence_year_end.py tests/test_absence_nightly.py -q`
Expected: all pass.

```bash
git add -A
git commit -m "feat: year end carries to the cap and expires the rest; carry-in and TOIL expiries; TOIL earned"
```

---

### Task 7: The chase and the admin dashboard

**Files:**
- Create: `absence/services/chase.py`, `absence/admin_dashboard.py`, `templates/admin/index.html`, `absence/migrations/000N_absence_chased_at.py`, `tests/test_absence_chase.py`; Modify: `absence/models/absence.py` (add `chased_at`), `config/settings.py` (`UNFOLD["DASHBOARD_CALLBACK"] = "absence.admin_dashboard.dashboard"`, `CHASE_AFTER_WORKING_DAYS = int(os.environ.get("CHASE_AFTER_WORKING_DAYS", "3"))`), `absence/services/nightly.py`

**Interfaces:**
- Produces: `chase.waiting(today) -> list[Absence]` (requested, older than `CHASE_AFTER_WORKING_DAYS` working days); `chase.notify_once(today) -> int` (emails the HR admins about those not yet chased, stamps `chased_at`); `admin_dashboard.dashboard(request, context) -> context` adding `waiting` and `email_configured`.

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_chase.py`:

```python
from datetime import date, datetime, timezone

from django.core import mail

from absence.models import Absence
from absence.services import bookings, chase
from tests.factories import absence_type, hours_employee


def _old_request(days_ago_from, requested_on):
    emp = hours_employee()
    a = bookings.request(None, emp, absence_type("AL"), date(2026, 8, 3))
    Absence.objects.filter(pk=a.pk).update(requested_at=datetime.combine(requested_on, datetime.min.time(), timezone.utc))
    return a


def test_waiting_counts_working_days(db):
    a = _old_request(None, date(2026, 6, 26))          # a Friday
    assert chase.waiting(date(2026, 6, 30)) == []       # Mon, Tue: two working days
    assert chase.waiting(date(2026, 7, 2)) == [a]       # Thursday: four


def test_notify_once(configured, db, hr_admin):
    a = _old_request(None, date(2026, 6, 1))
    assert chase.notify_once(date(2026, 6, 10)) == 1
    assert mail.outbox[-1].to == [hr_admin.email]
    assert chase.notify_once(date(2026, 6, 11)) == 0
    assert Absence.objects.get(pk=a.pk).chased_at is not None


def test_dashboard_lists_waiting(admin_client, db):
    _old_request(None, date(2026, 6, 1))
    body = admin_client.get("/admin/").content.decode()
    assert "waiting" in body.lower()
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_absence_chase.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement**

Add `chased_at = models.DateTimeField(null=True, blank=True)` to `Absence`; `makemigrations absence`.

`absence/services/chase.py`:

```python
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from absence.models import Absence
from absence.services import notify


def _working_days_between(start, end):
    n, d = 0, start
    while d < end:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def waiting(today):
    limit = settings.CHASE_AFTER_WORKING_DAYS
    return [a for a in Absence.objects.filter(status=Absence.Status.REQUESTED).select_related(
                "employment__employee", "absence_type")
            if _working_days_between(a.requested_at.date(), today) > limit]


def notify_once(today):
    rows = [a for a in waiting(today) if a.chased_at is None]
    if not rows:
        return 0
    if notify.requests_waiting(rows):
        Absence.objects.filter(pk__in=[a.pk for a in rows]).update(chased_at=timezone.now())
    return len(rows)
```

`absence/admin_dashboard.py`:

```python
from datetime import date

from accounts.mail import email_is_configured
from absence.services import chase


def dashboard(request, context):
    context["waiting"] = chase.waiting(date.today())
    context["email_configured"] = email_is_configured()
    return context
```

`templates/admin/index.html` extends unfold's index and adds a card: "N requests waiting more than X working days" with links to each decide page, and a line "Outgoing email is not configured" when not. Nightly: add `"chased": chase.notify_once(today)`.

- [ ] **Step 4: Run and commit**

Run: `python -m pytest tests/test_absence_chase.py -q`
Expected: 3 passed.

```bash
git add -A
git commit -m "feat: chase waiting requests once; dashboard card"
```

---

### Task 8: The payroll changes report

**Files:**
- Create: `absence/models/payroll.py`, `absence/services/payroll.py`, `absence/views/payroll.py`, `absence/management/commands/payroll_report.py`, `templates/absence/payroll.html`, `tests/test_absence_payroll.py`; Modify: `absence/models/__init__.py`, `config/settings.py` (`MEDIA_ROOT = BASE_DIR / "media"`, `MEDIA_URL = "media/"`), `absence/urls.py`, `hr/admin_site.py` (nav: Payroll), `requirements.txt` (`openpyxl`)

**Interfaces:**
- Produces: `PayrollRun(period_start, period_end, generated_at, generated_by, path, counts)`; `payroll.build(start, end) -> openpyxl.Workbook` with sheets `Starters, Leavers, Contract changes, Pay changes, Sickness, Unpaid, Family leave, TOIL`; `payroll.run(actor, start, end) -> PayrollRun` saving `media/payroll/YYYY-MM.xlsx`; URL `absence:payroll` (HR admin; GET lists runs, POST generates and downloads); command `payroll_report --period YYYY-MM`.

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_payroll.py`:

```python
from datetime import date
from decimal import Decimal

from absence.models import PayrollRun
from absence.services import bookings, payroll, toil
from people.models import PayRecord
from people.services import contracts, employments
from tests.factories import absence_type, hours_employee, make_contract_type, make_employee


def _sheet(wb, name):
    ws = wb[name]
    return [[c.value for c in row] for row in ws.iter_rows()]


def test_sections(db, hr_admin, employee_user):
    starter = hours_employee(start=date(2026, 6, 15))
    leaver = hours_employee(employee=make_employee(first="Lee"), start=date(2025, 1, 1))
    employments.end(hr_admin, leaver, date(2026, 6, 20), "resigned")
    changed = hours_employee(employee=make_employee(first="Cha"), start=date(2025, 1, 1), amount=Decimal("20"))
    contracts.add(hr_admin, changed, make_contract_type(), Decimal("10"), date(2026, 6, 1))
    PayRecord.objects.create(employment=changed, from_date=date(2026, 6, 1), basis="annual", amount=26000)
    sick = bookings.request(employee_user, changed, absence_type("SICK"), date(2026, 6, 3), date(2026, 6, 4), category="mental")
    unpaid = bookings.request(employee_user, changed, absence_type("UNPAID"), date(2026, 6, 10))
    bookings.approve(hr_admin, unpaid)
    ct = changed.contracts.first().contract_type
    from tests.factories import make_policy
    make_policy(ct, "TOIL")
    toil.earn(hr_admin, changed, Decimal("2"), date(2026, 6, 5), "late")
    wb = payroll.build(date(2026, 6, 1), date(2026, 6, 30))
    assert _sheet(wb, "Starters")[1][0] == starter.employee.name
    assert _sheet(wb, "Leavers")[1][0] == leaver.employee.name
    assert any(r[0] == changed.employee.name for r in _sheet(wb, "Contract changes")[1:])
    assert _sheet(wb, "Pay changes")[1][3] == 26000
    sick_rows = _sheet(wb, "Sickness")
    assert sick_rows[1][1] == date(2026, 6, 3) and "mental" not in str(sick_rows)
    assert _sheet(wb, "Unpaid")[1][3] == 7.5
    assert _sheet(wb, "TOIL")[1][2] == 2


def test_run_saves_file_and_row(db, hr_admin, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    hours_employee(start=date(2026, 6, 15))
    run = payroll.run(hr_admin, date(2026, 6, 1), date(2026, 6, 30))
    assert (tmp_path / "payroll" / "2026-06.xlsx").exists()
    assert run.counts["Starters"] == 1 and PayrollRun.objects.count() == 1


def test_view_requires_hr_admin(employee_client, admin_client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    assert employee_client.get("/absence/payroll/").status_code == 403
    assert admin_client.get("/absence/payroll/").status_code == 200
    r = admin_client.post("/absence/payroll/", {"period": "2026-06"})
    assert r.status_code == 200 and r["Content-Type"].startswith("application/vnd.openxmlformats")
```

- [ ] **Step 2: Run to see them fail**

Run: `pip install openpyxl && pip freeze | grep -i openpyxl >> requirements.txt && python -m pytest tests/test_absence_payroll.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement**

`absence/models/payroll.py`:

```python
from django.conf import settings
from django.db import models


class PayrollRun(models.Model):
    period_start = models.DateField()
    period_end = models.DateField()
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    path = models.CharField(max_length=200)
    counts = models.JSONField(default=dict)

    class Meta:
        ordering = ["-period_start", "-generated_at"]

    def __str__(self):
        return f"Payroll {self.period_start:%b %Y} ({self.generated_at:%d %b %Y %H:%M})"
```

`absence/services/payroll.py`:

```python
"""The monthly changes report for the bureau. Dates and units, never a
sickness category, never any pay arithmetic."""

from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from openpyxl import Workbook

from absence.models import Absence, LedgerEntry, PayrollRun
from people.models import Contract, Employment, PayRecord
from people.services import contracts

SHEETS = ["Starters", "Leavers", "Contract changes", "Pay changes", "Sickness", "Unpaid", "Family leave", "TOIL"]
FAMILY = ("MAT", "PAT", "SPL", "ADOPT")


def _emp_name(e):
    return e.employee.name


def _rows(start, end):
    rows = {s: [] for s in SHEETS}
    for e in Employment.objects.filter(start_date__range=(start, end)).select_related("employee"):
        c = contracts.active_on(e, e.start_date).first()
        rows["Starters"].append([_emp_name(e), e.start_date, c.contract_type.name if c else "",
                                 float(contracts.contracted_amount(e, e.start_date)), c.contract_type.unit if c else ""])
    for e in Employment.objects.filter(end_date__range=(start, end)).select_related("employee"):
        rows["Leavers"].append([_emp_name(e), e.end_date, e.get_leaving_reason_display()])
    for c in Contract.objects.filter(Q(from_date__range=(start, end)) | Q(to_date__range=(start, end))
                                     ).select_related("employment__employee", "contract_type"):
        rows["Contract changes"].append([_emp_name(c.employment), c.from_date, c.to_date, float(c.weekly_amount),
                                         c.contract_type.unit, c.get_basis_display(), c.notes])
    for p in PayRecord.objects.filter(from_date__range=(start, end)).select_related("employment__employee"):
        rows["Pay changes"].append([_emp_name(p.employment), p.from_date, p.get_basis_display(), float(p.amount), p.reason])
    live = Absence.objects.filter(status=Absence.Status.APPROVED, start_date__lte=end, end_date__gte=start
                                  ).select_related("employment__employee", "absence_type")
    for a in live:
        code = a.absence_type.code
        if code == "SICK":
            rows["Sickness"].append([_emp_name(a.employment), a.start_date, a.end_date,
                                     "self-certified" if a.self_certified else "certified"])
        elif code in FAMILY:
            rows["Family leave"].append([_emp_name(a.employment), a.absence_type.name, a.expected_start, a.actual_start,
                                         a.expected_return, a.kit_days.count()])
        elif not a.absence_type.paid:
            rows["Unpaid"].append([_emp_name(a.employment), a.start_date, a.end_date,
                                   float(a.hours if a.is_partial else a.cost_units or 0), a.absence_type.name])
    for l in LedgerEntry.objects.filter(pot__absence_type__code="TOIL", date__range=(start, end),
                                        kind__in=(LedgerEntry.Kind.TOIL_EARNED, LedgerEntry.Kind.TOIL_TAKEN)
                                        ).select_related("pot__employment__employee"):
        rows["TOIL"].append([_emp_name(l.pot.employment), l.date, float(l.units), l.get_kind_display(), l.note])
    return rows


HEADERS = {
    "Starters": ["Name", "Start", "Contract type", "Weekly amount", "Unit"],
    "Leavers": ["Name", "Last day", "Reason"],
    "Contract changes": ["Name", "From", "To", "Weekly amount", "Unit", "Basis", "Notes"],
    "Pay changes": ["Name", "From", "Basis", "Amount", "Reason"],
    "Sickness": ["Name", "From", "To", "Certification"],
    "Unpaid": ["Name", "From", "To", "Units", "Type"],
    "Family leave": ["Name", "Type", "Expected start", "Actual start", "Expected return", "KIT days"],
    "TOIL": ["Name", "Date", "Units", "Kind", "Note"],
}


def build(start, end):
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in _rows(start, end).items():
        ws = wb.create_sheet(name)
        ws.append(HEADERS[name])
        for r in rows:
            ws.append(r)
    return wb


@transaction.atomic
def run(actor, start, end):
    wb = build(start, end)
    folder = Path(settings.MEDIA_ROOT) / "payroll"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{start:%Y-%m}.xlsx"
    wb.save(path)
    counts = {name: ws.max_row - 1 for name, ws in zip(wb.sheetnames, wb.worksheets)}
    return PayrollRun.objects.create(period_start=start, period_end=end, generated_by=actor,
                                     path=str(path.relative_to(settings.MEDIA_ROOT)), counts=counts)
```

`absence/views/payroll.py`: HR admin only (`access.can_view_restricted`); GET lists `PayrollRun` rows and the period form; POST parses `YYYY-MM` into the month's first and last day, calls `payroll.run`, and returns the file as an attachment with content type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. Command `payroll_report --period YYYY-MM` calls `payroll.run(None, …)` and prints the path.

- [ ] **Step 4: Run and commit**

Run: `DEBUG=1 python manage.py makemigrations absence && python -m pytest tests/test_absence_payroll.py -q`
Expected: 3 passed.

```bash
git add -A
git commit -m "feat: the payroll changes report as a saved spreadsheet"
```

---

### Task 9: The read API

**Files:**
- Create: `api/__init__.py`, `api/auth.py`, `api/views.py`, `api/urls.py`, `tests/test_api.py`; Modify: `config/settings.py` (`HR_API_TOKENS = frozenset(t for t in os.environ.get("HR_API_TOKENS", "").split(",") if t)`), `config/urls.py` (`path("api/v1/", include("api.urls"))`)

**Interfaces:**
- Produces: `GET /api/v1/people`, `GET /api/v1/patterns?employee=<id>`, `GET /api/v1/absences?from=YYYY-MM-DD&to=YYYY-MM-DD`, all requiring `Authorization: Bearer <token>` with the token in `HR_API_TOKENS`; JSON shapes below.

- [ ] **Step 1: Write the failing tests**

`tests/test_api.py`:

```python
from datetime import date

import pytest

from absence.services import bookings
from people.services import positions
from tests.factories import absence_type, hours_employee, make_employee, make_team


@pytest.fixture
def api(client, settings):
    settings.HR_API_TOKENS = frozenset({"t0k"})
    return lambda url: client.get(url, HTTP_AUTHORIZATION="Bearer t0k")


def test_token_required(client, settings):
    settings.HR_API_TOKENS = frozenset({"t0k"})
    assert client.get("/api/v1/people").status_code == 401
    assert client.get("/api/v1/people", HTTP_AUTHORIZATION="Bearer wrong").status_code == 401


def test_people(api, db):
    emp = hours_employee()
    positions.add(None, emp, "Receptionist", make_team(), None, emp.start_date)
    data = api("/api/v1/people").json()
    row = data["people"][0]
    assert row["id"] == emp.employee.pk and row["email"] == emp.employee.work_email
    assert row["unit"] == "hours" and row["contract_type"] == "Reception"
    assert row["employment"] == {"start": "2026-04-01", "end": None}
    assert row["positions"] == [{"title": "Receptionist", "team": "Reception"}]


def test_patterns(api, db):
    emp = hours_employee()
    data = api(f"/api/v1/patterns?employee={emp.employee.pk}").json()
    v = data["patterns"][0]
    assert v["effective_from"] == "2026-04-01" and len(v["days"]) == 7
    assert v["days"][0] == {"weekday": 0, "am": "3.75", "pm": "3.75"}


def test_absences_overlap_window_and_hide_category(api, db, hr_admin):
    emp = hours_employee()
    long = bookings.request(hr_admin, emp, absence_type("AL"), date(2026, 5, 25), date(2026, 6, 12))
    bookings.approve(hr_admin, long)
    bookings.request(hr_admin, emp, absence_type("SICK"), date(2026, 6, 15), category="mental")
    pending = bookings.request(hr_admin, emp, absence_type("AL"), date(2026, 6, 20))
    data = api("/api/v1/absences?from=2026-06-01&to=2026-06-30").json()["absences"]
    by_start = {a["start"]: a for a in data}
    assert "2026-05-25" in by_start                              # overlaps, not contained
    assert by_start["2026-06-15"]["label"] == "Sick" and "mental" not in str(data)
    assert by_start["2026-06-20"]["status"] == "requested" and pending.pk == by_start["2026-06-20"]["id"]
    assert by_start["2026-05-25"] == {"id": long.pk, "employee": emp.employee.pk, "type": "AL", "label": "Leave",
                                      "status": "approved", "start": "2026-05-25", "end": "2026-06-12",
                                      "start_half": "", "end_half": "", "partial": None}
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_api.py -q`
Expected: 404s.

- [ ] **Step 3: Implement**

`api/auth.py`:

```python
from functools import wraps

from django.conf import settings
from django.http import JsonResponse


def token_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        header = request.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else ""
        if not token or token not in settings.HR_API_TOKENS:
            return JsonResponse({"error": "unauthorised"}, status=401)
        return view(request, *args, **kwargs)
    return wrapped
```

`api/views.py`:

```python
from datetime import date

from django.http import HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_GET

from absence.models import Absence
from api.auth import token_required
from people.models import Employee, WorkingPattern
from people.services import contracts, employments, positions


def _iso(d):
    return d.isoformat() if d else None


@require_GET
@token_required
def people(request):
    today = date.today()
    out = []
    for e in Employee.objects.all():
        emp = employments.current(e, today) or e.employments.order_by("-start_date").first()
        if emp is None:
            continue
        c = contracts.active_on(emp, today).first()
        out.append({
            "id": e.pk, "first_name": e.first_name, "last_name": e.last_name, "name": e.name,
            "email": e.work_email,
            "contract_type": c.contract_type.name if c else None, "unit": c.contract_type.unit if c else None,
            "employment": {"start": _iso(emp.start_date), "end": _iso(emp.end_date)},
            "positions": [{"title": p.title, "team": p.team.name} for p in positions.on(emp, today)],
        })
    return JsonResponse({"people": out})


@require_GET
@token_required
def patterns(request):
    try:
        employee = Employee.objects.get(pk=int(request.GET.get("employee", "")))
    except (ValueError, Employee.DoesNotExist):
        return HttpResponseBadRequest("employee=<id> required")
    out = []
    for v in WorkingPattern.objects.filter(employment__employee=employee).order_by("effective_from").prefetch_related("days"):
        out.append({"effective_from": _iso(v.effective_from),
                    "days": [{"weekday": d.weekday, "am": str(d.am_units), "pm": str(d.pm_units)} for d in v.days.all()]})
    return JsonResponse({"patterns": out})


@require_GET
@token_required
def absences(request):
    try:
        start = date.fromisoformat(request.GET["from"])
        end = date.fromisoformat(request.GET["to"])
    except (KeyError, ValueError):
        return HttpResponseBadRequest("from and to (YYYY-MM-DD) required")
    qs = Absence.objects.filter(status__in=(Absence.Status.APPROVED, Absence.Status.REQUESTED),
                                start_date__lte=end, end_date__gte=start
                                ).select_related("employment__employee", "absence_type")
    out = [{
        "id": a.pk, "employee": a.employment.employee_id, "type": a.absence_type.code,
        "label": a.absence_type.calendar_label, "status": a.status,
        "start": _iso(a.start_date), "end": _iso(a.end_date),
        "start_half": a.start_half, "end_half": a.end_half,
        "partial": ({"start_time": a.start_time.strftime("%H:%M"), "end_time": a.end_time.strftime("%H:%M"),
                     "hours": str(a.hours)} if a.is_partial else None),
    } for a in qs]
    return JsonResponse({"absences": out})
```

`api/urls.py` maps `people`, `patterns`, `absences` to those views.

- [ ] **Step 4: Run and commit**

Run: `python -m pytest tests/test_api.py -q`
Expected: 4 passed.

```bash
git add -A
git commit -m "feat: the read API for the rota: people, patterns, absences"
```

---

### Task 10: The retention report

**Files:**
- Create: `people/services/retention.py`, `templates/people/retention.html`, `tests/test_retention.py`; Modify: `people/views.py`, `people/urls.py`, `config/settings.py` (`RETENTION_DAYS`), `hr/admin_site.py` (nav: Retention)

**Interfaces:**
- Produces: `RETENTION_DAYS = {"personal": 2190, "pay": 2190, "health": 2190, "audit": 2555}` overridable from `RETENTION_DAYS_<CATEGORY>` environment variables; `retention.due(today) -> list[dict]` with `employee, category, ended, due_since`; URL `people:retention` (HR admin only).

- [ ] **Step 1: Write the failing tests**

`tests/test_retention.py`:

```python
from datetime import date

from people.services import retention
from tests.factories import make_employee, make_employment


def test_due_lists_leavers_past_period(db, settings):
    settings.RETENTION_DAYS = {"personal": 30, "pay": 60, "health": 60, "audit": 90}
    old = make_employee(first="Old")
    make_employment(employee=old, start=date(2020, 1, 1), end_date=date(2026, 1, 31), leaving_reason="resigned")
    fresh = make_employee(first="New")
    make_employment(employee=fresh, start=date(2020, 1, 1), end_date=date(2026, 6, 1), leaving_reason="resigned")
    rows = retention.due(date(2026, 6, 15))
    cats = {(r["employee"].pk, r["category"]) for r in rows}
    assert (old.pk, "personal") in cats and (old.pk, "pay") in cats and (old.pk, "audit") in cats
    assert all(pk != fresh.pk for pk, _ in cats)


def test_view_is_admin_only(employee_client, admin_client):
    assert employee_client.get("/people/retention/").status_code == 403
    assert admin_client.get("/people/retention/").status_code == 200
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_retention.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement**

`people/services/retention.py`:

```python
from datetime import timedelta

from django.conf import settings

from people.models import Employee
from people.services import employments


def due(today):
    out = []
    for e in Employee.objects.all():
        if employments.current(e, today) is not None or e.employments.filter(start_date__gt=today).exists():
            continue
        last = e.employments.order_by("-end_date").first()
        if last is None or last.end_date is None:
            continue
        for category, days in settings.RETENTION_DAYS.items():
            deadline = last.end_date + timedelta(days=days)
            if today > deadline:
                out.append({"employee": e, "category": category, "ended": last.end_date,
                            "due_since": deadline})
    return out
```

`people/views.py` gains `retention(request)` (403 unless `access.can_view_restricted`), rendering the rows grouped by employee with a note that deletion is manual in this release. Settings:

```python
RETENTION_DAYS = {
    cat: int(os.environ.get(f"RETENTION_DAYS_{cat.upper()}", default))
    for cat, default in (("personal", 2190), ("pay", 2190), ("health", 2190), ("audit", 2555))
}
```

- [ ] **Step 4: Run and commit**

Run: `python -m pytest tests/test_retention.py -q`
Expected: 2 passed.

```bash
git add -A
git commit -m "feat: the retention report lists what is past its period"
```

---

### Task 11: Navigation, docs, README, and the full run

**Files:**
- Modify: `templates/base.html`, `hr/admin_site.py`, `README.md`; Create: `docs/admin/absence.md`, `docs/admin/year-end.md`, `docs/admin/payroll.md`, `docs/admin/api.md`, `tests/test_docs.py`

- [ ] **Step 1: Write the failing test**

`tests/test_docs.py`:

```python
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs" / "admin"


def test_every_guide_page_exists_and_is_linked():
    index = (DOCS / "README.md").read_text()
    for page in ("people.md", "sign-in.md", "absence.md", "year-end.md", "payroll.md", "api.md"):
        assert (DOCS / page).exists(), page
        assert page in index, page


def test_absence_guide_names_every_policy_field():
    text = (DOCS / "absence.md").read_text()
    for field in ("weeks_per_year", "carry_over_max_weeks", "carry_over_expires_after_days", "rounding",
                  "bank_holiday_handling", "toil_expires_after_days", "leave_year_basis"):
        assert field in text, field
```

- [ ] **Step 2: Run to see it fail**

Run: `python -m pytest tests/test_docs.py -q`
Expected: FileNotFoundError.

- [ ] **Step 3: Write the pages and wire the navigation**

`base.html` nav: My record, Leave (`absence:mine`), Request leave, Calendar, Balances, Approvals (N) when approver, My team when approver, Admin when HR admin. `hr/admin_site.py` navigation gains Payroll (`absence:payroll`) and Retention (`people:retention`) under an "Reports" group for HR admins.

`docs/admin/absence.md`: absence types and every flag; policies and every field named above, with what depends on it and what goes wrong when it is set wrong; tiers; bank holidays and closed days; how a request is costed; what the calendar shows and to whom. `docs/admin/year-end.md`: what the nightly job does on the day after a leave year ends, the carry cap, the carry-in and TOIL expiries, and how to reverse a line with an adjustment. `docs/admin/payroll.md`: the period, the eight sheets and their columns, where the file is saved, and the command. `docs/admin/api.md`: the three endpoints, the token in `HR_API_TOKENS`, and the JSON shapes. `docs/admin/README.md` links all six pages. `README.md` gains the environment variables added in this plan: `SITE_URL`, `CHASE_AFTER_WORKING_DAYS`, `HR_API_TOKENS`, `RETENTION_DAYS_*`.

- [ ] **Step 4: Run everything, lint, check migrations and the deploy check, commit**

Run: `ruff check . && DEBUG=1 python manage.py makemigrations --check --dry-run && python -m pytest -q && DEBUG=0 SECRET_KEY=x ALLOWED_HOSTS=ci CSRF_TRUSTED_ORIGINS=https://ci EMAIL_HOST=smtp.example DEFAULT_FROM_EMAIL='HR <hr@example.org>' OIDC_RSA_PRIVATE_KEY='' python manage.py collectstatic --noinput && DEBUG=0 SECRET_KEY=x ALLOWED_HOSTS=ci CSRF_TRUSTED_ORIGINS=https://ci python manage.py check --deploy`
Expected: all green; `check --deploy` reports only Django's warnings about the throwaway key.

```bash
git add -A
git commit -m "docs: absence, year end, payroll and API guide pages; navigation"
```

---

## Self-review

**Spec coverage:** section 5 requesting with cost, balance, negative warning, overlap refusal, pot-less types, self-certified types written approved (Task 2); deciding with balance, calendar and who else is off, approve in one transaction, decline writes nothing, emails, the chase after N working days with the dashboard (Tasks 3, 7); cancelling by the employee until start and by admin any time (Task 2); calendar with labels only, counts and the min-present warning (Task 4); balances for current and next year with links to lines (Task 5); year end with carry cap, expiry, carry-in expiry, TOIL expiry, all reversible (Task 6); emails through one door that never raises (Task 1). Section 6 payroll report with every listed section, saved with a `PayrollRun` row, no sickness category (Task 8); errors: transactions, overlap and routing rules already in the services, missing policy naming itself (plan 2), read-only API, failed email logged and shown (Tasks 1, 7). Section 7 the three endpoints, overlap semantics, pending included, "Sick" and never the category, token from the environment, no push (Task 9). Section 3 retention report (Task 10). Documentation (Task 11). Family leave: expected and actual dates on the request, KIT days (Task 2). Family-leave `expected_start`, `actual_start` and `expected_return` are editable by HR admins in the admin (Task 2).

**Placeholders:** templates are described by their contents rather than written out in full, as every field and link they show is named; the executor writes the markup in the design system.

**Type consistency:** `bookings.request(actor, employment, absence_type, start_date, end_date, start_half, end_half, start_time, end_time, hours, category)` is called with that positional order in Task 2; `calendar.days_for(start, end, team)` and `calendar.warning_if_approved(absence, team)` are used in Task 3 as defined in Task 4; `access.route_for`, `access.can_view`, `access.can_view_restricted`, `access.employee_for` are plan 1's names.

**Review Focus:** dates outside employment (Task 2 `test_dates_after_employment_end_refused`), year end twice (Task 6 `test_close_twice_is_a_no_op`), negative carry (Task 6 `test_negative_balance_carries_in_full`), API overlap (Task 9 `test_absences_overlap_window_and_hide_category`), approver off that day and HR admin as decider (Task 3).

---

## Execution notes (2026-09-28/29)

Executed subagent-driven; the ledger at `.superpowers/sdd/2026-09-28-absence-workflow/progress.md` (untracked) recorded every ruling. The plan was written before plan 2's final shape, so a pre-flight scan produced sixteen rulings; the main ones, and what the final review changed:

- **Pages never write on GET.** `pots.for_day` opens a pot with its entitlement and automatic bank holidays, so pages use `pots.lookup` and `balances.rows`; the nightly opens this year's and next year's pot for every allowance with a policy (`pots_opened`), so "not opened yet" only ever means "before tonight" or "not employed then".
- **Automatic bank-holiday rows** are excluded from the calendar, the API and the cancel page; the calendar counts AM/PM half days as away and hour partials as present; HR admins see the type name (never a category).
- **Requests** are two-step without JavaScript (validate, show cost and balance after, confirm); the approver link is built from `SITE_URL` + `notify.DECIDE_PATH` (`hr.W002` warns when `SITE_URL` is unset); when email is not configured the link is shown on screen; family dates are edited by HR through `bookings.set_family_dates`; KIT days through `bookings.add_kit_day`; a routed approver or HR admin can record an absence for someone else (`absence:request_for`, approved at once, `requested_by` = the recorder).
- **Approvals**: a decider never decides their own employee's request; a decided or cancelled request opens read-only for anyone it was routed to; the mobile tab bar holds at most five items (Calendar and Balances live in the More sheet).
- **Year end** (rewritten from the brief): one EXPIRY line zeroes the old pot and a CARRY_IN of the capped amount opens the next (negative carries in full; leavers' debts are left and reported); TOIL is never capped — each unused lot is carried as a TOIL_EARNED line with its earn date and expires by `toil_expires_after_days`; positive TOIL adjustments are lots; both expiries count leave *requested* by the deadline and wait while a request made in time is undecided; `close` re-syncs the old pot first, refuses while a request is waiting on it, and no service writes to a closed pot (approve/cancel/recost/request/recalculate refuse; `ledger.adjust` on the current pot is the remedy, with an "Adjust balance" form on the Pot admin).
- **Ending an employment** cancels the person's live absences after the leaving date (plan-1 service; cancellations follow the pot they were booked to).
- **Payroll**: sheets chosen by type flags; spanning absences clipped per month with in-period costing (`costing.cost_between`); the Sickness sheet has a Self-certified column and never a category; leaver balances as at the leaving date; carried TOIL lines listed once; the file lands in `MEDIA_ROOT` (`/var/lib/practice-hr/media` in production).
- **API**: bearer tokens compared with `hmac`, `csrf_exempt`, `no-store`, overlap window, "Sick" for any health-sensitive type, `type` code kept, automatic rows excluded, `hr.W001` when no token is configured.
- **Retention**: the audit category is a per-employee proxy from the employment end; the page deletes nothing.
- **Known limitations left for a follow-up** (all recorded in the ledger): the leaver audit note is truncated before its "not cancelled" list; a recorded sickness carries no "Recorded by" comment; a missing next-year policy is reported nightly; the payroll file for a month is overwritten on regeneration; per-window rounding of spanning unpaid absences; `Employee.work_email` help text still says the rota receives the account email (the API sends the work email; the rota matches on `id`); no throttling on the API; the half-day calendar rule is a policy call for the practice.

