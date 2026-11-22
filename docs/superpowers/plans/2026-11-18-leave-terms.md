# Leave Terms on the Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Practice HR holds each contract's annual leave terms (days or weeks a year, with service steps) and sends every contract, with the terms in force, in the staff feed, so AMG Shift Central can work leave allowances out.

**Architecture:** Two nullable fields and two small step tables on the existing `ContractType` and `Contract` models. One new service, `people/services/leave_terms.py`, owns the rules, the audit entries and the one-line description. The admin gains a step table on the contract type page and a page of its own for a contract's terms. `GET /api/v1/people` gains a `contracts` list. Practice HR never turns terms into hours.

**Tech Stack:** Django 5.2, Python 3.13, django-unfold admin, SQLite, pytest-django. Lint is `ruff check .` (pyflakes rules only).

**Spec:** `docs/superpowers/specs/2026-11-18-allowance-rules-design.md` in `devachnid/shift-central`, sections 4 (all of part A) and 10. Read section 4 before starting. This plan is part A only; Shift Central's part is a separate plan in that repository.

## Global Constraints

- A base figure and every step total is in **days** for a contract type whose unit is `hours` and in **weeks** for one whose unit is `sessions`. No field stores which; the type's unit decides.
- A base is more than 0 and at most 99. `after_years` is 1 or more and unique within its owner. Totals rise with the years and the first is more than the base. Steps need a base.
- `Contract.leave_terms` is `usual` (default), `own` or `none`. Only `own` holds a base and steps; saving any other choice clears them.
- Terms are not dated: editing them corrects them for the whole contract. Nothing else about an existing contract becomes editable (the "existing contracts only end" rule stays).
- Every write goes through `people/services/leave_terms.py` and is audited with `people.services.audit.record`.
- The feed only gains a field. Existing fields of `/api/v1/people` keep their names, order and values.
- Practice HR's own leave (`absence` app: policies, pots, ledger) is not touched and does not read these terms.
- Bank holidays are not a term; do not add a field for them.
- Seeds send no email and no push. No secret, token or real person's detail goes in a test, a fixture or a doc.
- The full suite takes about 11 minutes. Run the named test files while working; run the whole suite once, in Task 5.
- Commit messages end with the two attribution lines the session gives (`Co-Authored-By:` and `Claude-Session:`); no other model name anywhere in the repository.

## File Structure

| File | Responsibility |
|---|---|
| `people/models/contract.py` (modify) | `leave_base` on `ContractType`; `leave_terms`, `leave_base` on `Contract`; `ContractTypeLeaveStep`, `ContractLeaveStep`. |
| `people/models/__init__.py` (modify) | Export the two step models. |
| `people/migrations/0018_leave_terms.py` (create, generated) | The schema change. |
| `people/migrations/0019_gp_full_time_week_is_8.py` (create) | 9 to 8 on the three GP types. |
| `people/services/leave_terms.py` (create) | `check`, `resolved`, `describe`, `set_type_terms`, `set_contract_terms`. |
| `people/admin_forms.py` (modify) | `steps_of`, `LeaveStepFormSet`, `ContractTermsForm`. |
| `people/admin.py` (modify) | Step inline and save on `ContractTypeAdmin`; new `ContractAdmin`; the "Leave terms" line on `ContractInline`. |
| `api/views.py` (modify) | `contracts` on each `/people` record. |
| `tests/data/people_feed.json` (create) | The sample feed both repositories test against. |
| `tests/test_leave_terms.py` (create) | Models, migration, service. |
| `tests/test_leave_terms_admin.py` (create) | The admin pages. |
| `tests/test_api.py` (modify) | The feed. |
| `docs/admin/people.md`, `docs/admin/api.md`, `docs/admin/absence.md`, `docs/guides/hr-administrator.md` (modify) | The guide. |
| `people/management/commands/seed_demo.py` (modify) | Demo GP types at 8 sessions. |

---

### Task 1: Models, migrations and the 8-session week

**Files:**
- Modify: `people/models/contract.py`, `people/models/__init__.py`, `people/management/commands/seed_demo.py:54`
- Create: `people/migrations/0018_leave_terms.py` (generated), `people/migrations/0019_gp_full_time_week_is_8.py`
- Test: `tests/test_leave_terms.py`

**Interfaces:**
- Produces: `ContractType.leave_base` (Decimal or None); `ContractType.leave_steps` (related manager of `ContractTypeLeaveStep(contract_type, after_years, total)`, ordered by `after_years`); `Contract.LeaveTerms.USUAL / OWN / NONE` (values `"usual"`, `"own"`, `"none"`); `Contract.leave_terms`; `Contract.leave_base`; `Contract.leave_steps` (related manager of `ContractLeaveStep(contract, after_years, total)`). Both step models are exported from `people.models`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_leave_terms.py`:

```python
"""Leave terms on contract types and contracts (Shift Central's allowance
spec, section 4): what the models hold, and the practice's 8-session week."""
from decimal import Decimal as D

import pytest
from django.db import IntegrityError, transaction

from people.models import Contract, ContractLeaveStep, ContractType, ContractTypeLeaveStep
from tests.factories import make_contract, make_contract_type, make_employment

pytestmark = pytest.mark.django_db


def test_a_new_contract_takes_the_usual_terms_and_holds_none_of_its_own():
    c = make_contract(make_employment())
    assert c.leave_terms == Contract.LeaveTerms.USUAL == "usual"
    assert c.leave_base is None and not c.leave_steps.exists()
    assert c.contract_type.leave_base is None and not c.contract_type.leave_steps.exists()


def test_steps_are_kept_in_order_of_years_one_per_year():
    ct = make_contract_type()
    ContractTypeLeaveStep.objects.create(contract_type=ct, after_years=5, total=D("25"))
    ContractTypeLeaveStep.objects.create(contract_type=ct, after_years=1, total=D("23"))
    assert [s.after_years for s in ct.leave_steps.all()] == [1, 5]
    with pytest.raises(IntegrityError), transaction.atomic():
        ContractTypeLeaveStep.objects.create(contract_type=ct, after_years=5, total=D("26"))
    c = make_contract(make_employment(), ct)
    ContractLeaveStep.objects.create(contract=c, after_years=3, total=D("24"))
    with pytest.raises(IntegrityError), transaction.atomic():
        ContractLeaveStep.objects.create(contract=c, after_years=3, total=D("25"))


def test_the_seeded_gp_types_are_full_time_at_8_sessions():
    for name in ("Partner", "Salaried GP", "GP trainee"):
        assert ContractType.objects.get(name=name).full_time_weekly == D("8"), name
    assert ContractType.objects.get(name="Reception").full_time_weekly == D("37.5")
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_leave_terms.py -q`
Expected: an `ImportError` for `ContractLeaveStep`.

- [ ] **Step 3: Add the fields and the step models**

In `people/models/contract.py`, change the `full_time_weekly` help text to say 8 sessions, and add `leave_base` to `ContractType` after `full_time_weekly`:

```python
        help_text="What full time is in this unit: 8 sessions, 37.5 hours. FTE is derived from it.")
    leave_base = models.DecimalField(
        "usual annual leave a year", max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="In days for an hours type, in weeks for a sessions type. AMG Shift Central works "
                  "allowances out from it. Leave blank for a type whose allowances are typed there.")
```

Add to `Contract`, after `Basis`:

```python
    class LeaveTerms(models.TextChoices):
        USUAL = "usual", "Usual for the contract type"
        OWN = "own", "Own terms"
        NONE = "none", "Not worked out"
```

and after `notes`:

```python
    leave_terms = models.CharField(max_length=5, choices=LeaveTerms.choices, default=LeaveTerms.USUAL)
    leave_base = models.DecimalField(
        "annual leave a year", max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Only with Own terms: days a year for an hours contract, weeks a year for a sessions contract.")
```

At the end of the file, after `Contract` and before `PayRecord`, add:

```python
class LeaveStep(models.Model):
    """"After `after_years` complete years the total becomes `total`", in
    the unit of the base it steps up from (days or weeks)."""
    after_years = models.PositiveSmallIntegerField("after (complete years)", validators=[MinValueValidator(1)])
    total = models.DecimalField("total becomes", max_digits=5, decimal_places=2)

    class Meta:
        abstract = True
        ordering = ["after_years"]

    def __str__(self):
        return f"{self.total} after {self.after_years} years"


class ContractTypeLeaveStep(LeaveStep):
    contract_type = models.ForeignKey(ContractType, on_delete=models.CASCADE, related_name="leave_steps")

    class Meta(LeaveStep.Meta):
        constraints = [models.UniqueConstraint(fields=["contract_type", "after_years"], name="one_type_leave_step_per_years")]


class ContractLeaveStep(LeaveStep):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="leave_steps")

    class Meta(LeaveStep.Meta):
        constraints = [models.UniqueConstraint(fields=["contract", "after_years"], name="one_contract_leave_step_per_years")]
```

In `people/models/__init__.py` change the contract import and `__all__`:

```python
from .contract import Contract, ContractLeaveStep, ContractType, ContractTypeLeaveStep, PayRecord  # noqa: E402
```

```python
__all__ = [
    "AuditEntry", "Contract", "ContractLeaveStep", "ContractType", "ContractTypeLeaveStep",
    "EmergencyContact", "Employee", "Employment", "PatternDay", "PayRecord", "Position",
    "PositionTitle", "Team", "WorkingPattern",
]
```

- [ ] **Step 4: Generate the schema migration**

Run: `.venv/bin/python manage.py makemigrations people -n leave_terms`
Expected: `people/migrations/0018_leave_terms.py`, creating the two models, adding three fields and altering `full_time_weekly`. Open it and check it contains nothing else.

- [ ] **Step 5: Write the data migration**

Create `people/migrations/0019_gp_full_time_week_is_8.py`:

```python
"""The practice's full-time GP week is 8 sessions. The three GP types were
seeded at 9 (0008); a type someone has already changed is left alone."""
from decimal import Decimal

from django.db import migrations

GP_TYPES = ("Partner", "Salaried GP", "GP trainee")


def to_eight(apps, schema_editor):
    ContractType = apps.get_model("people", "ContractType")
    ContractType.objects.filter(name__in=GP_TYPES, full_time_weekly=Decimal("9")).update(full_time_weekly=Decimal("8"))


class Migration(migrations.Migration):
    dependencies = [("people", "0018_leave_terms")]
    operations = [migrations.RunPython(to_eight, migrations.RunPython.noop)]
```

In `people/management/commands/seed_demo.py`, change the two GP rows of `CONTRACT_TYPES`:

```python
    "Partner": (SESSIONS, "8"), "Salaried GP": (SESSIONS, "8"),
```

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_leave_terms.py tests/test_contracts.py tests/test_seed_demo.py -q`
Expected: all pass. (A trial run of the whole suite with the 9 to 8 change passed, so no other test should need changing.)

Run: `.venv/bin/python manage.py makemigrations --check --dry-run`
Expected: "No changes detected".

- [ ] **Step 7: Commit**

```bash
git add people/models people/migrations/0018_leave_terms.py people/migrations/0019_gp_full_time_week_is_8.py people/management/commands/seed_demo.py tests/test_leave_terms.py
git commit -m "Leave terms: fields and step tables on contract types and contracts; GP full time is 8 sessions"
```

---

### Task 2: The leave terms service

**Files:**
- Create: `people/services/leave_terms.py`
- Test: `tests/test_leave_terms.py` (append)

**Interfaces:**
- Consumes: Task 1's models; `people.services.audit.record(actor, obj, changes, note="")`.
- Produces (steps are always a list of `(after_years: int, total: Decimal)` tuples):
  - `check(base, steps) -> list` : the steps sorted by years, or `django.core.exceptions.ValidationError`. A dict error keyed `leave_base` for a bad base; a plain message for a bad step.
  - `resolved(contract) -> dict | None` : `{"base": Decimal, "steps": [(int, Decimal), ...]}`.
  - `describe(contract) -> str`.
  - `set_type_terms(actor, contract_type, base, steps=()) -> ContractType`.
  - `set_contract_terms(actor, contract, mode, base=None, steps=()) -> Contract`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_leave_terms.py`:

```python
# --- the service ---------------------------------------------------------------------------------

from django.core.exceptions import ValidationError  # noqa: E402

from people.models import AuditEntry  # noqa: E402
from people.services import leave_terms  # noqa: E402


def test_check_sorts_good_steps():
    assert leave_terms.check(D("22"), [(5, D("25")), (1, D("23"))]) == [(1, D("23")), (5, D("25"))]
    assert leave_terms.check(None, []) == [] and leave_terms.check(D("0.5"), []) == []


@pytest.mark.parametrize("base,steps,says", [
    (None, [(1, D("23"))], "need the figure they step up from"),
    (D("0"), [], "More than 0"),
    (D("99.5"), [], "at most 99"),
    (D("22"), [(0, D("23"))], "at least 1 complete year"),
    (D("22"), [(1, D("23")), (1, D("24"))], "same number of years"),
    (D("22"), [(1, D("22"))], "more than the figure before it"),
    (D("22"), [(1, D("24")), (5, D("23"))], "more than the figure before it"),
    (D("22"), [(1, D("100"))], "at most 99"),
])
def test_check_refuses(base, steps, says):
    with pytest.raises(ValidationError) as e:
        leave_terms.check(base, steps)
    assert says in "; ".join(e.value.messages)


def test_setting_a_types_terms_replaces_them_and_is_audited(hr_admin):
    ct = make_contract_type()
    leave_terms.set_type_terms(hr_admin, ct, D("22"), [(1, D("23")), (5, D("25"))])
    ct.refresh_from_db()
    assert ct.leave_base == D("22") and [(s.after_years, s.total) for s in ct.leave_steps.all()] == [(1, D("23")), (5, D("25"))]
    rows = {a.field: (a.before, a.after) for a in AuditEntry.objects.filter(model="people.contracttype", object_id=ct.pk)}
    assert rows == {"leave_base": ("", "22"), "leave_steps": ("", "23 after 1 year; 25 after 5 years")}
    AuditEntry.objects.all().delete()
    leave_terms.set_type_terms(hr_admin, ct, D("22.00"), [(5, D("25")), (1, D("23"))])      # the same again
    assert not AuditEntry.objects.exists()
    leave_terms.set_type_terms(hr_admin, ct, None)
    ct.refresh_from_db()
    assert ct.leave_base is None and not ct.leave_steps.exists()


def test_a_refused_change_writes_nothing(hr_admin):
    ct = make_contract_type()
    leave_terms.set_type_terms(hr_admin, ct, D("22"), [(1, D("23"))])
    AuditEntry.objects.all().delete()
    with pytest.raises(ValidationError):
        leave_terms.set_type_terms(hr_admin, ct, D("25"), [(1, D("24"))])
    ct.refresh_from_db()
    assert ct.leave_base == D("22") and ct.leave_steps.count() == 1 and not AuditEntry.objects.exists()


def test_a_contracts_own_terms_and_what_clears_them(hr_admin):
    c = make_contract(make_employment())
    with pytest.raises(ValidationError) as e:
        leave_terms.set_contract_terms(hr_admin, c, "own")
    assert "need a figure" in "; ".join(e.value.messages)
    with pytest.raises(ValidationError):
        leave_terms.set_contract_terms(hr_admin, c, "sometimes")
    leave_terms.set_contract_terms(hr_admin, c, "own", D("27"), [(10, D("30"))])
    c.refresh_from_db()
    assert (c.leave_terms, c.leave_base, c.leave_steps.count()) == ("own", D("27"), 1)
    fields = set(AuditEntry.objects.filter(model="people.contract", object_id=c.pk).values_list("field", flat=True))
    assert fields == {"leave_terms", "leave_base", "leave_steps"}
    leave_terms.set_contract_terms(hr_admin, c, "none", D("27"), [(10, D("30"))])       # a figure sent with another choice is dropped
    c.refresh_from_db()
    assert (c.leave_terms, c.leave_base, c.leave_steps.count()) == ("none", None, 0)


def test_resolved_and_describe_for_each_choice(hr_admin):
    reception = make_contract_type()
    trainee = make_contract_type("GP trainee", "sessions", D("8"))
    partner = make_contract_type("Partner", "sessions", D("8"))
    leave_terms.set_type_terms(hr_admin, reception, D("22"), [(1, D("23")), (5, D("25"))])
    leave_terms.set_type_terms(hr_admin, partner, D("8"))
    usual = make_contract(make_employment(), reception)
    assert leave_terms.resolved(usual) == {"base": D("22"), "steps": [(1, D("23")), (5, D("25"))]}
    assert leave_terms.describe(usual) == "Usual for Reception: 22 days; 23 after 1 year; 25 after 5 years"
    gp = make_contract(make_employment(), partner, D("6"))
    assert leave_terms.describe(gp) == "Usual for Partner: 8 weeks"
    blank = make_contract(make_employment(), trainee, D("8"))
    assert leave_terms.resolved(blank) is None
    assert leave_terms.describe(blank) == "Usual for GP trainee: none set, so not worked out"
    own = make_contract(make_employment(), reception)
    leave_terms.set_contract_terms(hr_admin, own, "own", D("27.5"))
    assert leave_terms.resolved(own) == {"base": D("27.5"), "steps": []}
    assert leave_terms.describe(own) == "Own: 27.5 days"
    leave_terms.set_contract_terms(hr_admin, own, "none")
    assert leave_terms.resolved(own) is None and leave_terms.describe(own) == "Not worked out"
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_leave_terms.py -q`
Expected: `ImportError: cannot import name 'leave_terms'`.

- [ ] **Step 3: Write the service**

Create `people/services/leave_terms.py`:

```python
"""Annual leave terms, held on a contract type (the usual terms) and on a
contract (its own, when they differ). A base and each step's total are in
days for an hours contract and weeks for a sessions one. AMG Shift Central
reads the terms in force through the feed and works the allowances out;
nothing here turns terms into hours, and Practice HR's own leave policies
do not read them."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from people.models import Contract, ContractLeaveStep, ContractType, ContractTypeLeaveStep
from people.services import audit

MOST = Decimal("99")
Terms = Contract.LeaveTerms


def check(base, steps):
    """The steps sorted by years, or ValidationError. `steps` is an iterable
    of (after_years, total)."""
    steps = sorted(steps)
    if base is None:
        if steps:
            raise ValidationError({"leave_base": "Steps need the figure they step up from."})
        return []
    if not Decimal("0") < base <= MOST:
        raise ValidationError({"leave_base": "More than 0 and at most 99."})
    if len({years for years, _ in steps}) != len(steps):
        raise ValidationError("Two steps have the same number of years.")
    before = base
    for years, total in steps:
        if years < 1:
            raise ValidationError("A step starts after at least 1 complete year.")
        if total <= before:
            raise ValidationError(f"The total after {_years(years)} must be more than the figure before it ({_plain(before)}).")
        if total > MOST:
            raise ValidationError("A total is at most 99.")
        before = total
    return steps


def _steps(owner):
    return [(s.after_years, s.total) for s in owner.leave_steps.all()]


def resolved(contract):
    """The terms in force for a contract, {"base", "steps"}, or None when
    its allowances are not worked out."""
    if contract.leave_terms == Terms.OWN:
        owner = contract
    elif contract.leave_terms == Terms.USUAL:
        owner = contract.contract_type
    else:
        return None
    if owner.leave_base is None:
        return None
    return {"base": owner.leave_base, "steps": _steps(owner)}


def _plain(number):
    """22.00 as "22", 27.50 as "27.5"."""
    return f"{number.normalize():f}"


def _years(years):
    return f"{years} year" if years == 1 else f"{years} years"


def _steps_text(steps):
    return "; ".join(f"{_plain(total)} after {_years(years)}" for years, total in steps)


def _text(terms, unit):
    word = "days" if unit == ContractType.Unit.HOURS else "weeks"
    base = f"{_plain(terms['base'])} {word}"
    return f"{base}; {_steps_text(terms['steps'])}" if terms["steps"] else base


def describe(contract):
    """One line for the admin: which terms apply and what they are."""
    ct = contract.contract_type
    terms = resolved(contract)
    if contract.leave_terms == Terms.NONE:
        return "Not worked out"
    if contract.leave_terms == Terms.OWN:
        return f"Own: {_text(terms, ct.unit)}" if terms else "Own: no figure set"
    return f"Usual for {ct.name}: {_text(terms, ct.unit)}" if terms else f"Usual for {ct.name}: none set, so not worked out"


def _show(base):
    return "" if base is None else _plain(base)


def _replace(owner, step_model, key, base, steps):
    owner.leave_base = base
    owner.leave_steps.all().delete()
    step_model.objects.bulk_create([step_model(**{key: owner}, after_years=years, total=total) for years, total in steps])


@transaction.atomic
def set_type_terms(actor, contract_type, base, steps=()):
    """A contract type's usual terms. Every contract of the type on "Usual
    for the contract type" follows them from the next read of the feed."""
    steps = check(base, steps)
    changes = {"leave_base": (_show(contract_type.leave_base), _show(base)),
               "leave_steps": (_steps_text(_steps(contract_type)), _steps_text(steps))}
    _replace(contract_type, ContractTypeLeaveStep, "contract_type", base, steps)
    contract_type.save(update_fields=["leave_base"])
    audit.record(actor, contract_type, changes)
    return contract_type


@transaction.atomic
def set_contract_terms(actor, contract, mode, base=None, steps=()):
    """Which terms a contract takes. Only Own terms hold a figure and
    steps: with either other choice whatever is sent is dropped."""
    if mode not in Terms.values:
        raise ValidationError({"leave_terms": "Choose which leave terms apply."})
    if mode != Terms.OWN:
        base, steps = None, ()
    elif base is None:
        raise ValidationError({"leave_base": "Own terms need a figure."})
    steps = check(base, steps)
    changes = {"leave_terms": (contract.leave_terms, mode),
               "leave_base": (_show(contract.leave_base), _show(base)),
               "leave_steps": (_steps_text(_steps(contract)), _steps_text(steps))}
    contract.leave_terms = mode
    _replace(contract, ContractLeaveStep, "contract", base, steps)
    contract.save(update_fields=["leave_terms", "leave_base"])
    audit.record(actor, contract, changes)
    return contract
```

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_leave_terms.py -q && .venv/bin/ruff check people tests/test_leave_terms.py`
Expected: all pass; ruff reports nothing. (If `.venv/bin/ruff` is missing: `.venv/bin/pip install ruff==0.16.6`.)

- [ ] **Step 5: Commit**

```bash
git add people/services/leave_terms.py tests/test_leave_terms.py
git commit -m "Leave terms: the service that checks, resolves, describes and audits them"
```

---

### Task 3: The admin pages

**Files:**
- Modify: `people/admin_forms.py`, `people/admin.py`
- Test: `tests/test_leave_terms_admin.py`

**Interfaces:**
- Consumes: `leave_terms.check`, `describe`, `set_type_terms`, `set_contract_terms` (Task 2).
- Produces: `/admin/people/contracttype/<pk>/change/` saves the usual terms; `/admin/people/contract/<pk>/change/` (new) saves a contract's terms and returns to its employment page; the Contracts inline on `/admin/people/employment/<pk>/change/` shows a "Leave terms" line with a Change link. `admin_forms.steps_of(formset) -> list[(int, Decimal)]`.

How Django's admin runs a change page, which this task relies on: the main form is validated and its values are put on the object (not saved); the inline formsets are built with that object as `formset.instance` and validated; then `save_model` runs, then `save_formset` once for each inline, even an empty one.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_leave_terms_admin.py`:

```python
"""Leave terms in the admin: the usual terms on a contract type, a
contract's own on its own page, and the line on the employment page."""
from decimal import Decimal as D

import pytest

from people.models import AuditEntry, Contract
from people.services import leave_terms
from tests.factories import make_contract, make_contract_type, make_employment

pytestmark = pytest.mark.django_db
STEPS = "leave_steps"


def _steps(*rows, initial=0, prefix=STEPS):
    """The inline's POST fields. Each row is (id, after_years, total, delete)."""
    data = {f"{prefix}-TOTAL_FORMS": len(rows), f"{prefix}-INITIAL_FORMS": initial}
    for i, (pk, years, total, delete) in enumerate(rows):
        data.update({f"{prefix}-{i}-id": pk, f"{prefix}-{i}-after_years": years, f"{prefix}-{i}-total": total})
        if delete:
            data[f"{prefix}-{i}-DELETE"] = "on"
    return data


def _type_post(ct, base, *rows, initial=0):
    return {"name": ct.name, "unit": ct.unit, "full_time_weekly": str(ct.full_time_weekly),
            "display_order": ct.display_order, "leave_base": base, "_save": "Save", **_steps(*rows, initial=initial)}


def test_the_type_page_saves_usual_terms_through_the_service(admin_client, hr_admin):
    ct = make_contract_type()
    url = f"/admin/people/contracttype/{ct.pk}/change/"
    assert "Usual annual leave a year" in admin_client.get(url).content.decode()
    r = admin_client.post(url, _type_post(ct, "22", ("", 5, "25", False), ("", 1, "23", False)))
    assert r.status_code == 302, r.content.decode()[:3000]
    ct.refresh_from_db()
    assert ct.leave_base == D("22") and [(s.after_years, s.total) for s in ct.leave_steps.all()] == [(1, D("23")), (5, D("25"))]
    audited = AuditEntry.objects.filter(model="people.contracttype", object_id=ct.pk)
    assert {a.field for a in audited} == {"leave_base", "leave_steps"} and {a.actor for a in audited} == {hr_admin}


def test_a_step_can_be_removed_and_the_terms_cleared(admin_client, hr_admin):
    ct = make_contract_type()
    leave_terms.set_type_terms(hr_admin, ct, D("22"), [(1, D("23")), (5, D("25"))])
    one, five = ct.leave_steps.all()
    url = f"/admin/people/contracttype/{ct.pk}/change/"
    r = admin_client.post(url, _type_post(ct, "22", (one.pk, 1, "23.00", False), (five.pk, 5, "25.00", True), initial=2))
    assert r.status_code == 302, r.content.decode()[:3000]
    assert [(s.after_years, s.total) for s in ct.leave_steps.all()] == [(1, D("23"))]
    one = ct.leave_steps.get()
    r = admin_client.post(url, _type_post(ct, "", (one.pk, 1, "23.00", True), initial=1))
    assert r.status_code == 302
    ct.refresh_from_db()
    assert ct.leave_base is None and not ct.leave_steps.exists()


@pytest.mark.parametrize("base,rows,says", [
    ("22", [("", 1, "22", False)], "more than the figure before it"),
    ("", [("", 1, "23", False)], "need the figure they step up from"),
    ("0", [], "More than 0"),
])
def test_bad_usual_terms_re_render_and_save_nothing(admin_client, base, rows, says):
    ct = make_contract_type()
    r = admin_client.post(f"/admin/people/contracttype/{ct.pk}/change/", _type_post(ct, base, *rows))
    assert r.status_code == 200 and says in r.content.decode()
    ct.refresh_from_db()
    assert ct.leave_base is None and not ct.leave_steps.exists() and not AuditEntry.objects.exists()


def test_the_other_fields_of_a_type_still_save(admin_client):
    ct = make_contract_type("Cleaning")
    data = _type_post(ct, "")
    data["display_order"] = 45
    assert admin_client.post(f"/admin/people/contracttype/{ct.pk}/change/", data).status_code == 302
    ct.refresh_from_db()
    assert ct.display_order == 45 and ct.leave_base is None


def test_the_employment_page_shows_each_contracts_terms_with_a_link(admin_client, hr_admin):
    emp = make_employment()
    ct = make_contract_type()
    leave_terms.set_type_terms(hr_admin, ct, D("22"), [(1, D("23"))])
    c = make_contract(emp, ct)
    body = admin_client.get(f"/admin/people/employment/{emp.pk}/change/").content.decode()
    assert "Usual for Reception: 22 days; 23 after 1 year" in body
    assert f'href="/admin/people/contract/{c.pk}/change/"' in body


def _contract_post(mode, base, *rows, initial=0):
    return {"leave_terms": mode, "leave_base": base, "_save": "Save", **_steps(*rows, initial=initial)}


def test_the_contract_page_sets_own_terms_and_returns_to_the_employment(admin_client, hr_admin):
    c = make_contract(make_employment())
    url = f"/admin/people/contract/{c.pk}/change/"
    body = admin_client.get(url).content.decode()
    assert "Own terms" in body and 'name="weekly_amount"' not in body          # the rest of the contract is read-only
    r = admin_client.post(url, _contract_post("own", "27", ("", 10, "30", False)))
    assert r.status_code == 302 and r["Location"] == f"/admin/people/employment/{c.employment_id}/change/"
    c.refresh_from_db()
    assert (c.leave_terms, c.leave_base) == ("own", D("27")) and [(s.after_years, s.total) for s in c.leave_steps.all()] == [(10, D("30"))]
    assert {a.actor for a in AuditEntry.objects.filter(model="people.contract", object_id=c.pk)} == {hr_admin}


def test_choosing_another_option_drops_the_contracts_own_figure(admin_client, hr_admin):
    c = make_contract(make_employment())
    leave_terms.set_contract_terms(hr_admin, c, "own", D("27"), [(10, D("30"))])
    step = c.leave_steps.get()
    r = admin_client.post(f"/admin/people/contract/{c.pk}/change/",
                          _contract_post("none", "27.00", (step.pk, 10, "30.00", False), initial=1))
    assert r.status_code == 302, r.content.decode()[:3000]
    c.refresh_from_db()
    assert (c.leave_terms, c.leave_base, c.leave_steps.count()) == ("none", None, 0)


def test_own_terms_without_a_figure_re_render(admin_client):
    c = make_contract(make_employment())
    r = admin_client.post(f"/admin/people/contract/{c.pk}/change/", _contract_post("own", ""))
    assert r.status_code == 200 and "Own terms need a figure" in r.content.decode()
    c.refresh_from_db()
    assert c.leave_terms == "usual"


def test_a_contract_cannot_be_added_deleted_or_otherwise_edited_from_its_page(admin_client):
    c = make_contract(make_employment(), amount=D("30"))
    assert admin_client.get("/admin/people/contract/add/").status_code == 403
    assert admin_client.post(f"/admin/people/contract/{c.pk}/delete/", {"post": "yes"}).status_code == 403
    data = _contract_post("usual", "")
    data.update({"weekly_amount": "10", "from_date": "2020-01-01"})
    admin_client.post(f"/admin/people/contract/{c.pk}/change/", data)
    c.refresh_from_db()
    assert c.weekly_amount == D("30") and Contract.objects.count() == 1


def test_the_contract_page_is_not_on_the_admin_index_and_is_for_hr_admins(admin_client, employee_client):
    c = make_contract(make_employment())
    assert 'href="/admin/people/contract/"' not in admin_client.get("/admin/").content.decode()
    assert employee_client.get(f"/admin/people/contract/{c.pk}/change/").status_code in (302, 403)
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_leave_terms_admin.py -q`
Expected: failures; the contract page tests fail with a 404.

- [ ] **Step 3: The forms**

In `people/admin_forms.py`, add `leave_terms` to the services import:

```python
from people.services import contracts, employments, leave_terms, positions
```

and add at the end of the file:

```python
def steps_of(formset):
    """The (after_years, total) pairs a leave-steps formset holds, less the
    rows ticked for deletion and the blank extra rows."""
    out = []
    for form in formset.forms:
        data = getattr(form, "cleaned_data", None) or {}
        if data.get("DELETE") or data.get("after_years") is None or data.get("total") is None:
            continue
        out.append((data["after_years"], data["total"]))
    return out


class LeaveStepFormSet(BaseInlineFormSet):
    """The steps table on a contract type and on a contract. The parent
    object already carries the form's new values when this runs, so the
    whole of the terms is checked together."""

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        owner = self.instance
        mode = getattr(owner, "leave_terms", None)
        if mode is not None and mode != Contract.LeaveTerms.OWN:
            return                      # a contract not on its own terms: the service drops whatever is here
        try:
            leave_terms.check(owner.leave_base, steps_of(self))
        except ValidationError as e:
            raise ValidationError(e.messages) from None


class ContractTermsForm(forms.ModelForm):
    """The contract's own page: only its leave terms can change."""
    class Meta:
        model = Contract
        fields = ["leave_terms", "leave_base"]

    def clean(self):
        data = super().clean()
        if data.get("leave_terms") == Contract.LeaveTerms.OWN and data.get("leave_base") is None:
            self.add_error("leave_base", "Own terms need a figure.")
        return data
```

- [ ] **Step 4: The admin classes**

In `people/admin.py`:

Add `HttpResponseRedirect` and the new names to the imports:

```python
from django.http import HttpResponseRedirect
```

```python
from people.models import (AuditEntry, Contract, ContractLeaveStep, ContractType, ContractTypeLeaveStep,
                           EmergencyContact, Employee, Employment, PatternDay, PayRecord, Position,
                           PositionTitle, Team, WorkingPattern)
from people.services import access, audit, contracts, employees, employments, leave_terms, pay, positions
```

Replace `ContractInline` with:

```python
class ContractInline(TabularInline):
    model = Contract
    form = admin_forms.ContractForm
    formset = admin_forms.ContractInlineFormSet
    extra = 0
    can_delete = False
    readonly_fields = ("leave_terms_in_force",)

    @admin.display(description="Leave terms")
    def leave_terms_in_force(self, obj):
        if obj is None or obj.pk is None:
            return "Usual for the contract type. Save, then use Change to give this contract its own."
        return format_html('{} <a href="{}">Change</a>', leave_terms.describe(obj),
                           reverse("admin:people_contract_change", args=[obj.pk]))
```

Replace `ContractTypeAdmin` with:

```python
STEPS_TITLE = "Service steps: after this many complete years, the total becomes"


class ContractTypeLeaveStepInline(TabularInline):
    model = ContractTypeLeaveStep
    formset = admin_forms.LeaveStepFormSet
    extra = 0
    verbose_name = "step"
    verbose_name_plural = STEPS_TITLE


@admin.register(ContractType)
class ContractTypeAdmin(ModelAdmin):
    list_display = ("name", "unit", "full_time_weekly", "leave_base", "display_order")
    inlines = [ContractTypeLeaveStepInline]

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        # The usual leave terms are written by the service in save_formset,
        # with the steps, so one audit entry covers both. Here the type is
        # saved with the figure it already had.
        request._leave_base = form.cleaned_data.get("leave_base")
        obj.leave_base = ContractType.objects.get(pk=obj.pk).leave_base if change else None
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        formset.save(commit=False)      # sets what the admin's change message reads; writes nothing
        try:
            leave_terms.set_type_terms(request.user, form.instance, request._leave_base, admin_forms.steps_of(formset))
        except ValidationError as e:    # LeaveStepFormSet has run the same check: a backstop
            messages.error(request, "; ".join(e.messages))


class ContractLeaveStepInline(TabularInline):
    model = ContractLeaveStep
    formset = admin_forms.LeaveStepFormSet
    extra = 0
    verbose_name = "step"
    verbose_name_plural = STEPS_TITLE + " (Own terms only)"


@admin.register(Contract)
class ContractAdmin(ModelAdmin):
    """A contract's own page, reached from the Contracts table on its
    employment. Only the leave terms change here: contracts are added and
    ended on the employment page, and nothing else about one is edited."""
    form = admin_forms.ContractTermsForm
    CONTRACT = ("employment", "contract_type", "basis", "from_date", "to_date", "weekly_amount", "notes")
    fields = (*CONTRACT, "leave_terms_in_force", "leave_terms", "leave_base")
    readonly_fields = (*CONTRACT, "leave_terms_in_force")
    inlines = [ContractLeaveStepInline]
    list_display = ("employment", "contract_type", "from_date", "to_date", "weekly_amount", "leave_terms")
    list_select_related = ("employment__employee", "contract_type")

    @admin.display(description="Leave terms in force")
    def leave_terms_in_force(self, obj):
        return leave_terms.describe(obj)

    def has_module_permission(self, request):
        return False                    # not on the index or the menu: it is reached from an employment

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        request._leave_terms = (form.cleaned_data["leave_terms"], form.cleaned_data.get("leave_base"))

    def save_formset(self, request, form, formset, change):
        formset.save(commit=False)
        mode, base = request._leave_terms
        try:
            leave_terms.set_contract_terms(request.user, Contract.objects.get(pk=form.instance.pk), mode, base,
                                           admin_forms.steps_of(formset))
        except ValidationError as e:
            messages.error(request, "; ".join(e.messages))

    def response_post_save_change(self, request, obj):
        return HttpResponseRedirect(reverse("admin:people_employment_change", args=[obj.employment_id]))
```

- [ ] **Step 5: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_leave_terms_admin.py tests/test_people_admin.py tests/test_leave_elsewhere.py tests/test_navigation.py -q`
Expected: all pass. If `test_the_contract_page_is_not_on_the_admin_index…` fails because the dashboard lists the model, check `hr/admin_site.py`'s `get_app_list`: `has_module_permission` returning False already keeps a model out of Django's app list, so the cause will be a hard-coded link; do not add one.

If a formset POST is refused with "ManagementForm data is missing", the inline's prefix is not `leave_steps`: print `response.context["inline_admin_formsets"][0].formset.prefix` in the test and use that for `STEPS`.

`LeaveStepFormSet.clean` raises errors that belong to the table as a whole (Django calls them non-form errors). If `test_bad_usual_terms_re_render_and_save_nothing` gets a 200 without the message in the page, the unfold inline template is not printing them: check `response.context["inline_admin_formsets"][0].formset.non_form_errors()` holds the message, then show it with `messages.error(request, ...)` from a `changeform_view` override on the two admins, and keep the test's assertion on the page text.

- [ ] **Step 6: Look at the pages**

Run: `.venv/bin/python manage.py runserver 8011` with `DEBUG=1`, sign in as an HR admin (the README's "Develop" section says how to make one), and open a contract type, an employment and a contract's own page. Check: the steps table reads sensibly, the "Leave terms" line and its Change link show on each contract row, and saving a contract's terms lands back on the employment page. Stop the server.

- [ ] **Step 7: Commit**

```bash
git add people/admin.py people/admin_forms.py tests/test_leave_terms_admin.py
git commit -m "Leave terms: usual terms on the contract type page, a contract's own on its own page"
```

---

### Task 4: The feed

**Files:**
- Modify: `api/views.py` (the module docstring and `people()`)
- Create: `tests/data/people_feed.json`
- Test: `tests/test_api.py` (append)

**Interfaces:**
- Consumes: `leave_terms.resolved(contract)`.
- Produces: each record of `GET /api/v1/people` gains `"contracts"`: every contract of the employment the record describes, oldest first, each `{"id", "contract_type", "unit", "from", "to", "weekly_amount", "full_time_weekly", "leave"}`. `leave` is `null` or `{"base": "22.00", "steps": [{"after_years": 1, "total": "23.00"}]}`. Amounts are strings with two decimal places.
- `tests/data/people_feed.json` is copied byte for byte into Shift Central's `tests/data/people_feed.json` by that repository's plan. Whoever changes one changes the other.

- [ ] **Step 1: Write the sample file**

Create `tests/data/people_feed.json`:

```json
{"people": [
  {"id": 101, "first_name": "Sam", "last_name": "Patel", "name": "Sam Patel", "email": "sam@practice.example",
   "contract_type": "Reception", "unit": "hours",
   "employment": {"start": "2025-06-01", "end": null},
   "positions": [{"title": "Receptionist", "team": "Reception"}],
   "contracts": [
     {"id": 41, "contract_type": "Reception", "unit": "hours", "from": "2025-06-01", "to": "2026-08-31",
      "weekly_amount": "22.50", "full_time_weekly": "37.50",
      "leave": {"base": "22.00", "steps": [{"after_years": 1, "total": "23.00"}, {"after_years": 5, "total": "25.00"}]}},
     {"id": 42, "contract_type": "Reception", "unit": "hours", "from": "2026-09-01", "to": null,
      "weekly_amount": "30.00", "full_time_weekly": "37.50",
      "leave": {"base": "22.00", "steps": [{"after_years": 1, "total": "23.00"}, {"after_years": 5, "total": "25.00"}]}}
   ]},
  {"id": 102, "first_name": "Alex", "last_name": "Morgan", "name": "Alex Morgan", "email": "alex@practice.example",
   "contract_type": "Partner", "unit": "sessions",
   "employment": {"start": "2019-04-01", "end": null},
   "positions": [{"title": "GP Partner", "team": "GPs"}],
   "contracts": [
     {"id": 43, "contract_type": "Partner", "unit": "sessions", "from": "2019-04-01", "to": null,
      "weekly_amount": "6.00", "full_time_weekly": "8.00",
      "leave": {"base": "8.00", "steps": []}}
   ]},
  {"id": 103, "first_name": "Jo", "last_name": "Okafor", "name": "Jo Okafor", "email": "jo@practice.example",
   "contract_type": "Management", "unit": "hours",
   "employment": {"start": "2015-01-05", "end": null},
   "positions": [{"title": "Practice Manager", "team": "Management"}],
   "contracts": [
     {"id": 44, "contract_type": "Management", "unit": "hours", "from": "2015-01-05", "to": null,
      "weekly_amount": "37.50", "full_time_weekly": "37.50",
      "leave": {"base": "27.00", "steps": [{"after_years": 10, "total": "30.00"}]}}
   ]},
  {"id": 104, "first_name": "Riley", "last_name": "Chen", "name": "Riley Chen", "email": "riley@practice.example",
   "contract_type": "GP trainee", "unit": "sessions",
   "employment": {"start": "2026-08-05", "end": null},
   "positions": [{"title": "GP Trainee", "team": "GPs"}],
   "contracts": [
     {"id": 45, "contract_type": "GP trainee", "unit": "sessions", "from": "2026-08-05", "to": null,
      "weekly_amount": "8.00", "full_time_weekly": "8.00",
      "leave": null}
   ]},
  {"id": 105, "first_name": "Casey", "last_name": "Lee", "name": "Casey Lee", "email": "casey@practice.example",
   "contract_type": null, "unit": null,
   "employment": {"start": "2026-10-01", "end": null},
   "positions": [],
   "contracts": []}
]}
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_api.py`:

```python
# --- contracts and leave terms in /people (Shift Central's allowance spec, 4.4) ------------------

import json  # noqa: E402
from decimal import Decimal as D  # noqa: E402
from pathlib import Path  # noqa: E402

from people.services import leave_terms  # noqa: E402
from tests.factories import make_employee  # noqa: E402

SAMPLE = Path(__file__).parent / "data" / "people_feed.json"


def _sample_world():
    """The people in tests/data/people_feed.json. Every date is in the past,
    so the feed for them is the same whatever today is."""
    reception, management = make_contract_type("Reception"), make_contract_type("Management")
    partner = make_contract_type("Partner", "sessions", D("8"))
    trainee = make_contract_type("GP trainee", "sessions", D("8"))
    leave_terms.set_type_terms(None, reception, D("22"), [(1, D("23")), (5, D("25"))])
    leave_terms.set_type_terms(None, partner, D("8"))
    gps = make_team("GPs")

    sam = make_employment(make_employee("Sam", "Patel", "sam@practice.example", pk=101), start=date(2025, 6, 1))
    make_position(sam, title="Receptionist", team=make_team("Reception"))
    make_contract(sam, reception, D("22.5"), pk=41, to_date=date(2026, 8, 31))
    make_contract(sam, reception, D("30"), start=date(2026, 9, 1), pk=42)

    alex = make_employment(make_employee("Alex", "Morgan", "alex@practice.example", pk=102), start=date(2019, 4, 1))
    make_position(alex, title="GP Partner", team=gps)
    make_contract(alex, partner, D("6"), pk=43)

    jo = make_employment(make_employee("Jo", "Okafor", "jo@practice.example", pk=103), start=date(2015, 1, 5))
    make_position(jo, title="Practice Manager", team=make_team("Management"))
    leave_terms.set_contract_terms(None, make_contract(jo, management, D("37.5"), pk=44), "own", D("27"), [(10, D("30"))])

    riley = make_employment(make_employee("Riley", "Chen", "riley@practice.example", pk=104), start=date(2026, 8, 5))
    make_position(riley, title="GP Trainee", team=gps)
    make_contract(riley, trainee, D("8"), pk=45)

    make_employment(make_employee("Casey", "Lee", "casey@practice.example", pk=105), start=date(2026, 10, 1))


def test_the_feed_is_the_sample_both_apps_test_against(api, db):
    _sample_world()
    got = sorted(api("/api/v1/people").json()["people"], key=lambda r: r["id"])
    assert got == json.loads(SAMPLE.read_text())["people"]


def test_a_change_to_the_usual_terms_reaches_every_contract_on_them(api, db):
    _sample_world()
    leave_terms.set_type_terms(None, make_contract_type("Reception"), D("24"))
    rows = {r["id"]: r for r in api("/api/v1/people").json()["people"]}
    assert [c["leave"] for c in rows[101]["contracts"]] == [{"base": "24.00", "steps": []}] * 2
    assert rows[103]["contracts"][0]["leave"]["base"] == "27.00"          # own terms are untouched


def test_a_leavers_contracts_are_those_of_their_last_employment(api, db):
    emp = hours_employee(start=date(2024, 1, 1), end_date=date(2024, 12, 31))
    row = api("/api/v1/people").json()["people"][0]
    assert row["employment"]["end"] == "2024-12-31"
    assert [c["id"] for c in row["contracts"]] == [emp.contracts.get().pk]
```

- [ ] **Step 3: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_api.py -q -k "sample or usual_terms or leavers_contracts"`
Expected: three failures on the missing `contracts` key.

- [ ] **Step 4: Add the field**

In `api/views.py`, import the service beside the other `people.services` imports:

```python
from people.services import leave_terms
```

Add above `people()`:

```python
def _contract(c):
    terms = leave_terms.resolved(c)
    return {
        "id": c.pk, "contract_type": c.contract_type.name, "unit": c.contract_type.unit,
        "from": _iso(c.from_date), "to": _iso(c.to_date),
        "weekly_amount": str(c.weekly_amount), "full_time_weekly": str(c.contract_type.full_time_weekly),
        "leave": None if terms is None else {
            "base": str(terms["base"]),
            "steps": [{"after_years": years, "total": str(total)} for years, total in terms["steps"]]},
    }
```

In `people()`, add after the `"positions"` line of the record:

```python
            "contracts": [_contract(c) for c in emp.contracts.select_related("contract_type")
                          .prefetch_related("leave_steps", "contract_type__leave_steps")],
```

In the module docstring, add inside the `/people` record after the `"positions"` line:

```
        "contracts": [{                # every contract of that employment, oldest first
            "id": 41, "contract_type": "Reception", "unit": "hours",
            "from": "2025-06-01", "to": null,
            "weekly_amount": "22.50", "full_time_weekly": "37.50",
            "leave": {"base": "22.00",             # null when allowances are not worked out
                      "steps": [{"after_years": 1, "total": "23.00"}]}
        }]
```

and after the paragraph that follows the record:

```
    `leave` is the annual leave terms in force for the contract (its own,
    or its type's usual terms): `base` and each `total` are days a year
    for an hours contract and weeks a year for a sessions one, and a step
    applies after that many complete years. AMG Shift Central works the
    allowances out from them; nothing here does.
```

- [ ] **Step 5: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_api.py -q`
Expected: all pass, the existing `/people` tests included.

- [ ] **Step 6: Commit**

```bash
git add api/views.py tests/test_api.py tests/data/people_feed.json
git commit -m "Feed: each person's contracts with the leave terms in force"
```

---

### Task 5: The guide, the whole suite and the pull request

**Files:**
- Modify: `docs/admin/people.md`, `docs/admin/api.md`, `docs/admin/absence.md:214`, `docs/guides/hr-administrator.md`
- Test: `tests/test_docs.py` (existing; it checks every link and anchor)

**Interfaces:**
- Consumes: everything above. Produces: documentation only.

- [ ] **Step 1: `docs/admin/people.md`**

In "## Contract type", change the seeded line to "full time 8 a week" for the three GP types, and in "### Full time weekly" change "9 sessions" to "8 sessions". Add after "### Full time weekly":

```markdown
### Usual annual leave a year / Service steps

The annual leave a contract of this type usually carries: **days a year for
an hours type, weeks a year for a sessions type**. The steps table beneath
it says how that grows with service: "after 1 complete year the total
becomes 23". Service counts from the employment's start date.

Practice HR does nothing with these figures itself. **AMG Shift Central
reads them and works each person's leave allowance out**, and it is the
record of the result. Every contract of this type follows them unless the
contract has [its own terms](#leave-terms). A change here reaches those
contracts at Shift Central's next read, for this leave year and the next;
check the figures it lists for confirmation there.

Leave both blank for a type whose allowances are typed into Shift Central
by hand: GP trainee is one, because NWSSP tells the practice each trainee's
allowance.

What is refused: steps with no starting figure; a figure of 0 or over 99; a
total that is not more than the one before it; two steps for the same
number of years. Bank holidays are not entered here: Shift Central gives
one day for each (2 sessions for a GP, pro rata).
```

In "## Contract", add after "### Notes":

```markdown
### Leave terms

Each row of the Contracts table shows the leave terms in force, with a
**Change** link to the contract's own page. There are three choices:

- **Usual for the contract type** (what a new contract gets): the terms on
  its [contract type](#usual-annual-leave-a-year--service-steps).
- **Own terms**: this contract's own figure and steps, in the same units.
  Use it when one person's contract differs from the rest of their type.
- **Not worked out**: Shift Central leaves this person's allowances for a
  manager to type.

The terms are the only thing about an existing contract that can be edited,
and editing them corrects them for the whole contract. **Terms that change
from a date are a new contract from that date**: end the old one the day
before, as for any other contractual change.
```

- [ ] **Step 2: `docs/admin/api.md`**

In "## `GET /api/v1/people`", add the `contracts` field to the example exactly as in the `api/views.py` docstring of Task 4, and add after the paragraph that follows the example:

```markdown
`contracts` is every contract of that employment, oldest first, with the
[leave terms](people.md#leave-terms) in force for each. `leave` is `null`
when the contract's allowances are not worked out. `base` and each `total`
are days a year for an hours contract and weeks a year for a sessions one;
amounts are strings with two decimal places. AMG Shift Central works leave
allowances out from this field.
```

- [ ] **Step 3: The two smaller pages**

In `docs/admin/absence.md` line 214, change "9 sessions…" to "8 sessions…".

In `docs/guides/hr-administrator.md` make three additions.

In "## Going live: your first month", step 1, after the sentence ending "with the right full-time week.", add:

```markdown
   If leave is held in AMG Shift Central, also set each type's **Usual
   annual leave a year** and its service steps here (see
   [Leave terms](#leave-terms)); leave them blank for GP trainee.
```

In "### How to add their employment, position and contract", after the numbered list (after "5. Choose **Save**."), add:

```markdown
#### Leave terms

A new contract takes the usual annual leave for its contract type: days a
year for staff on hours, weeks a year for GPs, with any steps for length of
service. After saving, each contract row shows the terms in force.

- If this person's contract says something different, choose **Change**
  beside the contract, pick **Own terms** and enter their figure and steps.
- For someone whose allowance is given to the practice (a GP trainee),
  pick **Not worked out**.

AMG Shift Central works the allowance out from these terms and lists it for
a manager to check. Leave itself is booked and approved there.
```

In "### How to change someone's hours", after step 5, add:

```markdown
The new contract takes the usual leave terms for its type. If the old
contract had its own terms, set them again on the new one (**Change**
beside it).
```

The anchor for "#### Leave terms" is `#leave-terms`.

- [ ] **Step 4: Run the docs tests and lint**

Run: `.venv/bin/python -m pytest tests/test_docs.py -q && .venv/bin/ruff check .`
Expected: pass; ruff reports nothing. A failing anchor means a heading and its link differ: the anchor for "### Usual annual leave a year / Service steps" is `#usual-annual-leave-a-year--service-steps` (the slash is dropped, leaving two hyphens).

- [ ] **Step 5: Commit**

```bash
git add docs
git commit -m "Guide: leave terms on contract types and contracts, and the contracts field of the feed"
```

- [ ] **Step 6: Run the whole suite**

Run in the background (about 11 minutes): `.venv/bin/python -m pytest -q -p no:cacheprovider`
Expected: every test passes (1,667 before this plan, plus the new ones). Fix anything that fails before going on.

Run: `.venv/bin/python manage.py makemigrations --check --dry-run`
Expected: "No changes detected".

- [ ] **Step 7: Push and open the pull request**

```bash
git push -u origin claude/hopeful-keller-lankio
```

Open a pull request against `main` titled "Leave terms on the contract, sent in the staff feed". The body says: what an HR admin now sees (the three places in Task 3), that the feed only gains `contracts`, that the GP full-time week is corrected from 9 to 8 sessions and FTE for GPs changes with it, that Practice HR's own leave is untouched, and that Shift Central's part follows in its own pull request. Merge commits are this repository's rule; do not merge until asked.

---

## Self-Review

- **Spec 4.1 (models):** Task 1. **4.2 (rules, `resolved`, audit, terms not dated):** Task 2, and the contract page's read-only fields in Task 3. **4.3 (screens):** Task 3. **4.4 (feed):** Task 4. **4.5 (8 sessions):** Task 1 and the docs in Task 5. **Section 10's Practice HR line and the shared sample file:** Tasks 2, 3 and 4.
- Names used across tasks: `leave_terms.check / resolved / describe / set_type_terms / set_contract_terms`, `admin_forms.steps_of`, `Contract.LeaveTerms`, related name `leave_steps` on both owners.
- Not in this plan, by the spec: anything in Shift Central; bank holiday terms; any change to the `absence` app.
