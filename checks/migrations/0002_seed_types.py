from django.db import migrations

# name, code, evidence, validity_months, remind_person, display_order. No
# positions: HR assigns the titles that need each type (docs/admin/compliance.md).
TYPES = [
    ("Right to work", "right_to_work", "file", None, True, 10),
    ("DBS", "dbs", "reference", 36, True, 20),
    ("References", "references", "none", None, False, 30),
    ("Occupational health", "occupational_health", "file", None, False, 40),
    ("Hep B immunity", "hep_b", "file", None, False, 50),
    ("Indemnity", "indemnity", "file", 12, False, 60),
    ("Professional registration", "professional_registration", "reference", 12, False, 70),
]


def seed(apps, schema_editor):
    CheckType = apps.get_model("checks", "CheckType")
    for name, code, evidence, months, remind, order in TYPES:
        CheckType.objects.get_or_create(code=code, defaults={
            "name": name, "evidence": evidence, "validity_months": months, "remind_person": remind,
            "display_order": order})


def unseed(apps, schema_editor):
    CheckType = apps.get_model("checks", "CheckType")
    CheckType.objects.filter(code__in=[t[1] for t in TYPES]).delete()


class Migration(migrations.Migration):
    dependencies = [("checks", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
