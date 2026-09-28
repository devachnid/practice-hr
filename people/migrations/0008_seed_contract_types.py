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
    dependencies = [("people", "0007_workingpattern_patternday_and_more")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
