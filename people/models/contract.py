from django.core.exceptions import ValidationError
from django.db import models

from .employment import Employment


class ContractType(models.Model):
    """Configurable: adding a kind of staff is a row, not a release."""
    class Unit(models.TextChoices):
        SESSIONS = "sessions", "Sessions"
        HOURS = "hours", "Hours"

    name = models.CharField(max_length=60, unique=True)
    unit = models.CharField(max_length=8, choices=Unit.choices)
    full_time_weekly = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text="What full time is in this unit: 9 sessions, 37.5 hours. FTE is derived from it.")
    display_order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class Contract(models.Model):
    """A dated contractual arrangement. Rows may overlap; the contracted
    amount on a day is their sum (people.services.contracts)."""
    class Basis(models.TextChoices):
        PERMANENT = "permanent", "Permanent"
        FIXED_TERM = "fixed_term", "Fixed term"

    employment = models.ForeignKey(Employment, on_delete=models.PROTECT, related_name="contracts")
    contract_type = models.ForeignKey(ContractType, on_delete=models.PROTECT, related_name="contracts")
    basis = models.CharField(max_length=10, choices=Basis.choices, default=Basis.PERMANENT)
    from_date = models.DateField()
    to_date = models.DateField(null=True, blank=True)
    weekly_amount = models.DecimalField(max_digits=5, decimal_places=2)
    notes = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["from_date", "id"]

    def __str__(self):
        return f"{self.weekly_amount} {self.contract_type.unit}/week {self.get_basis_display().lower()}"

    def clean(self):
        super().clean()
        if self.basis == self.Basis.FIXED_TERM and not self.to_date:
            raise ValidationError({"to_date": "A fixed-term contract needs an end date."})
        if self.to_date and self.to_date < self.from_date:
            raise ValidationError({"to_date": "End date is before the start date."})
        if self.employment_id:
            emp = self.employment
            if self.from_date < emp.start_date or (emp.end_date and self.from_date > emp.end_date):
                raise ValidationError({"from_date": "Outside the employment's dates."})

    def is_active_on(self, day):
        return self.from_date <= day and (self.to_date is None or day <= self.to_date)


class PayRecord(models.Model):
    """Dated pay, for the payroll changes report only. No arithmetic."""
    class Basis(models.TextChoices):
        ANNUAL = "annual", "Annual salary"
        HOURLY = "hourly", "Hourly rate"
        PER_SESSION = "session", "Per session"

    employment = models.ForeignKey(Employment, on_delete=models.PROTECT, related_name="pay_records")
    from_date = models.DateField()
    to_date = models.DateField(null=True, blank=True)
    basis = models.CharField(max_length=8, choices=Basis.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        ordering = ["from_date"]

    def __str__(self):
        return f"{self.get_basis_display()} {self.amount} from {self.from_date:%d %b %Y}"
