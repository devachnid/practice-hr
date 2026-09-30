"""The emails the absence workflow sends, one function per event. Each
returns whether the message went and never raises: address lookup and
rendering are inside the same guard as the send."""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.utils import timezone

from absence import mail
from people.services import access, contracts

log = logging.getLogger(__name__)

# The pages a decision is made on. The routes are registered at exactly these paths.
DECIDE_PATH = "/absence/decide/{pk}/"
CLAIM_DECIDE_PATH = "/absence/toil/{pk}/decide/"


def decide_url(absence):
    return settings.SITE_URL.rstrip("/") + DECIDE_PATH.format(pk=absence.pk)


def claim_decide_url(claim):
    return settings.SITE_URL.rstrip("/") + CLAIM_DECIDE_PATH.format(pk=claim.pk)


def hr_admin_addresses():
    User = get_user_model()
    return list(User.objects.filter(is_hr_admin=True, is_active=True).values_list("email", flat=True))


def approver_addresses(absence):
    """The routed manager's work email, or every active HR admin's but the
    requester's own (an HR admin's request goes to the other HR admins).
    `absence` is anything with an employment: a TOIL claim is routed the same."""
    manager = access.route_for(absence.employment, timezone.localdate())
    if manager is not None and manager.work_email:
        return [manager.work_email]
    employee = absence.employment.employee
    own = {address.lower() for address in (employee.work_email, getattr(employee.user, "email", "")) if address}
    return [address for address in hr_admin_addresses() if address.lower() not in own]


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
        _render("submitted", a=absence, url=decide_url(absence),
                unit=contracts.unit(absence.employment, absence.start_date) or ""),
        approver_addresses(absence), _requester_address(absence)))


def request_decided(absence):
    return _deliver(f"Your {absence.absence_type} request was {absence.get_status_display().lower()}", lambda: (
        _render("decided", a=absence), [_requester_address(absence)], None))


def absence_cancelled(absence):
    name = absence.employment.employee.name
    return _deliver(f"{name} cancelled {absence.absence_type}", lambda: (
        _render("cancelled", a=absence), approver_addresses(absence), None))


def requests_waiting(rows):
    """The chase's one email: the leave requests and TOIL claims that have
    waited too long (chase.waiting), one line each with its decide link."""
    from absence.models import ToilClaim
    rows = list(rows)
    claims = sum(isinstance(r, ToilClaim) for r in rows)
    parts = [f"{n} {what}(s)" for n, what in ((len(rows) - claims, "leave request"), (claims, "TOIL claim")) if n]
    return _deliver(f"{' and '.join(parts)} waiting", lambda: (
        _render("waiting", rows=[{"claim": r, "url": claim_decide_url(r), "unit": _claim_unit(r)}
                                 if isinstance(r, ToilClaim) else {"a": r, "url": decide_url(r)} for r in rows]),
        hr_admin_addresses(), None))


def _claim_unit(claim):
    return contracts.unit(claim.employment, claim.day) or ""


def claim_submitted(claim):
    name = claim.employment.employee.name
    return _deliver(f"TOIL claim from {name}", lambda: (
        _render("toil_submitted", c=claim, url=claim_decide_url(claim), unit=_claim_unit(claim)),
        approver_addresses(claim), _requester_address(claim)))


def claim_decided(claim):
    return _deliver(f"Your TOIL claim was {claim.get_status_display().lower()}", lambda: (
        _render("toil_decided", c=claim, unit=_claim_unit(claim)), [_requester_address(claim)], None))
