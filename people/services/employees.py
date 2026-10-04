from django.db import transaction

from people.models import Employee
from people.services import audit

EDITABLE = {
    "first_name", "last_name", "preferred_name", "work_email", "personal_email", "phone",
    "date_of_birth", "address_line1", "address_line2", "town", "postcode", "ni_number", "user",
    "bank_account_name", "bank_sort_code", "bank_account_number",
}


def diff(obj, fields):
    """{field: (before, after)} for the fields whose value would change."""
    out = {}
    for field, new in fields.items():
        old = getattr(obj, field)
        if old != new:
            out[field] = (old, new)
    return out


@transaction.atomic
def create(actor, **fields):
    unknown = set(fields) - EDITABLE
    if unknown:
        raise ValueError(f"not editable: {sorted(unknown)}")
    employee = Employee(**fields)
    employee.full_clean()
    employee.save()
    audit.record(actor, employee, {"created": ("", employee.name)})
    return employee


@transaction.atomic
def update(actor, employee, **fields):
    unknown = set(fields) - EDITABLE
    if unknown:
        raise ValueError(f"not editable: {sorted(unknown)}")
    changes = diff(employee, fields)
    for field, (_, new) in changes.items():
        setattr(employee, field, new)
    employee.full_clean()
    employee.save()
    audit.record(actor, employee, changes)
    return employee
