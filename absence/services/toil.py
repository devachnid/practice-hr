"""Time off in lieu earned. Taking it is an ordinary TOIL booking
(bookings.approve writes the toil_taken line); expiring it is
year_end.expire_toil."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from absence.models import AbsenceType, LedgerEntry
from absence.services import ledger, pots
from people.services import audit


@transaction.atomic
def earn(actor, employment, units, day, note):
    """Credit `units` of TOIL earned on `day` to the TOIL pot for that day,
    opening it if needed. Raises ValidationError for non-positive units, or
    when there is no contract or TOIL policy on the day."""
    units = Decimal(units).quantize(Decimal("0.01"))
    if units <= 0:
        raise ValidationError("TOIL earned must be more than zero.")
    pot = pots.for_day(employment, AbsenceType.objects.get(code="TOIL"), day, actor=actor)
    row = ledger.write(pot, LedgerEntry.Kind.TOIL_EARNED, units, actor, note=note, date=day)
    audit.record(actor, row, {"toil_earned": ("", units)}, note=note)
    return row
