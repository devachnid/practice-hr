from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_safe

from people.models import Employee
from people.services import access, contracts, employees, employments, patterns, positions, retention


class PersonalDetailsForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["personal_email", "phone", "address_line1", "address_line2", "town", "postcode"]


@login_required
def me(request):
    employee = access.employee_for(request.user)
    if employee is None:
        return render(request, "people/me.html", {"employee": None})
    today = timezone.localdate()
    if request.method == "POST":
        form = PersonalDetailsForm(request.POST, instance=employee)
        if form.is_valid():
            # The form has already copied its values onto `employee`
            # (ModelForm._post_clean), so diffing against it would find
            # nothing to audit. The service diffs a fresh row instead.
            employees.update(request.user, Employee.objects.get(pk=employee.pk),
                             **form.cleaned_data)
            messages.success(request, "Saved.")
            return redirect("people:me")
    else:
        form = PersonalDetailsForm(instance=employee)
    emp = employments.current(employee, today)
    ctx = {"employee": employee, "employment": emp, "form": form}
    if emp:
        ctx.update({
            "position": positions.primary_on(emp, today),
            "contracts": list(contracts.active_on(emp, today)),
            "contracted": contracts.contracted_amount(emp, today),
            "unit": contracts.unit(emp, today),
            "pattern": patterns.pattern_on(emp, today),
        })
    return render(request, "people/me.html", ctx)


@login_required
def team(request):
    me_ = access.employee_for(request.user)
    today = timezone.localdate()
    if not (me_ and access.is_approver(request.user, today)):
        raise PermissionDenied
    rows = []
    for emp in access.direct_reports(me_, today):
        pattern = patterns.pattern_on(emp, today)
        rows.append({
            "employee": emp.employee,
            "position": positions.primary_on(emp, today),
            "contracted": contracts.contracted_amount(emp, today),
            "unit": contracts.unit(emp, today),
            "pattern_total": patterns.weekly_total(pattern) if pattern else None,
        })
    return render(request, "people/team.html", {"rows": rows})


CATEGORY_LABELS = {
    "personal": "Personal record",
    "pay": "Pay records",
    "health": "Health records",
    "audit": "Audit log",
}


@login_required
@require_safe
def retention_report(request):
    """What is past its retention period, for HR to act on. Lists only: who,
    which category, when their employment ended and how long overdue. No
    figures, no absence detail, and nothing here deletes anything."""
    if not access.can_view_restricted(request.user):
        raise PermissionDenied
    today = timezone.localdate()
    people = {}
    for r in retention.due(today):
        entry = people.setdefault(r["employee"].pk, {
            "employee": r["employee"], "ended": r["ended"], "categories": []})
        entry["categories"].append({
            "label": CATEGORY_LABELS.get(r["category"], r["category"].title()),
            "due_since": r["due_since"],
            "overdue_days": (today - r["due_since"]).days,
        })
    rows = sorted(people.values(), key=lambda p: (p["ended"], p["employee"].name))
    return render(request, "people/retention.html", {"rows": rows})
