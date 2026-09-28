"""Who may see and decide what. Read by views, templates and the admin;
every rule about relationship-based access lives here."""

from django.db.models import Q

from people.models import Employee, Position
from people.services import employments, positions


def employee_for(user):
    if user is None or not user.is_authenticated:
        return None
    return Employee.objects.filter(user=user).first()


def line_manager(employee, day):
    return positions.manager_of(employee, day)


def direct_reports(manager, day):
    rows = (Position.objects.filter(line_manager=manager, primary=True, from_date__lte=day)
            .filter(Q(to_date__isnull=True) | Q(to_date__gte=day))
            .select_related("employment__employee"))
    return [p.employment for p in rows if p.employment.is_active_on(day)]


def is_approver(user, day):
    me = employee_for(user)
    return bool(me) and bool(direct_reports(me, day))


def can_view_restricted(user):
    return bool(user and user.is_authenticated and (user.is_hr_admin or user.is_superuser))


def can_view(user, employee, day=None):
    from django.utils import timezone
    day = day or timezone.localdate()
    if can_view_restricted(user):
        return True
    me = employee_for(user)
    if me is None:
        return False
    if me == employee:
        return True
    return line_manager(employee, day) == me


def route_for(employment, day):
    """The approver for a request from this employment, or None for the
    HR admin group: no manager, or the requester tops their own chain."""
    manager = line_manager(employment.employee, day)
    if manager is None:
        return None
    if employments.current(manager, day) is None:
        return None
    return manager
