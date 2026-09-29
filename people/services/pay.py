from django.db import transaction

from people.models import PayRecord
from people.services import audit

FIELDS = ("from_date", "to_date", "basis", "amount", "reason")


@transaction.atomic
def add(actor, employment, from_date, basis, amount, to_date=None, reason=""):
    record = PayRecord(employment=employment, from_date=from_date, to_date=to_date,
                       basis=basis, amount=amount, reason=reason)
    record.full_clean()
    record.save()
    audit.record(actor, record, {"created": ("", str(record))})
    return record


@transaction.atomic
def amend(actor, record, **fields):
    fresh = PayRecord.objects.get(pk=record.pk)
    changes = {f: (getattr(fresh, f), fields[f]) for f in FIELDS if f in fields and getattr(fresh, f) != fields[f]}
    for f, (_, new) in changes.items():
        setattr(fresh, f, new)
    fresh.full_clean()
    fresh.save()
    audit.record(actor, fresh, changes)
    return fresh
