from django.db import migrations

# The default starter and leaver templates (no positions: they apply to every
# title without one of its own). HR edits them in Admin › Compliance ›
# Checklist templates (docs/admin/compliance.md#checklists).
# order, title, owner, due_rule, due_days, link
STARTER = [
    (1, "Complete your details", "person", "before_start", 7, "details"),
    (2, "Read and sign the practice policies", "person", "after_start", 14, "sign_policies"),
    (3, "Upload your right-to-work document", "person", "before_start", 7, "upload:identity"),
    (4, "References received", "hr", "before_start", 7, ""),
    (5, "DBS check recorded", "hr", "after_start", 0, "check:dbs"),
    (6, "Occupational health clearance", "hr", "before_start", 0, "check:occupational_health"),
    (7, "Contract issued", "hr", "before_start", 14, "upload:contract"),
    (8, "Induction completed", "manager", "after_start", 5, ""),
    (9, "Clinical and practice systems access set up", "manager", "before_start", 1, ""),
    (10, "Buddy named", "manager", "after_start", 1, ""),
]
LEAVER = [
    (1, "Handover completed", "manager", "before_end", 5, ""),
    (2, "Equipment returned", "manager", "after_end", 0, ""),
    (3, "Systems access removed", "manager", "after_end", 0, ""),
    (4, "Smartcard returned", "manager", "after_end", 0, ""),
    (5, "Final pay and leave balance to payroll", "hr", "after_end", 7, ""),
    (6, "File closed and retention date noted", "hr", "after_end", 14, ""),
]
DEFAULTS = [("starter", "Default starter", STARTER), ("leaver", "Default leaver", LEAVER)]


def seed(apps, schema_editor):
    ChecklistTemplate = apps.get_model("onboarding", "ChecklistTemplate")
    TemplateItem = apps.get_model("onboarding", "TemplateItem")
    for kind, name, items in DEFAULTS:
        template, created = ChecklistTemplate.objects.get_or_create(kind=kind, name=name)
        if created:
            TemplateItem.objects.bulk_create(
                TemplateItem(template=template, order=order, title=title, owner=owner, due_rule=rule,
                             due_days=days, link=link)
                for order, title, owner, rule, days, link in items)


def unseed(apps, schema_editor):
    ChecklistTemplate = apps.get_model("onboarding", "ChecklistTemplate")
    for kind, name, _ in DEFAULTS:
        ChecklistTemplate.objects.filter(kind=kind, name=name, positions=None).delete()


class Migration(migrations.Migration):
    dependencies = [("onboarding", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
