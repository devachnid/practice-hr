"""The only writer of PolicyVersion and Signature rows, and the one reader
of what a person owes. A policy applies by the title of the person's
primary position (no titles: everyone); the latest version by issue date
is the one owed, due `sign_within_days` after it was issued, or after the
person's start if they joined later.

sign() records; it does not authenticate. The page that calls it has just
had the person prove who they are (the password typed again, or one of
their own passkeys) and passes the method it used."""
from dataclasses import dataclass
from datetime import date, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from documents.models import File, Policy, PolicyVersion, Signature
from documents.services import files
from people.services import access, audit, employments, positions

SIGNED_HOOKS = []          # callables(employee) run after every signature
SENTENCE = "I confirm I have read and understood {title} ({label})."
LABELS = {"signed": "Signed", "awaiting": "Awaiting signature", "overdue": "Overdue"}


@dataclass
class Owed:
    version: PolicyVersion
    due_on: date
    state: str             # "awaiting" or "overdue"


def confirmation(version):
    """The sentence the person ticks, and the one their signature keeps."""
    return SENTENCE.format(title=version.policy.title, label=version.label)


@transaction.atomic
def issue(actor, policy, label, upload, issued_on, sign_within_days):
    """A new version of `policy`. files.add is the last step that can
    refuse, because its bytes are not rolled back with the transaction: the
    policy row is locked and the audit row written first (on SQLite, the
    first write takes the database's write lock), so the version's checks,
    the label's uniqueness among them, still hold when it is saved after
    the bytes."""
    Policy.objects.select_for_update().get(pk=policy.pk)
    audit.record(actor, policy, {"issued": ("", label)})
    v = PolicyVersion(policy=policy, label=label, issued_on=issued_on, sign_within_days=sign_within_days,
                      issued_by=actor)
    v.full_clean(exclude=["file"])
    # the newest by issue date is the one owed: dated ahead, it would be owed
    # before it took effect; dated behind the current one, never
    if issued_on > timezone.localdate():
        raise ValidationError("The issue date cannot be after today.")
    latest = current(policy)
    if latest is not None and issued_on < latest.issued_on:
        raise ValidationError(f"The issue date cannot be before the current version's ({latest.label}, "
                              f"{latest.issued_on:%d %b %Y}).")
    title = f"{policy.title} ({label})"[:File._meta.get_field("title").max_length]
    v.file = files.add(actor, None, File.Category.POLICY, title, upload)
    v.save()
    return v


def current(policy):
    return policy.versions.order_by("-issued_on", "-id").first()


def _employment(employee, today):
    """The employment that counts today: the current one, else the next to start."""
    return (employments.current(employee, today)
            or employee.employments.filter(start_date__gt=today).order_by("start_date").first())


def applies_to(employee, today):
    emp = _employment(employee, today)
    if emp is None:
        return []
    pos = positions.primary_on(emp, max(emp.start_date, today))
    out = []
    for p in Policy.objects.filter(active=True).prefetch_related("positions"):
        wanted = list(p.positions.all())
        if not wanted or (pos is not None and pos.title in wanted):
            out.append(p)
    return out


def due(version, employee, today):
    """The date the person should have signed `version` by."""
    emp = _employment(employee, today)
    start = max(version.issued_on, emp.start_date) if emp is not None else version.issued_on
    return start + timedelta(days=version.sign_within_days)


def _status(signature, due_on, today):
    if signature is not None:
        return "signed"
    return "overdue" if today > due_on else "awaiting"


def state(employee, today):
    """One row per policy that applies: its current version, the person's
    signature of it (or None), when it is due, and a status."""
    rows = []
    for p in applies_to(employee, today):
        v = current(p)
        if v is None:
            continue
        s = Signature.objects.filter(employee=employee, version=v).first()
        due_on = due(v, employee, today)
        status = _status(s, due_on, today)
        rows.append({"policy": p, "version": v, "signature": s, "due_on": due_on, "status": status,
                     "label": LABELS[status]})
    return rows


def owed(employee, today):
    return [Owed(r["version"], r["due_on"], r["status"]) for r in state(employee, today) if r["signature"] is None]


def signable(employee, version, today):
    """The current version of a policy that applies to the person."""
    return version.policy in applies_to(employee, today) and current(version.policy) == version


@transaction.atomic
def sign(actor, version, method, ip):
    """The actor signs for themselves, the current version of a policy that
    applies to them, once. The caller has re-authenticated them by `method`."""
    if method not in Signature.Method.values:
        raise ValueError(method)
    me = access.employee_for(actor)
    if me is None or not signable(me, version, timezone.localdate()):
        raise PermissionDenied
    if Signature.objects.filter(employee=me, version=version).exists():
        raise ValidationError("You have already signed this version.")
    s = Signature(employee=me, version=version, method=method, confirmation_text=confirmation(version),
                  ip_address=ip or "")
    s.full_clean()
    s.save()
    audit.record(actor, s, {"signed": ("", f"{version} by {s.get_method_display().lower()}")})
    for hook in SIGNED_HOOKS:
        hook(me)
    return s
