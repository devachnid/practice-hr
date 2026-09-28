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


from decimal import Decimal  # noqa: E402

from people.models import Contract, ContractType  # noqa: E402


def make_contract_type(name="Reception", unit="hours", full_time=Decimal("37.5")):
    ct, _ = ContractType.objects.get_or_create(
        name=name, defaults={"unit": unit, "full_time_weekly": full_time})
    return ct


def make_contract(employment, ctype=None, amount=Decimal("37.5"), start=None, **kw):
    ctype = ctype or make_contract_type()
    return Contract.objects.create(
        employment=employment, contract_type=ctype, weekly_amount=amount,
        from_date=start or employment.start_date, **kw)


from people.models import PatternDay, WorkingPattern  # noqa: E402


def make_pattern(employment, days=None, effective_from=None):
    days = days if days is not None else {d: (Decimal("3.75"), Decimal("3.75")) for d in range(5)}
    pattern = WorkingPattern.objects.create(
        employment=employment, effective_from=effective_from or employment.start_date)
    for weekday in range(7):
        am, pm = days.get(weekday, (Decimal("0"), Decimal("0")))
        PatternDay.objects.create(pattern=pattern, weekday=weekday, am_units=am, pm_units=pm)
    return pattern
