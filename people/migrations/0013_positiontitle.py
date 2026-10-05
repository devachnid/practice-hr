import django.db.models.deletion
from django.db import migrations, models


def forwards(apps, schema_editor):
    Position = apps.get_model("people", "Position")
    PositionTitle = apps.get_model("people", "PositionTitle")
    for name in sorted(set(Position.objects.values_list("title", flat=True))):
        row, _ = PositionTitle.objects.get_or_create(name=name)
        Position.objects.filter(title=name).update(title_ref=row)


def backwards(apps, schema_editor):
    Position = apps.get_model("people", "Position")
    for position in Position.objects.select_related("title_ref"):
        position.title = position.title_ref.name
        position.save(update_fields=["title"])


class Migration(migrations.Migration):

    dependencies = [
        ("people", "0012_employee_work_email_help_text_rota_api"),
    ]

    operations = [
        migrations.CreateModel(
            name="PositionTitle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, unique=True)),
                ("display_order", models.PositiveIntegerField(default=100)),
            ],
            options={"ordering": ["display_order", "name"]},
        ),
        migrations.AddField(
            model_name="position",
            name="title_ref",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="positions", to="people.positiontitle"),
        ),
        migrations.RunPython(forwards, backwards),
        # Going backwards, RemoveField re-adds the text column; the temporary
        # default lets that happen on rows that already exist, and the
        # RunPython above then fills it from the title rows.
        migrations.AlterField(
            model_name="position", name="title", field=models.CharField(default="", max_length=80)),
        migrations.RemoveField(model_name="position", name="title"),
        migrations.RenameField(model_name="position", old_name="title_ref", new_name="title"),
        migrations.AlterField(
            model_name="position",
            name="title",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="positions", to="people.positiontitle"),
        ),
    ]
