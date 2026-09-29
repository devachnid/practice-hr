from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class AuditEntry(models.Model):
    """One row per field changed by a service, and one per view of a
    restricted section. Never edited, never deleted."""
    class Kind(models.TextChoices):
        CHANGE = "change", "Change"
        VIEWED = "viewed", "Viewed"

    # PROTECT: a login that has written to the log cannot be deleted, so the
    # log never loses who did what (deactivate the login instead). Null is
    # for writes with no person behind them.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")
    # The actor's email as it was at the write, kept as text: the login's
    # email can be changed later, and this is what the entry says.
    actor_email = models.CharField(max_length=254, blank=True, default="")
    at = models.DateTimeField(auto_now_add=True)
    kind = models.CharField(max_length=6, choices=Kind.choices)
    model = models.CharField(max_length=60)       # "people.employee"
    object_id = models.PositiveBigIntegerField()
    field = models.CharField(max_length=60)       # field name, or the section viewed
    before = models.TextField(blank=True, default="")
    after = models.TextField(blank=True, default="")
    note = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["-at", "-id"]
        verbose_name_plural = "audit entries"
        indexes = [models.Index(fields=["model", "object_id"])]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("Audit entries are never edited.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit entries are never deleted.")

    def __str__(self):
        return f"{self.at:%Y-%m-%d %H:%M} {self.kind} {self.model}#{self.object_id} {self.field}"
