"""The checklist pages: Getting started (the person's own items, before
and after their first day), their details form (while its item is open), the Done / Not needed /
Add / Remove / Upload posts (an upload only to an open item, but for
HR), and HR's Starters and leavers list and
checklist page. Every write is a service's (checklists, employees, files);
a GET writes nothing. Done is checklists.may_complete's (the item's owner,
or HR), but an item with a link is never closed by its owner's Done: it
closes itself when the linked thing happens, and the details item is HR's
to close once they have checked the details. Not needed, Add and Remove
are HR's (access.can_view_restricted)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from checks.services import checks
from documents.services import files, policies
from onboarding.forms import AddItemForm, DetailsForm, contact_formset
from onboarding.middleware import pre_start
from onboarding.models import Checklist, ChecklistItem, Owner
from onboarding.services import checklists
from people.models import Employee
from people.services import access, employees



def _back(request, item):
    """Where a post returns to: the page it came from, from a fixed list
    (never a URL taken from the request)."""
    where = request.POST.get("next", "")
    if where == "me":
        return redirect("people:me")
    if where == "team":
        return redirect("people:team")
    if where == "hr" and access.can_view_restricted(request.user):
        return redirect("onboarding:hr_detail", item.checklist_id)
    if where == "start":
        return redirect("onboarding:getting_started")
    if access.can_view_restricted(request.user):
        return redirect("onboarding:hr_detail", item.checklist_id)
    if item.owner == Owner.MANAGER:
        return redirect("people:team")
    return redirect("onboarding:getting_started")


def _hr_only(request):
    if not access.can_view_restricted(request.user):
        raise PermissionDenied


@login_required
def getting_started(request):
    me = access.employee_for(request.user)
    today = timezone.localdate()
    ctx = {"employee": me, "items": [], "owed": [], "asked": [], "is_pre_start": pre_start(request)}
    if me is not None:
        ctx.update({"items": checklists.own_items(me, today), "owed": policies.owed(me, today),
                    "asked": checks.asked_of(me),
                    "start_date": me.employments.filter(start_date__gt=today).order_by("start_date")
                    .values_list("start_date", flat=True).first()})
    return render(request, "onboarding/getting_started.html", ctx)


def _details_open(employee):
    return ChecklistItem.objects.filter(checklist__employment__employee=employee, owner=Owner.PERSON,
                                        link="details", state=ChecklistItem.State.OPEN).exists()


@login_required
def details(request):
    """Your own details (there is no way to name someone else), and only
    while your checklist's details item is open: once HR has checked them
    and ticked it off, the form is gone (404), so bank and NI details are
    never changed here unseen. Anyone without such an item, an HR admin with
    no employee record included, gets 404."""
    me = access.employee_for(request.user)
    if me is None or not _details_open(me):
        raise Http404
    data = request.POST if request.method == "POST" else None
    form = DetailsForm(data, instance=Employee.objects.get(pk=me.pk))
    contacts = contact_formset(me, data)
    if data is not None and form.is_valid() and contacts.is_valid():
        try:
            with transaction.atomic():
                # a fresh row: the form has already copied its values onto
                # its instance, so diffing against that would audit nothing
                employees.update(request.user, Employee.objects.get(pk=me.pk), **form.cleaned_data)
                employees.set_emergency_contacts(request.user, me, contacts.rows())
                checklists.details_submitted(request.user, me)
        except ValidationError as e:
            form.add_error(None, e.messages)
        else:
            messages.success(request, "Saved. HR will check your details and tick them off your list.")
            return redirect("onboarding:getting_started")
    return render(request, "onboarding/details_form.html", {"employee": me, "form": form, "contacts": contacts})


@login_required
@require_POST
def complete(request, pk):
    item = get_object_or_404(ChecklistItem.objects.select_related("checklist"), pk=pk)
    if item.link and not access.can_view_restricted(request.user):
        raise PermissionDenied
    try:
        checklists.complete(request.user, item, request.POST.get("note", ""))
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    else:
        messages.success(request, f"{item.title}: done.")
    return _back(request, item)


@login_required
@require_POST
def not_needed(request, pk):
    _hr_only(request)
    item = get_object_or_404(ChecklistItem.objects.select_related("checklist"), pk=pk)
    try:
        checklists.not_needed(request.user, item, request.POST.get("note", ""))
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    else:
        messages.success(request, f"{item.title}: not needed.")
    return redirect("onboarding:hr_detail", item.checklist_id)


@login_required
@require_POST
def add_item(request, pk):
    _hr_only(request)
    cl = get_object_or_404(Checklist, pk=pk)
    form = AddItemForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Not added: " + " ".join(
            f"{form.fields[f].label or f.replace('_', ' ').capitalize()}: {' '.join(errs)}"
            for f, errs in form.errors.items()))
        return redirect("onboarding:hr_detail", cl.pk)
    d = form.cleaned_data
    try:
        checklists.add_item(request.user, cl, d["title"], d["instruction"], d["owner"], d["due_on"], d["link"])
    except ValidationError as e:
        messages.error(request, "Not added: " + " ".join(e.messages))
    else:
        messages.success(request, f"{d['title']}: added.")
    return redirect("onboarding:hr_detail", cl.pk)


@login_required
@require_POST
def remove_item(request, pk):
    _hr_only(request)
    item = get_object_or_404(ChecklistItem, pk=pk)
    checklist_id = item.checklist_id
    checklists.remove_item(request.user, item)
    messages.success(request, f"{item.title}: removed.")
    return redirect("onboarding:hr_detail", checklist_id)


@login_required
@require_POST
def upload(request, pk):
    """A file for an item linked to an upload ("upload:<category>"), from
    Getting started or My record: the person's own item, or HR on any. The
    file is stored by files.add, whose hook closes the item."""
    item = get_object_or_404(ChecklistItem.objects.select_related("checklist__employment__employee"), pk=pk)
    kind, _, category = item.link.partition(":")
    if kind != "upload" or not category:
        raise Http404
    me = access.employee_for(request.user)
    own = item.owner == Owner.PERSON and me is not None and item.owner_employee_id == me.pk
    if not (own or access.can_view_restricted(request.user)):
        raise PermissionDenied
    if item.state != ChecklistItem.State.OPEN and not access.can_view_restricted(request.user):
        messages.error(request, f"{item.title} is already closed: nothing was uploaded.")
        return _back(request, item)
    upload_ = request.FILES.get("file")
    if upload_ is None:
        messages.error(request, "Choose a file to upload.")
        return _back(request, item)
    try:
        files.add(request.user, item.checklist.employment.employee, category, item.title, upload_)
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    else:
        messages.success(request, f"{item.title}: uploaded.")
    return _back(request, item)


@login_required
def hr_list(request):
    _hr_only(request)
    rows = []
    for cl in (Checklist.objects.filter(completed_at__isnull=True)
               .select_related("employment__employee").prefetch_related("items")):
        emp = cl.employment
        rows.append({"checklist": cl, "employee": emp.employee,
                     "date": emp.start_date if cl.kind == "starter" else emp.end_date,
                     "summary": checklists.summary(cl), "gaps": checklists.gaps(cl)})
    rows.sort(key=lambda r: (r["date"] is None, r["date"], r["employee"].name))
    return render(request, "onboarding/hr_list.html", {"rows": rows})


@login_required
def hr_detail(request, pk):
    _hr_only(request)
    cl = get_object_or_404(Checklist.objects.select_related("employment__employee"), pk=pk)
    items = list(cl.items.select_related("owner_employee", "done_by").order_by("due_on", "order", "pk"))
    employee = cl.employment.employee
    return render(request, "onboarding/hr_detail.html", {
        "checklist": cl, "employee": employee, "items": items, "summary": checklists.summary(cl),
        "gaps": checklists.gaps(cl), "add_form": AddItemForm(initial={"due_on": timezone.localdate()}),
        "employee_admin_url": reverse("admin:people_employee_change", args=[employee.pk]),
        "today": timezone.localdate()})
