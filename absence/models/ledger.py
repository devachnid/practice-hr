from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from people.models import Employment

from .types import AbsenceType


class Pot(models.Model):
    """One employment's allowance for one type and one leave year. No
    balance field: the balance is the sum of its entries."""
    employment = models.ForeignKey(Employment, on_delete=models.PROTECT, related_name="pots")
    absence_type = models.ForeignKey(AbsenceType, on_delete=models.PROTECT, related_name="pots")
    year_start = models.DateField()
    year_end = models.DateField()
    unit = models.CharField(max_length=8)

    class Meta:
        ordering = ["-year_start"]
        constraints = [models.UniqueConstraint(
            fields=["employment", "absence_type", "year_start"], name="one_pot_per_year")]

    def __str__(self):
        return f"{self.employment.employee} {self.absence_type} {self.year_start:%Y}/{self.year_end:%y}"


class LedgerEntry(models.Model):
    """The only thing that changes a pot. Never edited or deleted."""
    class Kind(models.TextChoices):
        ENTITLEMENT = "entitlement", "Entitlement"
        REVISION = "revision", "Entitlement revised"
        CARRY_IN = "carry_in", "Carried in"
        EXPIRY = "expiry", "Expired"
        BOOKING = "booking", "Booked"
        CANCELLATION = "cancellation", "Cancelled"
        TOIL_EARNED = "toil_earned", "TOIL earned"
        TOIL_TAKEN = "toil_taken", "TOIL taken"
        ADJUSTMENT = "adjustment", "Adjustment"

    pot = models.ForeignKey(Pot, on_delete=models.PROTECT, related_name="entries")
    date = models.DateField()
    kind = models.CharField(max_length=12, choices=Kind.choices)
    units = models.DecimalField(max_digits=7, decimal_places=2)
    absence = models.ForeignKey("absence.Absence", null=True, blank=True,
                                on_delete=models.PROTECT, related_name="ledger_entries")
    note = models.CharField(max_length=200, blank=True, default="")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "id"]
        verbose_name_plural = "ledger entries"

    def __str__(self):
        return f"{self.date:%d %b %Y} {self.get_kind_display()} {self.units:+}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("Ledger entries are never edited; write a new line.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Ledger entries are never deleted; write a new line.")
