"""What the admin index page shows beside the app list: leave requests and
TOIL claims that have waited too long, the compliance numbers, whether email
can go at all, and the emails that did not."""

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from absence.models import EmailFailure, ToilClaim
from absence.services import chase
from accounts.mail import email_is_configured
from people.models import Employee
from people.services import contracts, employments

# The compliance card's four numbers, in the order shown, with their labels.
# Each opens the Employees list filtered to the people it counts
# (people.admin.ComplianceFilter, which reads compliance_people too).
COMPLIANCE = (
    ("lapsed_checks", "Lapsed checks"),
    ("missing_checks", "Missing checks"),
    ("overdue_signatures", "Overdue signatures"),
    ("overdue_items", "Overdue checklist items"),
)


def _row(r):
    if isinstance(r, ToilClaim):
        return {"claim": r, "url": reverse("absence:toil_decide", args=[r.pk]), "asked": r.requested_at,
                "unit": contracts.unit(r.employment, r.day) or ""}
    return {"a": r, "url": reverse("absence:decide", args=[r.pk]), "asked": r.requested_at}


def compliance_people(today):
    """For each number on the card, one employee pk per thing counted (so
    a person with two lapsed checks is there twice). Checks and signatures
    are of the people employed today, by checks.state and policies.owed;
    checklist items are every open item past its due date, starter or
    leaver. Read-only."""
    from checks.services import checks
    from documents.services import policies
    from onboarding.models import ChecklistItem

    out = {key: [] for key, _ in COMPLIANCE}
    current = employments.active_on(today).values_list("employee_id", flat=True)
    for e in Employee.objects.filter(pk__in=current).order_by("pk"):
        for row in checks.state(e, today):
            if row.status == "lapsed":
                out["lapsed_checks"].append(e.pk)
            elif row.status == "missing":
                out["missing_checks"].append(e.pk)
        out["overdue_signatures"] += [e.pk for o in policies.owed(e, today) if o.state == "overdue"]
    out["overdue_items"] = list(ChecklistItem.objects.filter(state=ChecklistItem.State.OPEN, due_on__lt=today)
                                .values_list("checklist__employment__employee_id", flat=True))
    return out


def compliance_counts(today):
    return {key: len(pks) for key, pks in compliance_people(today).items()}


def dashboard(request, context):
    context["waiting"] = [_row(r) for r in chase.waiting(timezone.localdate())]
    context["waiting_claims"] = sum(1 for w in context["waiting"] if "claim" in w)
    context["waiting_requests"] = len(context["waiting"]) - context["waiting_claims"]
    context["chase_after"] = settings.CHASE_AFTER_WORKING_DAYS
    counts = compliance_counts(timezone.localdate())
    employees = reverse("admin:people_employee_changelist")
    context["compliance"] = [{"label": label, "count": counts[key], "url": f"{employees}?compliance={key}"}
                             for key, label in COMPLIANCE]
    context["email_configured"] = email_is_configured()
    context["email_failures"] = list(EmailFailure.objects.all()[:10])
    return context
