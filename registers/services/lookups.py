"""Running lookups against the registers (filled in by Task 3)."""


def unpause(body):
    """HR's Unpause, or a successful on-demand lookup: the schedule runs again."""
    if body.paused_at is not None:
        body.paused_at = None
        body.save(update_fields=["paused_at"])
