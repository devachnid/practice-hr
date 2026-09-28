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
