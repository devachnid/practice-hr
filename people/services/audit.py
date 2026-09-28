"""The one writer of AuditEntry. Every service in people and absence calls
record() after a change and viewed() when a restricted section is shown."""

from people.models import AuditEntry


def _label(obj):
    return f"{obj._meta.app_label}.{obj._meta.model_name}"


def record(actor, obj, changes, note=""):
    rows = [
        AuditEntry(actor=actor, kind=AuditEntry.Kind.CHANGE, model=_label(obj),
                   object_id=obj.pk, field=field, before=str(before), after=str(after), note=note)
        for field, (before, after) in changes.items() if before != after
    ]
    return AuditEntry.objects.bulk_create(rows)


def viewed(actor, obj, section):
    return AuditEntry.objects.create(
        actor=actor, kind=AuditEntry.Kind.VIEWED, model=_label(obj), object_id=obj.pk,
        field=section)
