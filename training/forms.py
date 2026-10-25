"""The site's training forms. None saves anything: the views pass cleaned
data to the services, which apply the rules (a certificate for an online
course, who may record for whom) and refuse on the page."""
from django import forms

from people.models import Employee, Team
from training.models import Course

ACCEPT = ".pdf,.jpg,.jpeg,.png,.docx"


class DateInput(forms.DateInput):
    input_type = "date"


def _courses():
    return Course.objects.filter(active=True)


class SelfRecordForm(forms.Form):
    course = forms.ModelChoiceField(queryset=_courses(), label="Course")
    done_on = forms.DateField(label="Date done", widget=DateInput)
    file = forms.FileField(label="Certificate", required=False, widget=forms.ClearableFileInput(attrs={"accept": ACCEPT}),
                           help_text="PDF, JPEG, PNG or DOCX. Needed for an online course.")


class RecordForm(forms.Form):
    """A manager's or HR's record for someone else (Task 9)."""
    course = forms.ModelChoiceField(queryset=_courses(), label="Course")
    done_on = forms.DateField(label="Date done", widget=DateInput)
    file = forms.FileField(label="Certificate", required=False, widget=forms.ClearableFileInput(attrs={"accept": ACCEPT}),
                           help_text="PDF, JPEG, PNG or DOCX, if there is one.")
    note = forms.CharField(label="Note", required=False, widget=forms.Textarea(attrs={"rows": 2}),
                           help_text="Seen by HR and managers, never the person.")


class RejectForm(forms.Form):
    note = forms.CharField(label="Why it is turned down", max_length=200, widget=forms.Textarea(attrs={"rows": 3}),
                           help_text="The person is emailed this, with where to record it again.")


class SessionForm(forms.Form):
    course = forms.ModelChoiceField(queryset=_courses(), label="Course")
    held_on = forms.DateField(label="Date held", widget=DateInput)
    trainer = forms.CharField(label="Trainer", required=False, max_length=120,
                              help_text="An outside provider or a colleague's name.")
    note = forms.CharField(label="Note", required=False, widget=forms.Textarea(attrs={"rows": 2}))
    file = forms.FileField(label="Attendance sheet", required=False,
                           widget=forms.ClearableFileInput(attrs={"accept": ACCEPT}),
                           help_text="PDF, JPEG, PNG or DOCX, if there is one. Shared by everyone's record.")
    attendees = forms.ModelMultipleChoiceField(queryset=Employee.objects.none(), label="Who attended",
                                               widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, attendees_queryset, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["attendees"].queryset = attendees_queryset


class MatrixFilterForm(forms.Form):
    """The matrix's GET filters. Unknown values are dropped, never an error:
    the page always renders."""
    course = forms.ModelChoiceField(queryset=Course.objects.filter(active=True), required=False, label="Course",
                                    empty_label="Every course")
    team = forms.ModelChoiceField(queryset=Team.objects.all(), required=False, label="Team", empty_label="Every team")
    q = forms.CharField(required=False, max_length=60, label="Name")
    show = forms.ChoiceField(required=False, label="Show", choices=[
        ("all", "Everyone"), ("problems", "Problems only"), ("to_verify", "To verify")])

    def filters(self):
        """Clean what is there; anything invalid is as if it were not given."""
        self.is_valid()
        d = self.cleaned_data if hasattr(self, "cleaned_data") else {}
        return {"course": d.get("course") or None, "team": d.get("team") or None, "query": d.get("q") or "",
                "show": d.get("show") or "all"}
