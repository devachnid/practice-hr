"""The employee's own absences: request (checked, then confirmed), list,
cancel, and keeping-in-touch days; and an absence recorded for someone by
their approver or an HR admin (request_for). Every write goes through
absence.services.bookings; a GET opens no pot (pots.lookup, never for_day)."""

from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from absence.forms import KitDayForm, RequestForm
from absence.models import Absence, AbsenceType, BankHoliday
from absence.services import balances, bookings, leave_year, notify, policies, pots, toil
from accounts.mail import email_is_configured
from people.models import Employee
from people.services import access, contracts, employments

S = Absence.Status


def _my_employment(request, today):
    employee = access.employee_for(request.user)
    return employee, (employments.current(employee, today) if employee else None)


def _may_cancel(user, absence, today):
    """The employee cancels a request any time and an approved absence until
    it starts; an HR admin cancels anyone else's live absence at any time,
    but their own by the employee's rule. Nobody cancels an automatic
    bank-holiday row: the nightly would only make it again."""
    if absence.auto_bank_holiday or absence.status not in bookings.LIVE:
        return False
    if absence.employment.employee.user_id != user.pk:
        return access.can_view_restricted(user)
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


def _fields(form, employment):
    d = form.cleaned_data
    return dict(employment=employment, absence_type=d["absence_type"], start_date=d["start_date"],
                end_date=d["end_date"], start_half=d["start_half"], end_half=d["end_half"],
                start_time=d.get("start_time"), end_time=d.get("end_time"), hours=d.get("hours"),
                category=d["category"], expected_start=d["expected_start"],
                expected_return=d["expected_return"])


def _request_page(request, employment, today, submit, for_employee=None):
    """The two-step request form for `employment`: a POST is checked and
    shown with its cost and balance; a POST with confirm=1 is passed to
    `submit(fields)`, which saves it and returns the response. Shared by
    the employee's own request and one recorded for them."""
    form = RequestForm(request.POST or None, employment=employment, today=today,
                       whose="your" if for_employee is None else "their")
    preview = None
    if request.method == "POST" and form.is_valid():
        fields = _fields(form, employment)
        try:
            if request.POST.get("confirm") == "1":
                return submit(fields)
            a = bookings.preview(**fields)
            preview = {"a": a, "balance": balances.after(employment, a.absence_type, a.start_date, a.cost_units, today),
                       "fields": [(name, value) for name in form.fields
                                  for value in request.POST.getlist(name)]}
        except ValidationError as e:
            # flattened: a field-keyed error may name a field this form
            # leaves out (the part-day fields, for a sessions allowance)
            form.add_error(None, e.messages)
    return render(request, "absence/request.html", {
        "form": form, "preview": preview, "unit": contracts.unit(employment, today), "for_employee": for_employee,
        "partial_allowed": "partial" in form.fields,
        "balances": balances.rows(employment, today, show_setup_gaps=access.can_view_restricted(request.user))})


@login_required
def request_leave(request):
    today = timezone.localdate()
    employee, employment = _my_employment(request, today)
    if employment is None:
        return render(request, "absence/request.html", {"no_employment": True, "employee": employee})

    def submit(fields):
        a = bookings.request(request.user, **fields)
        # after the service's transaction has committed, never inside it
        sent = notify.request_submitted(a) if a.status == S.REQUESTED else False
        _submit_message(request, a, sent)
        return redirect("absence:mine")

    return _request_page(request, employment, today, submit)


@login_required
def request_for(request, pk):
    """Record an absence for someone else. It is approved at once
    (bookings.record): the person recording it is the one who would have
    approved it, or an HR admin. The employee is emailed the decision."""
    employee = get_object_or_404(Employee, pk=pk)
    today = timezone.localdate()
    me = access.employee_for(request.user)
    if me is not None and me.pk == employee.pk:
        return redirect("absence:request")
    employment = employments.current(employee, today)
    if employment is None:
        if not access.can_view_restricted(request.user):
            raise PermissionDenied
        return render(request, "absence/request.html", {"no_employment": True, "employee": employee,
                                                        "for_employee": employee})
    if not access.may_record_for(request.user, employment, today):
        raise PermissionDenied
    recorder = me.name if me is not None else request.user.email

    def submit(fields):
        a = bookings.record(request.user, comment=f"Recorded by {recorder}", **fields)
        # after the service's transaction has committed, never inside it
        if not notify.request_decided(a):
            messages.warning(request, f"Saved, but the email to {employee.name} did not go. Let them know yourself.")
        messages.success(request, f"{a.absence_type.name} for {employee.name}: recorded and approved.")
        return redirect("absence:balances_for", employee.pk)

    return _request_page(request, employment, today, submit, for_employee=employee)


def _leave_year(employment, day):
    """(first day, last day) of the annual-leave year containing `day`, or
    (None, None) when there is no current employment or no policy to say:
    then My absences shows every earlier absence rather than guess. Reads
    only."""
    if employment is None:
        return None, None
    try:
        policy = policies.policy_for(employment, AbsenceType.objects.get(code="AL"), day)
    except (AbsenceType.DoesNotExist, ValidationError):
        return None, None
    return leave_year.bounds(policy, employment, day)


def _bank_groups(employment, rows, year_start, year_end):
    """The automatic bank-holiday rows by leave year: this one, then the
    next (the nightly charges both), each with its dates, rows and total.
    Without a known leave year, one group of everything."""
    names = dict(BankHoliday.objects.filter(nation="EW", date__in=[r["a"].start_date for r in rows])
                 .values_list("date", "name"))
    for r in rows:
        r["name"] = names.get(r["a"].start_date, "Bank holiday")
    rows.sort(key=lambda r: r["a"].start_date)
    if year_end is None:
        spans = [("this", None, None, rows)]
    else:
        next_start, next_end = _leave_year(employment, year_end + timedelta(days=1))
        next_start = next_start or year_end + timedelta(days=1)
        spans = [("this", year_start, year_end, [r for r in rows if r["a"].start_date <= year_end]),
                 ("next", next_start, next_end,
                  [r for r in rows if r["a"].start_date > year_end
                   and (next_end is None or r["a"].start_date <= next_end)])]
    return [{"which": which, "start": start, "end": end, "rows": group,
             "total": sum((r["a"].cost_units or 0 for r in group), Decimal("0"))}
            for which, start, end, group in spans if group or which == "this"]


def _toil(employment, today):
    """The TOIL card (toil.position), for someone with a contract today
    while the TOIL type is in use."""
    if employment is None or contracts.unit(employment, today) is None:
        return None
    if not AbsenceType.objects.filter(code="TOIL", active=True).exists():
        return None
    return toil.position(employment, today)


@login_required
def mine(request):
    """The employee's absences in three parts: coming up (requested or
    approved, not yet over, soonest first), earlier this leave year (newest
    first, declined and cancelled ones too), and the automatic bank-holiday
    rows of this leave year and the next, folded away under their counts
    and totals."""
    today = timezone.localdate()
    employee, employment = _my_employment(request, today)
    coming, earlier, bank = [], [], []
    year_start, year_end = _leave_year(employment, today)
    if employee is not None:
        summaries = {}
        qs = (Absence.objects.filter(employment__employee=employee)
              .select_related("absence_type", "employment__employee").prefetch_related("kit_days"))
        for a in qs:
            in_view = year_start is None or a.end_date >= year_start
            if a.auto_bank_holiday:
                if a.status == S.APPROVED and in_view:
                    bank.append({"a": a})
                continue
            upcoming = a.status in bookings.LIVE and a.end_date >= today
            if not (upcoming or in_view):
                continue
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
            (coming if upcoming else earlier).append({
                "a": a, "over": over, "can_cancel": _may_cancel(request.user, a, today),
                "kit": a.absence_type.is_family and a.status in bookings.LIVE,
            })
    coming.sort(key=lambda r: (r["a"].start_date, r["a"].pk))
    earlier.sort(key=lambda r: (r["a"].start_date, r["a"].pk), reverse=True)
    bank_groups = _bank_groups(employment, bank, year_start, year_end) if bank else []
    record_for = [e.employee for e in (access.direct_reports(employee, today) if employee else [])
                  if access.may_record_for(request.user, e, today)]
    return render(request, "absence/mine.html", {
        "employee": employee, "employment": employment, "coming": coming, "earlier": earlier,
        "bank": bank, "bank_this": bank_groups[0] if bank_groups else None,
        "bank_next": bank_groups[1] if len(bank_groups) > 1 else None, "bank_groups": bank_groups,
        "year_start": year_start, "year_end": year_end,
        "record_for": record_for, "record_any": access.can_view_restricted(request.user),
        "unit": contracts.unit(employment, today) if employment else "",
        "toil": _toil(employment, today),
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
