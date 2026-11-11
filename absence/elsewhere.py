"""Leave held somewhere else. With SHIFT_CENTRAL_URL set, AMG Shift Central
is the practice's leave system (its requirements, PAT-07) and this app's own
leave is switched off: the screens say where leave is, the nightly leaves the
pots alone, the payroll file keeps what HR still holds and the absences feed
is empty. The data and the code stay; unset the setting and it is all back."""

from functools import wraps

from django.conf import settings
from django.shortcuts import render


def url():
    """Shift Central's address with a closing slash, or "" when leave is here."""
    base = settings.SHIFT_CENTRAL_URL
    return f"{base}/" if base else ""


def moved(view):
    """A leave view while leave is elsewhere: one page saying so, whoever asks
    and however (a link in an old email included), and nothing is changed."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if url():
            return render(request, "absence/moved.html", {"leave_url": url()})
        return view(request, *args, **kwargs)
    return wrapper
