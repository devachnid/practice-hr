from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from people.models import AuditEntry, Employment
from people.services import employments
from tests.factories import make_employee, make_employment


def test_start_and_current(hr_admin):
    e = make_employee()
    emp = employments.start(hr_admin, e, date(2026, 4, 6))
    assert employments.current(e, date(2026, 4, 6)) == emp
    assert employments.current(e, date(2026, 4, 5)) is None
    assert AuditEntry.objects.filter(model="people.employment", object_id=emp.pk).exists()


def test_end_then_return_the_next_day(hr_admin):
    e = make_employee()
    first = employments.start(hr_admin, e, date(2024, 1, 1))
    employments.end(hr_admin, first, date(2026, 3, 31), Employment.LeavingReason.RESIGNED)
    second = employments.start(hr_admin, e, date(2026, 4, 1))
    assert employments.current(e, date(2026, 3, 31)) == first
    assert employments.current(e, date(2026, 4, 1)) == second


def test_overlapping_spell_refused(hr_admin):
    e = make_employee()
    employments.start(hr_admin, e, date(2026, 1, 1))
    with pytest.raises(ValidationError):
        employments.start(hr_admin, e, date(2026, 6, 1))


def test_service_years_reads_service_date(db):
    emp = make_employment(start=date(2026, 4, 6), continuous_service_date=date(2020, 10, 6))
    assert employments.service_years(emp, date(2026, 4, 6)) == Decimal("5.49")   # 182/365 into year six
    assert employments.service_years(emp, date(2025, 10, 5)) == Decimal("4.99")
    assert employments.service_years(emp, date(2025, 10, 6)) == Decimal("5.00")


def test_service_years_on_the_anniversary_is_whole(db):
    emp = make_employment(start=date(2026, 4, 1), continuous_service_date=date(2021, 10, 1))
    assert employments.service_years(emp, date(2026, 9, 30)) == Decimal("4.99")
    assert employments.service_years(emp, date(2026, 10, 1)) == Decimal("5.00")
    leap = make_employment(employee=make_employee(first="Lea"), start=date(2026, 4, 1),
                           continuous_service_date=date(2024, 2, 29))
    assert employments.service_years(leap, date(2025, 2, 28)) == Decimal("1.00")


def test_amend_refuses_a_start_date_overlapping_an_earlier_spell(hr_admin):
    e = make_employee()
    first = employments.start(hr_admin, e, date(2024, 1, 1))
    employments.end(hr_admin, first, date(2024, 12, 31), Employment.LeavingReason.RESIGNED)
    second = employments.start(hr_admin, e, date(2025, 1, 1))
    with pytest.raises(ValidationError):
        employments.amend(hr_admin, second, start_date=date(2024, 6, 1))
    second.refresh_from_db()
    assert second.start_date == date(2025, 1, 1)


def test_end_refuses_extending_past_a_following_spell(hr_admin):
    """Finding 3 (round 2): end() must re-check the overlap when it
    widens an already-bounded spell (a later end_date, or none at all)."""
    e = make_employee()
    first = employments.start(hr_admin, e, date(2024, 1, 1))
    employments.end(hr_admin, first, date(2024, 6, 30), Employment.LeavingReason.RESIGNED)
    employments.start(hr_admin, e, date(2024, 7, 1))
    with pytest.raises(ValidationError):
        employments.end(hr_admin, first, date(2024, 12, 31), Employment.LeavingReason.RESIGNED)
    first.refresh_from_db()
    assert first.end_date == date(2024, 6, 30)


def test_active_on_filters_by_day(db):
    a = make_employment(start=date(2026, 1, 1), end_date=date(2026, 6, 30),
                        leaving_reason="resigned")
    b = make_employment(employee=make_employee(first="Bo"), start=date(2026, 7, 1))
    assert list(employments.active_on(date(2026, 3, 1))) == [a]
    assert list(employments.active_on(date(2026, 8, 1))) == [b]
