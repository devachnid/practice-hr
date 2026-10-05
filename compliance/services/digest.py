"""The morning digest: every app's due items, filtered by the reminder
schedule and the sent log, one email per recipient with a section per
person. Only what a recipient was given by a producer is in their email:
their own items, their reports' (a manager), or everyone's (HR).

It assumes one run a day (hr_nightly): a second run the same day sends
only what the first did not. With no relay configured nothing is sent and
nothing is logged, so the first night with one sends what is due then. A send that fails is recorded
as an EmailFailure (absence.mail) and logs nothing, so the next night tries
again."""
import logging
from collections import defaultdict

from django.template.loader import render_to_string

from absence import mail
from accounts.mail import email_is_configured
from checks.services import due as checks_due
from compliance.models import ReminderSchedule, ReminderSent
from compliance.services import schedule
from documents.services import due as documents_due
from onboarding.services import due as onboarding_due
from registers.services import due as registers_due

log = logging.getLogger("hr.compliance")
SOURCES = (checks_due.due_items, documents_due.due_items, onboarding_due.due_items, registers_due.due_items)
SUBJECT = "Practice HR: things due"


def _when(item):
    if item.kind == "registration":
        if item.state == "missing":
            return "not recorded"
        return f"found {item.due_on:%-d %b %Y}"
    if item.state == "due_today":
        return "due today"
    if item.state == "due_soon":
        return f"due {item.due_on:%-d %b %Y}"
    if item.state == "overdue":
        return f"overdue since {item.due_on:%-d %b %Y}"
    if item.state == "lapsed":
        return f"expired on {item.due_on:%-d %b %Y}"     # valid through that day
    return "missing"


def _collect(today, sched):
    items = []
    for source in SOURCES:
        try:
            items.extend(source(today, sched))
        except Exception as exc:  # noqa: BLE001 - one app's fault must not stop the others' reminders
            log.error("compliance: %s failed: %s", source.__module__, exc.__class__.__name__)
    return items


def pending(today):
    """The items that should go today, by recipient, after the schedule and the sent log."""
    sched = ReminderSchedule.get()
    last_sent = {}
    by_recipient, seen = defaultdict(list), set()
    for item in _collect(today, sched):
        pair = (item.recipient.lower(), item.key)
        if pair in seen:              # an HR admin who is also the person, or the manager
            continue
        seen.add(pair)
        if pair not in last_sent:
            last_sent[pair] = (ReminderSent.objects.filter(recipient__iexact=item.recipient, key=item.key)
                               .order_by("-sent_on").values_list("sent_on", flat=True).first())
        last = last_sent[pair]
        if item.once and last is not None:
            continue
        if schedule.should_send(today, item.due_on, item.state, last, sched):
            by_recipient[item.recipient].append(item)
    return by_recipient


def _body(rows, today):
    def person(i):
        e = i.employee
        return (e.last_name, e.first_name, e.pk) if e is not None else ("", "", 0)
    rows = sorted(rows, key=lambda i: (*person(i), i.due_on, i.label))
    lines = [{"item": i, "when": _when(i), "who": i.employee.name if i.employee is not None else "The registers"}
             for i in rows]
    return render_to_string("email/compliance_digest.txt", {"lines": lines, "today": today})


def run(today):
    if not email_is_configured():
        return {"reminders_sent": 0, "reminders_failed": 0, "items": 0}
    sent = failed = items = 0
    for recipient, rows in pending(today).items():
        try:
            body = _body(rows, today)
        except Exception as exc:  # noqa: BLE001 - a template or data fault must not stop the rest
            log.error("compliance digest not built: %s", exc.__class__.__name__)
            mail.record_failure(SUBJECT, f"not built: {exc.__class__.__name__}")
            failed += 1
            continue
        if mail.send(SUBJECT, body, [recipient]):
            sent += 1
            ReminderSent.objects.bulk_create(
                [ReminderSent(recipient=recipient, key=i.key, sent_on=today) for i in rows])
            items += len(rows)
        else:
            failed += 1
    if sent or failed:
        log.info("compliance digest: %s sent, %s failed, %s items", sent, failed, items)
    return {"reminders_sent": sent, "reminders_failed": failed, "items": items}
