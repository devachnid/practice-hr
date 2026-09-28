"""A bank-holiday policy for each seeded hours contract type.

0004 gave the hours types "pot" handling on their annual-leave policy but no
policy for the bank-holiday pot itself, so every automatic bank-holiday
absence failed or cost nothing. The bank-holiday pot's weeks come from the
calendar (the leave year's bank holidays divided by five, in
accrual.bank_holiday_entitlement), so the policy's own weeks figure is never
read and is seeded as 0; its leave year and rounding copy the annual-leave
policy's so the two pots share a year. Idempotent: a type that already has a
bank-holiday policy is left alone.
"""

from decimal import Decimal

from django.db import migrations

HOURS_TYPES = ["Practice nurse", "HCA", "Reception", "Administration", "Management"]


def seed(apps, schema_editor):
    ContractType = apps.get_model("people", "ContractType")
    AbsenceType = apps.get_model("absence", "AbsenceType")
    Policy = apps.get_model("absence", "Policy")
    annual_leave = AbsenceType.objects.filter(code="AL").first()
    bank_holiday = AbsenceType.objects.filter(code="BH").first()
    if annual_leave is None or bank_holiday is None:
        return
    for name in HOURS_TYPES:
        ctype = ContractType.objects.filter(name=name, unit="hours").first()
        if ctype is None or Policy.objects.filter(contract_type=ctype, absence_type=bank_holiday).exists():
            continue
        al = (Policy.objects.filter(contract_type=ctype, absence_type=annual_leave)
              .order_by("effective_from").first())
        if al is None:
            continue
        Policy.objects.create(
            contract_type=ctype, absence_type=bank_holiday,
            effective_from=al.effective_from,
            weeks_per_year=Decimal("0"), leave_year_basis=al.leave_year_basis,
            year_start_month=al.year_start_month, year_start_day=al.year_start_day,
            rounding=al.rounding, bank_holiday_handling="pot")


class Migration(migrations.Migration):
    dependencies = [("absence", "0006_seed_bank_holidays")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
