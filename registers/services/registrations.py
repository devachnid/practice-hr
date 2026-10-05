"""Each person's registration numbers: which bodies their title needs, and
the one writer of Registration rows. The Welsh medical performers list is
keyed by the GMC number, so setting the GMC number also sets (or makes) the
Welsh row when the title needs it, and clearing it clears both."""
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from people.services import audit, employments, positions
from registers import numbers
from registers.models import RegisterBody, Registration

TWINS = {parent: child for child, parent in numbers.SHARES_NUMBER_WITH.items()}   # gmc -> mpl_wales


@dataclass
class Row:
    body: RegisterBody
    registration: Registration | None
    needed: bool


def _title(employee, today):
    emp = employments.current(employee, today)
    if emp is None:
        return None
    pos = positions.primary_on(emp, today)
    return pos.title if pos is not None else None


def needed(employee, today):
    """The active bodies the person's primary title needs, in display order."""
    title = _title(employee, today)
    if title is None:
        return []
    return list(RegisterBody.objects.filter(active=True, positions=title).order_by("display_order"))


def missing(employee, today):
    have = set(employee.registrations.values_list("body_id", flat=True))
    return [b for b in needed(employee, today) if b.pk not in have]


def rows(employee, today):
    """One row per body the title needs, plus any body a number is still
    held for (needed=False), for the pages."""
    need = needed(employee, today)
    held = {r.body_id: r for r in employee.registrations.select_related("body")}
    out = [Row(b, held.get(b.pk), True) for b in need]
    needed_ids = {b.pk for b in need}
    out += [Row(r.body, r, False) for r in held.values() if r.body_id not in needed_ids]
    return out


def number_fields(employee, today):
    """(form field name, body, label) for each number the Details tab
    shows: one per needed body, except a body that shares another's number."""
    out = []
    for b in needed(employee, today):
        if b.code in numbers.SHARES_NUMBER_WITH:
            continue
        out.append((f"registration_{b.code}", b, f"{numbers.label(b.code)} number"))
    return out


def _twin(employee, body, today):
    code = TWINS.get(body.code)
    if code is None:
        return None
    return next((b for b in needed(employee, today) if b.code == code), None)


@transaction.atomic
def set_number(actor, employee, body, number):
    """Set (or change) the person's number with `body`; checked tonight.
    Audited on the employee as registration:<code>. Raises ValidationError
    on a bad format."""
    today = timezone.localdate()
    value = numbers.normalise(number)
    if not value:
        raise ValidationError("Enter the number.", code="blank")
    numbers.check(body.code, value)
    reg, created = Registration.objects.get_or_create(employee=employee, body=body,
                                                      defaults={"number": value, "next_check_on": today})
    before = "" if created else reg.number
    if not created and reg.number != value:
        reg.number, reg.next_check_on = value, today
        reg.last_outcome, reg.last_status_text, reg.last_name_on_register, reg.last_checked_at = "", "", "", None
        reg.last_unreadable_at = None
        reg.save()
    if before != value:
        audit.record(actor, employee, {f"registration:{body.code}": (before, value)})
    twin = _twin(employee, body, today)
    if twin is not None:
        set_number(actor, employee, twin, value)
    return reg


@transaction.atomic
def clear_number(actor, employee, body):
    """Remove the number (its lookups go with it); the Welsh twin too."""
    reg = Registration.objects.filter(employee=employee, body=body).first()
    if reg is not None:
        audit.record(actor, employee, {f"registration:{body.code}": (reg.number, "")})
        reg.delete()
    twin_code = TWINS.get(body.code)
    if twin_code:
        twin = Registration.objects.filter(employee=employee, body__code=twin_code).first()
        if twin is not None:
            audit.record(actor, employee, {f"registration:{twin_code}": (twin.number, "")})
            twin.delete()
