"""Balances (this leave year and next, per type) and the ledger behind each
figure. Reads only: a pot that is not open yet is shown as such (pots.lookup,
never for_day) and no entitlement is synced on a GET."""

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from absence.models import Absence, LedgerEntry, Pot
from absence.services import balances, ledger
from people.models import Employee
from people.services import access, employments, positions

K = LedgerEntry.Kind

# Which ledger lines stand behind each figure of balances.summary. The link
# is the ledger page with ?kind=<kinds>, and ?period= where the summary splits
# a kind by date:
#   entitlement   entitlement + revision lines
#   carried_in    carry_in lines
#   taken         booking, toil_taken and cancellation lines whose absence ended before today
#   booked        the same kinds whose absence ends today or later
#   pending       no ledger lines: a request is written to the ledger only when approved.
#                 kind=pending lists the pot's waiting requests instead
#   expired       expiry lines
#   adjustments   adjustment + toil_earned lines
#   remaining     the whole ledger
BOOKING_KINDS = (K.BOOKING, K.TOIL_TAKEN, K.CANCELLATION)
FIGURES = {
    "entitlement": ((K.ENTITLEMENT, K.REVISION), ""),
    "carried_in": ((K.CARRY_IN,), ""),
    "taken": (BOOKING_KINDS, "taken"),
    "booked": (BOOKING_KINDS, "booked"),
    "pending": (("pending",), ""),
    "expired": ((K.EXPIRY,), ""),
    "adjustments": ((K.ADJUSTMENT, K.TOIL_EARNED), ""),
}


def _links(pot):
    if pot is None:
        return {}
    base = f"/absence/ledger/{pot.pk}/"
    links = {}
    for figure, (kinds, period) in FIGURES.items():
        links[figure] = f"{base}?kind={','.join(kinds)}" + (f"&period={period}" if period else "")
    return links


def _rows(employment, today, user):
    rows = balances.rows(employment, today, include_bh=True, with_next=True,
                         show_setup_gaps=access.can_view_restricted(user))
    for r in rows:
        r["links"], r["next_links"] = _links(r["pot"]), _links(r["next_pot"])
    return rows


def _render(request, employee):
    today = timezone.localdate()
    employment = employments.current(employee, today)
    return render(request, "absence/balances.html", {
        "employee": employee, "employment": employment,
        "rows": _rows(employment, today, request.user) if employment else []})


@login_required
def balances_view(request):
    employee = access.employee_for(request.user)
    if employee is None:
        return render(request, "absence/balances.html", {"employee": None, "employment": None, "rows": []})
    return _render(request, employee)


@login_required
def balances_for(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if not access.can_view(request.user, employee):
        raise PermissionDenied
    return _render(request, employee)


@login_required
def team(request):
    """Whose balances this user may open: an approver's direct reports, every
    employee for an HR admin."""
    today = timezone.localdate()
    if access.can_view_restricted(request.user):
        people = list(Employee.objects.all())
    else:
        me = access.employee_for(request.user)
        if me is None or not access.is_approver(request.user, today):
            raise PermissionDenied
        people = [e.employee for e in access.direct_reports(me, today)]
    rows = []
    for e in people:
        emp = employments.current(e, today)
        pos = positions.primary_on(emp, today) if emp else None
        rows.append({"employee": e, "position": pos, "employed": emp is not None})
    return render(request, "absence/balances_team.html", {"rows": rows})


def _filters(request):
    """(kinds, period) from ?kind= and ?period=, ignoring anything unknown;
    no valid kind means no filter."""
    kinds = [k for k in request.GET.get("kind", "").split(",") if k in LedgerEntry.Kind.values or k == "pending"]
    period = request.GET.get("period") if request.GET.get("period") in ("taken", "booked") else ""
    return kinds, period


@login_required
def ledger_view(request, pk):
    pot = get_object_or_404(Pot.objects.select_related("employment__employee", "absence_type"), pk=pk)
    if not access.can_view(request.user, pot.employment.employee):
        raise PermissionDenied
    today = timezone.localdate()
    kinds, period = _filters(request)
    waiting = None
    if kinds == ["pending"]:
        waiting = Absence.objects.filter(
            employment=pot.employment, absence_type=pot.absence_type, status=Absence.Status.REQUESTED,
            start_date__range=(pot.year_start, pot.year_end)).order_by("start_date")
    entries, running = [], Decimal("0")
    for e in pot.entries.select_related("absence", "actor"):
        running += e.units              # the true balance after the line, whatever is filtered out
        if waiting is not None:
            continue
        if kinds and e.kind not in kinds:
            continue
        if period and (e.absence is None or (e.absence.end_date < today) != (period == "taken")):
            continue
        entries.append({"e": e, "running": running})
    return render(request, "absence/ledger.html", {
        "pot": pot, "entries": entries, "waiting": waiting, "filtered": bool(kinds),
        "balance": ledger.balance(pot)})
