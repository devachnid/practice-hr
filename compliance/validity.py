"""The expiry arithmetic and the status rule that checks and training
share. Pure functions of dates: no models, no "today" of their own."""
import calendar
from datetime import timedelta

WINDOW_DAYS = 60     # "due soon" starts this many days before expiry, unless the reminder schedule says otherwise


def expires_from(done_on, validity_months):
    """`done_on` plus the months, clipped to the month's end (31 Jan plus one
    month is 28 or 29 Feb); None for a blank validity, which never expires."""
    if validity_months is None:
        return None
    month = done_on.month - 1 + validity_months
    year = done_on.year + month // 12
    month = month % 12 + 1
    day = min(done_on.day, calendar.monthrange(year, month)[1])
    return done_on.replace(year=year, month=month, day=day)


def status(expires_on, has_latest, required, today, window_days):
    """not_required, missing, current, due_soon (expiry within the window,
    today included) or lapsed (expiry before today)."""
    if not required:
        return "not_required"
    if not has_latest:
        return "missing"
    if expires_on is None:
        return "current"
    if expires_on < today:
        return "lapsed"
    if expires_on <= today + timedelta(days=window_days):
        return "due_soon"
    return "current"
