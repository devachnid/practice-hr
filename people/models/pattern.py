from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .employment import Employment


class WorkingPattern(models.Model):
    """A dated version of the whole working week, in the employment's unit.
    The master; the rota reads it. cycle_weeks is always 1 in this release."""
    employment = models.ForeignKey(Employment, on_delete=models.PROTECT, related_name="patterns")
    effective_from = models.DateField()
    cycle_weeks = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["-effective_from"]
        constraints = [models.UniqueConstraint(
            fields=["employment", "effective_from"], name="one_pattern_per_employment_per_date")]

    def __str__(self):
        return f"Pattern from {self.effective_from:%d %b %Y}"


class PatternDay(models.Model):
    pattern = models.ForeignKey(WorkingPattern, on_delete=models.CASCADE, related_name="days")
    weekday = models.PositiveSmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(6)])
    week_in_cycle = models.PositiveSmallIntegerField(default=0)
    am_units = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    pm_units = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        ordering = ["week_in_cycle", "weekday"]
        constraints = [models.UniqueConstraint(
            fields=["pattern", "weekday", "week_in_cycle"], name="one_day_per_pattern")]

    def units(self, half):
        return self.am_units if half == "AM" else self.pm_units
