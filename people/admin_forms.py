"""The admin's forms. Each runs its service's rules in clean(), through the
services' check_* helpers, so a refused change re-renders the page with the
error beside the row that caused it and the typed values kept — rather
than saving the rest, dropping that row, and showing its error beside
"changed successfully". The services run the same checks again when they
write; these only move the refusal to where it can be shown."""

from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from unfold.widgets import UnfoldAdminSelectWidget, UnfoldBooleanSwitchWidget

from accounts.services import logins
from people import ni
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
    """The employee page. On the add page two extra fields make their login
    (accounts.services.logins): Create a login account, ticked by default,
    and where the invitation goes. EmployeeAdmin leaves both out of the
    change page."""
    LOGIN_FIELDS = ("create_login", "invite_to")

    create_login = forms.BooleanField(
        label="Create a login account", required=False, initial=True, widget=UnfoldBooleanSwitchWidget,
        help_text="Their login is the work email; they are emailed a link to choose a password. Untick to "
                  "link a login that already exists in User, or to give them none.")
    invite_to = forms.ChoiceField(
        label="Send the invitation to", choices=[(logins.WORK, "Work email"), (logins.PERSONAL, "Personal email")],
        initial=logins.WORK, required=False, widget=UnfoldAdminSelectWidget,
        help_text="Personal email for a starter who cannot read the work mailbox yet; the login stays "
                  "the work email.")

    class Meta:
        model = Employee
        fields = ["first_name", "last_name", "preferred_name", "work_email", "personal_email",
                  "phone", "date_of_birth", "address_line1", "address_line2", "town", "postcode",
                  "ni_number", "bank_account_name", "bank_sort_code", "bank_account_number", "user"]

    actor = None            # EmployeeAdmin.get_form sets the requester: whose add this is

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "ni_number" in self.fields:     # left out for someone not shown it (EmployeeAdmin.get_fields)
            ni.accept_typed(self)

    def clean_ni_number(self):
        return ni.normalise(self.cleaned_data.get("ni_number"))

    def clean(self):
        data = super().clean()
        if "create_login" not in self.fields or not data.get("create_login"):
            return data
        if data.get("user") is not None:
            self.add_error("user", "Untick Create a login account to link an existing one.")
        if data.get("invite_to") == logins.PERSONAL and not data.get("personal_email"):
            self.add_error("invite_to", "Enter their personal email, or send the invitation to the work email.")
        if data.get("work_email"):
            try:
                logins.check_available(data["work_email"], self.actor, data.get("invite_to") or logins.WORK)
            except ValidationError as exc:
                self.add_error("work_email", exc)
        return data


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
