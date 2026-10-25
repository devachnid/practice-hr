"""The admin's training forms. Each runs the service's date and course
rules and sniffs an upload, so a refusal shows on the form before anything
is written; the admin then writes through training.record,
training.set_expiry, sessions.record_session, training.verify and
training.reject."""
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from unfold.widgets import (UnfoldAdminFileFieldWidget, UnfoldAdminSelectMultipleWidget, UnfoldAdminSelectWidget,
                            UnfoldAdminTextareaWidget, UnfoldAdminTextInputWidget)

from documents.services import files
from people.models import Employee
from people.services import employments
from training.models import Course, TrainingRecord, TrainingSession
from training.services import training


class DateInput(UnfoldAdminTextInputWidget):
    input_type = "date"


class AdminRecordForm(forms.ModelForm):
    upload = forms.FileField(label="Certificate", required=False, widget=UnfoldAdminFileFieldWidget,
                             help_text="PDF, JPEG, PNG or DOCX, if there is one.")

    class Meta:
        model = TrainingRecord
        fields = ["employee", "course", "done_on", "expires_on", "note"]
        labels = {"done_on": "Done on", "expires_on": "Expires on"}
        help_texts = {"expires_on": "Blank: worked out from the course's validity (none for a one-off course).",
                      "note": "Seen by HR and the line manager, never the person."}

    field_order = ["employee", "course", "done_on", "expires_on", "upload", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["course"].queryset = Course.objects.filter(active=True)
        self.fields["done_on"].required = True

    def clean_upload(self):
        upload = self.cleaned_data.get("upload")
        if upload:
            files.sniff(upload)
        return upload

    def clean(self):
        data = super().clean()
        if data.get("done_on") and not self.errors:
            try:
                training.check_date(data["done_on"], timezone.localdate())
            except ValidationError as e:
                self.add_error("done_on", e)
        return data


class AdminSessionForm(forms.ModelForm):
    upload = forms.FileField(label="Attendance sheet", required=False, widget=UnfoldAdminFileFieldWidget,
                             help_text="PDF, JPEG, PNG or DOCX, if there is one. Shared by everyone's record.")
    attendees = forms.ModelMultipleChoiceField(queryset=Employee.objects.none(), label="Who attended",
                                               widget=UnfoldAdminSelectMultipleWidget,
                                               help_text="Everyone employed today. Hold Ctrl or Cmd to pick several.")

    class Meta:
        model = TrainingSession
        fields = ["course", "held_on", "trainer", "note"]
        labels = {"held_on": "Held on"}
        widgets = {"held_on": DateInput, "course": UnfoldAdminSelectWidget, "trainer": UnfoldAdminTextInputWidget,
                   "note": UnfoldAdminTextareaWidget}

    field_order = ["course", "held_on", "trainer", "attendees", "upload", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields["course"].queryset = Course.objects.filter(active=True)
        self.fields["held_on"].required = True
        self.fields["attendees"].queryset = (Employee.objects.filter(pk__in=employments.active_on(today)
                                                                    .values("employee_id"))
                                             .order_by("last_name", "first_name"))

    def clean_upload(self):
        upload = self.cleaned_data.get("upload")
        if upload:
            files.sniff(upload)
        return upload

    def clean(self):
        data = super().clean()
        if data.get("held_on") and not self.errors:
            try:
                training.check_date(data["held_on"], timezone.localdate(), what="held")
            except ValidationError as e:
                self.add_error("held_on", e)
        return data


class AdminRejectForm(forms.Form):
    note = forms.CharField(label="Why it is turned down", max_length=200, widget=UnfoldAdminTextareaWidget,
                           help_text="The person is emailed this, with where to record it again.")
