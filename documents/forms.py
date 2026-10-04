"""The admin's upload and issue forms, and the person's sign form. An
upload is sniffed on the form, so a file whose bytes disagree with its
extension is refused before anything is written; FileAdmin.save_model then
stores it through files.add, PolicyAdmin's issue action through
policies.issue."""
from django import forms
from django.utils import timezone
from unfold.widgets import UnfoldAdminFileFieldWidget, UnfoldAdminIntegerFieldWidget, UnfoldAdminTextInputWidget

from documents.models import File, PolicyVersion
from documents.services import files


class UploadForm(forms.ModelForm):
    upload = forms.FileField(label="File", widget=UnfoldAdminFileFieldWidget,
                             help_text="PDF, JPEG, PNG or DOCX.")

    class Meta:
        model = File
        fields = ["employee", "category", "title", "upload", "hr_only"]
        labels = {"hr_only": "HR only"}
        help_texts = {"hr_only": "Not shown to the person on their own record."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Files without a person (policy versions) are added by their own service.
        self.fields["employee"].required = True

    def clean_upload(self):
        upload = self.cleaned_data["upload"]
        files.sniff(upload)
        return upload


class DateInput(UnfoldAdminTextInputWidget):
    input_type = "date"


class IssueForm(forms.Form):
    """A new version of one policy (PolicyAdmin's Issue new version)."""
    label = forms.CharField(max_length=40, widget=UnfoldAdminTextInputWidget,
                            help_text="What this version is called, e.g. v2 or October edition. Shown in "
                                      "the sentence people sign.")
    issued_on = forms.DateField(widget=DateInput, initial=timezone.localdate)
    sign_within_days = forms.IntegerField(label="Sign within (days)", initial=14, min_value=1, max_value=365,
                                          widget=UnfoldAdminIntegerFieldWidget,
                                          help_text="From the issue date, or from a later starter's first day.")
    upload = forms.FileField(label="File", widget=UnfoldAdminFileFieldWidget, help_text="PDF, JPEG, PNG or DOCX.")

    def __init__(self, *args, policy, **kwargs):
        super().__init__(*args, **kwargs)
        self.policy = policy

    def clean_label(self):
        label = self.cleaned_data["label"].strip()
        if PolicyVersion.objects.filter(policy=self.policy, label=label).exists():
            raise forms.ValidationError("This policy already has a version with that label.")
        return label

    def clean_upload(self):
        upload = self.cleaned_data["upload"]
        files.sniff(upload)
        return upload


class SignForm(forms.Form):
    """The sign page: the exact sentence as the label of a box that must be
    ticked, and the password typed again (the passkey button sends a
    credential instead; the view reads it). The password is never echoed."""
    confirm = forms.BooleanField(error_messages={"required": "Tick the box to confirm you have read it."})
    password = forms.CharField(label="Your password", required=False, strip=False,
                               widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
                               help_text="Typed again, to show it is you signing.")

    def __init__(self, *args, sentence, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["confirm"].label = sentence
