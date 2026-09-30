"""The seeded hours contract types move to the practice's standard contract.

0004 seeded every contract type's annual leave at 5.6 weeks from 1 April,
and 0007 gave each hours type a bank-holiday policy in the same year. The
practice's contract is: a 1 January leave year; 22 days full time (4.4
weeks), 23 after one complete year, 25 after three, 27 after five; earned
in monthly twelfths, a part month counting in full; plus the bank holidays
as a pot, one working day each, pro rata.

Only a row that still holds exactly what 0004 (or 0007) seeded is changed,
so a policy an HR admin has edited stays as they left it, and only on a
contract type whose staff have no annual-leave or bank-holiday pot yet: a
pot keeps the dates it was opened with, so moving the year under open
April pots would let the nightly open January pots overlapping them (the
docs say how to move a live type by hand). A type's annual-leave and
bank-holiday policies move together or not at all (both still as seeded),
so the two pots keep sharing a year. Run again, it finds nothing seeded
and changes nothing. The sessions (GP) seeds are untouched. Reverse is a
no-op.
"""

import datetime
from decimal import Decimal

from django.db import migrations

HOURS_TYPES = ["Practice nurse", "HCA", "Reception", "Administration", "Management"]
SEEDED_FROM = datetime.date(2020, 1, 1)

AS_SEEDED = dict(          # 0004's annual leave for an hours type, and the model defaults it left
    effective_from=SEEDED_FROM, effective_to=None, weeks_per_year=Decimal("5.6"), leave_year_basis="fixed",
    year_start_month=4, year_start_day=1, carry_over_max_weeks=None, carry_over_expires_after_days=None,
    rounding=Decimal("0.25"), bank_holiday_handling="pot", toil_expires_after_days=None, accrual="daily")
BANK_HOLIDAY_AS_SEEDED = {**AS_SEEDED, "weeks_per_year": Decimal("0")}      # 0007: a copy of it, no weeks

STANDARD = dict(year_start_month=1, year_start_day=1, weeks_per_year=Decimal("4.4"), accrual="monthly",
                bank_holiday_handling="pot")
TIERS = [(1, Decimal("0.2")), (3, Decimal("0.6")), (5, Decimal("1.0"))]    # 23, 25 and 27 days


def _as_seeded(policy, values):
    return all(getattr(policy, k) == v for k, v in values.items()) and not policy.tiers.exists()


def seed(apps, schema_editor):
    ContractType = apps.get_model("people", "ContractType")
    AbsenceType = apps.get_model("absence", "AbsenceType")
    Policy = apps.get_model("absence", "Policy")
    PolicyTier = apps.get_model("absence", "PolicyTier")
    Pot = apps.get_model("absence", "Pot")
    annual_leave = AbsenceType.objects.filter(code="AL").first()
    bank_holiday = AbsenceType.objects.filter(code="BH").first()
    if annual_leave is None:
        return
    for name in HOURS_TYPES:
        ctype = ContractType.objects.filter(name=name, unit="hours").first()
        if ctype is None or Pot.objects.filter(
                absence_type__in=[t for t in (annual_leave, bank_holiday) if t is not None],
                employment__contracts__contract_type=ctype).exists():
            continue
        al = Policy.objects.filter(contract_type=ctype, absence_type=annual_leave, effective_from=SEEDED_FROM).first()
        bh = (Policy.objects.filter(contract_type=ctype, absence_type=bank_holiday, effective_from=SEEDED_FROM).first()
              if bank_holiday is not None else None)
        if al is None or not _as_seeded(al, AS_SEEDED):
            continue
        if bh is not None and not _as_seeded(bh, BANK_HOLIDAY_AS_SEEDED):
            continue                         # its pot would be left in the April year
        for field, value in STANDARD.items():
            setattr(al, field, value)
        al.save()
        PolicyTier.objects.bulk_create(PolicyTier(policy=al, after_years=years, extra_weeks=extra)
                                       for years, extra in TIERS)
        if bh is not None:
            bh.year_start_month, bh.year_start_day = 1, 1
            bh.save()


class Migration(migrations.Migration):
    dependencies = [("absence", "0011_policy_accrual")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
