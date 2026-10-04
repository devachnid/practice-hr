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


def _contacts_summary(rows):
    return "; ".join(f"{r['name']} ({r['relationship']}) {r['phone']}" if r["relationship"]
                     else f"{r['name']} {r['phone']}" for r in rows)


@transaction.atomic
def set_emergency_contacts(actor, employee, rows):
    """Replace the person's emergency contacts with `rows` (dicts of name,
    relationship, phone), in that order of priority. Every row is checked
    before anything is written; the audit row holds before and after."""
    from people.models import EmergencyContact
    new = [EmergencyContact(employee=employee, name=(r.get("name") or "").strip(),
                            relationship=(r.get("relationship") or "").strip(),
                            phone=(r.get("phone") or "").strip(), priority=i)
           for i, r in enumerate(rows, start=1)]
    for contact in new:
        contact.full_clean()
    existing = employee.emergency_contacts.all()
    before = _contacts_summary(existing.values("name", "relationship", "phone"))
    after = _contacts_summary({"name": c.name, "relationship": c.relationship, "phone": c.phone} for c in new)
    if before == after:
        return list(existing)
    existing.delete()
    EmergencyContact.objects.bulk_create(new)
    audit.record(actor, employee, {"emergency_contacts": (before, after)})
    return list(employee.emergency_contacts.all())
