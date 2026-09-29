from django.conf import settings
from django.db import models


class PayrollRun(models.Model):
    """One generation of the payroll changes report: who ran it, when, for
    which period, where the file went (relative to MEDIA_ROOT) and how many
    rows each sheet held. The file is one per month and is replaced when the
    month is generated again; the runs are the record of each generation."""
    period_start = models.DateField()
    period_end = models.DateField()
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    path = models.CharField(max_length=200)
    counts = models.JSONField(default=dict)

    class Meta:
        ordering = ["-period_start", "-generated_at"]

    def __str__(self):
        return f"Payroll {self.period_start:%b %Y} ({self.generated_at:%d %b %Y %H:%M})"
