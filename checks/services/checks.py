"""The only writer of Check rows, and the one reader of a person's check
status. A check type is required by the title of the person's current
primary position; state() gives one row per required type, plus one per
other type the person has a check of, each with its latest check and a
status. Pages, reminders and the dashboard all read state()."""
import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from checks.models import Check, CheckType
from documents.models import File
from documents.services import files
from people.services import access, audit, employments, positions

RECORDED_HOOKS = []          # callables(check) run after a clear check is recorded or completed
CLEAR = (Check.Outcome.CLEAR, Check.Outcome.CLEAR_WITH_NOTES)
LABELS = {"current": "Current", "due_soon": "Due soon", "lapsed": "Lapsed", "missing": "Missing",
          "not_required": "Not required", "awaiting": "Awaiting"}


@dataclass
class Row:
    check_type: CheckType
    latest: Check | None
    status: str
    expires_on: date | None

    @property
    def label(self):
        return LABELS[self.status]


def expires_from(done_on, check_type):
    """done_on plus validity_months, month arithmetic clipped to the month's end; None for one-off."""
    if check_type.validity_months is None:
        return None
    month = done_on.month - 1 + check_type.validity_months
    year = done_on.year + month // 12
    month = month % 12 + 1
    day = min(done_on.day, calendar.monthrange(year, month)[1])
    return done_on.replace(year=year, month=month, day=day)


def required_for(employee, today):
    emp = employments.current(employee, today)
    if emp is None:
        return []
    pos = positions.primary_on(emp, today)
    if pos is None:
        return []
    return list(CheckType.objects.filter(active=True, positions=pos.title).order_by("display_order", "name"))


def _status(latest, required, today, window_days):
    if not required:
        return "not_required"
    if latest is None:
        return "missing"
    if latest.awaiting:
        return "awaiting"
    if latest.outcome not in CLEAR:
        return "missing"
    if latest.expires_on is None:
        return "current"
    if latest.expires_on < today:
        return "lapsed"
    if latest.expires_on <= today + timedelta(days=window_days):
        return "due_soon"
    return "current"


def _latest(employee, check_type):
    """The check that counts: a recorded one before one still awaiting,
    then the latest done, then the latest written."""
    return (Check.objects.filter(employee=employee, check_type=check_type).select_related("evidence")
            .order_by("awaiting", "-done_on", "-id").first())


def state(employee, today, window_days=60):
    required = required_for(employee, today)
    required_ids = {t.pk for t in required}
    extra = (CheckType.objects.filter(checks__employee=employee).exclude(pk__in=required_ids).distinct()
             .order_by("display_order", "name"))
    rows = []
    for t in [*required, *extra]:
        latest = _latest(employee, t)
        rows.append(Row(t, latest, _status(latest, t.pk in required_ids, today, window_days),
                        latest.expires_on if latest else None))
    return rows


def summary(employee, today, window_days=60):
    rows = state(employee, today, window_days)
    counts = {k: sum(1 for r in rows if r.status == k) for k in ("current", "due_soon", "lapsed", "missing")}
    expiries = [r.expires_on for r in rows if r.expires_on and r.status in ("current", "due_soon")]
    counts["next_expiry"] = min(expiries) if expiries else None
    return counts


def validate(check_type, done_on, outcome, fields, today):
    """The rules a recorded check meets; also run by the admin's forms so a
    refusal shows on the form before anything is written."""
    if done_on is None:
        raise ValidationError("Enter the date the check was done.")
    if done_on > today:
        raise ValidationError("The date done cannot be after today.")
    if outcome not in Check.Outcome.values:
        raise ValidationError("Choose an outcome.")
    if check_type.code == "dbs" and outcome in CLEAR and not fields.get("dbs_level"):
        raise ValidationError("A DBS check needs its disclosure level.")
    if check_type.evidence == CheckType.Evidence.REFERENCE and outcome in CLEAR and not fields.get("reference"):
        raise ValidationError(f"{check_type} needs its reference number.")


def _after(check):
    if check.outcome in CLEAR:
        for hook in RECORDED_HOOKS:
            hook(check)


@transaction.atomic
def record(actor, employee, check_type, done_on, outcome, expires_on=None, reference="", note="", evidence=None,
           dbs_level="", dbs_update_service=False):
    """HR records a check. `evidence` is a File already stored for this
    person, or None (the admin attaches an upload after, through
    upload_evidence, so the bytes are written last)."""
    fields = {"reference": reference, "note": note, "evidence": evidence, "dbs_level": dbs_level,
              "dbs_update_service": dbs_update_service}
    today = timezone.localdate()
    validate(check_type, done_on, outcome, fields, today)
    if evidence is not None and evidence.employee_id != employee.pk:
        raise ValidationError("The evidence must be one of this person's files.")
    c = Check(employee=employee, check_type=check_type, done_on=done_on, outcome=outcome,
              expires_on=expires_on or expires_from(done_on, check_type), recorded_by=actor, **fields)
    c.full_clean()
    c.save()
    audit.record(actor, c, {"recorded": ("", f"{check_type}: {c.get_outcome_display()}, done {done_on:%d %b %Y}")})
    _after(c)
    return c


@transaction.atomic
def ask(actor, employee, check_type):
    """HR asks the person for evidence: an awaiting row they can upload
    against from My record, until HR completes it."""
    if Check.objects.filter(employee=employee, check_type=check_type, awaiting=True).exists():
        raise ValidationError("Already asked.")
    c = Check.objects.create(employee=employee, check_type=check_type, awaiting=True, recorded_by=actor)
    audit.record(actor, c, {"asked": ("", str(check_type))})
    return c


@transaction.atomic
def upload_evidence(actor, check, upload):
    """The person, on their own awaiting check; HR, on any. Only a type
    whose evidence is a file takes one: a DBS certificate, for one, is not
    kept (its reference number is). files.add is the last fallible step
    before the link: its bytes are not rolled back with the transaction."""
    me = access.employee_for(actor)
    own = me is not None and me.pk == check.employee_id
    if not (own or access.can_view_restricted(actor)):
        raise PermissionDenied
    if own and not check.awaiting:
        raise ValidationError("This check is not waiting for anything from you.")
    if check.check_type.evidence != CheckType.Evidence.FILE:
        raise ValidationError(f"{check.check_type} takes no file.")
    category = File.Category.IDENTITY if check.check_type.code == "right_to_work" else File.Category.CERTIFICATE
    f = files.add(actor, check.employee, category, f"{check.check_type} evidence", upload)
    check.evidence = f
    check.save(update_fields=["evidence"])
    audit.record(actor, check, {"evidence": ("", f.pk)})
    return check


@transaction.atomic
def complete(actor, check, done_on, outcome, expires_on=None, **fields):
    """HR turns an awaiting check into a recorded one."""
    if not check.awaiting:
        raise ValidationError("Only a check still waiting can be completed.")
    today = timezone.localdate()
    validate(check.check_type, done_on, outcome, fields, today)
    for k, v in fields.items():
        setattr(check, k, v)
    check.done_on, check.outcome = done_on, outcome
    check.expires_on = expires_on or expires_from(done_on, check.check_type)
    check.awaiting, check.recorded_by = False, actor
    check.full_clean()
    check.save()
    audit.record(actor, check, {"completed": ("", f"{check.check_type}: {check.get_outcome_display()}")})
    _after(check)
    return check
