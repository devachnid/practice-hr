"""Requests nobody has decided. After CHASE_AFTER_WORKING_DAYS working days a
request is "waiting": it is listed on the admin dashboard, and the HR admins
are emailed about it once."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from absence.models import Absence, BankHoliday, ClosedDay
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
    """Requested absences older than CHASE_AFTER_WORKING_DAYS working days,
    oldest first. An automatic bank-holiday row is never a request."""
    rows = list(Absence.objects.filter(status=Absence.Status.REQUESTED, auto_bank_holiday=False)
                .select_related("employment__employee", "absence_type").order_by("requested_at", "pk"))
    if not rows:
        return []
    first = timezone.localtime(rows[0].requested_at).date()
    off = _non_working_dates(first, today)
    limit = settings.CHASE_AFTER_WORKING_DAYS
    return [a for a in rows
            if _working_days_between(timezone.localtime(a.requested_at).date(), today, off) > limit]


def notify_once(today):
    """Email the HR admins about the waiting requests not yet chased, and
    stamp them. Returns how many were stamped: none when the email did not
    go, so the next nightly run tries again."""
    rows = [a for a in waiting(today) if a.chased_at is None]
    if not rows or not notify.requests_waiting(rows):
        return 0
    return Absence.objects.filter(pk__in=[a.pk for a in rows]).update(chased_at=timezone.now())
