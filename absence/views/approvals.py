"""The approver's side: the queue of requests waiting on them and the page
they decide one on. Every write goes through absence.services.bookings; a GET
opens no pot (pots.lookup, never for_day)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from absence.forms import DecisionForm
from absence.models import Absence
from absence.services import bookings, calendar, notify
from absence.views.requests import _balance_after
from people.services import access, contracts, positions


def queue_for(user, today):
    """The requests waiting on this user: those routed to their employee, or
    every one for an HR admin. Never the user's own: an HR admin's request
    goes to another HR admin. Requested rows are filtered first and only the
    reports' rows are routed."""
    qs = (Absence.objects.filter(status=Absence.Status.REQUESTED)
          .select_related("employment__employee", "absence_type").order_by("start_date", "requested_at"))
    me = access.employee_for(user)
    if me is not None:
        qs = qs.exclude(employment__employee=me)
    if access.can_view_restricted(user):
        return qs
    if me is None:
        return qs.none()
    reports = [e.employee_id for e in access.direct_reports(me, today)]
    routed = [a.pk for a in qs.filter(employment__employee_id__in=reports)
              if access.route_for(a.employment, today) == me]
    return qs.filter(pk__in=routed)


def _may_decide(user, absence, today):
    return queue_for(user, today).filter(pk=absence.pk).exists()


def _may_see_queue(user, today):
    return access.is_approver(user, today) or access.can_view_restricted(user)


def _balance(absence, today):
    """What the requester's pot has left and would have after this, for the
    page. Never opens a pot; a missing contract or policy is a message."""
    try:
        return _balance_after(absence, today)
    except ValidationError:
        return {"error": True}


@login_required
def queue(request):
    today = timezone.localdate()
    if not _may_see_queue(request.user, today):
        raise PermissionDenied
    return render(request, "absence/queue.html", {"rows": queue_for(request.user, today)})


@login_required
def decide(request, pk):
    a = get_object_or_404(Absence.objects.select_related("employment__employee", "absence_type"), pk=pk)
    today = timezone.localdate()
    if not _may_decide(request.user, a, today):
        raise PermissionDenied
    form = DecisionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            if form.cleaned_data["action"] == "approve":
                bookings.approve(request.user, a, form.cleaned_data["comment"])
            else:
                bookings.decline(request.user, a, form.cleaned_data["comment"])
        except ValidationError as e:
            form.add_error(None, e.messages)
        else:
            # after the service's transaction has committed, never inside it
            notify.request_decided(a)
            messages.success(request, f"{a.absence_type.name} for {a.employment.employee.name}: "
                                      f"{a.get_status_display().lower()}.")
            return redirect("absence:queue")
    pos = positions.primary_on(a.employment, a.start_date)
    team = pos.team if pos else None
    return render(request, "absence/decide.html", {
        "a": a, "form": form, "team": team, "unit": contracts.unit(a.employment, a.start_date),
        "balance": _balance(a, today) if a.absence_type.uses_pot else None,
        "days": calendar.days_for(a.start_date, a.end_date, team),
        "warning": calendar.warning_if_approved(a, team) if team else None,
    })
