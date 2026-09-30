"""The approver's side: the queue of requests waiting on them and the page
they decide one on. Every write goes through absence.services.bookings; a GET
opens no pot (pots.lookup, never for_day)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from absence.forms import DecisionForm
from absence.models import Absence, ToilClaim
from absence.services import balances, bookings, calendar, notify
from people.services import access, contracts, positions


def routed(user, today, qs):
    """The rows of `qs` that are the user's to decide: those routed to their
    employee (access.route_for), or every one for an HR admin. Never the
    user's own: an HR admin's request goes to another HR admin. `qs` is any
    queryset of rows with an employment: absences, TOIL claims. Filter it
    (by status) first: only the reports' rows are routed, one by one."""
    qs = qs.select_related("employment__employee")
    me = access.employee_for(user)
    if me is not None:
        qs = qs.exclude(employment__employee=me)
    if access.can_view_restricted(user):
        return qs
    if me is None:
        return qs.none()
    reports = [e.employee_id for e in access.direct_reports(me, today)]
    mine = [row.pk for row in qs.filter(employment__employee_id__in=reports)
            if access.route_for(row.employment, today) == me]
    return qs.filter(pk__in=mine)


def _routed_to(user, today, statuses):
    """The absences in these statuses that are the user's to decide (routed)."""
    return routed(user, today, Absence.objects.filter(status__in=statuses).select_related("absence_type")
                  .order_by("start_date", "requested_at"))


def claims_for(user, today, statuses=(ToilClaim.Status.REQUESTED,)):
    """The TOIL claims in these statuses that are the user's to decide:
    routed exactly as leave is. By default the ones waiting, oldest day first."""
    return routed(user, today, ToilClaim.objects.filter(status__in=statuses).order_by("day", "requested_at"))


def queue_for(user, today):
    """The requests waiting on this user."""
    return _routed_to(user, today, [Absence.Status.REQUESTED])


def _may_open(user, absence, today):
    """Whether the request was ever the user's to decide, in any status: an
    approver opening a link after it was decided or cancelled is shown what
    happened, not refused."""
    return _routed_to(user, today, list(Absence.Status.values)).filter(pk=absence.pk).exists()


def _closed(absence):
    """Who closed a request that is no longer waiting, and when."""
    if absence.status == Absence.Status.CANCELLED:
        user, when = absence.cancelled_by, absence.cancelled_at
    else:
        user, when = absence.decided_by, absence.decided_at
    who = ""
    if user is not None:
        employee = access.employee_for(user)
        who = employee.name if employee else user.email
    return {"what": absence.get_status_display().lower(), "by": who, "on": when}


def _may_see_queue(user, today):
    return access.is_approver(user, today) or access.can_view_restricted(user)


def _balance(absence, today):
    """What the requester's pot has left and would have after this, for the
    page. Never opens a pot; a missing contract or policy is a message."""
    try:
        return balances.after(absence.employment, absence.absence_type, absence.start_date, absence.cost_units, today)
    except ValidationError:
        return {"error": True}


@login_required
def queue(request):
    today = timezone.localdate()
    if not _may_see_queue(request.user, today):
        raise PermissionDenied
    claims = list(claims_for(request.user, today))
    for c in claims:
        c.unit = contracts.unit(c.employment, c.day) or ""
    return render(request, "absence/queue.html", {"rows": queue_for(request.user, today), "claims": claims})


@login_required
def decide(request, pk):
    a = get_object_or_404(Absence.objects.select_related("employment__employee", "absence_type"), pk=pk)
    today = timezone.localdate()
    if not _may_open(request.user, a, today):
        raise PermissionDenied
    waiting = a.status == Absence.Status.REQUESTED
    form = DecisionForm(request.POST or None) if waiting else None
    if waiting and request.method == "POST" and form.is_valid():
        try:
            if form.cleaned_data["action"] == "approve":
                bookings.approve(request.user, a, form.cleaned_data["comment"])
            else:
                bookings.decline(request.user, a, form.cleaned_data["comment"])
        except ValidationError as e:
            form.add_error(None, e.messages)
        else:
            # after the service's transaction has committed, never inside it
            if not notify.request_decided(a):
                messages.warning(request, f"Saved, but the email to {a.employment.employee.name} did not go. "
                                          "Let them know yourself.")
            messages.success(request, f"{a.absence_type.name} for {a.employment.employee.name}: "
                                      f"{a.get_status_display().lower()}.")
            return redirect("absence:queue")
    pos = positions.primary_on(a.employment, a.start_date)
    team = pos.team if pos else None
    return render(request, "absence/decide.html", {
        "a": a, "form": form, "closed": None if waiting else _closed(a), "team": team,
        "unit": contracts.unit(a.employment, a.start_date),
        # the balance-after and the warning are about approving: not for a closed request
        "balance": _balance(a, today) if waiting and a.absence_type.uses_pot else None,
        "days": calendar.days_for(a.start_date, a.end_date, team),
        "warning": calendar.warning_if_approved(a, team) if waiting and team else None,
    })
