"""The employee's own absences: request (checked, then confirmed), list,
cancel, and keeping-in-touch days. Every write goes through
absence.services.bookings; a GET opens no pot (pots.lookup, never for_day)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from absence.forms import KitDayForm, RequestForm
from absence.models import Absence
from absence.services import balances, bookings, notify, pots
from accounts.mail import email_is_configured
from people.services import access, contracts, employments

S = Absence.Status


def _my_employment(request, today):
    employee = access.employee_for(request.user)
    return employee, (employments.current(employee, today) if employee else None)


def _may_cancel(user, absence, today):
    """The employee cancels a request any time and an approved absence until
    it starts; an HR admin cancels any live absence. Nobody cancels an
    automatic bank-holiday row: the nightly would only make it again."""
    if absence.auto_bank_holiday or absence.status not in bookings.LIVE:
        return False
    if access.can_view_restricted(user):
        return True
    if absence.employment.employee.user_id != user.pk:
        return False
    return absence.status == S.REQUESTED or absence.start_date > today


def _submit_message(request, absence, sent):
    if absence.status != S.REQUESTED:
        messages.success(request, "Recorded.")
        return
    if sent:
        messages.success(request, "Sent for approval.")
        return
    why = "Email is not set up here" if not email_is_configured() else "The email to your approver did not go"
    messages.warning(request, f"Saved and waiting for approval. {why}: send your approver this link "
                              f"to decide it: {notify.decide_url(absence)}")


@login_required
def request_leave(request):
    today = timezone.localdate()
    employee, employment = _my_employment(request, today)
    if employment is None:
        return render(request, "absence/request.html", {"no_employment": True, "employee": employee})
    form = RequestForm(request.POST or None, employment=employment, today=today)
    preview = None
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        fields = dict(employment=employment, absence_type=d["absence_type"], start_date=d["start_date"],
                      end_date=d["end_date"], start_half=d["start_half"], end_half=d["end_half"],
                      start_time=d.get("start_time"), end_time=d.get("end_time"), hours=d.get("hours"),
                      category=d["category"], expected_start=d["expected_start"],
                      expected_return=d["expected_return"])
        try:
            if request.POST.get("confirm") == "1":
                a = bookings.request(request.user, **fields)
                # after the service's transaction has committed, never inside it
                sent = notify.request_submitted(a) if a.status == S.REQUESTED else False
                _submit_message(request, a, sent)
                return redirect("absence:mine")
            a = bookings.preview(**fields)
            preview = {"a": a, "balance": balances.after(employment, a.absence_type, a.start_date, a.cost_units, today),
                       "fields": [(name, value) for name in form.fields
                                  for value in request.POST.getlist(name)]}
        except ValidationError as e:
            # flattened: a field-keyed error may name a field this form
            # leaves out (the part-day fields, for a sessions allowance)
            form.add_error(None, e.messages)
    return render(request, "absence/request.html", {
        "form": form, "preview": preview, "unit": contracts.unit(employment, today),
        "balances": balances.rows(employment, today, show_setup_gaps=access.can_view_restricted(request.user))})


@login_required
def mine(request):
    today = timezone.localdate()
    employee, employment = _my_employment(request, today)
    rows = []
    if employee is not None:
        summaries = {}
        qs = (Absence.objects.filter(employment__employee=employee)
              .select_related("absence_type", "employment__employee").prefetch_related("kit_days"))
        for a in qs:
            over = False
            if a.absence_type.uses_pot and a.status == S.REQUESTED and a.cost_units:
                try:
                    pot = pots.lookup(a.employment, a.absence_type, a.start_date)
                except ValidationError:
                    pot = None
                if pot is not None:
                    if pot.pk not in summaries:
                        summaries[pot.pk] = balances.summary(pot, today)
                    over = summaries[pot.pk]["remaining"] - a.cost_units < 0
            rows.append({
                "a": a, "over": over, "can_cancel": _may_cancel(request.user, a, today),
                "label": "Bank holiday (automatic)" if a.auto_bank_holiday else a.absence_type.name,
                "kit": a.absence_type.is_family and a.status in bookings.LIVE,
            })
    return render(request, "absence/mine.html", {
        "employee": employee, "employment": employment, "rows": rows,
        "unit": contracts.unit(employment, today) if employment else "",
        "balances": balances.rows(employment, today, show_setup_gaps=access.can_view_restricted(request.user))
        if employment else []})


@login_required
@require_POST
def cancel(request, pk):
    a = get_object_or_404(Absence.objects.select_related("employment__employee", "absence_type"), pk=pk)
    if not _may_cancel(request.user, a, timezone.localdate()):
        raise PermissionDenied
    try:
        bookings.cancel(request.user, a)
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
        return redirect("absence:mine")
    notify.absence_cancelled(a)
    messages.success(request, "Cancelled.")
    return redirect("absence:mine")


@login_required
@require_POST
def kit_day(request, pk):
    a = get_object_or_404(Absence.objects.select_related("employment__employee", "absence_type"), pk=pk)
    if a.employment.employee.user_id != request.user.pk and not access.can_view_restricted(request.user):
        raise PermissionDenied
    form = KitDayForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Give the keeping-in-touch day as a date.")
        return redirect("absence:mine")
    try:
        bookings.add_kit_day(request.user, a, form.cleaned_data["date"])
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    else:
        messages.success(request, "Keeping-in-touch day added.")
    return redirect("absence:mine")
