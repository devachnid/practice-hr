from decimal import ROUND_HALF_UP, Decimal


def round_to(value, step):
    """Nearest multiple of step, half up, keeping step's places."""
    steps = (Decimal(value) / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return (steps * step).quantize(step)
