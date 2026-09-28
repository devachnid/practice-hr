from datetime import date

import pytest
from django.core.exceptions import ValidationError

from tests.factories import make_employment


def test_active_on_respects_both_bounds(db):
    emp = make_employment(start=date(2026, 4, 6), end_date=date(2026, 9, 30))
    assert not emp.is_active_on(date(2026, 4, 5))
    assert emp.is_active_on(date(2026, 4, 6))
    assert emp.is_active_on(date(2026, 9, 30))
    assert not emp.is_active_on(date(2026, 10, 1))


def test_open_ended_is_active_forever(db):
    emp = make_employment()
    assert emp.is_active_on(date(2099, 1, 1))


def test_end_before_start_refused(db):
    emp = make_employment()
    emp.end_date = emp.start_date.replace(day=1)
    with pytest.raises(ValidationError):
        emp.full_clean()


def test_service_date_defaults_to_start(db):
    emp = make_employment()
    assert emp.continuous_service_date == emp.start_date
