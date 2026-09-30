"""Requests and TOIL claims nobody has decided. After
CHASE_AFTER_WORKING_DAYS working days one is "waiting": it is listed on the
admin dashboard, and the HR admins are emailed about it once (chased_at is
stamped on the absence or the claim)."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from absence.models import Absence, BankHoliday, ClosedDay, ToilClaim
from absence.services import notify


def _non_working_dates(start, end):
    """Bank holidays (England and Wales) and practice closures in (start, end]."""
    holidays = set(BankHoliday.objects.filter(nation="EW", date__gt=start, date__lte=end)
                   .values_list("date", flat=True))
    return holidays | set(ClosedDay.objects.filter(date__gt=start, date__lte=end)
                          .values_list("date", flat=True))


def _working_days_between(start, end, off):
    """Working days after `start`, up to and including `end`: not a weekend,
    not in `off`."""
    n, d = 0, start
    while d < end:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in off:
            n += 1
    return n


def waiting(today):
    """Requested absences and TOIL claims older than CHASE_AFTER_WORKING_DAYS
    working days, oldest first (absences before claims asked at the same
    moment). An automatic bank-holiday row is never a request."""
    rows = list(Absence.objects.filter(status=Absence.Status.REQUESTED, auto_bank_holiday=False)
                .select_related("employment__employee", "absence_type"))
    rows += list(ToilClaim.objects.filter(status=ToilClaim.Status.REQUESTED).select_related("employment__employee"))
    if not rows:
        return []
    rows.sort(key=lambda r: (r.requested_at, isinstance(r, ToilClaim), r.pk))
    first = timezone.localtime(rows[0].requested_at).date()
    off = _non_working_dates(first, today)
    limit = settings.CHASE_AFTER_WORKING_DAYS
    return [r for r in rows
            if _working_days_between(timezone.localtime(r.requested_at).date(), today, off) > limit]


def notify_once(today):
    """Email the HR admins about the waiting requests and claims not yet
    chased, and stamp them. Returns how many were stamped: none when the
    email did not go, so the next nightly run tries again."""
    rows = [r for r in waiting(today) if r.chased_at is None]
    if not rows or not notify.requests_waiting(rows):
        return 0
    now = timezone.now()
    return (Absence.objects.filter(pk__in=[r.pk for r in rows if isinstance(r, Absence)]).update(chased_at=now)
            + ToilClaim.objects.filter(pk__in=[r.pk for r in rows if isinstance(r, ToilClaim)])
            .update(chased_at=now))
