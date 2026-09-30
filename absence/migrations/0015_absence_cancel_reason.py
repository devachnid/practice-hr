from django.db import migrations, models

# bank_holidays.NOT_IMPLIED, as it was when this migration was written
NOT_IMPLIED = "no longer implied by the pattern or policy"


def mark_earlier_cancellations(apps, schema_editor):
    """Before this field, nobody could cancel an automatic bank-holiday row
    but the sync and a leaving date, and both cancelled it because it was no
    longer implied: say so, or the sync would take them for HR's own."""
    Absence = apps.get_model("absence", "Absence")
    Absence.objects.filter(auto_bank_holiday=True, status="cancelled").update(cancel_reason=NOT_IMPLIED)


class Migration(migrations.Migration):
    dependencies = [("absence", "0014_toilclaim")]
    operations = [
        migrations.AddField(
            model_name="absence",
            name="cancel_reason",
            field=models.CharField(blank=True, default="", max_length=60),
        ),
        migrations.RunPython(mark_earlier_cancellations, migrations.RunPython.noop),
    ]
