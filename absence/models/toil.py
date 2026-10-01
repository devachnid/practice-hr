from django.conf import settings
from django.db import models
from django.db.models import Q

from people.models import Employment

from .absence import Absence
from .ledger import LedgerEntry


class ToilClaim(models.Model):
    """Time worked in lieu, claimed for one day and decided by the person's
    approver as leave is. Approving writes the TOIL-earned ledger line
    (`earned`), dated the day worked; declining or cancelling writes
    nothing. Changed only by absence.services.toil."""
    Status = Absence.Status

    employment = models.ForeignKey(Employment, on_delete=models.PROTECT, related_name="toil_claims")
    day = models.DateField(help_text="The day the time was worked.")
    units = models.DecimalField(max_digits=5, decimal_places=2)
    reason = models.CharField(max_length=200)
    status = models.CharField(max_length=9, choices=Absence.Status.choices, default=Absence.Status.REQUESTED)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_comment = models.CharField(max_length=300, blank=True, default="")
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="+")
    cancelled_at = models.DateTimeField(null=True, blank=True)
    earned = models.OneToOneField(LedgerEntry, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name="toil_claim")
    chased_at = models.DateTimeField(null=True, blank=True)   # when HR were last nagged about this claim

    class Meta:
        verbose_name = "TOIL claim"
        verbose_name_plural = "TOIL claims"
        ordering = ["-day", "-id"]
        constraints = [models.CheckConstraint(condition=Q(units__gt=0), name="toil_claim_units_positive")]

    def __str__(self):
        from people.services import contracts
        unit = contracts.unit(self.employment, self.day) or "units"
        return f"{self.employment.employee.name}: {self.units.normalize():f} {unit} on {self.day:%d %b %Y}"
