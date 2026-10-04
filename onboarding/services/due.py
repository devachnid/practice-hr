"""What is due of the starter and leaver checklists, for the reminder digest
(compliance.due).

Every open item of a checklist whose employment ended no more than 90 days
ago (or has not ended): due soon inside the reminder window, due today,
then overdue. Each goes to its owner: the person (with an active login),
the line manager it was given to (with an active login), or every HR
admin. A line manager item with no manager (or one whose login is off) is
HR's to do, so HR is reminded of it."""
from datetime import timedelta

from django.db.models import Q
from django.urls import reverse

from absence.services.notify import hr_admin_addresses
from compliance.due import DueItem, link, state_by_date
from onboarding.models import ChecklistItem, Owner

ENDED_WITHIN_DAYS = 90


def _active_email(employee):
    user = employee.user if employee is not None else None
    return user.email if user is not None and user.is_active and user.email else None


def due_items(today, sched):
    out = []
    hr = hr_admin_addresses()
    last = today + timedelta(days=sched.start_days_before)
    ended_after = today - timedelta(days=ENDED_WITHIN_DAYS)
    items = (ChecklistItem.objects.filter(state=ChecklistItem.State.OPEN, due_on__lte=last)
             .filter(Q(checklist__employment__end_date__isnull=True)
                     | Q(checklist__employment__end_date__gte=ended_after))
             .select_related("checklist__employment__employee__user", "owner_employee__user"))
    for item in items:
        e = item.checklist.employment.employee
        state = state_by_date(today, item.due_on)
        key = f"item:{item.pk}:{item.due_on.isoformat()}"
        manager = _active_email(item.owner_employee) if item.owner == Owner.MANAGER else None
        if item.owner == Owner.PERSON:
            to, url = [_active_email(e)], reverse("onboarding:getting_started")
        elif manager:
            to, url = [manager], reverse("people:team")
        else:                                   # HR's, or a manager's with no manager able to sign in
            to, url = hr, reverse("onboarding:hr_detail", args=[item.checklist_id])
        out.extend(DueItem(e, r, "item", item.title, item.due_on, state, link(url), key) for r in to if r)
    return out
