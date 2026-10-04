"""NI numbers stored before the format was enforced (0015): strip the
whitespace and put them in capitals, so a value typed as "ab 123456c" meets
the validator. A value that still does not is left as it is, and reported
by employee pk (never a name or the value) for HR to correct; until then a
save that touches the record says so rather than failing."""
import re

from django.db import migrations

NI = re.compile(r"^[A-Z]{2}[0-9]{6}[A-D]\Z")      # as Employee.ni_number's validator (0016)


def normalise(value):
    """No whitespace anywhere, in capitals (as people.ni.normalise, frozen here)."""
    return "".join((value or "").split()).upper()


def normalise_ni_numbers(apps, schema_editor, out=print):
    """Rewrite each non-blank NI number that normalises to a valid one (or
    to blank, when it was only whitespace); leave the rest. Returns (number changed, pks still not valid) and
    prints the same: counts and pks only."""
    Employee = apps.get_model("people", "Employee")
    changed, bad = 0, []
    for pk, value in Employee.objects.exclude(ni_number="").order_by("pk").values_list("pk", "ni_number"):
        fixed = normalise(value)
        if fixed and not NI.match(fixed):          # whitespace only becomes blank, which is allowed
            bad.append(pk)
        elif fixed != value:
            Employee.objects.filter(pk=pk).update(ni_number=fixed)
            changed += 1
    if changed or bad:
        out(f"\n  NI numbers normalised: {changed}; still not valid: {len(bad)}"
            + (f" (employee pks {', '.join(str(pk) for pk in bad)})" if bad else ""))
    return changed, bad


class Migration(migrations.Migration):
    dependencies = [("people", "0016_ni_and_bank_formats_anchored")]
    operations = [migrations.RunPython(normalise_ni_numbers, migrations.RunPython.noop)]
