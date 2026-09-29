from django.db import models


class EmailFailure(models.Model):
    """An absence email that did not go: the relay refused it, or email is not
    configured. The subject and a short error only, never the body or the
    recipients. The dashboard lists the latest."""
    created_at = models.DateTimeField(auto_now_add=True)
    subject = models.CharField(max_length=200)
    error = models.CharField(max_length=200)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.subject}: {self.error}"
