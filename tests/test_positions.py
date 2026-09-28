from datetime import date

import pytest
from django.core.exceptions import ValidationError

from people.services import positions
from tests.factories import make_employee, make_employment, make_team


def _two():
    a = make_employment(employee=make_employee(first="Ann"))
    b = make_employment(employee=make_employee(first="Ben"))
    return a, b


def test_add_and_primary_on(hr_admin):
    a, b = _two()
    team = make_team()
    p = positions.add(hr_admin, b, "Receptionist", team, a.employee, b.start_date)
    assert positions.primary_on(b, b.start_date) == p
    assert positions.primary_on(b, date(2020, 1, 1)) is None


def test_self_management_refused(hr_admin):
    a, _ = _two()
    with pytest.raises(ValidationError):
        positions.add(hr_admin, a, "Manager", make_team(), a.employee, a.start_date)


def test_cycle_refused(hr_admin):
    a, b = _two()
    team = make_team()
    positions.add(hr_admin, b, "Receptionist", team, a.employee, b.start_date)
    with pytest.raises(ValidationError):
        positions.add(hr_admin, a, "Lead", team, b.employee, a.start_date)


def test_second_primary_on_same_dates_refused(hr_admin):
    a, b = _two()
    team = make_team()
    positions.add(hr_admin, b, "Receptionist", team, a.employee, b.start_date)
    with pytest.raises(ValidationError):
        positions.add(hr_admin, b, "Admin", team, a.employee, b.start_date)
    positions.add(hr_admin, b, "Admin", team, a.employee, b.start_date, primary=False)
    assert positions.on(b, b.start_date).count() == 2


def test_end_position(hr_admin):
    a, b = _two()
    p = positions.add(hr_admin, b, "Receptionist", make_team(), a.employee, b.start_date)
    positions.end(hr_admin, p, date(2026, 12, 31))
    assert positions.primary_on(b, date(2027, 1, 1)) is None
