"""What is due of the registrations, for the morning digest (compliance):
a standing problem, not-found or wrong-name result goes to HR and to the
line manager, with the body and the register's words (a registration
problem is the manager's to act on that day, unlike a lapsed check); a
body the title needs with no number is HR's from the employment start; a
page that has been unreadable for 14 days, or a paused body, is HR's
alone."""
from django.urls import reverse
from django.utils import timezone

from absence.services.notify import hr_admin_addresses
from compliance.due import DueItem, active_email, link
from people.models import Employee
from people.services import access, employments
from registers.models import RegisterBody
from registers.services import registrations
from registers.services.nightly import UNREADABLE_AFTER_DAYS

KIND = "registration"


def _label(reg):
    body = reg.body.name
    if reg.last_outcome == "problem":
        return f"{body}: {reg.last_status_text}"
    if reg.last_outcome == "not_found":
        return f"{body}: not found on the register"
    return f"{body}: the register shows {reg.last_name_on_register or 'someone else'}, not this person"


def due_items(today, sched):
    out = []
    hr = hr_admin_addresses()
    lookups_url = link(reverse("admin:registers_lookup_changelist"))
    employed = employments.active_on(today).values("employee_id")
    for e in Employee.objects.filter(pk__in=employed).select_related("user"):
        emp = employments.current(e, today)
        if emp is None:
            continue
        hr_url = link(reverse("admin:people_employee_change", args=[e.pk]))
        rows = [r for r in registrations.rows(e, today) if r.needed]
        for row in rows:
            reg = row.registration
            if reg is None:
                for r in hr:
                    out.append(DueItem(e, r, KIND, f"{row.body.name} number not recorded", emp.start_date, "missing",
                                       hr_url, f"registration:{e.pk}:{row.body.code}:missing"))
                continue
            latest = reg.lookups.order_by("-run_at", "-pk").first()
            if latest is None:
                continue
            if latest.outcome in ("problem", "not_found", "name_mismatch"):
                key = f"registration:{e.pk}:{row.body.code}:{latest.pk}"
                found = timezone.localtime(latest.run_at).date()
                for r in hr:
                    out.append(DueItem(e, r, KIND, _label(reg), found, "overdue", hr_url, key))
                manager = active_email(access.line_manager(e, today))
                if manager:
                    out.append(DueItem(e, manager, KIND, _label(reg), found, "overdue",
                                       link(reverse("people:team")), key))
            elif latest.outcome == "unreadable":
                since = _unreadable_since(reg)
                if since is not None and (today - since).days >= UNREADABLE_AFTER_DAYS:
                    for r in hr:
                        out.append(DueItem(e, r, KIND, f"{row.body.name}: could not be read since {since:%-d %b %Y}",
                                           since, "overdue", lookups_url,
                                           f"registration:{e.pk}:{row.body.code}:unreadable:{since.isoformat()}"))
    for body in RegisterBody.objects.filter(active=True, paused_at__isnull=False):
        paused_on = timezone.localtime(body.paused_at).date()
        for r in hr:
            out.append(DueItem(None, r, KIND, f"{body.name}: checks are paused (the page could not be read)",
                               paused_on, "overdue", lookups_url,
                               f"registration:body:{body.code}:paused:{paused_on.isoformat()}"))
    return out


def _unreadable_since(reg):
    """The date of the first of the unbroken run of unreadable lookups that ends at the latest."""
    since = None
    for lk in reg.lookups.order_by("-run_at", "-pk"):
        if lk.outcome != "unreadable":
            break
        since = timezone.localtime(lk.run_at).date()
    return since
