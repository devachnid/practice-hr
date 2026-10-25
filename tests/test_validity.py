"""The expiry arithmetic and the status rule checks and training share."""
import calendar
from datetime import date, timedelta

import pytest

from compliance import validity

Y = 2031      # a fixed year: the arithmetic is pure, no calendar dependence


def test_expires_from_adds_calendar_months_clipped_to_the_month_end():
    assert validity.expires_from(date(Y, 1, 31), 12) == date(Y + 1, 1, 31)
    assert validity.expires_from(date(Y, 1, 31), 1) == date(Y, 2, 29 if calendar.isleap(Y) else 28)
    assert validity.expires_from(date(Y, 12, 15), 13) == date(Y + 2, 1, 15)
    assert validity.expires_from(date(Y, 3, 31), 36) == date(Y + 3, 3, 31)


def test_a_blank_validity_never_expires():
    assert validity.expires_from(date(Y, 1, 31), None) is None


@pytest.mark.parametrize("expires_in,has_latest,required,expected", [
    (None, False, False, "not_required"),
    (10, True, False, "not_required"),       # a record the title no longer needs
    (None, False, True, "missing"),
    (None, True, True, "current"),           # a one-off: no expiry, current for good
    (61, True, True, "current"),
    (60, True, True, "due_soon"),            # the window's first day
    (0, True, True, "due_soon"),             # valid through today
    (-1, True, True, "lapsed"),
])
def test_status_follows_the_expiry_and_the_window(expires_in, has_latest, required, expected):
    today = date(Y, 6, 1)
    expires_on = today + timedelta(days=expires_in) if expires_in is not None else None
    assert validity.status(expires_on, has_latest, required, today, window_days=60) == expected


def test_the_window_is_the_callers():
    today = date(Y, 6, 1)
    assert validity.status(today + timedelta(days=20), True, True, today, window_days=10) == "current"
    assert validity.status(today + timedelta(days=10), True, True, today, window_days=10) == "due_soon"
    assert validity.WINDOW_DAYS == 60
