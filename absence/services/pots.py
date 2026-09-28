from django.db import transaction
from django.utils import timezone

from absence.models import Pot
from absence.services import leave_year, policies
from people.services import contracts


@transaction.atomic
def for_day(employment, absence_type, day):
    """The pot for the leave year containing `day`, created if needed.
    Raises ValidationError when there is no contract or no policy."""
    policy = policies.policy_for(employment, absence_type, day)
    start, end = leave_year.bounds(policy, employment, day)
    pot, _ = Pot.objects.get_or_create(
        employment=employment, absence_type=absence_type, year_start=start,
        defaults={"year_end": end, "unit": contracts.unit(employment, day)})
    return pot


def open_pots(today=None):
    today = today or timezone.localdate()
    return Pot.objects.filter(year_end__gte=today).select_related("employment__employee", "absence_type")
