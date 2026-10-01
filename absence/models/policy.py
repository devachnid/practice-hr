from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from people.models import ContractType

from .types import ZERO_EXPIRY, AbsenceType


class Policy(models.Model):
    """The allowance rules as data, per contract type and pot-backed type."""
    class Basis(models.TextChoices):
        FIXED = "fixed", "Fixed date"
        ANNIVERSARY = "anniversary", "Anniversary of start"

    class Accrual(models.TextChoices):
        DAILY = "daily", "Daily"
        MONTHLY = "monthly", "Monthly twelfths"

    class BankHolidays(models.TextChoices):
        CLOSED_NOT_CHARGED = "closed", "Practice closed, not charged"
        PRO_RATA_POT = "pot", "Pro-rated bank holiday pot"
        INCLUDED_IN_ANNUAL = "annual", "Included in annual leave"

    contract_type = models.ForeignKey(ContractType, on_delete=models.PROTECT, related_name="policies")
    absence_type = models.ForeignKey(AbsenceType, on_delete=models.PROTECT, related_name="policies",
                                     limit_choices_to={"uses_pot": True})
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    weeks_per_year = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal("5.6"),
        help_text="Entitlement in weeks; multiplied by the contracted weekly amount.")
    leave_year_basis = models.CharField(max_length=11, choices=Basis.choices, default=Basis.FIXED)
    year_start_month = models.PositiveSmallIntegerField(default=4)
    year_start_day = models.PositiveSmallIntegerField(default=1)
    carry_over_max_weeks = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    carry_over_expires_after_days = models.PositiveSmallIntegerField(null=True, blank=True)
    rounding = models.DecimalField(
        max_digits=3, decimal_places=2, default=Decimal("0.25"),
        help_text="Entitlements and costs are rounded to this step: 0.25 hour, 0.5 session.")
    bank_holiday_handling = models.CharField(
        max_length=6, choices=BankHolidays.choices, default=BankHolidays.CLOSED_NOT_CHARGED)
    accrual = models.CharField(
        max_length=7, choices=Accrual.choices, default=Accrual.DAILY,
        help_text="Daily: earned day by day across the leave year. Monthly twelfths: a twelfth of the year's "
                  "entitlement for each month of the leave year employed, a part month counting in full.")

    class Meta:
        verbose_name_plural = "policies"
        ordering = ["contract_type", "absence_type", "-effective_from"]

    def __str__(self):
        return f"{self.contract_type} / {self.absence_type} from {self.effective_from:%d %b %Y}"

    def clean(self):
        super().clean()
        if self.absence_type_id and not self.absence_type.uses_pot:
            raise ValidationError({"absence_type": "Only pot-backed types have a policy."})
        if self.absence_type_id and not self.absence_type.accrues:
            raise ValidationError({"absence_type": f"{self.absence_type} is earned, not accrued; it needs no "
                                                   f"policy — set its expiry on the absence type."})
        if self.carry_over_expires_after_days == 0:
            raise ValidationError({"carry_over_expires_after_days": ZERO_EXPIRY})
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "Ends before it starts."})
        if not 1 <= (self.year_start_month or 0) <= 12:
            raise ValidationError({"year_start_month": "A month is 1 to 12."})
        try:
            date(2001, self.year_start_month, self.year_start_day or 0)   # a common year: no 29 February
        except ValueError:
            raise ValidationError({"year_start_day": "Not a day of that month."}) from None

    def is_active_on(self, day):
        return self.effective_from <= day and (self.effective_to is None or day <= self.effective_to)


class PolicyTier(models.Model):
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name="tiers")
    after_years = models.PositiveSmallIntegerField()
    extra_weeks = models.DecimalField(max_digits=4, decimal_places=2)

    class Meta:
        ordering = ["after_years"]
        constraints = [models.UniqueConstraint(fields=["policy", "after_years"], name="one_tier_per_years")]

    def __str__(self):
        return f"+{self.extra_weeks} weeks after {self.after_years} years"
