"""The emails the absence workflow sends, one function per event. Each
returns whether the message went and never raises: address lookup and
rendering are inside the same guard as the send."""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.utils import timezone

from absence import mail
from people.services import access

log = logging.getLogger(__name__)

# The page a decision is made on. The route is registered at exactly this path.
DECIDE_PATH = "/absence/decide/{pk}/"


def decide_url(absence):
    return settings.SITE_URL.rstrip("/") + DECIDE_PATH.format(pk=absence.pk)


def hr_admin_addresses():
    User = get_user_model()
    return list(User.objects.filter(is_hr_admin=True, is_active=True).values_list("email", flat=True))


def approver_addresses(absence):
    """The routed manager's work email, or every active HR admin's."""
    manager = access.route_for(absence.employment, timezone.localdate())
    if manager is not None and manager.work_email:
        return [manager.work_email]
    return hr_admin_addresses()


def _requester_address(absence):
    return absence.employment.employee.work_email


def _render(name, **context):
    return render_to_string(f"absence/email/{name}.txt", context)


def _deliver(subject, build):
    """`build` returns (body, to, reply_to). Anything it raises is logged and
    recorded, and the event's page carries on."""
    try:
        body, to, reply_to = build()
    except Exception as exc:  # noqa: BLE001 - a template or data fault must not reach a page
        log.exception("absence email not built: %s", subject)
        mail.record_failure(subject, f"not built: {exc.__class__.__name__}")
        return False
    return mail.send(subject, body, to, reply_to=reply_to)


def request_submitted(absence):
    name = absence.employment.employee.name
    return _deliver(f"Leave request from {name}", lambda: (
        _render("submitted", a=absence, url=decide_url(absence)),
        approver_addresses(absence), _requester_address(absence)))


def request_decided(absence):
    return _deliver(f"Your {absence.absence_type} request was {absence.get_status_display().lower()}", lambda: (
        _render("decided", a=absence), [_requester_address(absence)], None))


def absence_cancelled(absence):
    name = absence.employment.employee.name
    return _deliver(f"{name} cancelled {absence.absence_type}", lambda: (
        _render("cancelled", a=absence), approver_addresses(absence), None))


def requests_waiting(absences):
    absences = list(absences)
    return _deliver(f"{len(absences)} leave request(s) waiting", lambda: (
        _render("waiting", rows=[{"a": a, "url": decide_url(a)} for a in absences]),
        hr_admin_addresses(), None))
