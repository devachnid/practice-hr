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


class TypeSelect(forms.Select):
    """The type <select>. Each option carries its type's flags, which
    absence/static/absence/request.js reads to show only the groups of the
    form the chosen type uses: sickness (health_sensitive) and family leave
    (is_family). Part of a day depends on the employment, not the type."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        t = getattr(value, "instance", None)
        if t is not None:
            option["attrs"].update({
                "data-health-sensitive": "1" if t.health_sensitive else "0",
                "data-family": "1" if t.is_family else "0",
            })
        return option


class RequestForm(forms.Form):
    """A request, checked against the requester's employment. The part-day
    fields are left out for anyone whose allowance is not in hours; the
    category and the family dates are there for everyone and used only by
    the types they belong to: clean() blanks them for any other type. A part
    day, where the allowance is in hours, is open to every type. The page
    groups the fields; its script hides and disables the sickness and family
    groups for a type that does not use them, so their values are kept but
    not sent. Without script every group shows, and what the server accepts
    is the same."""
    absence_type = forms.ModelChoiceField(
        queryset=AbsenceType.objects.filter(active=True).exclude(code="BH"), label="Type", widget=TypeSelect)
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

    def __init__(self, *args, employment=None, today=None, whose="your", **kw):
        super().__init__(*args, **kw)
        self.employment = employment
        self.whose = whose
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
                raise forms.ValidationError(f"Those dates are outside {self.whose} employment, which runs {runs}.")
        return d


class DecisionForm(forms.Form):
    action = forms.ChoiceField(choices=[("approve", "Approve"), ("decline", "Decline")])
    comment = forms.CharField(required=False, max_length=300)


class KitDayForm(forms.Form):
    date = _date(label="Keeping-in-touch day")


class PayrollPeriodForm(forms.Form):
    period = forms.RegexField(regex=r"^\d{4}-\d{2}$", max_length=7, label="Month (YYYY-MM)")


class ToilClaimForm(forms.Form):
    """A TOIL claim's shape: the day worked, how much and why. The rules
    (not after today, whole steps, a contract that day) are the service's,
    toil.check; the step and the latest day are also put on the inputs."""
    day = _date(label="Day worked")
    units = forms.DecimalField(max_digits=5, decimal_places=2, label="Hours worked in lieu")
    reason = forms.CharField(max_length=200, label="What for",
                             help_text="The clinic or cover, say. Your approver sees it, and it is noted on the ledger.")

    def __init__(self, *args, unit="hours", today=None, whose="your", window=None, **kw):
        super().__init__(*args, **kw)
        if today is not None:
            self.fields["day"].widget.attrs["max"] = today.isoformat()
        self.fields["day"].help_text = ("Today or earlier" + (f", up to {window} days ago: older TOIL would "
                                                              f"already have expired." if window else "."))
        sessions = unit == "sessions"
        step = "0.5" if sessions else "0.25"
        self.fields["units"].widget.attrs.update(step=step, min=step)
        self.fields["units"].label = "Sessions worked in lieu" if sessions else "Hours worked in lieu"
        self.fields["units"].help_text = ("In half sessions." if sessions
                                          else "In quarter hours: 1.25 is an hour and a quarter.")
        if whose != "your":
            self.fields["reason"].help_text = "The clinic or cover, say. Noted on the ledger, which they see."
