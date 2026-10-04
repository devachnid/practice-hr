"""Dated pre-employment and recurring checks. A CheckType says which
position titles need it and how long it lasts; a Check is one recorded
instance. Checks are append-only: a renewal is a new row, and the latest
by done_on is the one that counts (checks.services.checks.state)."""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class CheckType(models.Model):
    class Evidence(models.TextChoices):
        NONE = "none", "Nothing to attach"
        FILE = "file", "A file"
        REFERENCE = "reference", "A reference number"

    name = models.CharField(max_length=60, unique=True)
    code = models.SlugField(max_length=40, unique=True)
    validity_months = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1)],
                                                       help_text="Blank: a one-off check that never expires.")
    evidence = models.CharField(max_length=9, choices=Evidence.choices, default=Evidence.NONE)
    remind_person = models.BooleanField(default=False, help_text="Remind the person as well as HR.")
    positions = models.ManyToManyField("people.PositionTitle", blank=True, related_name="check_types",
                                       help_text="The titles that need this check.")
    display_order = models.PositiveIntegerField(default=100)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class Check(models.Model):
    class Outcome(models.TextChoices):
        CLEAR = "clear", "Clear"
        CLEAR_WITH_NOTES = "clear_with_notes", "Clear with notes"
        NOT_CLEAR = "not_clear", "Not clear"

    class DbsLevel(models.TextChoices):
        BASIC = "basic", "Basic"
        STANDARD = "standard", "Standard"
        ENHANCED = "enhanced", "Enhanced"
        ENHANCED_BARRED = "enhanced_barred", "Enhanced with barred lists"

    employee = models.ForeignKey("people.Employee", on_delete=models.PROTECT, related_name="checks")
    check_type = models.ForeignKey(CheckType, on_delete=models.PROTECT, related_name="checks")
    done_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    outcome = models.CharField(max_length=16, choices=Outcome.choices, blank=True, default="")
    reference = models.CharField(max_length=60, blank=True, default="")
    note = models.TextField(blank=True, default="")
    evidence = models.ForeignKey("documents.File", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    dbs_level = models.CharField(max_length=15, choices=DbsLevel.choices, blank=True, default="")
    dbs_update_service = models.BooleanField(default=False)
    awaiting = models.BooleanField(default=False, help_text="Asked of the person; not yet a recorded check.")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-done_on", "-id"]

    def __str__(self):
        return f"{self.check_type} for {self.employee}"
