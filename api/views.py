"""The read-only JSON API the rota polls. Every endpoint is a GET, needs
`Authorization: Bearer <token>` with the token in HR_API_TOKENS (api/auth.py),
and answers 401 `{"error": "unauthorised"}` (with `WWW-Authenticate: Bearer`)
otherwise, and 400 `{"error": "<what is wrong>"}` for a bad query string.
Dates are ISO (YYYY-MM-DD). Nothing here is written to.

GET /api/v1/people
    {"people": [{
        "id": 12,                      # the Employee's id, what the other endpoints use
        "first_name": "Sam", "last_name": "Patel", "name": "Sam Patel",
        "email": "sam@practice.example",           # the work address
        "contract_type": "Reception" | null,       # today's first contract; null if none
        "unit": "hours" | "sessions" | ... | null, # that contract type's unit
        "employment": {"start": "2026-04-01", "end": null},
        "positions": [{"title": "Receptionist", "team": "Reception"}]   # today's
    }]}
    Everyone with an employment, past leavers included: today's employment
    if there is one, otherwise the latest.

GET /api/v1/patterns?employee=<id>
    {"patterns": [{                    # oldest first; each holds from its date
        "effective_from": "2026-04-01",
        "days": [{"weekday": 0, "am": "3.75", "pm": "3.75"}]   # Monday is 0;
    }]}                                # units in the contract's unit, as strings
    Patterns of every employment the person has had, so a rehire's earlier
    spell's patterns are included.

GET /api/v1/absences?from=YYYY-MM-DD&to=YYYY-MM-DD
    {"absences": [{
        "id": 7, "employee": 12,       # the Employee's id
        "type": "AL", "label": "Leave" | "Sick" | ...,
        "status": "approved" | "requested",
        "start": "2026-05-25", "end": "2026-06-12",
        "start_half": "" | "PM", "end_half": "" | "AM",
        "partial": null | {"start_time": "09:00", "end_time": "11:00", "hours": "2.00"}
    }]}
    Every approved or requested absence that overlaps the window (from and to
    inclusive), including one that starts before `from` or ends after `to`.
    Not returned: declined and cancelled absences, and the automatic
    bank-holiday rows (the rota has its own bank-holiday calendar). `label`
    is the type's calendar_label, except that a health-sensitive type is
    always "Sick". No field carries the illness category.
"""

from datetime import date

from django.http import JsonResponse
from django.utils import timezone

from absence.models import Absence
from api.auth import token_required
from people.models import Employee, WorkingPattern
from people.services import contracts, employments, positions


def _iso(d):
    return d.isoformat() if d else None


def _bad_request(message):
    return JsonResponse({"error": message}, status=400)


@token_required
def people(request):
    today = timezone.localdate()
    out = []
    for e in Employee.objects.all():
        emp = employments.current(e, today) or e.employments.order_by("-start_date").first()
        if emp is None:
            continue
        c = contracts.active_on(emp, today).first()
        out.append({
            "id": e.pk, "first_name": e.first_name, "last_name": e.last_name, "name": e.name,
            "email": e.work_email,
            "contract_type": c.contract_type.name if c else None, "unit": c.contract_type.unit if c else None,
            "employment": {"start": _iso(emp.start_date), "end": _iso(emp.end_date)},
            "positions": [{"title": p.title.name, "team": p.team.name} for p in positions.on(emp, today)],
        })
    return JsonResponse({"people": out})


@token_required
def patterns(request):
    try:
        employee = Employee.objects.get(pk=int(request.GET.get("employee", "")))
    except (ValueError, Employee.DoesNotExist):
        return _bad_request("employee=<id> required")
    out = []
    versions = (WorkingPattern.objects.filter(employment__employee=employee)
                .order_by("effective_from", "pk").prefetch_related("days"))
    for v in versions:
        out.append({"effective_from": _iso(v.effective_from),
                    "days": [{"weekday": d.weekday, "am": str(d.am_units), "pm": str(d.pm_units)}
                             for d in v.days.all()]})
    return JsonResponse({"patterns": out})


@token_required
def absences(request):
    try:
        start = date.fromisoformat(request.GET["from"])
        end = date.fromisoformat(request.GET["to"])
    except (KeyError, ValueError):
        return _bad_request("from and to (YYYY-MM-DD) required")
    if end < start:
        return _bad_request("to is before from")
    qs = (Absence.objects
          .filter(status__in=(Absence.Status.APPROVED, Absence.Status.REQUESTED),
                  auto_bank_holiday=False, start_date__lte=end, end_date__gte=start)
          .select_related("employment", "absence_type")
          .order_by("start_date", "pk"))
    out = [{
        "id": a.pk, "employee": a.employment.employee_id, "type": a.absence_type.code,
        "label": "Sick" if a.absence_type.health_sensitive else a.absence_type.calendar_label,
        "status": a.status,
        "start": _iso(a.start_date), "end": _iso(a.end_date),
        "start_half": a.start_half, "end_half": a.end_half,
        "partial": ({"start_time": a.start_time.strftime("%H:%M"), "end_time": a.end_time.strftime("%H:%M"),
                     "hours": str(a.hours)} if a.is_partial else None),
    } for a in qs]
    return JsonResponse({"absences": out})
