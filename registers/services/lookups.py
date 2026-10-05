"""Running lookups against the registers: one on demand, or everything due
tonight. The one writer of Lookup rows and of the registration's
denormalised "last" fields; a clear or problem result also records a
Professional registration check through the checks service. Never raises."""
import logging
import random
import time
from datetime import timedelta

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.utils import timezone

from checks.models import Check, CheckType
from checks.services import checks
from compliance.models import ReminderSchedule
from people.services import employments
from registers import adapters
from registers.models import Lookup, RegisterBody, Registration
from registers.services import registrations

# Never log the number, the name or the page: the error class, the body code and the registration pk only.
log = logging.getLogger("hr.registers")
PAUSE_AFTER = 3                 # unreadable results in a row across a body: pause it
PAUSE_BETWEEN_SECONDS = 2       # between two requests to the same body
sleep = time.sleep              # replaced by the tests
COUNTS = ("run", "clear", "problem", "not_found", "name_mismatch", "unreadable", "skipped")
JITTER = (-1, 0, 1)             # days either way, so the load stays spread


def unpause(body):
    """HR's Unpause, or a successful on-demand lookup: the schedule runs again."""
    if body.paused_at is not None:
        body.paused_at = None
        body.save(update_fields=["paused_at"])


def _next_check(today):
    every = ReminderSchedule.get().registration_every_days
    return today + timedelta(days=every + random.choice(JITTER))


def _record_check(registration, outcome, status_text, today):
    check_type = CheckType.objects.get(code="professional_registration")
    result = Check.Outcome.CLEAR if outcome == "clear" else Check.Outcome.NOT_CLEAR
    checks.record(None, registration.employee, check_type, today, result, reference=registration.number,
                  note=f"{registration.body.name}: {status_text}"[:2000])


def _pause_if_dead(body):
    last = list(Lookup.objects.filter(registration__body=body).order_by("-run_at", "-pk")
                .values_list("outcome", flat=True)[:PAUSE_AFTER])
    if len(last) == PAUSE_AFTER and all(o == "unreadable" for o in last) and body.paused_at is None:
        body.paused_at = timezone.now()
        body.save(update_fields=["paused_at"])
        log.warning("register body %s paused after %s unreadable lookups", body.code, PAUSE_AFTER)


def run(registration, trigger, requested_by=None):
    """Look the registration up now. Returns the Lookup written."""
    today = timezone.localdate()
    body = RegisterBody.objects.get(pk=registration.body_id)       # fresh: the pause may have changed
    try:
        result = adapters.lookup(body.code, registration.number, registration.employee.last_name)
    except Exception as exc:  # noqa: BLE001 - belt and braces: adapters.lookup never raises
        result = adapters.Result("unreadable", exc.__class__.__name__, "", "")
    with transaction.atomic():
        lk = Lookup.objects.create(
            registration=registration, trigger=trigger, requested_by=requested_by, outcome=result.outcome,
            status_text=result.status_text[:200], name_on_register=result.name_on_register[:120],
            page_hash=result.page_hash, error=result.status_text[:80] if result.outcome == "unreadable" else "")
        registration.last_outcome, registration.last_status_text = result.outcome, result.status_text[:200]
        registration.last_name_on_register, registration.last_checked_at = result.name_on_register[:120], lk.run_at
        registration.next_check_on = _next_check(today)
        registration.save(update_fields=["last_outcome", "last_status_text", "last_name_on_register",
                                         "last_checked_at", "next_check_on"])
        if result.outcome in ("clear", "problem"):
            try:
                with transaction.atomic():
                    _record_check(registration, result.outcome, result.status_text, today)
            except (ValidationError, ObjectDoesNotExist) as exc:
                log.error("registration %s (%s): check not recorded: %s", registration.pk, body.code,
                          exc.__class__.__name__)
        if result.outcome == "unreadable":
            _pause_if_dead(body)
        elif trigger == Lookup.Trigger.ON_DEMAND:
            unpause(body)
    if result.outcome == "unreadable":
        log.info("registration %s (%s) unreadable: %s", registration.pk, body.code, lk.error)
    return lk


def _due(today):
    """(registration, why-not) for each registration due tonight; why-not is
    "" when it should run, else why it is skipped: the person is not employed
    today, their title no longer needs the body, or the body is off."""
    employed = set(employments.active_on(today).values_list("employee_id", flat=True))
    out = []
    for reg in (Registration.objects.filter(next_check_on__lte=today)
                .select_related("body", "employee").order_by("body__display_order", "pk")):
        body = reg.body
        if reg.employee_id not in employed:
            out.append((reg, "not employed"))
        elif body.pk not in {b.pk for b in registrations.needed(reg.employee, today)}:
            out.append((reg, "not needed"))
        elif not body.active or not body.verified:
            out.append((reg, "body inactive or unverified"))
        else:
            out.append((reg, ""))
    return out


def scheduled(today):
    """Tonight's lookups, one at a time, a pause between two to the same
    body; a body that pauses mid-run is skipped from then on."""
    counts = dict.fromkeys(COUNTS, 0)
    last_body = None
    for reg, why in _due(today):
        reg.body.refresh_from_db(fields=["paused_at"])
        if why or reg.body.paused_at is not None:
            counts["skipped"] += 1
            continue
        if last_body == reg.body_id:
            sleep(PAUSE_BETWEEN_SECONDS)
        last_body = reg.body_id
        lk = run(reg, Lookup.Trigger.SCHEDULED)
        counts["run"] += 1
        counts[lk.outcome] += 1
    return counts
