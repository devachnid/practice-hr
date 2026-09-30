"""TOIL is earned, not accrued, so it has no policy.

Two fields on the absence type: `accrues` (off for a type that is earned:
its pots start at zero and only claims, adjustments and carry-ins add to
them; the pot borrows the annual-leave policy's leave year and rounding,
policies.policy_for) and `earned_expires_after_days` (how long an earned lot
may be used, which the TOIL policy's `toil_expires_after_days` held).

The TOIL type is set not to accrue, with 365 days, unless a TOIL policy said
otherwise: then the days of the one in force latest (the newest
effective_from) are copied onto the type, while the type still holds the
default. A TOIL policy saying "never" (blank) is not copied: TOIL expires
after twelve months. Every TOIL policy (and its tiers) is then deleted, and
the policy's TOIL field dropped. Reverse puts the field back, empty, and
the type's fields go; the deleted policies are not restored.
"""

from django.db import migrations, models

DEFAULT_DAYS = 365


def forward(apps, schema_editor):
    AbsenceType = apps.get_model("absence", "AbsenceType")
    Policy = apps.get_model("absence", "Policy")
    toil = AbsenceType.objects.filter(code="TOIL").first()
    if toil is None:
        return
    toil.accrues = False
    if toil.earned_expires_after_days is None:
        toil.earned_expires_after_days = DEFAULT_DAYS
    rows = Policy.objects.filter(absence_type=toil)
    days = (rows.filter(toil_expires_after_days__isnull=False).order_by("-effective_from", "-pk")
            .values_list("toil_expires_after_days", flat=True).first())
    if days is not None and toil.earned_expires_after_days == DEFAULT_DAYS:
        toil.earned_expires_after_days = days
    toil.save(update_fields=["accrues", "earned_expires_after_days"])
    rows.delete()                                       # their tiers go with them (CASCADE)


class Migration(migrations.Migration):

    dependencies = [
        ("absence", "0012_seed_standard_contract"),
    ]

    operations = [
        migrations.AddField(
            model_name="absencetype",
            name="accrues",
            field=models.BooleanField(
                default=True, help_text="Off for types that are earned, such as TOIL: pots start at zero and only "
                                        "claims, adjustments and carry-ins add to them"),
        ),
        migrations.AddField(
            model_name="absencetype",
            name="earned_expires_after_days",
            field=models.PositiveSmallIntegerField(
                blank=True, null=True, help_text="For earned types: how many days after the day it was earned a "
                                                 "lot may be used. Blank means never."),
        ),
        migrations.RunPython(forward, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="policy",
            name="toil_expires_after_days",
        ),
        migrations.AlterField(
            model_name="absencetype",
            name="uses_pot",
            field=models.BooleanField(
                default=False,
                help_text="Draws on an allowance. Needs a policy per contract type, unless it is earned."),
        ),
    ]
