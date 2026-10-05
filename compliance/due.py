"""The one shape every app's `due_items(today, sched)` returns: one line for
one recipient. `key` names the thing and its due date, so the sent log can
tell a new cadence from one already running; `once` marks a notice that
goes a single time (a line manager told that a report's check has lapsed)."""
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DueItem:
    employee: object
    recipient: str
    kind: str          # check | policy | item
    label: str
    due_on: date
    state: str         # due_soon | due_today | overdue | lapsed | missing
    url: str
    key: str
    once: bool = False


def link(path):
    """An absolute link for an email, from SITE_URL, as the absence emails build theirs."""
    from django.conf import settings
    return settings.SITE_URL.rstrip("/") + path


def active_email(employee):
    """The login address of `employee`, when they have a login that is switched on; else None."""
    user = employee.user if employee is not None else None
    return user.email if user is not None and user.is_active and user.email else None


def state_by_date(today, due_on):
    """due_today on the day, overdue after it, due_soon before it."""
    if due_on == today:
        return "due_today"
    return "overdue" if due_on < today else "due_soon"
