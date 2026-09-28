from datetime import date

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext

from people.context_processors import roles
from people.services import access, positions
from tests.factories import make_employee, make_employment, make_team

User = get_user_model()
DAY = date(2026, 6, 1)


def _person(first, user=None):
    e = make_employee(first=first, user=user)
    return e, make_employment(employee=e, start=date(2026, 1, 1))


def test_route_and_reports(hr_admin, employee_user):
    boss, boss_emp = _person("Boss", user=hr_admin)
    sam, sam_emp = _person("Sam", user=employee_user)
    positions.add(None, sam_emp, "Receptionist", make_team(), boss, DAY)
    assert access.line_manager(sam, DAY) == boss
    assert access.route_for(sam_emp, DAY) == boss
    assert access.direct_reports(boss, DAY) == [sam_emp]
    assert access.is_approver(hr_admin, DAY)
    assert not access.is_approver(employee_user, DAY)


def test_route_without_manager_goes_to_admin_group(db):
    sam, sam_emp = _person("Sam")
    positions.add(None, sam_emp, "Manager", make_team(), None, DAY)
    assert access.route_for(sam_emp, DAY) is None


def test_route_to_admin_group_when_manager_has_left(db):
    boss, boss_emp = _person("Boss")
    sam, sam_emp = _person("Sam")
    positions.add(None, sam_emp, "Receptionist", make_team(), boss, date(2026, 1, 1))
    from people.services import employments
    employments.end(None, boss_emp, date(2026, 5, 31), "resigned")
    assert access.route_for(sam_emp, DAY) is None
    assert access.route_for(sam_emp, date(2026, 5, 1)) == boss


def test_can_view(hr_admin, employee_user):
    other_user = User.objects.create_user(email="o@example.org", password="pw")
    boss, boss_emp = _person("Boss", user=other_user)
    sam, sam_emp = _person("Sam", user=employee_user)
    stranger, _ = _person("Stranger")
    positions.add(None, sam_emp, "Receptionist", make_team(), boss, DAY)
    assert access.can_view(employee_user, sam)
    assert access.can_view(other_user, sam)
    assert not access.can_view(employee_user, boss)
    assert not access.can_view(employee_user, stranger)
    assert access.can_view(hr_admin, stranger)
    assert access.can_view_restricted(hr_admin)
    assert not access.can_view_restricted(other_user)


def test_employee_for(employee_user):
    assert access.employee_for(employee_user) is None
    sam, _ = _person("Sam", user=employee_user)
    assert access.employee_for(employee_user) == sam


def test_roles_context_processor_memoises_per_request(hr_admin):
    request = RequestFactory().get("/")
    request.user = hr_admin
    roles(request)
    with CaptureQueriesContext(connection) as ctx:
        roles(request)
    assert len(ctx.captured_queries) == 0
