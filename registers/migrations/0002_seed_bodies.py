from django.db import migrations

# name, code, display_order. No titles: HR assigns the titles that need each
# body (docs/admin/compliance.md#professional-registrations).
BODIES = [
    ("GMC", "gmc", 10),
    ("Welsh medical performers list", "mpl_wales", 20),
    ("NMC", "nmc", 30),
    ("GPhC", "gphc", 40),
]


def seed(apps, schema_editor):
    RegisterBody = apps.get_model("registers", "RegisterBody")
    for name, code, order in BODIES:
        RegisterBody.objects.get_or_create(code=code, defaults={"name": name, "display_order": order})


def unseed(apps, schema_editor):
    RegisterBody = apps.get_model("registers", "RegisterBody")
    RegisterBody.objects.filter(code__in=[b[1] for b in BODIES], registrations=None).delete()


class Migration(migrations.Migration):
    dependencies = [("registers", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
