"""One door for every email the absence app sends. It never raises into a
page: a failure is logged, recorded as an EmailFailure for the dashboard, and
reported by the return value. Not being configured counts as a failure, so
the dashboard can say emails are not going."""

import logging

from django.conf import settings
from django.core.mail import EmailMessage

from absence.models import EmailFailure
from accounts.mail import TRACKING_OFF, email_is_configured

log = logging.getLogger(__name__)


def record_failure(subject, error, to=()):
    """Subject and a short error, never the body or the recipients: an
    address a relay quotes back in its refusal is scrubbed out."""
    error = str(error)
    for address in to:
        error = error.replace(str(address), "<address>")
    try:
        EmailFailure.objects.create(subject=str(subject)[:200], error=error[:200])
    except Exception:  # noqa: BLE001 - recording a failure must not become one
        log.exception("absence email failure could not be recorded: %s", subject)


def send(subject, body, to, reply_to=None):
    """True when the message was handed to the relay, False otherwise."""
    to = list(to or [])
    try:
        if not email_is_configured():
            record_failure(subject, "email is not configured")
            return False
        if not to:
            record_failure(subject, "no recipients")
            return False
        EmailMessage(subject=subject, body=body, to=to, from_email=settings.DEFAULT_FROM_EMAIL,
                     reply_to=[reply_to] if reply_to else None, headers=TRACKING_OFF).send()
        return True
    except Exception as exc:  # noqa: BLE001 - a relay fault must not surface in a page
        log.exception("absence email failed: %s", subject)
        record_failure(subject, str(exc) or exc.__class__.__name__, to)
        return False
