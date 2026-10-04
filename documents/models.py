from django.conf import settings
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
