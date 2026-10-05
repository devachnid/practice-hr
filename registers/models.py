"""Professional registrations: the bodies a position title needs (GMC, the
Welsh medical performers list, NMC, GPhC), each person's number with each
body, and the append-only log of lookups against the register. A clear or
problem lookup also records a Professional registration check
(registers.services.lookups); the lookups here are the register's own
words and the audit trail of each run."""
from django.conf import settings
from django.db import models
from django.utils import timezone


class RegisterBody(models.Model):
    name = models.CharField(max_length=60, unique=True)
    code = models.SlugField(max_length=20, unique=True)
    positions = models.ManyToManyField("people.PositionTitle", blank=True, related_name="register_bodies",
                                       help_text="The titles that need a registration with this body.")
    active = models.BooleanField(default=True)
    verified = models.BooleanField(default=False, editable=False,
                                   help_text="Its parser has saved pages to test against; set by the code, not here.")
    paused_at = models.DateTimeField(null=True, blank=True, editable=False,
                                     help_text="Set when three lookups in a row could not read the page.")
    display_order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "register body"
        verbose_name_plural = "register bodies"

    def __str__(self):
        return self.name

    @property
    def paused(self):
        return self.paused_at is not None


class Lookup(models.Model):
    class Outcome(models.TextChoices):
        CLEAR = "clear", "Clear"
        PROBLEM = "problem", "Problem"
        NOT_FOUND = "not_found", "Not found"
        NAME_MISMATCH = "name_mismatch", "Name does not match"
        UNREADABLE = "unreadable", "Could not read the page"

    class Trigger(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        ON_DEMAND = "on_demand", "On demand"

    registration = models.ForeignKey("registers.Registration", on_delete=models.CASCADE, related_name="lookups")
    run_at = models.DateTimeField(default=timezone.now)
    trigger = models.CharField(max_length=10, choices=Trigger.choices)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="+")
    outcome = models.CharField(max_length=14, choices=Outcome.choices)
    status_text = models.CharField(max_length=200, blank=True, default="")
    name_on_register = models.CharField(max_length=120, blank=True, default="")
    page_hash = models.CharField(max_length=64, blank=True, default="")
    error = models.CharField(max_length=80, blank=True, default="")

    class Meta:
        ordering = ["-run_at", "-pk"]
        verbose_name = "registration lookup"

    def __str__(self):
        return f"{self.registration} {self.get_outcome_display()} {self.run_at:%d %b %Y}"


class Registration(models.Model):
    """One person's number with one body. The last_outcome, last_status_text
    and last_name_on_register fields are the latest READABLE lookup's: an
    unreadable one sets last_checked_at and last_unreadable_at and leaves
    them, so a site that is down never hides a standing problem."""
    employee = models.ForeignKey("people.Employee", on_delete=models.PROTECT, related_name="registrations")
    body = models.ForeignKey(RegisterBody, on_delete=models.PROTECT, related_name="registrations")
    number = models.CharField(max_length=20)
    next_check_on = models.DateField()
    last_outcome = models.CharField(max_length=14, choices=Lookup.Outcome.choices, blank=True, default="")
    last_status_text = models.CharField(max_length=200, blank=True, default="")
    last_name_on_register = models.CharField(max_length=120, blank=True, default="")
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_unreadable_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the latest lookup could not read the page; cleared by a readable one.")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["employee", "body"], name="registration_one_per_body")]
        ordering = ["body__display_order", "pk"]

    def __str__(self):
        return f"{self.employee.name}: {self.body} {self.number}"
