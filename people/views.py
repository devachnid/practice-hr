from datetime import date

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from people.models import Employee
from people.services import access, contracts, employees, employments, patterns, positions


class PersonalDetailsForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["personal_email", "phone", "address_line1", "address_line2", "town", "postcode"]


@login_required
def me(request):
    employee = access.employee_for(request.user)
    if employee is None:
        return render(request, "people/me.html", {"employee": None})
    today = date.today()
    if request.method == "POST":
        form = PersonalDetailsForm(request.POST, instance=employee)
        if form.is_valid():
            employees.update(request.user, employee, **form.cleaned_data)
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
    today = date.today()
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
