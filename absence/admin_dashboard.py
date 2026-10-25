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

# The compliance card's numbers, in the order shown, with their labels.
# Each opens the Employees list filtered to the people it counts, but the
# training numbers, which open the matrix (people.admin.ComplianceFilter
# reads compliance_people too).
COMPLIANCE = (
    ("lapsed_checks", "Lapsed checks"),
    ("missing_checks", "Missing checks"),
    ("overdue_signatures", "Overdue signatures"),
    ("overdue_items", "Overdue checklist items"),
    ("registration_problems", "Registration problems"),
    ("training_problems", "Training lapsed or missing"),
    ("training_to_verify", "Training to verify"),
)
# The two training numbers open the matrix with its filter on, not the Employees list.
MATRIX_SHOW = {"training_problems": "problems", "training_to_verify": "to_verify"}


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
    leaver, but those of an employment that ended more than 90 days ago.
    Read-only."""
    from checks.services import checks
    from documents.services import policies
    from onboarding.models import ChecklistItem
    from onboarding.services import due
    from registers.services import registrations
    from training.services import training

    out = {key: [] for key, _ in COMPLIANCE}
    current = employments.active_on(today).values_list("employee_id", flat=True)
    for e in Employee.objects.filter(pk__in=current).order_by("pk"):
        emp = employments.current(e, today)
        for row in checks.state(e, today):
            status = checks.owed_status(row, emp, today)     # an unanswered request is still missing
            if status == "lapsed":
                out["lapsed_checks"].append(e.pk)
            elif status == "missing":
                out["missing_checks"].append(e.pk)
        out["overdue_signatures"] += [e.pk for o in policies.owed(e, today) if o.state == "overdue"]
        out["registration_problems"] += [
            e.pk for r in registrations.rows(e, today)
            if r.needed and r.registration is not None
            and r.registration.last_outcome in ("problem", "not_found", "name_mismatch")]
        for row in training.state(e, today):
            if row.pending is not None:
                out["training_to_verify"].append(e.pk)
            elif row.status in ("lapsed", "missing"):
                out["training_problems"].append(e.pk)
    overdue = ChecklistItem.objects.filter(state=ChecklistItem.State.OPEN, due_on__lt=today)
    # as the reminders: nothing of an employment that ended more than 90 days ago
    out["overdue_items"] = list(due.still_chased(overdue, today)
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
    matrix_url = reverse("training:matrix")
    context["compliance"] = [
        {"label": label, "count": counts[key],
         "url": f"{matrix_url}?show={MATRIX_SHOW[key]}" if key in MATRIX_SHOW else f"{employees}?compliance={key}"}
        for key, label in COMPLIANCE]
    context["email_configured"] = email_is_configured()
    context["email_failures"] = list(EmailFailure.objects.all()[:10])
    return context
