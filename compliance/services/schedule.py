"""The reminder cadence, as pure date arithmetic."""


def should_send(today, due_on, state, last_sent, sched):
    """The cadence: first day inside the window, every Y days before due,
    the due date itself, then every Z days after. `last_sent` is the day
    this recipient last had this key, or None."""
    days = (due_on - today).days
    if days > sched.start_days_before:
        return False
    if days == 0:
        return last_sent != today
    if last_sent is None:
        return True
    gap = (today - last_sent).days
    if days > 0:
        return gap >= max(sched.every_days_before, 1)
    return gap >= max(sched.every_days_overdue, 1)
