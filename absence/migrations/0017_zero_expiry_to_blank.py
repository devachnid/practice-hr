from django.db import migrations


def zero_to_blank(apps, schema_editor):
    """A 0 in either expiry field was read as "never" until 0 was refused as
    an expiry (blank means never): keep what it meant."""
    apps.get_model("absence", "AbsenceType").objects.filter(earned_expires_after_days=0).update(
        earned_expires_after_days=None)
    apps.get_model("absence", "Policy").objects.filter(carry_over_expires_after_days=0).update(
        carry_over_expires_after_days=None)


class Migration(migrations.Migration):
    dependencies = [("absence", "0016_seed_bank_holidays_2029_2030")]
    operations = [migrations.RunPython(zero_to_blank, migrations.RunPython.noop)]
