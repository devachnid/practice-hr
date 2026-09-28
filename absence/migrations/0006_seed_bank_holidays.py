from datetime import date

from django.db import migrations

EW = [
    (date(2026, 1, 1), "New Year's Day"), (date(2026, 4, 3), "Good Friday"),
    (date(2026, 4, 6), "Easter Monday"), (date(2026, 5, 4), "Early May bank holiday"),
    (date(2026, 5, 25), "Spring bank holiday"), (date(2026, 8, 31), "Summer bank holiday"),
    (date(2026, 12, 25), "Christmas Day"), (date(2026, 12, 28), "Boxing Day (substitute)"),
    (date(2027, 1, 1), "New Year's Day"), (date(2027, 3, 26), "Good Friday"),
    (date(2027, 3, 29), "Easter Monday"), (date(2027, 5, 3), "Early May bank holiday"),
    (date(2027, 5, 31), "Spring bank holiday"), (date(2027, 8, 30), "Summer bank holiday"),
    (date(2027, 12, 27), "Christmas Day (substitute)"), (date(2027, 12, 28), "Boxing Day (substitute)"),
    (date(2028, 1, 3), "New Year's Day (substitute)"), (date(2028, 4, 14), "Good Friday"),
    (date(2028, 4, 17), "Easter Monday"), (date(2028, 5, 1), "Early May bank holiday"),
    (date(2028, 5, 29), "Spring bank holiday"), (date(2028, 8, 28), "Summer bank holiday"),
    (date(2028, 12, 25), "Christmas Day"), (date(2028, 12, 26), "Boxing Day"),
]


def seed(apps, schema_editor):
    BankHoliday = apps.get_model("absence", "BankHoliday")
    for d, name in EW:
        BankHoliday.objects.get_or_create(date=d, nation="EW", defaults={"name": name})


class Migration(migrations.Migration):
    dependencies = [("absence", "0005_calendar_pot_ledger_absence")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
