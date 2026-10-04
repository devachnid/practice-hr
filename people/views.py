from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_safe

from checks.services import checks
from people.models import Employee
from people.services import access, contracts, employees, employments, patterns, positions, retention


class PersonalDetailsForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["personal_email", "phone", "address_line1", "address_line2", "town", "postcode"]
        labels = {"address_line1": "Address line 1", "address_line2": "Address line 2"}
        # The person's own details, so the browser may offer what it knows.
        # Set here rather than site-wide: the admin's forms are about
        # someone else, where the HR admin's own saved email would be wrong.
        widgets = {
            "personal_email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel"}),
            "address_line1": forms.TextInput(attrs={"autocomplete": "address-line1"}),
            "address_line2": forms.TextInput(attrs={"autocomplete": "address-line2"}),
            "town": forms.TextInput(attrs={"autocomplete": "address-level2"}),
            "postcode": forms.TextInput(attrs={"autocomplete": "postal-code"}),
        }


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
    ctx = {"employee": employee, "employment": emp, "form": form,
           # listing titles is not opening a file: no audit until files.open
           "files": employee.files.filter(hr_only=False, superseded_by__isnull=True),
           "checks": checks.state(employee, today) if access.can_view_checks(request.user, employee) else []}
    if emp:
        from onboarding.services import checklists   # onboarding imports people's services
        ctx["checklist_items"] = [i for i in checklists.own_items(employee, today)
                                  if i.checklist.employment_id == emp.pk]
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
    from onboarding.services import checklists    # onboarding imports people's services
    # a manager whose starter has not started yet has no report today, but has their items
    todo = checklists.items_owned_by(me_, today) if me_ else []
    if not (me_ and (todo or access.is_approver(request.user, today))):
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
            # counts and the next expiry only: a manager never sees which checks
            "checks": checks.summary(emp.employee, today),
        })
    return render(request, "people/team.html", {"rows": rows, "todo": todo, "today": today})


CATEGORY_LABELS = {
    "personal": "Personal record",
    "pay": "Pay records",
    "health": "Health records",
    "audit": "Audit log",
    "checks": "Pre-employment and other checks",
    "files": "Stored files",
    "signatures": "Policy signatures",
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
