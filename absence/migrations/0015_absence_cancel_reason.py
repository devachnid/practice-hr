from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("absence", "0014_toilclaim")]
    operations = [
        migrations.AddField(
            model_name="absence",
            name="cancel_reason",
            field=models.CharField(blank=True, default="", max_length=60),
        ),
    ]
