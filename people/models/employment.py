from django.core.exceptions import ValidationError
from django.db import models

from .employee import Employee


class Team(models.Model):
    name = models.CharField(max_length=60, unique=True)
    display_order = models.PositiveIntegerField(default=100)
    min_present = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Warn an approver when agreeing a request would leave fewer "
                  "of this team present on a day. Blank means never warn.")

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class Employment(models.Model):
    """One dated spell of employment. A returner gets a new row; history
    stays on the old one. Spells for one employee never overlap
    (people.services.employments.start enforces it)."""
    class LeavingReason(models.TextChoices):
        RESIGNED = "resigned", "Resigned"
        RETIRED = "retired", "Retired"
        END_OF_FIXED_TERM = "fixed_term", "End of fixed term"
        DISMISSED = "dismissed", "Dismissed"
        REDUNDANCY = "redundancy", "Redundancy"
        DEATH = "death", "Death in service"
        OTHER = "other", "Other"

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="employments")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    leaving_reason = models.CharField(
        max_length=12, choices=LeavingReason.choices, blank=True, default="")
    continuous_service_date = models.DateField(
        help_text="Defaults to the start date. Earlier when reckonable service "
                  "carries over from elsewhere in the NHS or an earlier spell. "
                  "Service tiers read this, never the start date.")

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        end = f"{self.end_date:%d %b %Y}" if self.end_date else "present"
        return f"{self.employee} {self.start_date:%d %b %Y} to {end}"

    def clean(self):
        super().clean()
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date is before the start date."})
        if self.end_date and not self.leaving_reason:
            raise ValidationError({"leaving_reason": "Say why the employment ended."})

    def save(self, *args, **kwargs):
        if not self.continuous_service_date:
            self.continuous_service_date = self.start_date
        super().save(*args, **kwargs)

    def is_active_on(self, day):
        if day < self.start_date:
            return False
        return self.end_date is None or day <= self.end_date
