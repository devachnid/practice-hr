from django import template
from django.template.defaultfilters import date as date_filter
from django.template.defaultfilters import floatformat

register = template.Library()


@register.filter
def units(value, unit=""):
    """An amount in the employment's unit: "22.50 hours", "3 sessions"."""
    if value is None:
        return "—"
    return f"{floatformat(value, '-2')} {unit or ''}".strip()


@register.filter
def when(absence):
    """An absence's dates as the requester gave them: halves or times."""
    start = date_filter(absence.start_date, "j M Y")
    if absence.is_partial:
        return f"{start}, {absence.start_time:%H:%M}–{absence.end_time:%H:%M} ({floatformat(absence.hours, '-2')} hours)"
    first = start + (" (afternoon)" if absence.start_half == "PM" else "")
    if absence.end_date == absence.start_date:
        return first + (" (morning)" if absence.end_half == "AM" else "")
    last = date_filter(absence.end_date, "j M Y") + (" (morning)" if absence.end_half == "AM" else "")
    return f"{first} – {last}"


STATUS_TONES = {"requested": "badge-warning", "approved": "badge-ok",
                "declined": "badge-muted", "cancelled": "badge-muted"}


@register.filter
def status_tone(status):
    """The .badge modifier for an absence's status (components.css)."""
    return STATUS_TONES.get(status, "badge-muted")
