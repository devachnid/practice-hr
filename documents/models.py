from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class File(models.Model):
    """One stored document. `path` is opaque under MEDIA_ROOT; the original
    name is kept for the download. Never edited, only superseded."""
    class Category(models.TextChoices):
        CONTRACT = "contract", "Contract"
        OFFER = "offer", "Offer letter"
        IDENTITY = "identity", "Identity"
        CERTIFICATE = "certificate", "Certificate"
        OCCUPATIONAL_HEALTH = "occupational_health", "Occupational health"
        CORRESPONDENCE = "correspondence", "Correspondence"
        POLICY = "policy", "Policy"
        OTHER = "other", "Other"

    employee = models.ForeignKey("people.Employee", null=True, blank=True, on_delete=models.PROTECT,
                                 related_name="files")
    category = models.CharField(max_length=20, choices=Category.choices)
    title = models.CharField(max_length=120)
    path = models.CharField(max_length=200, unique=True)
    original_name = models.CharField(max_length=200)
    content_type = models.CharField(max_length=80)
    size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    hr_only = models.BooleanField(default=False)
    superseded_by = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="supersedes")
    superseded_note = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["-uploaded_at", "-id"]

    def __str__(self):
        return self.title


class Policy(models.Model):
    """A practice policy people sign. Who must sign follows the title of
    their primary position; no titles means everyone."""
    title = models.CharField(max_length=120, unique=True)
    positions = models.ManyToManyField("people.PositionTitle", blank=True, related_name="policies",
                                       help_text="Leave empty for everyone.")
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "policies"
        ordering = ["title"]

    def __str__(self):
        return self.title


class PolicyVersion(models.Model):
    """One issued text of a policy; the latest by issue date is the one owed.
    Its file has no person (File.employee is None)."""
    policy = models.ForeignKey(Policy, on_delete=models.PROTECT, related_name="versions")
    label = models.CharField(max_length=40)
    file = models.ForeignKey(File, on_delete=models.PROTECT, related_name="+")
    issued_on = models.DateField()
    sign_within_days = models.PositiveSmallIntegerField(default=14)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-issued_on", "-id"]
        constraints = [models.UniqueConstraint(fields=["policy", "label"], name="one_label_per_policy")]

    def __str__(self):
        return f"{self.policy} ({self.label})"


class Signature(models.Model):
    """A person's signature of one version: the exact sentence they ticked,
    how they proved it was them, and from where. Never changed."""
    class Method(models.TextChoices):
        PASSWORD = "password", "Password"
        PASSKEY = "passkey", "Passkey"

    employee = models.ForeignKey("people.Employee", on_delete=models.PROTECT, related_name="signatures")
    version = models.ForeignKey(PolicyVersion, on_delete=models.PROTECT, related_name="signatures")
    signed_at = models.DateTimeField(auto_now_add=True)
    method = models.CharField(max_length=8, choices=Method.choices)
    confirmation_text = models.CharField(max_length=300)
    ip_address = models.CharField(max_length=45, blank=True, default="")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["employee", "version"], name="one_signature_per_version")]

    def __str__(self):
        return f"{self.employee}: {self.version}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("A signature is never changed.")
        super().save(*args, **kwargs)
