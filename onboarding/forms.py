"""The starter's details form (their own record, written by
employees.update and employees.set_emergency_contacts) and HR's Add item
form. No form here saves anything: the views pass cleaned data to the
services."""
from django import forms

from onboarding.models import Owner
from people import ni
from people.models import Employee


class DetailsForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["preferred_name", "personal_email", "phone", "address_line1", "address_line2", "town",
                  "postcode", "ni_number", "bank_account_name", "bank_sort_code", "bank_account_number"]
        labels = {"preferred_name": "Preferred name", "address_line1": "Address line 1",
                  "address_line2": "Address line 2", "bank_account_name": "Name on the account",
                  "bank_sort_code": "Sort code", "bank_account_number": "Account number"}
        help_texts = {"preferred_name": "What you would like to be called at work, if not your first name.",
                      "bank_sort_code": "Six digits as NN-NN-NN.", "bank_account_number": "Eight digits."}
        # The person's own details, so the browser may offer what it knows
        # (as people.views.PersonalDetailsForm); bank details are never
        # offered or kept by the browser.
        widgets = {
            "personal_email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel"}),
            "address_line1": forms.TextInput(attrs={"autocomplete": "address-line1"}),
            "address_line2": forms.TextInput(attrs={"autocomplete": "address-line2"}),
            "town": forms.TextInput(attrs={"autocomplete": "address-level2"}),
            "postcode": forms.TextInput(attrs={"autocomplete": "postal-code"}),
            "ni_number": forms.TextInput(attrs={"autocomplete": "off"}),
            "bank_account_name": forms.TextInput(attrs={"autocomplete": "off"}),
            "bank_sort_code": forms.TextInput(attrs={"autocomplete": "off", "inputmode": "numeric"}),
            "bank_account_number": forms.TextInput(attrs={"autocomplete": "off", "inputmode": "numeric"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ni.accept_typed(self)              # "ab 12 34 56 c" as printed on a payslip

    def clean_ni_number(self):
        return ni.normalise(self.cleaned_data.get("ni_number"))


class EmergencyContactForm(forms.Form):
    """One contact. A row left wholly blank is no contact; one begun needs
    a name and a phone number."""
    name = forms.CharField(max_length=120, required=False)
    relationship = forms.CharField(max_length=60, required=False)
    phone = forms.CharField(max_length=30, required=False,
                            widget=forms.TextInput(attrs={"inputmode": "tel"}))

    def clean(self):
        data = super().clean()
        if any(data.get(f) for f in ("name", "relationship", "phone")):
            for field in ("name", "phone"):
                if not data.get(field):
                    self.add_error(field, "Needed for a contact.")
        return data


class BaseEmergencyContactFormSet(forms.BaseFormSet):
    def rows(self):
        """The contacts given, in order, blank rows left out."""
        return [f.cleaned_data for f in self.forms
                if f.cleaned_data and any(f.cleaned_data.get(k) for k in ("name", "relationship", "phone"))]


EmergencyContactFormSet = forms.formset_factory(EmergencyContactForm, formset=BaseEmergencyContactFormSet,
                                                extra=3, max_num=3, validate_max=True)


def contact_formset(employee, data=None):
    initial = list(employee.emergency_contacts.values("name", "relationship", "phone"))
    return EmergencyContactFormSet(data, initial=initial, prefix="contacts")


class AddItemForm(forms.Form):
    title = forms.CharField(max_length=120)
    instruction = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    owner = forms.ChoiceField(choices=Owner.choices)
    due_on = forms.DateField(label="Due", widget=forms.DateInput(attrs={"type": "date"}))
    link = forms.CharField(max_length=40, required=False,
                           help_text='Optional: "details", "sign_policies", "upload:<category>" or '
                                     '"check:<check type code>", which close it automatically.')
