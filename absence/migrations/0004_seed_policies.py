import datetime
from decimal import Decimal

from django.db import migrations

SEEDED_TYPES = ["Partner", "Salaried GP", "GP trainee", "Practice nurse", "HCA",
                "Reception", "Administration", "Management"]


def seed(apps, schema_editor):
    ContractType = apps.get_model("people", "ContractType")
    AbsenceType = apps.get_model("absence", "AbsenceType")
    Policy = apps.get_model("absence", "Policy")
    annual_leave = AbsenceType.objects.filter(code="AL").first()
    if annual_leave is None:
        return
    for name in SEEDED_TYPES:
        ctype = ContractType.objects.filter(name=name).first()
        if ctype is None:
            continue
        sessions = ctype.unit == "sessions"
        Policy.objects.get_or_create(
            contract_type=ctype, absence_type=annual_leave,
            effective_from=datetime.date(2020, 1, 1),
            defaults=dict(
                weeks_per_year=Decimal("5.6"), leave_year_basis="fixed",
                year_start_month=4, year_start_day=1,
                rounding=Decimal("0.5") if sessions else Decimal("0.25"),
                bank_holiday_handling="closed" if sessions else "pot"))


class Migration(migrations.Migration):
    dependencies = [
        ("absence", "0003_policy_policytier"),
        ("people", "0010_contracttype_min_and_work_email_help"),
        ("people", "0008_seed_contract_types"),
    ]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
