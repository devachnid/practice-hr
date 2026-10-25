from django.db import migrations

# name, code, delivery, validity_months, display_order. No titles and not
# required of everyone: HR sets that up (docs/admin/compliance.md). A
# starting list, not a rule.
COURSES = [
    ("Basic life support", "basic_life_support", "face_to_face", 12, 10),
    ("Fire safety", "fire_safety", "online", 12, 20),
    ("Information governance", "information_governance", "online", 12, 30),
    ("Infection prevention and control", "infection_control", "online", 12, 40),
    ("Safeguarding children", "safeguarding_children", "online", 36, 50),
    ("Safeguarding adults", "safeguarding_adults", "online", 36, 60),
    ("Equality and diversity", "equality_diversity", "online", 36, 70),
    ("Health and safety", "health_safety", "online", 36, 80),
    ("Conflict resolution", "conflict_resolution", "online", 36, 90),
    ("Chaperone", "chaperone", "online", None, 100),
]


def seed(apps, schema_editor):
    Course = apps.get_model("training", "Course")
    for name, code, delivery, months, order in COURSES:
        Course.objects.get_or_create(code=code, defaults={
            "name": name, "delivery": delivery, "validity_months": months, "display_order": order})


def unseed(apps, schema_editor):
    Course = apps.get_model("training", "Course")
    Course.objects.filter(code__in=[c[1] for c in COURSES]).delete()


class Migration(migrations.Migration):
    dependencies = [("training", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
