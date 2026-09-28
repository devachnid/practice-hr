"""What is past its retention period. Read-only: this lists, it never deletes.

The period for each category runs from the end of the person's last
employment. Anyone with a current or future employment is not a leaver
and is never listed."""

from datetime import timedelta

from django.conf import settings

from people.models import Employee
from people.services import employments


def due(today):
    """One row per (leaver, category) whose period has passed on `today`:
    employee, category, ended (their last employment's end date) and
    due_since (the day after which the category was overdue)."""
    out = []
    for e in Employee.objects.all():
        if employments.current(e, today) is not None or e.employments.filter(start_date__gt=today).exists():
            continue
        last = e.employments.filter(end_date__isnull=False).order_by("-end_date").first()
        if last is None:
            continue
        for category, days in settings.RETENTION_DAYS.items():
            deadline = last.end_date + timedelta(days=days)
            if today > deadline:
                out.append({"employee": e, "category": category, "ended": last.end_date,
                            "due_since": deadline})
    return out
