"""What the admin index page shows beside the app list: leave requests and
TOIL claims that have waited too long, whether email can go at all, and the
emails that did not."""

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from absence.models import EmailFailure, ToilClaim
from absence.services import chase
from accounts.mail import email_is_configured
from people.services import contracts


def _row(r):
    if isinstance(r, ToilClaim):
        return {"claim": r, "url": reverse("absence:toil_decide", args=[r.pk]), "asked": r.requested_at,
                "unit": contracts.unit(r.employment, r.day) or ""}
    return {"a": r, "url": reverse("absence:decide", args=[r.pk]), "asked": r.requested_at}


def dashboard(request, context):
    context["waiting"] = [_row(r) for r in chase.waiting(timezone.localdate())]
    context["chase_after"] = settings.CHASE_AFTER_WORKING_DAYS
    context["email_configured"] = email_is_configured()
    context["email_failures"] = list(EmailFailure.objects.all()[:10])
    return context
