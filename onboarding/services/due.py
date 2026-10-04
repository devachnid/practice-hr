"""What is due of the starter and leaver checklists, for the reminder digest
(compliance.due).

Every open item of a checklist whose employment ended no more than 90 days
ago (or has not ended): due soon inside the reminder window, due today,
then overdue. Each goes to its owner: the person, the line manager it was
given to, or every HR admin. An item whose owner has no login that is
switched on (or a line manager item with no manager) is HR's to do, so HR
is reminded of it; so is a details item the person has sent (submitted_at),
which waits on HR checking it."""
from datetime import timedelta

from django.db.models import Q
from django.urls import reverse

from absence.services.notify import hr_admin_addresses
from compliance.due import DueItem, active_email, link, state_by_date
from onboarding.models import ChecklistItem, Owner

ENDED_WITHIN_DAYS = 90


def still_chased(items, today):
    """`items` (ChecklistItem rows) less those of an employment that ended
    more than ENDED_WITHIN_DAYS ago: the reminders and the dashboard's
    Overdue checklist items leave those alone."""
    ended_after = today - timedelta(days=ENDED_WITHIN_DAYS)
    return items.filter(Q(checklist__employment__end_date__isnull=True)
                        | Q(checklist__employment__end_date__gte=ended_after))


def due_items(today, sched):
    out = []
    hr = hr_admin_addresses()
    last = today + timedelta(days=sched.start_days_before)
    items = (still_chased(ChecklistItem.objects.filter(state=ChecklistItem.State.OPEN, due_on__lte=last), today)
             .select_related("checklist__employment__employee__user", "owner_employee__user"))
    for item in items:
        e = item.checklist.employment.employee
        state = state_by_date(today, item.due_on)
        key = f"item:{item.pk}:{item.due_on.isoformat()}"
        owner = {Owner.PERSON: e, Owner.MANAGER: item.owner_employee}.get(item.owner)
        if item.link == "details" and item.submitted_at is not None:
            owner = None                        # sent: HR's to check, not the person's to chase
        address = active_email(owner)
        if address and item.owner == Owner.PERSON:
            to, url = [address], reverse("onboarding:getting_started")
        elif address:
            to, url = [address], reverse("people:team")
        else:                                   # HR's, or an owner who cannot sign in: HR does it
            to, url = hr, reverse("onboarding:hr_detail", args=[item.checklist_id])
        out.extend(DueItem(e, r, "item", item.title, item.due_on, state, link(url), key) for r in to if r)
    return out
