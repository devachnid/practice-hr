"""The admin's check forms. Each runs checks.validate and sniffs an upload,
so a refusal shows on the form before anything is written (a clear check
of a type whose evidence is a file needs its file: uploaded here, or
already sent by the person); CheckAdmin then writes through checks.record
/ checks.complete (each storing an upload last, through files.add) and
checks.ask."""
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from unfold.widgets import (UnfoldAdminFileFieldWidget, UnfoldAdminSelectWidget, UnfoldAdminTextareaWidget,
                            UnfoldAdminTextInputWidget, UnfoldBooleanWidget)

from checks.models import Check, CheckType
from checks.services import checks
from documents.services import files
from people.models import Employee

RESULT_FIELDS = ["done_on", "outcome", "expires_on", "reference", "note", "upload", "dbs_level",
                 "dbs_update_service"]
LABELS = {"done_on": "Done on", "expires_on": "Expires on", "dbs_level": "DBS disclosure level",
          "dbs_update_service": "On the DBS update service"}
HELP = {
    "expires_on": "Blank: worked out from the check type's validity (none for a one-off check).",
    "reference": "The certificate or registration number, for a type whose evidence is a reference.",
    "note": "HR only. Never shown to the person or their manager.",
    "dbs_level": "Needed for a DBS check.",
}


class DateInput(UnfoldAdminTextInputWidget):
    input_type = "date"


class _Result(forms.ModelForm):
    """The result of a check: shared by the add page and Complete."""
    upload = forms.FileField(label="Evidence file", required=False, widget=UnfoldAdminFileFieldWidget,
                             help_text="PDF, JPEG, PNG or DOCX, for a type whose evidence is a file (needed "
                                       "for a clear result unless the person has sent it). Never a DBS "
                                       "certificate: record its number instead.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["done_on"].required = True
        self.fields["outcome"].required = True
        self.fields["outcome"].choices = Check.Outcome.choices

    def _check_type(self):
        raise NotImplementedError

    def _evidence(self):
        """Evidence the check has already (the person's upload on a request)."""
        return None

    def clean_upload(self):
        upload = self.cleaned_data.get("upload")
        if upload:
            files.sniff(upload)
        return upload

    def clean(self):
        data = super().clean()
        check_type = self._check_type()
        if check_type is None or self.errors:
            return data
        try:
            checks.validate(check_type, data.get("done_on"), data.get("outcome"),
                            {**data, "evidence": self._evidence()}, timezone.localdate())
        except ValidationError as e:
            self.add_error(None, e)
        if data.get("upload") and check_type.evidence != CheckType.Evidence.FILE:
            self.add_error("upload", f"{check_type} takes no file.")
        return data


class RecordForm(_Result):
    class Meta:
        model = Check
        fields = ["employee", "check_type", *[f for f in RESULT_FIELDS if f != "upload"]]
        labels = LABELS
        help_texts = HELP

    field_order = ["employee", "check_type", *RESULT_FIELDS]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["check_type"].queryset = CheckType.objects.filter(active=True)

    def _check_type(self):
        return self.cleaned_data.get("check_type")


class CompleteForm(_Result):
    """Completing an awaiting check: its person and type are fixed."""
    class Meta:
        model = Check
        fields = [f for f in RESULT_FIELDS if f != "upload"]
        labels = LABELS
        help_texts = HELP
        widgets = {"done_on": DateInput, "expires_on": DateInput, "outcome": UnfoldAdminSelectWidget,
                   "reference": UnfoldAdminTextInputWidget, "note": UnfoldAdminTextareaWidget,
                   "dbs_level": UnfoldAdminSelectWidget, "dbs_update_service": UnfoldBooleanWidget}

    field_order = RESULT_FIELDS

    def _check_type(self):
        return self.instance.check_type

    def _evidence(self):
        return self.instance.evidence


class AskForm(forms.Form):
    employee = forms.ModelChoiceField(queryset=Employee.objects.all(), widget=UnfoldAdminSelectWidget,
                                      label="Person")
    check_type = forms.ModelChoiceField(queryset=CheckType.objects.filter(active=True),
                                        widget=UnfoldAdminSelectWidget, label="Check",
                                        help_text="They see it on My record (on Getting started before their "
                                                  "first day), with an upload form for a type whose "
                                                  "evidence is a file.")
