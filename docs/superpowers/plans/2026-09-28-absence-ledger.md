# Absence Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `absence` app's core: absence types, policies with service tiers, pots, the ledger, the accrual integral, costing from working patterns, bookings that write the ledger, automatic bank-holiday charging, and the nightly safety net. No pages yet beyond the admin; plan 3 adds requests, the calendar, year end, payroll and the API.

**Architecture:** Every balance is a sum of `LedgerEntry` rows; nothing stores a balance. `accrual.entitlement` and `costing.cost` are pure functions over the effective-dated `people` rows. `ledger.sync_entitlement` reconciles by writing a revision line for the difference. Signals in `absence` re-sync when a contract, employment, policy or tier changes, and `nightly.run` re-syncs everything as a safety net. All writes go through `absence/services/`.

**Tech Stack:** As plan 1. No new dependency in this plan.

**Spec:** `docs/superpowers/specs/2026-09-27-practice-hr-foundation-and-absence-design.md`, section 4, plus "Entitlement and revisions", "Bank holidays are charged automatically" and the nightly parts of sections 3 and 5.

## Global Constraints

- As plan 1: Django 5.2 LTS, Python 3.13, SQLite WAL, unfold, no build step, secrets from the environment, no network in tests, every write through `absence/services/`.
- `LedgerEntry` rows are never edited or deleted. Corrections are new lines.
- No stored balance field anywhere.
- Every service function that writes to the ledger runs in one transaction.
- Overlapping approved or requested absences for one employment are refused in the service.
- A policy missing for a pot-backed type in use is a `ValidationError` naming the missing policy, never a silent zero.
- Units are `Decimal`, two places. Rounding is to the policy's step (0.25 hour, 0.5 session), half up.

## Review Focus

1. **An absence whose range crosses the leave-year boundary** (28 March to 3 April on a 1 April year) draws on one pot or two? This plan refuses it with "Book the two leave years separately", pinned in Task 9. Plan 3's request form shows the message.
2. **A day with no pattern** (a booking before the first pattern version, or a weekend) must cost zero, not error. Task 8.
3. **A leap year** must accrue the same entitlement as a common year for a full-year employee (days cancel out) and must not crash on 29 February. Task 5.
4. **Two revisions for one cause** must not be written when `sync_entitlement` runs twice in a row; and a contract change that leaves the entitlement equal after rounding must write nothing. Task 6.
5. **A bank holiday auto-absence for a day the person does not work** must never be created, and a pattern change that stops them working Mondays must remove the Monday one with a cancellation line. Task 10.

---

## File structure

| Path | Responsibility |
|---|---|
| `absence/__init__.py`, `absence/apps.py` (connects signals in `ready()`) | App wiring. |
| `absence/models/types.py` | `AbsenceType`. |
| `absence/models/policy.py` | `Policy`, `PolicyTier`. |
| `absence/models/calendar.py` | `BankHoliday`, `ClosedDay`. |
| `absence/models/ledger.py` | `Pot`, `LedgerEntry`. |
| `absence/models/absence.py` | `Absence`, `KitDay`. |
| `absence/services/policies.py` | `policy_for`, `tier_extra_weeks`. |
| `absence/services/leave_year.py` | `bounds`. |
| `absence/services/rounding.py` | `round_to`. |
| `absence/services/accrual.py` | `entitlement(pot)`, `bank_holiday_entitlement(pot)`. |
| `absence/services/pots.py` | `for_day`, `open_pots`. |
| `absence/services/ledger.py` | `write`, `balance`, `sync_entitlement`. |
| `absence/services/costing.py` | `cost(absence)`, `halves_covered`. |
| `absence/services/bookings.py` | `request`, `approve`, `decline`, `cancel`, `record_sickness`, `overlaps`. |
| `absence/services/balances.py` | `summary(pot, today)`. |
| `absence/services/bank_holidays.py` | `sync_auto_absences`. |
| `absence/services/nightly.py` | `run(today)`. |
| `absence/signals.py` | Re-sync on people and policy changes. |
| `absence/admin.py` | Types, policies with tiers, bank holidays, closed days, pots (read-only) with ledger inline, absences (read-only list). |
| `absence/migrations/` | Schema plus seeds for types, bank holidays, and default policies. |
| `tests/test_absence_*.py` | One per task. `tests/factories.py` gains absence helpers. |

---

### Task 1: The absence app and AbsenceType

**Files:**
- Create: `absence/__init__.py`, `absence/apps.py`, `absence/models/__init__.py`, `absence/models/types.py`, `absence/migrations/0001_initial.py`, `absence/migrations/0002_seed_types.py`, `tests/test_absence_types.py`; Modify: `config/settings.py` (add `"absence"` to `INSTALLED_APPS`), `tests/factories.py`

**Interfaces:**
- Produces: `AbsenceType(name, code, paid, uses_pot, needs_approval, self_certified, calendar_label, payroll_reportable, health_sensitive, display_order, active)`; `AbsenceType.objects.get(code="AL")` etc. with codes `AL, BH, STUDY, TOIL, SICK, MAT, PAT, SPL, ADOPT, COMP, DEP, UNPAID, OTHER`; `tests.factories.absence_type(code)`.

- [ ] **Step 1: Write the failing test**

Append to `tests/factories.py`:

```python
def absence_type(code="AL"):
    from absence.models import AbsenceType
    return AbsenceType.objects.get(code=code)
```

`tests/test_absence_types.py`:

```python
from absence.models import AbsenceType


def test_seeded_types(db):
    codes = set(AbsenceType.objects.values_list("code", flat=True))
    assert {"AL", "BH", "STUDY", "TOIL", "SICK", "MAT", "PAT", "SPL", "ADOPT", "COMP", "DEP",
            "UNPAID", "OTHER"} <= codes
    al = AbsenceType.objects.get(code="AL")
    assert al.uses_pot and al.needs_approval and al.paid and al.calendar_label == "Leave"
    sick = AbsenceType.objects.get(code="SICK")
    assert not sick.uses_pot and not sick.needs_approval and sick.self_certified
    assert sick.health_sensitive and sick.calendar_label == "Sick"
    dep = AbsenceType.objects.get(code="DEP")
    assert not dep.paid and not dep.uses_pot and not dep.needs_approval
```

- [ ] **Step 2: Run to see it fail**

Run: `python -m pytest tests/test_absence_types.py -q`
Expected: ImportError `absence`.

- [ ] **Step 3: Implement**

`absence/apps.py`:

```python
from django.apps import AppConfig


class AbsenceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "absence"

    def ready(self):
        from . import signals  # noqa: F401
```

`absence/signals.py` (empty for now; Task 7 fills it):

```python
"""Re-sync entitlements when the rows they are computed from change."""
```

`absence/models/types.py`:

```python
from django.db import models


class AbsenceType(models.Model):
    """Configurable. The flags decide the workflow; nothing in the code
    tests a type's name."""
    name = models.CharField(max_length=40, unique=True)
    code = models.CharField(max_length=8, unique=True)
    paid = models.BooleanField(default=True)
    uses_pot = models.BooleanField(
        default=False, help_text="Draws on an allowance. Needs a policy per contract type.")
    needs_approval = models.BooleanField(default=True)
    self_certified = models.BooleanField(
        default=False, help_text="The employee records it themselves, after the fact.")
    calendar_label = models.CharField(
        max_length=20, default="Away",
        help_text="What colleagues see on the calendar: Leave, Sick, Away.")
    payroll_reportable = models.BooleanField(default=False)
    health_sensitive = models.BooleanField(
        default=False, help_text="Category and dates are restricted to HR admins and the line manager.")
    display_order = models.PositiveIntegerField(default=100)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name
```

`absence/models/__init__.py` exports `AbsenceType`. Add `"absence"` after `"people"` in `INSTALLED_APPS`.

`absence/migrations/0002_seed_types.py` (after `makemigrations absence` writes `0001`):

```python
from django.db import migrations

# code, name, paid, uses_pot, needs_approval, self_certified, label, payroll, health, order
SEED = [
    ("AL", "Annual leave", True, True, True, False, "Leave", False, False, 10),
    ("BH", "Bank holiday", True, True, False, False, "Leave", False, False, 20),
    ("STUDY", "Study leave", True, True, True, False, "Away", False, False, 30),
    ("TOIL", "TOIL", True, True, True, False, "Leave", True, False, 40),
    ("SICK", "Sickness", True, False, False, True, "Sick", True, True, 50),
    ("MAT", "Maternity leave", True, False, True, False, "Away", True, False, 60),
    ("PAT", "Paternity leave", True, False, True, False, "Away", True, False, 70),
    ("SPL", "Shared parental leave", True, False, True, False, "Away", True, False, 80),
    ("ADOPT", "Adoption leave", True, False, True, False, "Away", True, False, 90),
    ("COMP", "Compassionate leave", True, False, True, False, "Away", False, False, 100),
    ("DEP", "Dependants leave", False, False, False, True, "Away", True, False, 110),
    ("UNPAID", "Unpaid leave", False, False, True, False, "Away", True, False, 120),
    ("OTHER", "Other", True, False, True, False, "Away", False, False, 130),
]


def seed(apps, schema_editor):
    AbsenceType = apps.get_model("absence", "AbsenceType")
    for code, name, paid, pot, appr, selfc, label, payroll, health, order in SEED:
        AbsenceType.objects.get_or_create(code=code, defaults=dict(
            name=name, paid=paid, uses_pot=pot, needs_approval=appr, self_certified=selfc,
            calendar_label=label, payroll_reportable=payroll, health_sensitive=health,
            display_order=order))


class Migration(migrations.Migration):
    dependencies = [("absence", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
```

- [ ] **Step 4: Migrate, run, commit**

Run: `DEBUG=1 python manage.py makemigrations absence && python -m pytest tests/test_absence_types.py -q`
Expected: 1 passed.

```bash
git add -A
git commit -m "feat: absence app and seeded absence types"
```

---

### Task 2: Policy, PolicyTier, and policy lookup

**Files:**
- Create: `absence/models/policy.py`, `absence/services/__init__.py`, `absence/services/policies.py`, `absence/migrations/0004_seed_policies.py`, `tests/test_absence_policies.py`; Modify: `absence/models/__init__.py`, `tests/factories.py`

**Interfaces:**
- Produces: `Policy(contract_type, absence_type, effective_from, effective_to, weeks_per_year, leave_year_basis, year_start_month, year_start_day, carry_over_max_weeks, carry_over_expires_after_days, rounding, bank_holiday_handling, toil_expires_after_days)` with `Basis.FIXED/ANNIVERSARY` and `BankHolidays.CLOSED_NOT_CHARGED/PRO_RATA_POT/INCLUDED_IN_ANNUAL`; `PolicyTier(policy, after_years, extra_weeks)`; `policies.policy_for(employment, absence_type, day) -> Policy` raising `ValidationError` when none; `policies.tier_extra_weeks(policy, employment, day) -> Decimal`; `tests.factories.make_policy(ctype, code="AL", **kw)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/factories.py`:

```python
def make_policy(ctype, code="AL", **kw):
    from absence.models import Policy
    kw.setdefault("weeks_per_year", Decimal("5.6"))
    kw.setdefault("effective_from", date(2020, 1, 1))
    kw.setdefault("rounding", Decimal("0.25") if ctype.unit == "hours" else Decimal("0.5"))
    return Policy.objects.create(contract_type=ctype, absence_type=absence_type(code), **kw)
```

`tests/test_absence_policies.py`:

```python
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from absence.models import PolicyTier
from absence.services import policies
from tests.factories import (absence_type, make_contract, make_contract_type, make_employment,
                             make_policy)


def test_policy_for_reads_the_contract_type_on_the_day(db):
    emp = make_employment(start=date(2026, 4, 1))
    ct = make_contract_type()
    make_contract(emp, ct)
    p = make_policy(ct)
    assert policies.policy_for(emp, absence_type("AL"), date(2026, 6, 1)) == p


def test_missing_policy_names_it(db):
    emp = make_employment(start=date(2026, 4, 1))
    make_contract(emp, make_contract_type("HCA"))
    with pytest.raises(ValidationError) as e:
        policies.policy_for(emp, absence_type("AL"), date(2026, 6, 1))
    assert "HCA" in str(e.value) and "Annual leave" in str(e.value)


def test_no_contract_is_also_an_error(db):
    emp = make_employment()
    with pytest.raises(ValidationError):
        policies.policy_for(emp, absence_type("AL"), emp.start_date)


def test_effective_dated_policies(db):
    emp = make_employment(start=date(2020, 1, 1))
    ct = make_contract_type()
    make_contract(emp, ct)
    old = make_policy(ct, effective_from=date(2020, 1, 1), effective_to=date(2026, 3, 31))
    new = make_policy(ct, effective_from=date(2026, 4, 1), weeks_per_year=Decimal("6"))
    assert policies.policy_for(emp, absence_type("AL"), date(2026, 3, 31)) == old
    assert policies.policy_for(emp, absence_type("AL"), date(2026, 4, 1)) == new


def test_tier_extra_weeks_highest_reached(db):
    emp = make_employment(start=date(2026, 4, 1), continuous_service_date=date(2019, 10, 1))
    ct = make_contract_type()
    p = make_policy(ct)
    PolicyTier.objects.create(policy=p, after_years=5, extra_weeks=Decimal("1"))
    PolicyTier.objects.create(policy=p, after_years=10, extra_weeks=Decimal("2"))
    assert policies.tier_extra_weeks(p, emp, date(2024, 9, 30)) == Decimal("0")
    assert policies.tier_extra_weeks(p, emp, date(2024, 10, 1)) == Decimal("1")
    assert policies.tier_extra_weeks(p, emp, date(2029, 10, 1)) == Decimal("2")
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_absence_policies.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement**

`absence/models/policy.py`:

```python
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from people.models import ContractType

from .types import AbsenceType


class Policy(models.Model):
    """The allowance rules as data, per contract type and pot-backed type."""
    class Basis(models.TextChoices):
        FIXED = "fixed", "Fixed date"
        ANNIVERSARY = "anniversary", "Anniversary of start"

    class BankHolidays(models.TextChoices):
        CLOSED_NOT_CHARGED = "closed", "Practice closed, not charged"
        PRO_RATA_POT = "pot", "Pro-rated bank holiday pot"
        INCLUDED_IN_ANNUAL = "annual", "Included in annual leave"

    contract_type = models.ForeignKey(ContractType, on_delete=models.PROTECT, related_name="policies")
    absence_type = models.ForeignKey(AbsenceType, on_delete=models.PROTECT, related_name="policies",
                                     limit_choices_to={"uses_pot": True})
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    weeks_per_year = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal("5.6"),
        help_text="Entitlement in weeks; multiplied by the contracted weekly amount.")
    leave_year_basis = models.CharField(max_length=11, choices=Basis.choices, default=Basis.FIXED)
    year_start_month = models.PositiveSmallIntegerField(default=4)
    year_start_day = models.PositiveSmallIntegerField(default=1)
    carry_over_max_weeks = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    carry_over_expires_after_days = models.PositiveSmallIntegerField(null=True, blank=True)
    rounding = models.DecimalField(
        max_digits=3, decimal_places=2, default=Decimal("0.25"),
        help_text="Entitlements and costs are rounded to this step: 0.25 hour, 0.5 session.")
    bank_holiday_handling = models.CharField(
        max_length=6, choices=BankHolidays.choices, default=BankHolidays.CLOSED_NOT_CHARGED)
    toil_expires_after_days = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "policies"
        ordering = ["contract_type", "absence_type", "-effective_from"]

    def __str__(self):
        return f"{self.contract_type} / {self.absence_type} from {self.effective_from:%d %b %Y}"

    def clean(self):
        super().clean()
        if self.absence_type_id and not self.absence_type.uses_pot:
            raise ValidationError({"absence_type": "Only pot-backed types have a policy."})
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "Ends before it starts."})

    def is_active_on(self, day):
        return self.effective_from <= day and (self.effective_to is None or day <= self.effective_to)


class PolicyTier(models.Model):
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name="tiers")
    after_years = models.PositiveSmallIntegerField()
    extra_weeks = models.DecimalField(max_digits=4, decimal_places=2)

    class Meta:
        ordering = ["after_years"]
        constraints = [models.UniqueConstraint(fields=["policy", "after_years"], name="one_tier_per_years")]

    def __str__(self):
        return f"+{self.extra_weeks} weeks after {self.after_years} years"
```

Export `Policy`, `PolicyTier`.

`absence/services/policies.py`:

```python
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Q

from absence.models import Policy
from people.services import contracts, employments


def policy_for(employment, absence_type, day):
    contract = contracts.active_on(employment, day).first()
    if contract is None:
        raise ValidationError(f"{employment.employee} has no contract on {day:%d %b %Y}.")
    ct = contract.contract_type
    policy = (Policy.objects.filter(contract_type=ct, absence_type=absence_type, effective_from__lte=day)
              .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=day))
              .order_by("-effective_from").first())
    if policy is None:
        raise ValidationError(f"No {absence_type} policy for {ct} on {day:%d %b %Y}. "
                              f"Add one under Absence › Policies.")
    return policy


def tier_extra_weeks(policy, employment, day):
    years = employments.service_years(employment, day)
    extra = Decimal("0")
    for tier in policy.tiers.all():
        if years >= tier.after_years:
            extra = tier.extra_weeks
    return extra
```

`absence/migrations/0004_seed_policies.py` (after the `0003` schema migration for Policy): one `AL` policy per seeded contract type, effective 2020-01-01, 5.6 weeks, fixed 1 April year, rounding 0.5 for sessions types and 0.25 for hours types, `bank_holiday_handling="closed"` for sessions types and `"pot"` for hours types. Written as a `RunPython` in the same shape as `0002_seed_types.py`, looking up `people.ContractType` and `absence.AbsenceType` through `apps.get_model`.

- [ ] **Step 4: Migrate, run, commit**

Run: `DEBUG=1 python manage.py makemigrations absence && python -m pytest tests/test_absence_policies.py -q`
Expected: 5 passed.

```bash
git add -A
git commit -m "feat: allowance policies with service tiers, and the policy lookup"
```

---

### Task 3: Leave-year bounds and rounding

**Files:**
- Create: `absence/services/leave_year.py`, `absence/services/rounding.py`, `tests/test_absence_leave_year.py`

**Interfaces:**
- Produces: `leave_year.bounds(policy, employment, day) -> (start, end)`; `rounding.round_to(value, step) -> Decimal`.

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_leave_year.py`:

```python
from datetime import date
from decimal import Decimal

from absence.services import leave_year, rounding
from tests.factories import make_contract_type, make_employment, make_policy


def test_fixed_year_from_first_april(db):
    p = make_policy(make_contract_type())
    emp = make_employment(start=date(2020, 1, 1))
    assert leave_year.bounds(p, emp, date(2026, 3, 31)) == (date(2025, 4, 1), date(2026, 3, 31))
    assert leave_year.bounds(p, emp, date(2026, 4, 1)) == (date(2026, 4, 1), date(2027, 3, 31))


def test_anniversary_year(db):
    p = make_policy(make_contract_type(), leave_year_basis="anniversary")
    emp = make_employment(start=date(2025, 7, 14))
    assert leave_year.bounds(p, emp, date(2026, 7, 13)) == (date(2025, 7, 14), date(2026, 7, 13))
    assert leave_year.bounds(p, emp, date(2026, 7, 14)) == (date(2026, 7, 14), date(2027, 7, 13))


def test_anniversary_on_29_feb(db):
    p = make_policy(make_contract_type(), leave_year_basis="anniversary")
    emp = make_employment(start=date(2024, 2, 29))
    assert leave_year.bounds(p, emp, date(2025, 6, 1)) == (date(2025, 2, 28), date(2026, 2, 27))


def test_round_to():
    assert rounding.round_to(Decimal("104.712"), Decimal("0.25")) == Decimal("104.75")
    assert rounding.round_to(Decimal("184.109"), Decimal("0.25")) == Decimal("184.00")
    assert rounding.round_to(Decimal("47.75"), Decimal("0.5")) == Decimal("48.0")
    assert rounding.round_to(Decimal("47.74"), Decimal("0.5")) == Decimal("47.5")
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_absence_leave_year.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement**

`absence/services/rounding.py`:

```python
from decimal import ROUND_HALF_UP, Decimal


def round_to(value, step):
    """Nearest multiple of step, half up, keeping step's places."""
    steps = (Decimal(value) / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return (steps * step).quantize(step)
```

`absence/services/leave_year.py`:

```python
from datetime import date, timedelta

from absence.models import Policy


def _safe_date(year, month, day):
    try:
        return date(year, month, day)
    except ValueError:            # 29 February in a common year
        return date(year, month, 28)


def bounds(policy, employment, day):
    """The leave year containing `day`: (first day, last day)."""
    if policy.leave_year_basis == Policy.Basis.ANNIVERSARY:
        month, dom = employment.start_date.month, employment.start_date.day
    else:
        month, dom = policy.year_start_month, policy.year_start_day
    start = _safe_date(day.year, month, dom)
    if start > day:
        start = _safe_date(day.year - 1, month, dom)
    end = _safe_date(start.year + 1, month, dom) - timedelta(days=1)
    return start, end
```

- [ ] **Step 4: Run and commit**

Run: `python -m pytest tests/test_absence_leave_year.py -q`
Expected: 4 passed.

```bash
git add -A
git commit -m "feat: leave-year bounds, fixed or anniversary, and step rounding"
```

---

### Task 4: Bank holidays, closed days, Pot and LedgerEntry

**Files:**
- Create: `absence/models/calendar.py`, `absence/models/ledger.py`, `absence/migrations/000N_seed_bank_holidays.py`, `absence/services/pots.py`, `absence/services/ledger.py` (write and balance only; sync in Task 6), `tests/test_absence_ledger.py`; Modify: `absence/models/__init__.py`, `tests/factories.py`

**Interfaces:**
- Produces: `BankHoliday(date, name, nation)`, `ClosedDay(date, reason)`; `Pot(employment, absence_type, year_start, year_end, unit)`; `LedgerEntry(pot, date, kind, units, absence, note, actor, created_at)` with `Kind` values `ENTITLEMENT, REVISION, CARRY_IN, EXPIRY, BOOKING, CANCELLATION, TOIL_EARNED, TOIL_TAKEN, ADJUSTMENT`; `pots.for_day(employment, absence_type, day) -> Pot` (creates, sets `unit` from the contract); `pots.open_pots(today) -> QuerySet[Pot]` (year_end >= today); `ledger.write(pot, kind, units, actor=None, absence=None, note="", date=None) -> LedgerEntry`; `ledger.balance(pot) -> Decimal`; `tests.factories.make_pot(employment, code="AL", day=None)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/factories.py`:

```python
def make_pot(employment, code="AL", day=None):
    from absence.services import pots
    return pots.for_day(employment, absence_type(code), day or employment.start_date)


def hours_employee(start=date(2026, 4, 1), amount=Decimal("37.5"), **kw):
    """A Reception employee with a contract, an AL policy and a Mon-Fri
    3.75/3.75 pattern. Returns the employment."""
    emp = make_employment(start=start, **kw)
    ct = make_contract_type()
    make_contract(emp, ct, amount=amount)
    if not ct.policies.exists():
        make_policy(ct)
    make_pattern(emp)
    return emp
```

`tests/test_absence_ledger.py`:

```python
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from absence.models import BankHoliday, LedgerEntry, Pot
from absence.services import ledger, pots
from tests.factories import absence_type, hours_employee, make_employment


def test_seeded_bank_holidays(db):
    assert BankHoliday.objects.filter(date=date(2026, 12, 28), nation="EW").exists()
    assert BankHoliday.objects.filter(date=date(2027, 3, 26)).exists()


def test_for_day_creates_once_with_unit(db):
    emp = hours_employee()
    pot = pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    again = pots.for_day(emp, absence_type("AL"), date(2027, 3, 31))
    assert pot == again
    assert (pot.year_start, pot.year_end, pot.unit) == (date(2026, 4, 1), date(2027, 3, 31), "hours")
    assert Pot.objects.count() == 1


def test_for_day_needs_a_contract(db):
    emp = make_employment()
    with pytest.raises(ValidationError):
        pots.for_day(emp, absence_type("AL"), emp.start_date)


def test_write_and_balance(db, hr_admin):
    pot = pots.for_day(hours_employee(), absence_type("AL"), date(2026, 6, 1))
    ledger.write(pot, LedgerEntry.Kind.ENTITLEMENT, Decimal("210"), hr_admin, note="year")
    ledger.write(pot, LedgerEntry.Kind.BOOKING, Decimal("-7.5"))
    assert ledger.balance(pot) == Decimal("202.5")
    assert pot.entries.count() == 2


def test_ledger_rows_are_immutable(db):
    pot = pots.for_day(hours_employee(), absence_type("AL"), date(2026, 6, 1))
    row = ledger.write(pot, LedgerEntry.Kind.ENTITLEMENT, Decimal("1"))
    row.units = Decimal("2")
    with pytest.raises(ValidationError):
        row.save()
    with pytest.raises(ValidationError):
        row.delete()


def test_open_pots(db):
    emp = hours_employee(start=date(2025, 4, 1))
    pots.for_day(emp, absence_type("AL"), date(2025, 6, 1))
    current = pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    assert list(pots.open_pots(date(2026, 6, 1))) == [current]
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_absence_ledger.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement**

`absence/models/calendar.py`:

```python
from django.db import models


class BankHoliday(models.Model):
    date = models.DateField()
    name = models.CharField(max_length=60)
    nation = models.CharField(max_length=2, default="EW", help_text="EW, S or NI")

    class Meta:
        ordering = ["date"]
        constraints = [models.UniqueConstraint(fields=["date", "nation"], name="one_holiday_per_day")]

    def __str__(self):
        return f"{self.name} {self.date:%d %b %Y}"


class ClosedDay(models.Model):
    """A practice closure that is not a bank holiday. Never charged."""
    date = models.DateField(unique=True)
    reason = models.CharField(max_length=120)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.reason} {self.date:%d %b %Y}"
```

`absence/models/ledger.py`:

```python
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from people.models import Employment

from .types import AbsenceType


class Pot(models.Model):
    """One employment's allowance for one type and one leave year. No
    balance field: the balance is the sum of its entries."""
    employment = models.ForeignKey(Employment, on_delete=models.PROTECT, related_name="pots")
    absence_type = models.ForeignKey(AbsenceType, on_delete=models.PROTECT, related_name="pots")
    year_start = models.DateField()
    year_end = models.DateField()
    unit = models.CharField(max_length=8)

    class Meta:
        ordering = ["-year_start"]
        constraints = [models.UniqueConstraint(
            fields=["employment", "absence_type", "year_start"], name="one_pot_per_year")]

    def __str__(self):
        return f"{self.employment.employee} {self.absence_type} {self.year_start:%Y}/{self.year_end:%y}"


class LedgerEntry(models.Model):
    """The only thing that changes a pot. Never edited or deleted."""
    class Kind(models.TextChoices):
        ENTITLEMENT = "entitlement", "Entitlement"
        REVISION = "revision", "Entitlement revised"
        CARRY_IN = "carry_in", "Carried in"
        EXPIRY = "expiry", "Expired"
        BOOKING = "booking", "Booked"
        CANCELLATION = "cancellation", "Cancelled"
        TOIL_EARNED = "toil_earned", "TOIL earned"
        TOIL_TAKEN = "toil_taken", "TOIL taken"
        ADJUSTMENT = "adjustment", "Adjustment"

    pot = models.ForeignKey(Pot, on_delete=models.PROTECT, related_name="entries")
    date = models.DateField()
    kind = models.CharField(max_length=12, choices=Kind.choices)
    units = models.DecimalField(max_digits=7, decimal_places=2)
    absence = models.ForeignKey("absence.Absence", null=True, blank=True,
                                on_delete=models.PROTECT, related_name="ledger_entries")
    note = models.CharField(max_length=200, blank=True, default="")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "id"]
        verbose_name_plural = "ledger entries"

    def __str__(self):
        return f"{self.date:%d %b %Y} {self.get_kind_display()} {self.units:+}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("Ledger entries are never edited; write a new line.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Ledger entries are never deleted; write a new line.")
```

The `absence` FK is a string reference; Task 7 creates the model. Until then `makemigrations` will complain about the missing model, so **in this task** also create a minimal `absence/models/absence.py` with the fields Task 7 fills in later? No: keep one migration per task. Instead, in this task declare the FK as `models.ForeignKey("absence.Absence", …)` and create `absence/models/absence.py` now with the full `Absence` and `KitDay` models from Task 7's Step 3 (they are data only). Task 7 then adds only the costing service and tests. Export everything from `absence/models/__init__.py`.

`absence/services/pots.py`:

```python
from datetime import date

from django.db import transaction

from absence.models import Pot
from absence.services import leave_year, policies
from people.services import contracts


@transaction.atomic
def for_day(employment, absence_type, day):
    """The pot for the leave year containing `day`, created if needed.
    Raises ValidationError when there is no contract or no policy."""
    policy = policies.policy_for(employment, absence_type, day)
    start, end = leave_year.bounds(policy, employment, day)
    pot, _ = Pot.objects.get_or_create(
        employment=employment, absence_type=absence_type, year_start=start,
        defaults={"year_end": end, "unit": contracts.unit(employment, day)})
    return pot


def open_pots(today=None):
    today = today or date.today()
    return Pot.objects.filter(year_end__gte=today).select_related("employment__employee", "absence_type")
```

`absence/services/ledger.py` (Task 6 appends `sync_entitlement`):

```python
from datetime import date as _date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from absence.models import LedgerEntry


@transaction.atomic
def write(pot, kind, units, actor=None, absence=None, note="", date=None):
    return LedgerEntry.objects.create(
        pot=pot, date=date or _date.today(), kind=kind, units=Decimal(units),
        absence=absence, note=note[:200], actor=actor)


def balance(pot):
    return pot.entries.aggregate(t=Sum("units"))["t"] or Decimal("0")
```

`absence/migrations/000N_seed_bank_holidays.py` seeds England and Wales for 2026 to 2028, from the gov.uk list, checked against gov.uk before release:

```python
from datetime import date

from django.db import migrations

EW = [
    (date(2026, 1, 1), "New Year's Day"), (date(2026, 4, 3), "Good Friday"),
    (date(2026, 4, 6), "Easter Monday"), (date(2026, 5, 4), "Early May bank holiday"),
    (date(2026, 5, 25), "Spring bank holiday"), (date(2026, 8, 31), "Summer bank holiday"),
    (date(2026, 12, 25), "Christmas Day"), (date(2026, 12, 28), "Boxing Day (substitute)"),
    (date(2027, 1, 1), "New Year's Day"), (date(2027, 3, 26), "Good Friday"),
    (date(2027, 3, 29), "Easter Monday"), (date(2027, 5, 3), "Early May bank holiday"),
    (date(2027, 5, 31), "Spring bank holiday"), (date(2027, 8, 30), "Summer bank holiday"),
    (date(2027, 12, 27), "Christmas Day (substitute)"), (date(2027, 12, 28), "Boxing Day (substitute)"),
    (date(2028, 1, 3), "New Year's Day (substitute)"), (date(2028, 4, 14), "Good Friday"),
    (date(2028, 4, 17), "Easter Monday"), (date(2028, 5, 1), "Early May bank holiday"),
    (date(2028, 5, 29), "Spring bank holiday"), (date(2028, 8, 28), "Summer bank holiday"),
    (date(2028, 12, 25), "Christmas Day"), (date(2028, 12, 26), "Boxing Day"),
]


def seed(apps, schema_editor):
    BankHoliday = apps.get_model("absence", "BankHoliday")
    for d, name in EW:
        BankHoliday.objects.get_or_create(date=d, nation="EW", defaults={"name": name})


class Migration(migrations.Migration):
    dependencies = [("absence", "<previous>")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
```

- [ ] **Step 4: Migrate, run, commit**

Run: `DEBUG=1 python manage.py makemigrations absence && python -m pytest tests/test_absence_ledger.py -q`
Expected: 6 passed.

```bash
git add -A
git commit -m "feat: pots, the immutable ledger, bank holidays and closed days"
```

---

### Task 5: The accrual integral

**Files:**
- Create: `absence/services/accrual.py`, `tests/test_absence_accrual.py`

**Interfaces:**
- Produces: `accrual.entitlement(pot) -> Decimal` (rounded to the policy step); `accrual.bank_holiday_entitlement(pot) -> Decimal`; `accrual.daily_rates(pot) -> list[tuple[date, Decimal]]` (unrounded, for the balances page's explanation).

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_accrual.py`:

```python
from datetime import date
from decimal import Decimal

import pytest

from absence.models import PolicyTier
from absence.services import accrual, pots
from people.services import contracts
from tests.factories import (absence_type, hours_employee, make_contract, make_contract_type,
                             make_employment, make_pattern, make_policy)

D = Decimal
Y = date(2026, 6, 1)   # any day in the 2026/27 fixed year


def al(emp):
    return pots.for_day(emp, absence_type("AL"), Y)


@pytest.mark.parametrize("amount,expected", [
    (D("37.5"), D("210.00")),      # full-timer: 5.6 weeks × 37.5
    (D("18.75"), D("105.00")),     # part-timer
])
def test_full_year(db, amount, expected):
    assert accrual.entitlement(al(hours_employee(amount=amount))) == expected


def test_mid_year_starter(db):
    emp = hours_employee(start=date(2026, 10, 1))
    assert accrual.entitlement(al(emp)) == D("104.75")      # 210 × 182/365 = 104.71


def test_mid_year_leaver(db):
    emp = hours_employee(end_date=date(2026, 9, 30), leaving_reason="resigned")
    assert accrual.entitlement(al(emp)) == D("105.25")      # 210 × 183/365 = 105.29


def test_tier_step_in_month_seven(db):
    emp = hours_employee(continuous_service_date=date(2021, 10, 1))
    policy = emp.contracts.first().contract_type.policies.get()
    PolicyTier.objects.create(policy=policy, after_years=5, extra_weeks=D("1"))
    # 183 days at 5.6 weeks, 182 at 6.6: 37.5 × (5.6×183 + 6.6×182) / 365 = 228.70
    assert accrual.entitlement(al(emp)) == D("228.75")


def test_fixed_term_ending_month_nine(db, hr_admin):
    emp = hours_employee(amount=D("18.75"))
    ct = make_contract_type()
    contracts.add(hr_admin, emp, ct, D("18.75"), date(2026, 4, 1), basis="fixed_term",
                  to_date=date(2026, 12, 31))
    # 275 days at 37.5, 90 at 18.75: 5.6 × (37.5×275 + 18.75×90) / 365 = 184.11
    assert accrual.entitlement(al(emp)) == D("184.00")


def test_sessions_unit(db):
    emp = make_employment(start=date(2026, 4, 1))
    ct = make_contract_type("Salaried GP", "sessions", D("9"))
    make_contract(emp, ct, amount=D("8"))
    make_policy(ct, weeks_per_year=D("6"))
    make_pattern(emp, {d: (D("1"), D("1")) for d in range(4)})
    assert accrual.entitlement(al(emp)) == D("48.0")


def test_leap_year_same_as_common(db):
    emp = hours_employee(start=date(2023, 4, 1))
    pot_leap = pots.for_day(emp, absence_type("AL"), date(2024, 2, 29))   # 2023/24 has 366 days
    pot_common = pots.for_day(emp, absence_type("AL"), date(2025, 6, 1))
    assert accrual.entitlement(pot_leap) == accrual.entitlement(pot_common) == D("210.00")


def test_bank_holiday_pot_pro_rata(db):
    emp = hours_employee(amount=D("18.75"))
    policy = emp.contracts.first().contract_type.policies.get()
    make_policy(policy.contract_type, "BH", bank_holiday_handling="pot")
    pot = pots.for_day(emp, absence_type("BH"), Y)
    # 10 bank holidays fall in 2026/27 (both Easters) → 10/5 weeks × 18.75 = 37.5
    assert accrual.bank_holiday_entitlement(pot) == D("37.50")
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_absence_accrual.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement**

`absence/services/accrual.py`:

```python
"""The entitlement of a pot, as a day-by-day integral over its leave year.
Pure: reads people rows and policies, writes nothing."""

from datetime import timedelta
from decimal import Decimal

from absence.models import BankHoliday
from absence.services import policies, rounding
from people.services import contracts


def _days(pot):
    d = pot.year_start
    while d <= pot.year_end:
        yield d
        d += timedelta(days=1)


def _policy(pot, day):
    return policies.policy_for(pot.employment, pot.absence_type, day)


def daily_rates(pot, weeks_for_day=None):
    """[(day, unrounded units accrued that day)]. weeks_for_day(policy, day)
    overrides the weeks figure; bank_holiday_entitlement uses that."""
    employment = pot.employment
    days_in_year = (pot.year_end - pot.year_start).days + 1
    out = []
    for day in _days(pot):
        if not employment.is_active_on(day):
            out.append((day, Decimal("0")))
            continue
        weekly = contracts.contracted_amount(employment, day)
        if not weekly:
            out.append((day, Decimal("0")))
            continue
        policy = _policy(pot, day)
        if weeks_for_day is not None:
            weeks = weeks_for_day(policy, day)
        else:
            weeks = policy.weeks_per_year + policies.tier_extra_weeks(policy, employment, day)
        out.append((day, weeks * weekly / days_in_year))
    return out


def _rounded_total(pot, rates):
    total = sum((r for _, r in rates), Decimal("0"))
    first_active = next((d for d in _days(pot) if pot.employment.is_active_on(d)
                         and contracts.contracted_amount(pot.employment, d)), None)
    if first_active is None:
        return Decimal("0")
    return rounding.round_to(total, _policy(pot, first_active).rounding)


def entitlement(pot):
    return _rounded_total(pot, daily_rates(pot))


def bank_holiday_entitlement(pot):
    """Under pro_rata_pot: the year's bank holidays divided by five, as weeks."""
    n = BankHoliday.objects.filter(date__range=(pot.year_start, pot.year_end), nation="EW").count()
    weeks = Decimal(n) / Decimal("5")
    return _rounded_total(pot, daily_rates(pot, weeks_for_day=lambda policy, day: weeks))
```

Performance note for the implementer: `contracted_amount` and `policy_for` each issue a query per day, so a full year is about 1,100 queries. Acceptable for the nightly job and for a single page; plan 3's balances page calls `entitlement` once per pot. If a test in plan 3 pins query counts, prefetch the employment's contracts and policies into dictionaries here rather than caching across calls.

- [ ] **Step 4: Run and commit**

Run: `python -m pytest tests/test_absence_accrual.py -q`
Expected: 9 passed.

```bash
git add -A
git commit -m "feat: the accrual integral: tiers, pro-rating, concurrent contracts, leap years"
```

---

### Task 6: Entitlement sync and revisions

**Files:**
- Modify: `absence/services/ledger.py`; Create: `tests/test_absence_sync.py`

**Interfaces:**
- Produces: `ledger.sync_entitlement(pot, actor=None, cause="") -> LedgerEntry | None`; `ledger.entitlement_lines_total(pot) -> Decimal`.

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_sync.py`:

```python
from datetime import date
from decimal import Decimal

from absence.models import LedgerEntry
from absence.services import ledger, pots
from people.services import contracts
from tests.factories import absence_type, hours_employee, make_contract_type

D = Decimal


def test_first_sync_writes_entitlement(db):
    pot = pots.for_day(hours_employee(), absence_type("AL"), date(2026, 6, 1))
    row = ledger.sync_entitlement(pot, cause="pot created")
    assert row.kind == LedgerEntry.Kind.ENTITLEMENT and row.units == D("210.00")
    assert row.note == "pot created"


def test_second_sync_is_a_no_op(db):
    pot = pots.for_day(hours_employee(), absence_type("AL"), date(2026, 6, 1))
    ledger.sync_entitlement(pot)
    assert ledger.sync_entitlement(pot) is None
    assert pot.entries.count() == 1


def test_contract_change_writes_one_revision(db, hr_admin):
    emp = hours_employee(amount=D("18.75"))
    pot = pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    ledger.sync_entitlement(pot)
    contracts.add(hr_admin, emp, make_contract_type(), D("18.75"), date(2026, 10, 1))
    row = ledger.sync_entitlement(pot, hr_admin, cause="contract added 1 Oct")
    assert row.kind == LedgerEntry.Kind.REVISION
    # 105 + 5.6 × 18.75 × 182/365 = 105 + 52.36 → 157.25 total; revision is the difference
    assert ledger.entitlement_lines_total(pot) == D("157.25")
    assert row.units == D("52.25") and row.note == "contract added 1 Oct"


def test_change_that_rounds_to_nothing_writes_nothing(db, hr_admin):
    emp = hours_employee()
    pot = pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    ledger.sync_entitlement(pot)
    contracts.add(hr_admin, emp, make_contract_type(), D("0.01"), date(2027, 3, 31))
    assert ledger.sync_entitlement(pot) is None
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_absence_sync.py -q`
Expected: AttributeError `sync_entitlement`.

- [ ] **Step 3: Implement**

Append to `absence/services/ledger.py`:

```python
def entitlement_lines_total(pot):
    kinds = (LedgerEntry.Kind.ENTITLEMENT, LedgerEntry.Kind.REVISION)
    return pot.entries.filter(kind__in=kinds).aggregate(t=Sum("units"))["t"] or Decimal("0")


@transaction.atomic
def sync_entitlement(pot, actor=None, cause=""):
    """Bring the entitlement lines up to accrual.entitlement(pot). Writes
    one line for the difference, or nothing. Idempotent."""
    from absence.services import accrual
    if pot.absence_type.code == "BH":
        expected = accrual.bank_holiday_entitlement(pot)
    else:
        expected = accrual.entitlement(pot)
    existing = entitlement_lines_total(pot)
    delta = expected - existing
    if delta == 0:
        return None
    kind = LedgerEntry.Kind.ENTITLEMENT if existing == 0 and not pot.entries.filter(
        kind=LedgerEntry.Kind.ENTITLEMENT).exists() else LedgerEntry.Kind.REVISION
    return write(pot, kind, delta, actor, note=cause or "entitlement recalculated",
                 date=pot.year_start if kind == LedgerEntry.Kind.ENTITLEMENT else None)
```

- [ ] **Step 4: Run and commit**

Run: `python -m pytest tests/test_absence_sync.py -q`
Expected: 4 passed.

```bash
git add -A
git commit -m "feat: sync_entitlement writes the difference as a revision line"
```

---

### Task 7: Re-sync on change: signals

**Files:**
- Modify: `absence/signals.py`; Create: `tests/test_absence_signals.py`

**Interfaces:**
- Produces: `post_save` handlers on `people.Contract`, `people.Employment`, `absence.Policy`, `absence.PolicyTier` that call `ledger.sync_entitlement` for every open pot affected, with a cause string naming the change; `signals.resync_employment(employment, cause)`, `signals.resync_contract_type(contract_type, cause)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_signals.py`:

```python
from datetime import date
from decimal import Decimal

from absence.models import LedgerEntry, PolicyTier
from absence.services import ledger, pots
from people.services import contracts, employments
from tests.factories import absence_type, hours_employee, make_contract_type

D = Decimal


def test_contract_add_resyncs_open_pot(db, hr_admin):
    emp = hours_employee(amount=D("18.75"))
    pot = pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    ledger.sync_entitlement(pot)
    contracts.add(hr_admin, emp, make_contract_type(), D("18.75"), date(2026, 10, 1))
    row = pot.entries.filter(kind=LedgerEntry.Kind.REVISION).get()
    assert "contract" in row.note.lower()


def test_employment_end_resyncs(db, hr_admin):
    emp = hours_employee()
    pot = pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    ledger.sync_entitlement(pot)
    employments.end(hr_admin, emp, date(2026, 9, 30), "resigned")
    assert ledger.entitlement_lines_total(pot) == D("105.25")


def test_tier_added_resyncs_every_pot_of_the_type(db):
    a = hours_employee(continuous_service_date=date(2015, 1, 1))
    b = hours_employee(continuous_service_date=date(2026, 4, 1))
    pa = pots.for_day(a, absence_type("AL"), date(2026, 6, 1))
    pb = pots.for_day(b, absence_type("AL"), date(2026, 6, 1))
    ledger.sync_entitlement(pa)
    ledger.sync_entitlement(pb)
    policy = a.contracts.first().contract_type.policies.get()
    PolicyTier.objects.create(policy=policy, after_years=5, extra_weeks=D("1"))
    assert ledger.entitlement_lines_total(pa) == D("247.50")   # 6.6 × 37.5
    assert ledger.entitlement_lines_total(pb) == D("210.00")
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_absence_signals.py -q`
Expected: assertion failures (no revision rows).

- [ ] **Step 3: Implement**

`absence/signals.py`:

```python
"""Re-sync entitlements when the rows they are computed from change.
The nightly job repeats this for every open pot as a safety net."""

from datetime import date

from django.db.models.signals import post_save
from django.dispatch import receiver

from absence.models import Policy, PolicyTier
from absence.services import ledger, pots
from people.models import Contract, Employment


def resync_employment(employment, cause):
    for pot in pots.open_pots(date.today()).filter(employment=employment):
        ledger.sync_entitlement(pot, cause=cause)


def resync_contract_type(contract_type, cause):
    for pot in pots.open_pots(date.today()):
        if pot.employment.contracts.filter(contract_type=contract_type).exists():
            ledger.sync_entitlement(pot, cause=cause)


@receiver(post_save, sender=Contract)
def _contract_saved(sender, instance, created, **kwargs):
    resync_employment(instance.employment, f"contract {'added' if created else 'changed'}: {instance}")


@receiver(post_save, sender=Employment)
def _employment_saved(sender, instance, created, **kwargs):
    if not created:
        resync_employment(instance, "employment dates changed")


@receiver(post_save, sender=Policy)
def _policy_saved(sender, instance, **kwargs):
    resync_contract_type(instance.contract_type, f"policy changed: {instance}")


@receiver(post_save, sender=PolicyTier)
def _tier_saved(sender, instance, **kwargs):
    resync_contract_type(instance.policy.contract_type, f"tier changed: {instance}")
```

Note: `pots.open_pots` uses today's date, so a test that builds pots in 2026 must run while 2026/27 is open; the tests above use the 2026/27 year and `date.today()` in this codebase's CI is later than April 2026. If CI moves past March 2027, change the tests to build pots in the current leave year via `date.today()`.

- [ ] **Step 4: Run and commit**

Run: `python -m pytest tests/test_absence_signals.py tests/test_absence_sync.py tests/test_contracts.py -q`
Expected: all pass.

```bash
git add -A
git commit -m "feat: entitlements re-sync when contracts, employments, policies or tiers change"
```

---

### Task 8: Costing from the working pattern

**Files:**
- Create: `absence/services/costing.py`, `tests/test_absence_costing.py`

**Interfaces:**
- Consumes: `Absence` and `KitDay` models as written in Task 4 (fields: `employment, absence_type, status, start_date, end_date, start_half, end_half, start_time, end_time, hours, cost_units, requested_at, requested_by, decided_at, decided_by, decision_comment, cancelled_at, cancelled_by, category, self_certified, expected_start, actual_start, expected_return, auto_bank_holiday`; `Status` = `REQUESTED, APPROVED, DECLINED, CANCELLED`; `Absence.is_partial` property true when `hours` is not None).
- Produces: `costing.halves_covered(absence) -> list[tuple[date, str]]`; `costing.cost(absence) -> Decimal` (rounded to the policy step when the type has a policy, else to 0.25); `costing.MIDDAY = time(13, 0)`.

For reference, the `Absence` model written in Task 4 is:

```python
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from people.models import Employment

from .types import AbsenceType


class Absence(models.Model):
    """The booking. Either a date range with half-day markers or a single
    day with times and hours (hours-unit employments only)."""
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"

    class Category(models.TextChoices):
        ILLNESS = "illness", "Illness"
        INJURY = "injury", "Injury"
        MENTAL_HEALTH = "mental", "Mental health"
        SURGERY = "surgery", "Surgery or procedure"
        PREGNANCY = "pregnancy", "Pregnancy-related"
        OTHER = "other", "Other"

    employment = models.ForeignKey(Employment, on_delete=models.PROTECT, related_name="absences")
    absence_type = models.ForeignKey(AbsenceType, on_delete=models.PROTECT, related_name="absences")
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.REQUESTED)
    start_date = models.DateField()
    end_date = models.DateField()
    start_half = models.CharField(max_length=2, blank=True, default="")   # "" or "PM"
    end_half = models.CharField(max_length=2, blank=True, default="")     # "" or "AM"
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    cost_units = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    decision_comment = models.CharField(max_length=300, blank=True, default="")
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    category = models.CharField(max_length=9, choices=Category.choices, blank=True, default="")
    self_certified = models.BooleanField(default=False)
    expected_start = models.DateField(null=True, blank=True)
    actual_start = models.DateField(null=True, blank=True)
    expected_return = models.DateField(null=True, blank=True)
    auto_bank_holiday = models.BooleanField(default=False)

    class Meta:
        ordering = ["-start_date"]
        verbose_name_plural = "absences"

    def __str__(self):
        return f"{self.employment.employee} {self.absence_type} {self.start_date:%d %b}–{self.end_date:%d %b %Y}"

    @property
    def is_partial(self):
        return self.hours is not None

    def clean(self):
        super().clean()
        if self.end_date < self.start_date:
            raise ValidationError({"end_date": "Ends before it starts."})
        if self.is_partial:
            if self.start_date != self.end_date:
                raise ValidationError({"end_date": "A partial day is one day."})
            if not (self.start_time and self.end_time) or self.end_time <= self.start_time:
                raise ValidationError({"end_time": "Give a start and an end time, in order."})
            if self.hours <= 0:
                raise ValidationError({"hours": "Must be more than zero."})
        if self.start_half not in ("", "PM") or self.end_half not in ("", "AM"):
            raise ValidationError("Half-day markers are PM for the start and AM for the end.")
        if self.start_date == self.end_date and self.start_half == "PM" and self.end_half == "AM":
            raise ValidationError("A single day cannot start PM and end AM.")


class KitDay(models.Model):
    absence = models.ForeignKey(Absence, on_delete=models.CASCADE, related_name="kit_days")
    date = models.DateField()

    class Meta:
        ordering = ["date"]
        constraints = [models.UniqueConstraint(fields=["absence", "date"], name="one_kit_day")]
```

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_costing.py`:

```python
from datetime import date, time
from decimal import Decimal

from absence.models import Absence, BankHoliday, ClosedDay
from absence.services import costing
from tests.factories import absence_type, hours_employee, make_pattern

D = Decimal
MON, TUE, WED = date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3)


def absence(emp, start, end=None, **kw):
    kw.setdefault("absence_type", absence_type("AL"))
    return Absence(employment=emp, start_date=start, end_date=end or start, **kw)


def test_full_days(db):
    a = absence(hours_employee(), MON, WED)
    assert costing.halves_covered(a) == [(MON, "AM"), (MON, "PM"), (TUE, "AM"), (TUE, "PM"),
                                         (WED, "AM"), (WED, "PM")]
    assert costing.cost(a) == D("22.50")


def test_pm_start_am_end(db):
    a = absence(hours_employee(), MON, WED, start_half="PM", end_half="AM")
    assert costing.cost(a) == D("15.00")


def test_weekend_and_no_pattern_cost_zero(db):
    emp = hours_employee(start=date(2026, 4, 1))
    assert costing.cost(absence(emp, date(2026, 6, 6), date(2026, 6, 7))) == D("0.00")
    before_pattern = hours_employee(start=date(2026, 1, 5))
    before_pattern.patterns.all().delete()
    assert costing.cost(absence(before_pattern, date(2026, 6, 1))) == D("0.00")


def test_bank_holiday_closed_not_charged(db):
    BankHoliday.objects.get_or_create(date=MON, nation="EW", defaults={"name": "Test"})
    assert costing.cost(absence(hours_employee(), MON, WED)) == D("15.00")


def test_closed_day_never_charged(db):
    ClosedDay.objects.create(date=TUE, reason="Training")
    assert costing.cost(absence(hours_employee(), MON, WED)) == D("15.00")


def test_partial_day(db):
    emp = hours_employee()
    a = absence(emp, MON, start_time=time(9, 0), end_time=time(10, 30), hours=D("1.5"))
    assert costing.cost(a) == D("1.50")


def test_partial_day_capped_at_halves_touched(db):
    emp = hours_employee()
    make_pattern(emp, {0: (D("3.75"), D("0"))}, effective_from=date(2026, 5, 1))
    a = absence(emp, MON, start_time=time(9, 0), end_time=time(13, 0), hours=D("4"))
    assert costing.cost(a) == D("3.75")
    b = absence(emp, MON, start_time=time(9, 0), end_time=time(14, 0), hours=D("5"))
    assert costing.cost(b) == D("3.75")
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_absence_costing.py -q`
Expected: ImportError `costing`.

- [ ] **Step 3: Implement**

`absence/services/costing.py`:

```python
"""What a booking costs, in the employment's unit, from the working
pattern in force on each day. Pure."""

from datetime import time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError

from absence.models import BankHoliday, ClosedDay, Policy
from absence.services import policies, rounding
from people.services import patterns

MIDDAY = time(13, 0)


def halves_covered(absence):
    out = []
    day = absence.start_date
    while day <= absence.end_date:
        halves = ["AM", "PM"]
        if day == absence.start_date and absence.start_half == "PM":
            halves.remove("AM")
        if day == absence.end_date and absence.end_half == "AM":
            halves.remove("PM")
        out.extend((day, h) for h in halves)
        day += timedelta(days=1)
    return out


def _handling(absence):
    try:
        return policies.policy_for(absence.employment, absence.absence_type, absence.start_date)
    except ValidationError:
        return None


def _skip(day, policy):
    if ClosedDay.objects.filter(date=day).exists():
        return True
    handling = policy.bank_holiday_handling if policy else Policy.BankHolidays.CLOSED_NOT_CHARGED
    if handling == Policy.BankHolidays.CLOSED_NOT_CHARGED:
        return BankHoliday.objects.filter(date=day, nation="EW").exists()
    return False


def cost(absence):
    policy = _handling(absence)
    step = policy.rounding if policy else Decimal("0.25")
    emp = absence.employment
    if absence.is_partial:
        day = absence.start_date
        if _skip(day, policy):
            return Decimal("0.00")
        cap = Decimal("0")
        if absence.start_time < MIDDAY:
            cap += patterns.units_on(emp, day, "AM")
        if absence.end_time > MIDDAY:
            cap += patterns.units_on(emp, day, "PM")
        return rounding.round_to(min(absence.hours, cap), step)
    total = Decimal("0")
    for day, half in halves_covered(absence):
        if _skip(day, policy):
            continue
        total += patterns.units_on(emp, day, half)
    return rounding.round_to(total, step)
```

- [ ] **Step 4: Run and commit**

Run: `python -m pytest tests/test_absence_costing.py -q`
Expected: 7 passed.

```bash
git add -A
git commit -m "feat: costing a booking from the working pattern, with partial days and closed days"
```

---

### Task 9: Bookings: request, approve, decline, cancel, sickness

**Files:**
- Create: `absence/services/bookings.py`, `absence/services/balances.py`, `tests/test_absence_bookings.py`

**Interfaces:**
- Produces: `bookings.overlaps(employment, start, end, exclude_pk=None) -> bool` (against `REQUESTED` and `APPROVED`); `bookings.request(actor, employment, absence_type, start_date, end_date=None, start_half="", end_half="", start_time=None, end_time=None, hours=None, category="", requested_by=None) -> Absence` (approves at once when `needs_approval` is false); `bookings.approve(actor, absence, comment="") -> Absence`; `bookings.decline(actor, absence, comment="") -> Absence`; `bookings.cancel(actor, absence) -> Absence`; `bookings.recost(actor, absence, note) -> LedgerEntry | None`; `balances.summary(pot, today) -> dict` with keys `entitlement, carried_in, taken, booked, pending, expired, adjustments, remaining`.

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_bookings.py`:

```python
from datetime import date, time
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from absence.models import Absence, LedgerEntry
from absence.services import balances, bookings, ledger, pots
from tests.factories import absence_type, hours_employee, make_pattern

D = Decimal
MON, WED = date(2026, 6, 1), date(2026, 6, 3)


def test_request_then_approve_writes_booking(db, hr_admin, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    assert a.status == Absence.Status.REQUESTED and a.cost_units == D("22.50")
    pot = pots.for_day(emp, absence_type("AL"), MON)
    assert pot.entries.count() == 0
    bookings.approve(hr_admin, a, "fine")
    a.refresh_from_db()
    assert a.status == Absence.Status.APPROVED and a.decided_by == hr_admin
    line = pot.entries.get(kind=LedgerEntry.Kind.BOOKING)
    assert line.units == D("-22.50") and line.absence == a


def test_decline_writes_nothing(db, hr_admin, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("AL"), MON)
    bookings.decline(hr_admin, a, "short staffed")
    assert Absence.objects.get(pk=a.pk).status == Absence.Status.DECLINED
    assert LedgerEntry.objects.count() == 0


def test_cancel_restores_exactly(db, hr_admin, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    bookings.approve(hr_admin, a)
    pot = pots.for_day(emp, absence_type("AL"), MON)
    before = ledger.balance(pot)
    bookings.cancel(employee_user, a)
    assert ledger.balance(pot) == before + D("22.50")
    assert Absence.objects.get(pk=a.pk).status == Absence.Status.CANCELLED


def test_overlap_refused(db, employee_user):
    emp = hours_employee()
    bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    with pytest.raises(ValidationError):
        bookings.request(employee_user, emp, absence_type("AL"), WED)


def test_partial_only_for_hours_unit(db, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("DEP"), MON,
                         start_time=time(9, 0), end_time=time(10, 30), hours=D("1.5"))
    assert a.status == Absence.Status.APPROVED and a.cost_units == D("1.50")
    from tests.factories import make_contract, make_contract_type, make_employee, make_employment
    gp = make_employment(employee=make_employee(first="Gee"))
    make_contract(gp, make_contract_type("Salaried GP", "sessions", D("9")), amount=D("8"))
    make_pattern(gp, {d: (D("1"), D("1")) for d in range(4)})
    with pytest.raises(ValidationError):
        bookings.request(employee_user, gp, absence_type("DEP"), MON,
                         start_time=time(9, 0), end_time=time(10, 30), hours=D("1.5"))


def test_crossing_leave_year_refused(db, employee_user):
    emp = hours_employee()
    with pytest.raises(ValidationError) as e:
        bookings.request(employee_user, emp, absence_type("AL"), date(2027, 3, 29), date(2027, 4, 2))
    assert "two leave years" in str(e.value)


def test_sickness_needs_no_approval_and_no_pot(db, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("SICK"), MON, WED, category="illness")
    assert a.status == Absence.Status.APPROVED and a.self_certified
    assert LedgerEntry.objects.count() == 0


def test_sickness_over_seven_days_not_self_certified(db, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("SICK"), MON, date(2026, 6, 10), category="illness")
    assert not a.self_certified


def test_negative_balance_allowed_but_reported(db, hr_admin, employee_user):
    emp = hours_employee(amount=D("7.5"))          # 42 hours a year
    make_pattern(emp, {0: (D("3.75"), D("3.75"))})
    pot = pots.for_day(emp, absence_type("AL"), MON)
    ledger.sync_entitlement(pot)
    for week in range(7):
        a = bookings.request(employee_user, emp, absence_type("AL"), date(2026, 6, 1 + 7 * week))
        bookings.approve(hr_admin, a)
    s = balances.summary(pot, date(2026, 6, 20))
    assert s["remaining"] == D("-10.50")
    assert s["taken"] == D("22.50") and s["booked"] == D("30.00")


def test_summary_keys(db, employee_user):
    emp = hours_employee()
    pot = pots.for_day(emp, absence_type("AL"), MON)
    ledger.sync_entitlement(pot)
    bookings.request(employee_user, emp, absence_type("AL"), MON)
    s = balances.summary(pot, MON)
    assert s == {"entitlement": D("210.00"), "carried_in": D("0"), "taken": D("0"), "booked": D("0"),
                 "pending": D("7.50"), "expired": D("0"), "adjustments": D("0"), "remaining": D("210.00")}
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_absence_bookings.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement**

`absence/services/bookings.py`:

```python
"""Every change of an Absence's status, and the ledger line it implies."""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from absence.models import Absence, LedgerEntry
from absence.services import costing, leave_year, ledger, policies, pots
from people.services import audit, contracts

LIVE = (Absence.Status.REQUESTED, Absence.Status.APPROVED)
SELF_CERT_DAYS = 7


def overlaps(employment, start, end, exclude_pk=None):
    qs = Absence.objects.filter(employment=employment, status__in=LIVE,
                                start_date__lte=end, end_date__gte=start)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


def _check_leave_year(absence):
    if not absence.absence_type.uses_pot:
        return
    policy = policies.policy_for(absence.employment, absence.absence_type, absence.start_date)
    _, end = leave_year.bounds(policy, absence.employment, absence.start_date)
    if absence.end_date > end:
        raise ValidationError("This crosses the end of the leave year. Book the two leave years separately.")


@transaction.atomic
def request(actor, employment, absence_type, start_date, end_date=None, start_half="", end_half="",
            start_time=None, end_time=None, hours=None, category="", requested_by=None):
    a = Absence(employment=employment, absence_type=absence_type, start_date=start_date,
                end_date=end_date or start_date, start_half=start_half, end_half=end_half,
                start_time=start_time, end_time=end_time, hours=hours, category=category,
                requested_by=requested_by or actor)
    a.full_clean(exclude=["employment", "absence_type", "requested_by"])
    if a.is_partial and contracts.unit(employment, start_date) != "hours":
        raise ValidationError({"hours": "Partial days are only for people whose allowance is in hours."})
    if overlaps(employment, a.start_date, a.end_date):
        raise ValidationError("There is already an absence on those dates.")
    _check_leave_year(a)
    if absence_type.code == "SICK":
        a.self_certified = (a.end_date - a.start_date) < timedelta(days=SELF_CERT_DAYS)
    a.cost_units = costing.cost(a)
    a.save()
    audit.record(actor, a, {"requested": ("", str(a))})
    if not absence_type.needs_approval:
        return approve(actor, a)
    return a


@transaction.atomic
def approve(actor, absence, comment=""):
    if absence.status != Absence.Status.REQUESTED:
        raise ValidationError("Only a requested absence can be approved.")
    if overlaps(absence.employment, absence.start_date, absence.end_date, exclude_pk=absence.pk):
        raise ValidationError("Another absence now overlaps these dates.")
    absence.cost_units = costing.cost(absence)
    absence.status = Absence.Status.APPROVED
    absence.decided_at = timezone.now()
    absence.decided_by = actor
    absence.decision_comment = comment
    absence.save()
    if absence.absence_type.uses_pot and absence.cost_units:
        pot = pots.for_day(absence.employment, absence.absence_type, absence.start_date)
        kind = LedgerEntry.Kind.TOIL_TAKEN if absence.absence_type.code == "TOIL" else LedgerEntry.Kind.BOOKING
        ledger.write(pot, kind, -absence.cost_units, actor, absence=absence,
                     note=f"{absence.start_date:%d %b}–{absence.end_date:%d %b %Y}", date=absence.start_date)
    audit.record(actor, absence, {"status": ("requested", "approved")})
    return absence


@transaction.atomic
def decline(actor, absence, comment=""):
    if absence.status != Absence.Status.REQUESTED:
        raise ValidationError("Only a requested absence can be declined.")
    absence.status = Absence.Status.DECLINED
    absence.decided_at = timezone.now()
    absence.decided_by = actor
    absence.decision_comment = comment
    absence.save()
    audit.record(actor, absence, {"status": ("requested", "declined")})
    return absence


@transaction.atomic
def cancel(actor, absence):
    if absence.status not in LIVE:
        raise ValidationError("Only a requested or approved absence can be cancelled.")
    was = absence.status
    absence.status = Absence.Status.CANCELLED
    absence.cancelled_at = timezone.now()
    absence.cancelled_by = actor
    absence.save()
    if was == Absence.Status.APPROVED and absence.absence_type.uses_pot and absence.cost_units:
        pot = pots.for_day(absence.employment, absence.absence_type, absence.start_date)
        ledger.write(pot, LedgerEntry.Kind.CANCELLATION, absence.cost_units, actor, absence=absence,
                     note="cancelled", date=absence.start_date)
    audit.record(actor, absence, {"status": (was, "cancelled")})
    return absence


@transaction.atomic
def recost(actor, absence, note):
    """An HR admin re-prices an approved absence after a pattern change.
    Writes an adjustment for the difference, or nothing."""
    if absence.status != Absence.Status.APPROVED or not absence.absence_type.uses_pot:
        raise ValidationError("Only an approved, pot-backed absence can be re-costed.")
    new = costing.cost(absence)
    delta = absence.cost_units - new
    if delta == 0:
        return None
    absence.cost_units = new
    absence.save()
    pot = pots.for_day(absence.employment, absence.absence_type, absence.start_date)
    return ledger.write(pot, LedgerEntry.Kind.ADJUSTMENT, delta, actor, absence=absence, note=note)
```

`absence/services/balances.py`:

```python
from decimal import Decimal

from django.db.models import Sum

from absence.models import Absence, LedgerEntry
from absence.services import ledger

K = LedgerEntry.Kind


def _sum(qs):
    return qs.aggregate(t=Sum("units"))["t"] or Decimal("0")


def summary(pot, today):
    entries = pot.entries
    booked_lines = entries.filter(kind__in=(K.BOOKING, K.TOIL_TAKEN, K.CANCELLATION))
    taken = -_sum(booked_lines.filter(absence__end_date__lt=today))
    booked = -_sum(booked_lines.filter(absence__end_date__gte=today))
    pending = Absence.objects.filter(
        employment=pot.employment, absence_type=pot.absence_type, status=Absence.Status.REQUESTED,
        start_date__range=(pot.year_start, pot.year_end)).aggregate(t=Sum("cost_units"))["t"] or Decimal("0")
    return {
        "entitlement": ledger.entitlement_lines_total(pot),
        "carried_in": _sum(entries.filter(kind=K.CARRY_IN)),
        "taken": taken,
        "booked": booked,
        "pending": pending,
        "expired": -_sum(entries.filter(kind=K.EXPIRY)),
        "adjustments": _sum(entries.filter(kind__in=(K.ADJUSTMENT, K.TOIL_EARNED))),
        "remaining": ledger.balance(pot),
    }
```

- [ ] **Step 4: Run and commit**

Run: `python -m pytest tests/test_absence_bookings.py -q`
Expected: 10 passed.

```bash
git add -A
git commit -m "feat: bookings write the ledger; balances summarise it"
```

---

### Task 10: Automatic bank-holiday absences

**Files:**
- Create: `absence/services/bank_holidays.py`, `tests/test_absence_bank_holidays.py`

**Interfaces:**
- Produces: `bank_holidays.sync_auto_absences(employment, year_start, year_end, actor=None) -> dict` with `created`, `removed` and `skipped` counts.

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_bank_holidays.py`:

```python
from datetime import date
from decimal import Decimal

from absence.models import Absence, LedgerEntry, Policy
from absence.services import bank_holidays, ledger, pots
from people.services import patterns
from tests.factories import absence_type, hours_employee, make_policy

D = Decimal
Y0, Y1 = date(2026, 4, 1), date(2027, 3, 31)


def _with_pot_handling(emp):
    ct = emp.contracts.first().contract_type
    ct.policies.filter(absence_type__code="AL").update(bank_holiday_handling=Policy.BankHolidays.PRO_RATA_POT)
    make_policy(ct, "BH", bank_holiday_handling="pot")


def test_creates_one_per_working_bank_holiday(db):
    emp = hours_employee()
    _with_pot_handling(emp)
    result = bank_holidays.sync_auto_absences(emp, Y0, Y1)
    assert result == {"created": 10, "removed": 0, "skipped": 0}   # ten in 2026/27, all weekdays
    a = Absence.objects.get(employment=emp, start_date=date(2026, 5, 4))
    assert a.auto_bank_holiday and a.status == "approved" and a.cost_units == D("7.50")
    pot = pots.for_day(emp, absence_type("BH"), Y0)
    assert ledger.balance(pot) == D("-75.00")


def test_idempotent(db):
    emp = hours_employee()
    _with_pot_handling(emp)
    bank_holidays.sync_auto_absences(emp, Y0, Y1)
    assert bank_holidays.sync_auto_absences(emp, Y0, Y1) == {"created": 0, "removed": 0, "skipped": 0}


def test_non_working_day_not_created_and_pattern_change_removes(db, hr_admin):
    emp = hours_employee()
    _with_pot_handling(emp)
    bank_holidays.sync_auto_absences(emp, Y0, Y1)
    patterns.set_pattern(hr_admin, emp, date(2026, 4, 1), {d: (D("3.75"), D("3.75")) for d in (1, 2, 3, 4)})
    result = bank_holidays.sync_auto_absences(emp, Y0, Y1)
    assert result["removed"] == 6      # the six Monday bank holidays
    assert Absence.objects.filter(employment=emp, auto_bank_holiday=True, status="approved").count() == 4
    pot = pots.for_day(emp, absence_type("BH"), Y0)
    assert pot.entries.filter(kind=LedgerEntry.Kind.CANCELLATION).count() == 6


def test_included_in_annual_draws_on_al(db):
    emp = hours_employee()
    ct = emp.contracts.first().contract_type
    ct.policies.filter(absence_type__code="AL").update(bank_holiday_handling=Policy.BankHolidays.INCLUDED_IN_ANNUAL)
    bank_holidays.sync_auto_absences(emp, Y0, Y1)
    pot = pots.for_day(emp, absence_type("AL"), Y0)
    assert ledger.balance(pot) == D("-75.00")


def test_closed_not_charged_creates_nothing(db):
    emp = hours_employee()
    assert bank_holidays.sync_auto_absences(emp, Y0, Y1) == {"created": 0, "removed": 0, "skipped": 0}
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_absence_bank_holidays.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement**

`absence/services/bank_holidays.py`:

```python
"""Bank holidays are charged automatically under the two pot handlings."""

from django.core.exceptions import ValidationError
from django.db import transaction

from absence.models import Absence, AbsenceType, BankHoliday, Policy
from absence.services import bookings, policies
from people.services import patterns


def _target_type(handling):
    if handling == Policy.BankHolidays.PRO_RATA_POT:
        return AbsenceType.objects.get(code="BH")
    if handling == Policy.BankHolidays.INCLUDED_IN_ANNUAL:
        return AbsenceType.objects.get(code="AL")
    return None


@transaction.atomic
def sync_auto_absences(employment, year_start, year_end, actor=None):
    """Create the approved bank-holiday absences the pattern and policy
    imply, cancel the ones they no longer imply. Idempotent. A day the
    person has already booked off is skipped and counted."""
    created = removed = skipped = 0
    al = AbsenceType.objects.get(code="AL")
    existing = {a.start_date: a for a in Absence.objects.filter(
        employment=employment, auto_bank_holiday=True, status=Absence.Status.APPROVED,
        start_date__range=(year_start, year_end))}
    wanted = {}
    for bh in BankHoliday.objects.filter(date__range=(year_start, year_end), nation="EW"):
        if not employment.is_active_on(bh.date):
            continue
        try:
            policy = policies.policy_for(employment, al, bh.date)
        except ValidationError:
            continue
        target = _target_type(policy.bank_holiday_handling)
        if target is None:
            continue
        units = patterns.units_on(employment, bh.date, "AM") + patterns.units_on(employment, bh.date, "PM")
        if units:
            wanted[bh.date] = target
    for day, absence in list(existing.items()):
        if wanted.get(day) != absence.absence_type:
            bookings.cancel(actor, absence)
            removed += 1
            del existing[day]
    for day, target in wanted.items():
        if day in existing:
            continue
        a = Absence(employment=employment, absence_type=target, start_date=day, end_date=day,
                    auto_bank_holiday=True, requested_by=actor)
        a.full_clean(exclude=["employment", "absence_type", "requested_by"])
        a.save()
        try:
            bookings.approve(actor, a, comment="bank holiday")
        except ValidationError:
            a.status = Absence.Status.DECLINED
            a.decision_comment = "already off that day"
            a.save()
            skipped += 1
            continue
        created += 1
    return {"created": created, "removed": removed, "skipped": skipped}
```

`bookings.cancel` on an auto absence writes the cancellation line like any other; `bookings.approve` refuses an overlap with the person's own leave, which is what `skipped` counts.

- [ ] **Step 4: Run and commit**

Run: `python -m pytest tests/test_absence_bank_holidays.py tests/test_absence_bookings.py -q`
Expected: all pass.

```bash
git add -A
git commit -m "feat: automatic bank-holiday absences under the pot handlings"
```

---

### Task 11: Nightly safety net, admin, and the hr_nightly hook

**Files:**
- Create: `absence/services/nightly.py`, `absence/admin.py`, `tests/test_absence_nightly.py`, `tests/test_absence_admin.py`; Modify: `people/management/commands/hr_nightly.py`, `hr/admin_site.py` (navigation)

**Interfaces:**
- Produces: `absence.services.nightly.run(today) -> dict` with `pots_synced`, `revisions`, `bank_holiday_created`, `bank_holiday_removed`; admin for `AbsenceType`, `Policy` (tiers inline), `BankHoliday`, `ClosedDay`, `Pot` (read-only, ledger inline read-only, a "Recalculate" action calling `sync_entitlement`), `Absence` (read-only list with filters).

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_nightly.py`:

```python
from datetime import date

from absence.services import nightly, pots
from tests.factories import absence_type, hours_employee


def test_nightly_syncs_open_pots_and_bank_holidays(db):
    emp = hours_employee(start=date(2026, 4, 1))
    pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    result = nightly.run(date(2026, 6, 1))
    assert result["pots_synced"] == 1 and result["revisions"] == 1
    assert nightly.run(date(2026, 6, 1))["revisions"] == 0


def test_command_includes_absence(db, capsys):
    from django.core.management import call_command
    call_command("hr_nightly")
    assert "absence:" in capsys.readouterr().out
```

`tests/test_absence_admin.py`:

```python
def test_changelists_render(admin_client, db):
    for url in ("/admin/absence/absencetype/", "/admin/absence/policy/", "/admin/absence/bankholiday/",
                "/admin/absence/closedday/", "/admin/absence/pot/", "/admin/absence/absence/"):
        assert admin_client.get(url).status_code == 200, url


def test_pot_and_absence_are_read_only(admin_client, db):
    assert admin_client.get("/admin/absence/pot/add/").status_code == 403
    assert admin_client.get("/admin/absence/absence/add/").status_code == 403
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_absence_nightly.py tests/test_absence_admin.py -q`
Expected: ImportError / 404.

- [ ] **Step 3: Implement**

`absence/services/nightly.py`:

```python
from absence.services import bank_holidays, ledger, pots
from people.services import employments


def run(today):
    synced = revisions = 0
    for pot in pots.open_pots(today):
        synced += 1
        if ledger.sync_entitlement(pot, cause="nightly recalculation") is not None:
            revisions += 1
    created = removed = 0
    for pot in pots.open_pots(today).filter(absence_type__code="AL"):
        r = bank_holidays.sync_auto_absences(pot.employment, pot.year_start, pot.year_end)
        created += r["created"]
        removed += r["removed"]
    return {"pots_synced": synced, "revisions": revisions,
            "bank_holiday_created": created, "bank_holiday_removed": removed}
```

In `hr_nightly.py`, import `from absence.services import nightly as absence_nightly` and add `"absence": absence_nightly.run(today)` to `results`.

`absence/admin.py`:

```python
from django.contrib import admin, messages
from unfold.admin import ModelAdmin, TabularInline

from absence.models import (Absence, AbsenceType, BankHoliday, ClosedDay, LedgerEntry, Policy,
                            PolicyTier, Pot)
from absence.services import ledger


@admin.register(AbsenceType)
class AbsenceTypeAdmin(ModelAdmin):
    list_display = ("name", "code", "paid", "uses_pot", "needs_approval", "self_certified",
                    "calendar_label", "payroll_reportable", "health_sensitive", "active")
    list_editable = ("active",)


class PolicyTierInline(TabularInline):
    model = PolicyTier
    extra = 0


@admin.register(Policy)
class PolicyAdmin(ModelAdmin):
    list_display = ("contract_type", "absence_type", "effective_from", "effective_to", "weeks_per_year",
                    "leave_year_basis", "bank_holiday_handling")
    list_filter = ("contract_type", "absence_type")
    inlines = [PolicyTierInline]


@admin.register(BankHoliday)
class BankHolidayAdmin(ModelAdmin):
    list_display = ("date", "name", "nation")


@admin.register(ClosedDay)
class ClosedDayAdmin(ModelAdmin):
    list_display = ("date", "reason")


class LedgerEntryInline(TabularInline):
    model = LedgerEntry
    extra = 0
    can_delete = False
    fields = ("date", "kind", "units", "absence", "note", "actor")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Pot)
class PotAdmin(ModelAdmin):
    list_display = ("employment", "absence_type", "year_start", "year_end", "unit", "balance")
    list_filter = ("absence_type",)
    inlines = [LedgerEntryInline]
    actions = ["recalculate"]

    @admin.display(description="Balance")
    def balance(self, obj):
        return ledger.balance(obj)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Recalculate entitlement")
    def recalculate(self, request, queryset):
        n = sum(1 for pot in queryset if ledger.sync_entitlement(pot, request.user, "recalculated by admin"))
        messages.info(request, f"{n} pot(s) revised.")


@admin.register(Absence)
class AbsenceAdmin(ModelAdmin):
    list_display = ("employment", "absence_type", "status", "start_date", "end_date", "cost_units",
                    "auto_bank_holiday")
    list_filter = ("status", "absence_type", "auto_bank_holiday")
    date_hierarchy = "start_date"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
```

Add an "Absence" group to `hr/admin_site.py`'s `navigation`: Absence types, Policies, Bank holidays, Closed days, Pots, Absences, using `reverse("admin:absence_<model>_changelist")`.

- [ ] **Step 4: Run everything, lint, check migrations, commit**

Run: `ruff check . && DEBUG=1 python manage.py makemigrations --check --dry-run && python -m pytest -q`
Expected: all green.

```bash
git add -A
git commit -m "feat: absence admin, nightly recalculation and bank-holiday sync"
```

---

## Self-review

**Spec coverage (section 4 and the nightly parts):** AbsenceType with every flag (1); Policy fields, tiers, leave-year basis, rounding, bank-holiday handling, TOIL expiry field (2); leave-year bounds and rounding (3); Pot, immutable LedgerEntry with every kind, BankHoliday, ClosedDay, Absence and KitDay (4); the accrual integral including the bank-holiday pot formula (5); `sync_entitlement` idempotent with a cause note (6); re-sync on contract, employment, policy and tier changes (7); costing with halves, closed days, partial-day cap at MIDDAY (8); bookings that write and restore the ledger, overlap refusal, partial-day unit rule, sickness self-certification, re-costing as an adjustment, balances (9); automatic bank-holiday absences created, removed and idempotent (10); nightly safety net and the admin (11). **Deferred to plan 3:** carry-over, expiry, TOIL earned, year end, the chase, the calendar, the request pages, the payroll report, the API, and TOIL expiry by `toil_expires_after_days`.

**Placeholders:** the seed migrations name `<previous>` for the dependency the generator fills in; everything else is written out.

**Type consistency:** `pots.for_day(employment, absence_type, day)`, `ledger.write(pot, kind, units, actor, absence, note, date)`, `ledger.sync_entitlement(pot, actor, cause)`, `costing.cost(absence)`, `bookings.request/approve/decline/cancel`, `balances.summary(pot, today)` are used with those signatures throughout and are what plan 3 consumes.

**Review Focus:** year-boundary refusal (Task 9 `test_crossing_leave_year_refused`), no-pattern day (Task 8 `test_weekend_and_no_pattern_cost_zero`), leap year (Task 5 `test_leap_year_same_as_common`), double sync and rounding-to-nothing (Task 6), non-working bank holiday and pattern change (Task 10).
