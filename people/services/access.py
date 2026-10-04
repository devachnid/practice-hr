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


def may_record_for(user, employment, day):
    """Who records an absence for someone else (spec §5, "or by their
    manager on the day"): the person their requests are routed to, and HR
    admins. Never for yourself: that is an ordinary request."""
    me = employee_for(user)
    if me is not None and me.pk == employment.employee_id:
        return False
    if can_view_restricted(user):
        return True
    return me is not None and route_for(employment, day) == me


def can_view_file(user, file):
    """HR always; the person their own unless HR-only; any employee a
    policy version's file (category Policy, no person: the policies page's
    Read link); nobody else (managers never see documents)."""
    if can_view_restricted(user):
        return True
    me = employee_for(user)
    if me is None:
        return False
    if file.category == "policy" and file.employee_id is None and not file.hr_only:
        return True
    return file.employee_id == me.pk and not file.hr_only


def can_view_checks(user, employee):
    """A person's checks in detail: HR always, and the person themselves
    (never HR's note: the page leaves it out). A line manager sees only a
    per-report summary (checks.summary) on My team, never the detail."""
    if can_view_restricted(user):
        return True
    me = employee_for(user)
    return me is not None and me.pk == employee.pk


def is_pre_start(user, day):
    """A starter before their first day: a login linked to an employee with
    no current employment and one that starts after `day`. Never an HR
    admin (or superuser): HR is never gated, whatever their own record says."""
    if can_view_restricted(user):
        return False
    me = employee_for(user)
    return me is not None and employee_is_pre_start(me, day)


def employee_is_pre_start(employee, day):
    """The person has no current employment and one that starts after `day`."""
    return (employments.current(employee, day) is None
            and employee.employments.filter(start_date__gt=day).exists())
