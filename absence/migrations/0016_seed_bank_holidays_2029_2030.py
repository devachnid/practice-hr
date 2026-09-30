from datetime import date

from django.db import migrations

EW = [
    (date(2029, 1, 1), "New Year's Day"), (date(2029, 3, 30), "Good Friday"),
    (date(2029, 4, 2), "Easter Monday"), (date(2029, 5, 7), "Early May bank holiday"),
    (date(2029, 5, 28), "Spring bank holiday"), (date(2029, 8, 27), "Summer bank holiday"),
    (date(2029, 12, 25), "Christmas Day"), (date(2029, 12, 26), "Boxing Day"),
    (date(2030, 1, 1), "New Year's Day"), (date(2030, 4, 19), "Good Friday"),
    (date(2030, 4, 22), "Easter Monday"), (date(2030, 5, 6), "Early May bank holiday"),
    (date(2030, 5, 27), "Spring bank holiday"), (date(2030, 8, 26), "Summer bank holiday"),
    (date(2030, 12, 25), "Christmas Day"), (date(2030, 12, 26), "Boxing Day"),
]


def seed(apps, schema_editor):
    BankHoliday = apps.get_model("absence", "BankHoliday")
    for d, name in EW:
        BankHoliday.objects.get_or_create(date=d, nation="EW", defaults={"name": name})


class Migration(migrations.Migration):
    dependencies = [("absence", "0015_absence_cancel_reason")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
