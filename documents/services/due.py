"""What is due of the policies, for the reminder digest (compliance.due).

For each person with an active login, each policy version they owe
(policies.owed): due soon inside the reminder window, due today, then
overdue. The person is reminded; HR admins too once it is overdue."""
from django.urls import reverse

from absence.services.notify import hr_admin_addresses
from compliance.due import DueItem, link, state_by_date
from documents.services import policies
from people.models import Employee


def due_items(today, sched):
    out = []
    hr = hr_admin_addresses()
    own_url = link(reverse("documents:policies"))
    for e in Employee.objects.filter(user__isnull=False, user__is_active=True).select_related("user"):
        for owed in policies.owed(e, today):
            if (owed.due_on - today).days > sched.start_days_before:
                continue                      # awaiting, but not inside the window yet
            version = owed.version
            state = state_by_date(today, owed.due_on)
            key = f"policy:{e.pk}:{version.pk}:{owed.due_on.isoformat()}"
            label = f"Sign {version.policy.title} ({version.label})"
            out.append(DueItem(e, e.user.email, "policy", label, owed.due_on, state, own_url, key))
            if state == "overdue":
                hr_url = link(reverse("admin:documents_policy_change", args=[version.policy_id]))
                out.extend(DueItem(e, r, "policy", label, owed.due_on, state, hr_url, key) for r in hr)
    return out
