"""The admin's upload form. The upload is sniffed here, so a file whose
bytes disagree with its extension is refused on the form, before anything
is written; FileAdmin.save_model then stores it through files.add."""
from django import forms
from unfold.widgets import UnfoldAdminFileFieldWidget

from documents.models import File
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
