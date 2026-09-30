from django.core.exceptions import ValidationError
from django.db import models

# The family-leave types: they carry expected and actual dates and KIT days.
FAMILY_CODES = ("MAT", "PAT", "SPL", "ADOPT")


class AbsenceType(models.Model):
    """Configurable. The flags decide the workflow; nothing in the code
    tests a type's name."""
    name = models.CharField(max_length=40, unique=True)
    code = models.CharField(max_length=8, unique=True)
    paid = models.BooleanField(default=True)
    uses_pot = models.BooleanField(
        default=False, help_text="Draws on an allowance. Needs a policy per contract type, unless it is earned.")
    accrues = models.BooleanField(
        default=True, help_text="Off for types that are earned, such as TOIL: pots start at zero and only "
                                "claims, adjustments and carry-ins add to them")
    earned_expires_after_days = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="For earned types: how many days after the day it was earned a lot "
                                         "may be used. Blank means never.")
    needs_approval = models.BooleanField(default=True)
    self_certified = models.BooleanField(
        default=False, help_text="The employee records it themselves, after the fact.")
    calendar_label = models.CharField(
        max_length=20, default="Away",
        help_text="What colleagues see on the calendar: Leave, Sick, Away.")
    payroll_reportable = models.BooleanField(default=False)
    health_sensitive = models.BooleanField(
        default=False, help_text="Category and dates are restricted to HR admins and the line manager.")
    display_order = models.PositiveIntegerField(default=100)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.accrues and self.earned_expires_after_days is not None:
            raise ValidationError({"earned_expires_after_days":
                                   "Only for a type that does not accrue: turn Accrues off, or leave this blank."})

    @property
    def is_family(self):
        return self.code in FAMILY_CODES
