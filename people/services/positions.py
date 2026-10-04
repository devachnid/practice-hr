from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from people.models import Position
from people.services import audit, titles


def on(employment, day):
    return Position.objects.filter(
        employment=employment, from_date__lte=day
    ).filter(Q(to_date__isnull=True) | Q(to_date__gte=day)).select_related("title", "team", "line_manager")


def primary_on(employment, day):
    return on(employment, day).filter(primary=True).first()


def manager_of(employee, day):
    """The line manager of the employee's current primary position, or None."""
    from people.services import employments
    emp = employments.current(employee, day)
    if emp is None:
        return None
    pos = primary_on(emp, day)
    return pos.line_manager if pos else None


def _would_cycle(employee, manager, day):
    """Walking up from `manager` must never reach `employee`."""
    seen = set()
    cur = manager
    while cur is not None:
        if cur == employee:
            return True
        if cur.pk in seen:
            return True
        seen.add(cur.pk)
        cur = manager_of(cur, day)
    return False


def _primary_clash(employment, from_date, to_date, exclude_pk=None):
    if employment.pk is None:
        return False
    clash = Position.objects.filter(employment=employment, primary=True).filter(
        Q(to_date__isnull=True) | Q(to_date__gte=from_date))
    if to_date is not None:
        clash = clash.filter(from_date__lte=to_date)
    if exclude_pk is not None:
        clash = clash.exclude(pk=exclude_pk)
    return clash.exists()


def check_add(employment, line_manager, from_date, primary=True, to_date=None):
    """add()'s rules, without writing: raises ValidationError keyed by the
    field at fault."""
    if line_manager is not None:
        if line_manager == employment.employee:
            raise ValidationError({"line_manager": "A person cannot be their own manager."})
        if _would_cycle(employment.employee, line_manager, from_date):
            raise ValidationError({"line_manager": "That would make the reporting line a loop."})
    if primary and _primary_clash(employment, from_date, to_date):
        raise ValidationError({"primary": "There is already a primary position on those dates."})


def check_end(position, to_date):
    """end()'s rule, without writing. Only widening an already-bounded
    primary spell (extending it, or reopening it) can newly reach a later
    primary position; one that was already open-ended could never have let
    one exist."""
    if position.primary and position.to_date is not None and (to_date is None or to_date > position.to_date):
        if _primary_clash(position.employment, position.from_date, to_date, exclude_pk=position.pk):
            raise ValidationError({"primary": "There is already a primary position on those dates."})


@transaction.atomic
def add(actor, employment, title, team, line_manager, from_date, primary=True, to_date=None):
    """`title` is a PositionTitle; a name is accepted and looked up."""
    if isinstance(title, str):
        title = titles.get_or_create(title)
    check_add(employment, line_manager, from_date, primary, to_date)
    pos = Position(employment=employment, title=title, team=team, line_manager=line_manager,
                   primary=primary, from_date=from_date, to_date=to_date)
    pos.full_clean()
    pos.save()
    audit.record(actor, pos, {"created": ("", f"{title}, {team}, reports to {line_manager or 'nobody'}")})
    from onboarding.services import checklists   # here: onboarding imports this module
    # a starter checklist picks up its title and manager; an error there never stops the save
    checklists.guarded(actor, employment, "starter", checklists.position_added, pos)
    return pos


@transaction.atomic
def end(actor, position, to_date):
    check_end(position, to_date)
    before = position.to_date
    position.to_date = to_date
    position.full_clean()
    position.save()
    audit.record(actor, position, {"to_date": (before, to_date)})
    return position
