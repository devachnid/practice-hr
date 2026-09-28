"""Who is off, and who is present. Only approved absences count (a request
waiting is not on the calendar), and an automatic bank-holiday row is not
"someone off": everyone has the day. Colleagues see the type's calendar
label and nothing else; an HR admin, asking for `detail`, also sees the
type's name. A sickness category is never read here."""

import calendar as cal
from datetime import timedelta

from django.db.models import Q

from absence.models import Absence
from absence.services import costing
from people.models import Position


def _load(start, end, team):
    """What a run of days needs, in two queries: the approved absences that
    touch them and, for a team, the primary positions that do."""
    absences = list(Absence.objects.filter(
        status=Absence.Status.APPROVED, auto_bank_holiday=False, start_date__lte=end, end_date__gte=start,
    ).select_related("employment__employee", "absence_type"))
    spells = None
    if team is not None:
        spells = list(Position.objects.filter(team=team, primary=True, from_date__lte=end)
                      .filter(Q(to_date__isnull=True) | Q(to_date__gte=start))
                      .select_related("employment__employee"))
    return absences, spells


def _members(spells, day):
    return [p.employment for p in spells if p.is_active_on(day) and p.employment.is_active_on(day)]


def _halves(absence, cache):
    if absence.pk not in cache:
        by_day = {}
        for d, half in costing.halves_covered(absence):
            by_day.setdefault(d, []).append(half)
        cache[absence.pk] = by_day
    return cache[absence.pk]


def _off(day, absences, spells, cache, detail):
    ids = None if spells is None else {e.pk for e in _members(spells, day)}
    rows = []
    for a in absences:
        if not (a.start_date <= day <= a.end_date) or (ids is not None and a.employment_id not in ids):
            continue
        label = a.absence_type.calendar_label
        shown = label
        if detail and a.absence_type.name != label:
            shown = f"{label} · {a.absence_type.name}"
        rows.append({"employee": a.employment.employee, "label": shown,
                     "partial_hours": a.hours if a.is_partial else None,
                     "halves": _halves(a, cache)[day], "employment_id": a.employment_id,
                     "whole_day": not a.is_partial})
    return rows


def _present(day, absences, spells, cache):
    members = _members(spells, day)
    away = {r["employment_id"] for r in _off(day, absences, spells, cache, False) if r["whole_day"]}
    return len(members) - len(away), len(members)


def _public(rows):
    return [{k: v for k, v in r.items() if k not in ("employment_id", "whole_day")} for r in rows]


def off_on(day, team=None, detail=False):
    """Who is off on a day: employee, label, partial_hours, halves."""
    absences, spells = _load(day, day, team)
    return _public(_off(day, absences, spells, {}, detail))


def present(team, day):
    """(present, headcount) for a team on a day. Someone off for part of a
    day is still present."""
    absences, spells = _load(day, day, team)
    return _present(day, absences, spells, {})


def days_for(start, end, team, detail=False):
    """One dict per day from start to end: day, off, present, headcount."""
    absences, spells = _load(start, end, team)
    cache, out, day = {}, [], start
    while day <= end:
        p, n = _present(day, absences, spells, cache) if team else (None, None)
        out.append({"day": day, "off": _public(_off(day, absences, spells, cache, detail)),
                    "present": p, "headcount": n})
        day += timedelta(days=1)
    return out


def warning_if_approved(absence, team):
    """A sentence when approving would leave the team under its minimum, else None."""
    if not team or not team.min_present or absence.is_partial:
        return None
    absences, spells = _load(absence.start_date, absence.end_date, team)
    cache, day = {}, absence.start_date
    while day <= absence.end_date:
        p, _ = _present(day, absences, spells, cache)
        if p - 1 < team.min_present:
            return f"Approving leaves fewer than {team.min_present} of {team} present on {day:%-d %b %Y}."
        day += timedelta(days=1)
    return None


def month(year, month_, team=None, detail=False):
    """The month as weeks of seven days: day, in_month, off (only in the month)."""
    grid = cal.Calendar(firstweekday=0).monthdatescalendar(year, month_)
    absences, spells = _load(grid[0][0], grid[-1][-1], team)
    cache = {}
    return [[{"day": d, "in_month": d.month == month_,
              "off": _public(_off(d, absences, spells, cache, detail)) if d.month == month_ else []}
             for d in week] for week in grid]
