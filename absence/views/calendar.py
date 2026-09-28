"""The who's-off calendar: a month at a time, for the practice or one team.
Everyone signed in sees colleagues' calendar labels; an HR admin also sees
the absence type's name."""

from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from absence.services import calendar
from people.models import Team
from people.services import access


def _month(text, today):
    try:
        year, month = (int(part) for part in text.split("-"))
        return date(year, month, 1)
    except (ValueError, AttributeError):
        return today.replace(day=1)


def _shift(first, by):
    index = first.year * 12 + first.month - 1 + by
    return date(index // 12, index % 12 + 1, 1)


@login_required
def calendar_view(request):
    today = timezone.localdate()
    first = _month(request.GET.get("month", ""), today)
    teams = list(Team.objects.all())
    chosen = None
    if request.GET.get("team", "").isdigit():
        chosen = next((t for t in teams if t.pk == int(request.GET["team"])), None)
    weeks = calendar.month(first.year, first.month, chosen, detail=access.can_view_restricted(request.user))
    team_part = f"&team={chosen.pk}" if chosen else ""
    return render(request, "absence/calendar.html", {
        "weeks": weeks, "first": first, "today": today, "teams": teams, "team": chosen,
        "prev_url": f"?month={_shift(first, -1):%Y-%m}{team_part}",
        "next_url": f"?month={_shift(first, 1):%Y-%m}{team_part}",
        "month_value": f"{first:%Y-%m}"})
