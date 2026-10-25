"""The site's training pages. Every write is a service's (training,
sessions); a GET writes nothing. Recording your own (self_record) returns
to My record, or to Getting started before your first day."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from people.models import Employee
from people.services import access, employments
from training.forms import MatrixFilterForm, RecordForm, RejectForm, SelfRecordForm, SessionForm
from training.models import TrainingRecord
from training.services import matrix, sessions, training


def _own_page(request):
    if access.is_pre_start(request.user, timezone.localdate()):
        return redirect("onboarding:getting_started")
    return redirect("people:me")


def _form_errors(form):
    return " ".join(e for errors in form.errors.values() for e in errors)


@login_required
@require_POST
def self_record(request):
    form = SelfRecordForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, _form_errors(form))
        return _own_page(request)
    d = form.cleaned_data
    try:
        training.self_record(request.user, d["course"], d["done_on"], upload=d.get("file") or None)
    except PermissionDenied:
        messages.error(request, "There is no employee record linked to your login yet. Ask the practice manager.")
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    else:
        messages.success(request, f"Recorded. HR or your manager will verify your {d['course']} training.")
    return _own_page(request)


def _person_or_403(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if not access.can_view_training(request.user, employee):
        raise PermissionDenied
    return employee


@login_required
@require_safe
def person(request, pk):
    """One person's training, for HR, the person and their line manager:
    the rows with the note (HR and the manager only), a record form for
    those who may record for them, Verify / Reject on pending rows."""
    employee = _person_or_403(request, pk)
    today = timezone.localdate()
    can_record = access.may_record_training_for(request.user, employee, today)
    me = access.employee_for(request.user)
    if access.can_view_restricted(request.user):
        back = reverse("admin:people_employee_change", args=[employee.pk])
    elif me is not None and me.pk == employee.pk:
        back = reverse("onboarding:getting_started" if access.is_pre_start(request.user, today) else "people:me")
    else:
        back = reverse("people:team")
    return render(request, "training/person.html", {
        "employee": employee, "rows": training.state(employee, today),
        "can_record": can_record, "form": RecordForm(initial={"done_on": today}) if can_record else None,
        "back": back})


@login_required
@require_POST
def record(request, pk):
    employee = _person_or_403(request, pk)
    if not access.may_record_training_for(request.user, employee, timezone.localdate()):
        raise PermissionDenied
    form = RecordForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, _form_errors(form))
        return redirect("training:person", employee.pk)
    d = form.cleaned_data
    try:
        training.record(request.user, employee, d["course"], d["done_on"], upload=d.get("file") or None,
                        note=d["note"])
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    else:
        messages.success(request, f"{d['course']} recorded for {employee.name}.")
    return redirect("training:person", employee.pk)


def _record_or_403(request, pk):
    rec = get_object_or_404(TrainingRecord.objects.select_related("employee", "course"), pk=pk)
    if not access.may_verify(request.user, rec):
        raise PermissionDenied
    return rec


@login_required
@require_POST
def verify(request, pk):
    rec = _record_or_403(request, pk)
    try:
        training.verify(request.user, rec)
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    else:
        messages.success(request, f"{rec.course} verified for {rec.employee.name}.")
    return redirect("training:person", rec.employee_id)


@login_required
@require_http_methods(["GET", "POST"])
def reject(request, pk):
    """GET asks why; only the POST rejects (and emails the person)."""
    rec = _record_or_403(request, pk)
    form = RejectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            training.reject(request.user, rec, form.cleaned_data["note"])
        except ValidationError as e:
            form.add_error(None, e.messages)
        else:
            messages.success(request, f"{rec.course} turned down for {rec.employee.name}; they have been told why.")
            return redirect("training:person", rec.employee_id)
    return render(request, "training/reject.html", {"record": rec, "form": form})


@login_required
@require_http_methods(["GET", "POST"])
def session(request):
    """Record a face-to-face group: HR for anyone employed today, a manager
    for their reports today (sessions.record_session checks the day held)."""
    today = timezone.localdate()
    hr = access.can_view_restricted(request.user)
    if hr:
        pks = employments.active_on(today).values("employee_id")
    else:
        me = access.employee_for(request.user)
        reports = access.direct_reports(me, today) if me is not None else []
        if not reports:
            raise PermissionDenied
        pks = [emp.employee_id for emp in reports]
    candidates = Employee.objects.filter(pk__in=pks).order_by("last_name", "first_name")
    form = SessionForm(request.POST or None, request.FILES or None, attendees_queryset=candidates,
                       initial={"held_on": today})
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            s = sessions.record_session(request.user, d["course"], d["held_on"], list(d["attendees"]),
                                        trainer=d["trainer"], note=d["note"], upload=d.get("file") or None)
        except PermissionDenied:
            form.add_error("attendees", "Only people who report to you on that date.")
        except ValidationError as e:
            form.add_error(None, e.messages)
        else:
            n = s.records.count()
            messages.success(request, f"{s.course} on {s.held_on:%-d %b %Y} recorded for {n} "
                                      f"{'person' if n == 1 else 'people'}.")
            return redirect("admin:training_trainingsession_changelist" if hr else "people:team")
    return render(request, "training/session.html", {"form": form, "hr": hr})


def _matrix(request):
    if not access.can_view_restricted(request.user):
        raise PermissionDenied
    form = MatrixFilterForm(request.GET)
    f = form.filters()
    today = timezone.localdate()
    return form, f, today, matrix.build(today, **f)


@login_required
@require_safe
def matrix_page(request):
    """HR's training matrix: people down, courses across, filtered by the
    form (GET; the page writes nothing). Each name opens the person page."""
    form, f, today, m = _matrix(request)
    return render(request, "training/matrix.html", {
        "form": form, "courses": m.courses,
        "grid": [(entry.employee, [entry.cells.get(c.pk) for c in m.courses]) for entry in m.rows], "today": today,
        "csv_url": f"{reverse('training:matrix_csv')}?{request.GET.urlencode()}" if request.GET else
        reverse("training:matrix_csv")})


@login_required
@require_safe
def matrix_csv(request):
    form, f, today, m = _matrix(request)
    response = HttpResponse(matrix.to_csv(m), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{matrix.filename(today, **f)}"'
    return response
