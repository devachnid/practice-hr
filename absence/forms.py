from django import forms
from django.utils import dateformat

from absence.models import Absence, AbsenceType
from people.services import contracts

HALF_START = [("", "All day"), ("PM", "Afternoon only")]
HALF_END = [("", "All day"), ("AM", "Morning only")]


def _date(**kw):
    return forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), **kw)


def _time(**kw):
    return forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"), **kw)


class RequestForm(forms.Form):
    """A request, checked against the requester's employment. The part-day
    fields are left out for anyone whose allowance is not in hours; the
    category and the family dates are shown to everyone and used only by
    the types they belong to (no script, so nothing is hidden)."""
    absence_type = forms.ModelChoiceField(
        queryset=AbsenceType.objects.filter(active=True).exclude(code="BH"), label="Type")
    start_date = _date(label="First day")
    end_date = _date(required=False, label="Last day", help_text="Leave empty for a single day.")
    start_half = forms.ChoiceField(choices=HALF_START, required=False, label="On the first day")
    end_half = forms.ChoiceField(choices=HALF_END, required=False, label="On the last day")
    partial = forms.BooleanField(required=False, label="Part of a day, in hours",
                                 help_text="Then give the times and the hours, for the first day only.")
    start_time = _time(required=False, label="From")
    end_time = _time(required=False, label="Until")
    hours = forms.DecimalField(required=False, min_value=0, decimal_places=2)
    category = forms.ChoiceField(choices=[("", "—")] + Absence.Category.choices, required=False,
                                 label="Kind of sickness", help_text="Sickness only, in broad terms.")
    expected_start = _date(required=False, help_text="Family leave only.")
    expected_return = _date(required=False, help_text="Family leave only.")

    def __init__(self, *args, employment=None, today=None, **kw):
        super().__init__(*args, **kw)
        self.employment = employment
        if employment is not None and today is not None and contracts.unit(employment, today) != "hours":
            for name in ("partial", "start_time", "end_time", "hours"):
                del self.fields[name]

    def clean(self):
        d = super().clean()
        d["end_date"] = d.get("end_date") or d.get("start_date")
        if d.get("partial"):
            if not (d.get("start_time") and d.get("end_time") and d.get("hours")):
                raise forms.ValidationError("A part day needs a start time, an end time and the hours.")
            d["end_date"] = d["start_date"]
            d["start_half"] = d["end_half"] = ""
        else:
            d["start_time"] = d["end_time"] = d["hours"] = None
        t = d.get("absence_type")
        if t and t.code == "SICK" and not d.get("category"):
            self.add_error("category", "Say which kind, in broad terms.")
        if t and t.code != "SICK":
            d["category"] = ""
        if t and not t.is_family:
            d["expected_start"] = d["expected_return"] = None
        emp = self.employment
        if emp is not None and d.get("start_date") and d.get("end_date"):
            if not (emp.is_active_on(d["start_date"]) and emp.is_active_on(d["end_date"])):
                runs = f"from {dateformat.format(emp.start_date, 'j M Y')}"
                if emp.end_date:
                    runs += f" to {dateformat.format(emp.end_date, 'j M Y')}"
                raise forms.ValidationError(f"Those dates are outside your employment, which runs {runs}.")
        return d


class DecisionForm(forms.Form):
    action = forms.ChoiceField(choices=[("approve", "Approve"), ("decline", "Decline")])
    comment = forms.CharField(required=False, max_length=300)


class KitDayForm(forms.Form):
    date = _date(label="Keeping-in-touch day")


class PayrollPeriodForm(forms.Form):
    period = forms.RegexField(regex=r"^\d{4}-\d{2}$", label="Month (YYYY-MM)")
