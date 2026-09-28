from datetime import date

from people.models import Employee, Employment, Team  # noqa: E402

MON = date(2026, 4, 6)  # a Monday, in the 2026/27 leave year


def make_employee(first="Sam", last="Patel", email=None, **kw):
    """Default emails carry a counter so two default employees never collide."""
    email = email or f"{first}.{last}.{Employee.objects.count() + 1}@example.org".lower()
    return Employee.objects.create(first_name=first, last_name=last, work_email=email, **kw)


def make_employment(employee=None, start=MON, **kw):
    employee = employee or make_employee()
    kw.setdefault("continuous_service_date", start)
    return Employment.objects.create(employee=employee, start_date=start, **kw)


def make_team(name="Reception", **kw):
    return Team.objects.create(name=name, **kw)


from people.models import Position  # noqa: E402


def make_position(employment, manager=None, title="Receptionist", team=None, start=None, **kw):
    team = team or Team.objects.first() or make_team()
    return Position.objects.create(
        employment=employment, title=title, team=team, line_manager=manager,
        from_date=start or employment.start_date, **kw)
