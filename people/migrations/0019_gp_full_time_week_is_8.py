"""The practice's full-time GP week is 8 sessions. The three GP types were
seeded at 9 (0008); a type someone has already changed is left alone. The reverse is
deliberately a no-op: unapplying leaves the week at 8."""
from decimal import Decimal

from django.db import migrations

GP_TYPES = ("Partner", "Salaried GP", "GP trainee")


def to_eight(apps, schema_editor):
    ContractType = apps.get_model("people", "ContractType")
    ContractType.objects.filter(name__in=GP_TYPES, full_time_weekly=Decimal("9")).update(full_time_weekly=Decimal("8"))


class Migration(migrations.Migration):
    dependencies = [("people", "0018_leave_terms")]
    operations = [migrations.RunPython(to_eight, migrations.RunPython.noop)]
