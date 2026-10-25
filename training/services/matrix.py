"""The training matrix: everyone employed today down the side, courses
across, each cell a training.Row. Built from a handful of queries whatever
the practice's size (the people, their primary positions, the courses and
their titles, the records), never one per person or per cell. Read-only;
the CSV is the same grid as text."""
import csv
import io
from collections import defaultdict
from dataclasses import dataclass, field

from django.db.models import Q
from django.utils.text import slugify

from compliance import validity
from people.models import Position
from people.services import employments
from training.models import Course, TrainingRecord
from training.services import training

SHOW = ("all", "problems", "to_verify")


@dataclass
class Entry:
    employee: object
    cells: dict = field(default_factory=dict)       # course pk -> training.Row


@dataclass
class Matrix:
    courses: list
    rows: list


def _wanted(row, show):
    if show == "to_verify":
        return row.pending is not None
    if show == "problems":
        return row.status in training.PROBLEMS or row.status == "awaiting_verification" or row.pending is not None
    return True


def build(today, course=None, team=None, query="", show="all", window_days=validity.WINDOW_DAYS):
    emps = list(employments.active_on(today).select_related("employee")
                .order_by("employee__last_name", "employee__first_name", "employee_id"))
    query = (query or "").strip().lower()
    if query:
        emps = [m for m in emps if query in m.employee.name.lower()]
    primaries = {p.employment_id: p for p in
                 Position.objects.filter(employment_id__in=[m.pk for m in emps], primary=True, from_date__lte=today)
                 .filter(Q(to_date__isnull=True) | Q(to_date__gte=today))}
    if team is not None:
        emps = [m for m in emps if m.pk in primaries and primaries[m.pk].team_id == team.pk]
    by_pk = {c.pk: c for c in Course.objects.all()}
    everyone, by_title = set(), defaultdict(set)
    for c in Course.objects.filter(active=True).prefetch_related("positions"):
        if c.everyone:
            everyone.add(c.pk)
        for t in c.positions.all():
            by_title[t.pk].add(c.pk)
    records = defaultdict(lambda: defaultdict(list))
    for r in (TrainingRecord.objects.filter(employee_id__in=[m.employee_id for m in emps])
              .select_related("certificate", "session").order_by("-done_on", "-id")):
        records[r.employee_id][r.course_id].append(r)
    rows, shown = [], set()
    for m in emps:
        pos = primaries.get(m.pk)
        required = everyone | (by_title.get(pos.title_id, set()) if pos is not None else set())
        wanted = {course.pk} if course is not None else required | set(records[m.employee_id])
        cells = {}
        for pk in wanted:
            recs = records[m.employee_id].get(pk, [])
            if course is not None and pk not in required and not recs:
                continue                      # neither needs nor has the filtered course: an empty cell
            row = training.build_row(by_pk[pk], recs, pk in required, today, window_days)
            if _wanted(row, show):
                cells[pk] = row
        if show != "all" and not cells:
            continue
        rows.append(Entry(m.employee, cells))
        shown |= set(cells)
    if course is not None:
        courses = [course]                    # the filtered course is the column, even with nobody to show
    else:
        courses = sorted((by_pk[pk] for pk in shown), key=lambda c: (c.display_order, c.name))
        if show == "all":                     # a column this person neither needs nor has reads "Not required"
            for entry in rows:
                for c in courses:
                    if c.pk not in entry.cells:
                        entry.cells[c.pk] = training.build_row(c, [], False, today, window_days)
    return Matrix(courses, rows)


def _cell(row):
    if row is None:
        return ""
    if row.expires_on is not None and row.latest is not None:
        return f"{row.label}, {row.expires_on:%d %b %Y}"
    if row.latest is not None:
        return f"{row.label}, done {row.latest.done_on:%d %b %Y}"
    return row.label


def to_csv(m):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Person", *[c.name for c in m.courses]])
    for entry in m.rows:
        w.writerow([entry.employee.name, *[_cell(entry.cells.get(c.pk)) for c in m.courses]])
    return out.getvalue()


def filename(today, course=None, team=None, query="", show="all"):
    parts = ["training-matrix"]
    if course is not None:
        parts.append(course.code)
    if team is not None:
        parts.append(slugify(team.name))
    if (query or "").strip():
        parts.append(slugify(query))
    if show != "all":
        parts.append(show)
    parts.append(today.isoformat())
    return "-".join(parts) + ".csv"
