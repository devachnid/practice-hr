"""What is due of the checks, for the reminder digest (compliance.due).

For each currently employed person, each check type their title needs that
is due soon (inside the reminder window before it expires), lapsed or
missing (checks.owed_status: a request for evidence nobody has answered
does not stop a check being missing). HR admins are reminded of every one; the person too when the type
has remind_person and they have an active login; the line manager once, the
first time a check lapses, without saying which check (a manager sees counts
of a report's checks, never which)."""
from django.urls import reverse

from absence.services.notify import hr_admin_addresses
from checks.services import checks
from compliance.due import DueItem, active_email, link, state_by_date
from people.models import Employee
from people.services import access, employments

MANAGER_LABEL = "A check has lapsed (HR has the details)"


def due_items(today, sched):
    out = []
    hr = hr_admin_addresses()
    own_url, team_url = link(reverse("people:me")), link(reverse("people:team"))
    employed = employments.active_on(today).values("employee_id")
    for e in Employee.objects.filter(pk__in=employed).select_related("user"):
        emp = employments.current(e, today)
        if emp is None:
            continue
        rows = [(r, checks.owed_status(r, emp, today))
                for r in checks.state(e, today, window_days=sched.start_days_before)]
        rows = [(r, status) for r, status in rows if status in ("due_soon", "lapsed", "missing")]
        if not rows:
            continue
        hr_url = link(reverse("admin:checks_check_changelist") + f"?employee__id__exact={e.pk}")
        person = active_email(e)
        for row, status in rows:
            # missing has no expiry: it has been owed since the employment started
            due = row.expires_on if status != "missing" else emp.start_date
            key = f"check:{e.pk}:{row.check_type.code}:{due.isoformat()}:{status}"
            state = state_by_date(today, due) if status == "due_soon" else status
            label = row.check_type.name
            for r in hr:
                out.append(DueItem(e, r, "check", label, due, state, hr_url, key))
            if row.check_type.remind_person and person:
                out.append(DueItem(e, person, "check", label, due, state, own_url, key))
            if status == "lapsed":
                manager = active_email(access.line_manager(e, today))
                if manager:
                    out.append(DueItem(e, manager, "check", MANAGER_LABEL, due, "lapsed", team_url, key, once=True))
    return out
