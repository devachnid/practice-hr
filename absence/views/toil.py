"""The TOIL claim pages: claim your own, record one for a report (approved
at once, as request_for records leave), decide one, cancel one. Every write
goes through absence.services.toil and emails go after it returns; a GET
writes nothing and opens no pot. Routing and who may open a claim are
leave's (approvals.routed, access.may_record_for)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from absence.forms import DecisionForm, ToilClaimForm
from absence.models import AbsenceType, ToilClaim
from absence.services import notify, toil
from absence.views.approvals import routed
from accounts.mail import email_is_configured
from people.models import Employee
from people.services import access, contracts, employments

S = ToilClaim.Status


def _claim_page(request, employment, today, submit, for_employee=None):
    """The claim form for `employment`; a valid POST is passed to
    `submit(day, units, reason)`, which saves it and returns the response.
    Shared by your own claim and one recorded for someone."""
    unit = contracts.unit(employment, today) or "hours"
    window = AbsenceType.objects.get(code="TOIL").earned_expires_after_days
    form = ToilClaimForm(request.POST or None, unit=unit, today=today, window=window,
                         whose="your" if for_employee is None else "their")
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            return submit(d["day"], d["units"], d["reason"])
        except ValidationError as e:
            form.add_error(None, e.messages)
    return render(request, "absence/toil_claim.html", {
        "form": form, "for_employee": for_employee, "toil": toil.position(employment, today),
        "expires_after": window})


@login_required
def claim(request):
    today = timezone.localdate()
    employee = access.employee_for(request.user)
    employment = employments.current(employee, today) if employee else None
    if employment is None:
        return render(request, "absence/toil_claim.html", {"no_employment": True, "employee": employee})

    def submit(day, units, reason):
        c = toil.claim(request.user, employment, day, units, reason)
        # after the service's transaction has committed, never inside it
        if c.status != S.REQUESTED:
            messages.success(request, "Recorded.")
        elif notify.claim_submitted(c):
            messages.success(request, "Sent for approval.")
        else:
            why = "Email is not set up here" if not email_is_configured() else "The email to your approver did not go"
            messages.warning(request, f"Saved and waiting for approval. {why}: send your approver this link "
                                      f"to decide it: {notify.claim_decide_url(c)}")
        return redirect("absence:mine")

    return _claim_page(request, employment, today, submit)


@login_required
def claim_for(request, pk):
    """Record a claim for someone else: their routed approver or an HR
    admin, so it is approved at once (toil.claim). They are emailed."""
    employee = get_object_or_404(Employee, pk=pk)
    today = timezone.localdate()
    me = access.employee_for(request.user)
    if me is not None and me.pk == employee.pk:
        return redirect("absence:toil_claim")
    employment = employments.current(employee, today)
    if employment is None:
        if not access.can_view_restricted(request.user):
            raise PermissionDenied
        return render(request, "absence/toil_claim.html", {"no_employment": True, "employee": employee,
                                                           "for_employee": employee})
    if not access.may_record_for(request.user, employment, today):
        raise PermissionDenied

    def submit(day, units, reason):
        c = toil.claim(request.user, employment, day, units, reason, requested_by=request.user)
        # after the service's transaction has committed, never inside it
        if not notify.claim_decided(c):
            messages.warning(request, f"Saved, but the email to {employee.name} did not go. Let them know yourself.")
        messages.success(request, f"TOIL for {employee.name}: recorded and approved.")
        return redirect("absence:balances_for", employee.pk)

    return _claim_page(request, employment, today, submit, for_employee=employee)


def _closed(claim):
    """Who closed a claim that is no longer waiting, and when."""
    if claim.status == S.CANCELLED:
        user, when = claim.cancelled_by, claim.cancelled_at
    else:
        user, when = claim.decided_by, claim.decided_at
    who = ""
    if user is not None:
        employee = access.employee_for(user)
        who = employee.name if employee else user.email
    return {"what": claim.get_status_display().lower(), "by": who, "on": when}


@login_required
def decide(request, pk):
    c = get_object_or_404(ToilClaim.objects.select_related("employment__employee", "requested_by"), pk=pk)
    today = timezone.localdate()
    # ever the user's to decide, in any status: a link opened after the decision shows what happened
    if not routed(request.user, today, ToilClaim.objects.filter(pk=c.pk)).exists():
        raise PermissionDenied
    waiting = c.status == S.REQUESTED
    form = DecisionForm(request.POST or None) if waiting else None
    if waiting and request.method == "POST" and form.is_valid():
        try:
            if form.cleaned_data["action"] == "approve":
                toil.approve(request.user, c, form.cleaned_data["comment"])
            else:
                toil.decline(request.user, c, form.cleaned_data["comment"])
        except ValidationError as e:
            form.add_error(None, e.messages)
        else:
            # after the service's transaction has committed, never inside it
            name = c.employment.employee.name
            if not notify.claim_decided(c):
                messages.warning(request, f"Saved, but the email to {name} did not go. Let them know yourself.")
            messages.success(request, f"TOIL claim for {name}: {c.get_status_display().lower()}.")
            return redirect("absence:queue")
    asked_by = ""                          # someone other than the person recorded it for them
    if c.requested_by_id and c.requested_by_id != c.employment.employee.user_id:
        by = access.employee_for(c.requested_by)
        asked_by = by.name if by else c.requested_by.email
    return render(request, "absence/toil_decide.html", {
        "c": c, "form": form, "closed": None if waiting else _closed(c),
        "unit": contracts.unit(c.employment, c.day) or "", "toil": toil.position(c.employment, today),
        "asked_by": asked_by,
    })


@login_required
@require_POST
def cancel(request, pk):
    c = get_object_or_404(ToilClaim.objects.select_related("employment__employee"), pk=pk)
    if not toil.may_cancel(request.user, c):
        raise PermissionDenied
    try:
        toil.cancel(request.user, c)
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    else:
        messages.success(request, "Claim cancelled.")
    return redirect("absence:mine")
