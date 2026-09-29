from datetime import date, timedelta

from absence.models import Policy


def _safe_date(year, month, day):
    try:
        return date(year, month, day)
    except ValueError:            # 29 February in a common year
        return date(year, month, 28)


def bounds(policy, employment, day):
    """The leave year containing `day`: (first day, last day)."""
    if policy.leave_year_basis == Policy.Basis.ANNIVERSARY:
        month, dom = employment.start_date.month, employment.start_date.day
    else:
        month, dom = policy.year_start_month, policy.year_start_day
    start = _safe_date(day.year, month, dom)
    if start > day:
        start = _safe_date(day.year - 1, month, dom)
    end = _safe_date(start.year + 1, month, dom) - timedelta(days=1)
    return start, end
