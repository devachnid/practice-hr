"""The admin's forms. Each runs its service's rules in clean(), through the
services' check_* helpers, so a refused change re-renders the page with the
error beside the row that caused it and the typed values kept — rather
than saving the rest, dropping that row, and showing its error beside
"changed successfully". The services run the same checks again when they
write; these only move the refusal to where it can be shown."""

from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from people.models import Contract, Employee, Employment, Position
from people.services import contracts, employments, positions

ONLY_END = "Existing positions and contracts only end; add a new row for a change."


def add_error(form, error):
    """Put a service's ValidationError on the form: on its field where the
    form has that field, as a non-field error otherwise."""
    if hasattr(error, "error_dict"):
        for field, errors in error.error_dict.items():
            form.add_error(field if field in form.fields else None, errors)
    else:
        form.add_error(None, error)


def _rows(formset):
    """The forms that would be saved: changed, valid so far, not deleted."""
    for form in formset.forms:
        if not form.has_changed() or form.errors:
            continue
        if formset.can_delete and formset._should_delete_form(form):
            continue
        yield form


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["first_name", "last_name", "preferred_name", "work_email", "personal_email",
                  "phone", "date_of_birth", "address_line1", "address_line2", "town", "postcode",
                  "ni_number", "bank_account_name", "bank_sort_code", "bank_account_number", "user"]


def check_employment(form, employee, fresh, data, changed):
    """The employment rules for one form: a new spell (fresh is None), or a
    change to an existing one."""
    try:
        if fresh is None:
            employments.check_start(employee, data["start_date"], data.get("end_date"))
            return
        if "end_date" in changed or "leaving_reason" in changed:
            employments.check_end(fresh, data.get("end_date"))
        if "start_date" in changed or "continuous_service_date" in changed:
            employments.check_amend(fresh, data.get("start_date"))
    except ValidationError as e:
        add_error(form, e)


class EmploymentForm(forms.ModelForm):
    class Meta:
        model = Employment
        fields = ["employee", "start_date", "end_date", "leaving_reason", "continuous_service_date"]

    def clean(self):
        data = super().clean()
        if self.errors:
            return data
        if self.instance.pk is None:
            if data.get("employee") is not None:
                check_employment(self, data["employee"], None, data, self.changed_data)
        else:
            fresh = Employment.objects.get(pk=self.instance.pk)
            check_employment(self, fresh.employee, fresh, data, self.changed_data)
        return data


class EmploymentInlineFormSet(BaseInlineFormSet):
    """Employment rows on the Employee page."""

    def clean(self):
        super().clean()
        for form in _rows(self):
            fresh = (Employment.objects.get(pk=form.instance.pk)
                     if form.instance.pk is not None else None)
            check_employment(form, self.instance, fresh, form.cleaned_data, form.changed_data)


class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = ["title", "team", "line_manager", "primary", "from_date", "to_date"]


class PositionInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        for form in _rows(self):
            data = form.cleaned_data
            try:
                if form.instance.pk is None:
                    positions.check_add(self.instance, data.get("line_manager"), data["from_date"],
                                        data.get("primary", False), data.get("to_date"))
                elif set(form.changed_data) - {"to_date"}:
                    form.add_error(None, ONLY_END)
                else:
                    positions.check_end(Position.objects.get(pk=form.instance.pk), data.get("to_date"))
            except ValidationError as e:
                add_error(form, e)


class ContractForm(forms.ModelForm):
    class Meta:
        model = Contract
        fields = ["contract_type", "basis", "from_date", "to_date", "weekly_amount", "notes"]


class ContractInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        for form in _rows(self):
            data = form.cleaned_data
            try:
                if form.instance.pk is None:
                    contracts.check_add(self.instance, data["contract_type"], data["from_date"],
                                        data.get("to_date"))
                elif set(form.changed_data) - {"to_date"}:
                    form.add_error(None, ONLY_END)
                else:
                    contracts.check_end(Contract.objects.get(pk=form.instance.pk), data.get("to_date"))
            except ValidationError as e:
                add_error(form, e)
