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
CATEGORY = {  # check type code -> the File category its evidence is stored under; else CERTIFICATE
    "right_to_work": File.Category.IDENTITY,
    "occupational_health": File.Category.OCCUPATIONAL_HEALTH,
    "hep_b": File.Category.OCCUPATIONAL_HEALTH,
}
LABELS = {"current": "Current", "due_soon": "Due soon", "lapsed": "Lapsed", "missing": "Missing",
          "not_required": "Not required", "awaiting": "Awaiting"}


@dataclass
class Row:
    check_type: CheckType
    latest: Check | None
    status: str
    expires_on: date | None
    asked: Check | None = None       # the request still waiting on the person, whatever the status

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


def _asked(employee, check_type):
    return (Check.objects.filter(employee=employee, check_type=check_type, awaiting=True)
            .select_related("check_type", "evidence")
            .order_by("-id").first())


def asked_of(employee):
    """The requests for evidence still waiting on the person (awaiting
    checks), one per type, oldest type first: Getting started shows them
    before the person's first day, when My record is not yet theirs."""
    return list(Check.objects.filter(employee=employee, awaiting=True).select_related("check_type", "evidence")
                .order_by("check_type__display_order", "check_type__name", "-id"))


def state(employee, today, window_days=60):
    required = required_for(employee, today)
    required_ids = {t.pk for t in required}
    extra = (CheckType.objects.filter(checks__employee=employee).exclude(pk__in=required_ids).distinct()
             .order_by("display_order", "name"))
    rows = []
    for t in [*required, *extra]:
        latest = _latest(employee, t)
        rows.append(Row(t, latest, _status(latest, t.pk in required_ids, today, window_days),
                        latest.expires_on if latest else None, _asked(employee, t)))
    return rows


def owed_status(row, employment, today):
    """The status the reminders and the dashboard go by: row.status, except
    that a required check asked of the person and not answered (its only
    row a request with nothing uploaded) is *missing* once their employment
    has started: asking does not stop it being owed. The pages keep
    *Awaiting*."""
    if (row.status == "awaiting" and row.asked is not None and row.asked.evidence_id is None
            and employment is not None and employment.start_date <= today):
        return "missing"
    return row.status


def summary(employee, today, window_days=60):
    rows = state(employee, today, window_days)
    counts = {k: sum(1 for r in rows if r.status == k)
              for k in ("current", "due_soon", "lapsed", "missing", "awaiting")}
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
    if (check_type.evidence == CheckType.Evidence.FILE and outcome in CLEAR
            and not (fields.get("upload") or fields.get("evidence"))):
        raise ValidationError(f"{check_type} needs its evidence file.")


def _after(check):
    if check.outcome in CLEAR:
        for hook in RECORDED_HOOKS:
            hook(check)


@transaction.atomic
def record(actor, employee, check_type, done_on, outcome, expires_on=None, reference="", note="", evidence=None,
           dbs_level="", dbs_update_service=False, upload=None):
    """HR records a check. `evidence` is a File already stored for this
    person, or None; `upload` is a new file to store as its evidence, written
    last (_attach), after the row and the hooks. A clear check of a
    type whose evidence is a file needs one or the other."""
    fields = {"reference": reference, "note": note, "evidence": evidence, "dbs_level": dbs_level,
              "dbs_update_service": dbs_update_service}
    today = timezone.localdate()
    validate(check_type, done_on, outcome, {**fields, "upload": upload}, today)
    _takes_file(check_type, upload)
    if evidence is not None and evidence.employee_id != employee.pk:
        raise ValidationError("The evidence must be one of this person's files.")
    c = Check(employee=employee, check_type=check_type, done_on=done_on, outcome=outcome,
              expires_on=expires_on or expires_from(done_on, check_type), recorded_by=actor, **fields)
    c.full_clean(exclude=["recorded_by"])      # None when the system records it (a register lookup)
    c.save()
    audit.record(actor, c, {"recorded": ("", f"{check_type}: {c.get_outcome_display()}, done {done_on:%d %b %Y}")})
    _after(c)
    if upload is not None:
        _attach(actor, c, upload)
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
    """The person, once, on their own awaiting check; HR, on an awaiting
    check or a recorded one with no evidence yet (their own too). Only a type
    whose evidence is a file takes one: a DBS certificate, for one, is not
    kept (its reference number is). files.add is the last fallible step
    before the link: its bytes are not rolled back with the transaction."""
    hr = access.can_view_restricted(actor)
    me = access.employee_for(actor)
    own = me is not None and me.pk == check.employee_id
    if not (own or hr):
        raise PermissionDenied
    if not hr:                            # the person: once, on a check asked of them
        if not check.awaiting:
            raise ValidationError("This check is not waiting for anything from you.")
        if check.evidence_id is not None:
            raise ValidationError("Already uploaded; HR will record it.")
    elif not check.awaiting and check.evidence_id is not None:
        # a recorded check's evidence is part of the record: never repointed
        raise ValidationError("This check already has its evidence.")
    return _attach(actor, check, upload)


def _takes_file(check_type, upload):
    if upload is not None and check_type.evidence != CheckType.Evidence.FILE:
        raise ValidationError(f"{check_type} takes no file.")


def _attach(actor, check, upload):
    """Store `upload` as the check's evidence (record, complete and
    upload_evidence, once each has applied its own rules)."""
    _takes_file(check.check_type, upload)
    category = CATEGORY.get(check.check_type.code, File.Category.CERTIFICATE)
    before = check.evidence_id or ""
    f = files.add(actor, check.employee, category, f"{check.check_type} evidence", upload)
    check.evidence = f
    check.save(update_fields=["evidence"])
    audit.record(actor, check, {"evidence": (before, f.pk)})
    return check


@transaction.atomic
def complete(actor, check, done_on, outcome, expires_on=None, upload=None, **fields):
    """HR turns an awaiting check into a recorded one. `upload`, a new
    evidence file, is stored last, as for record(); the person's own upload
    counts as the evidence too."""
    if not check.awaiting:
        raise ValidationError("Only a check still waiting can be completed.")
    today = timezone.localdate()
    validate(check.check_type, done_on, outcome,
             {**fields, "upload": upload, "evidence": fields.get("evidence") or check.evidence}, today)
    _takes_file(check.check_type, upload)
    for k, v in fields.items():
        setattr(check, k, v)
    check.done_on, check.outcome = done_on, outcome
    check.expires_on = expires_on or expires_from(done_on, check.check_type)
    check.awaiting, check.recorded_by = False, actor
    check.full_clean()
    check.save()
    audit.record(actor, check, {"completed": ("", f"{check.check_type}: {check.get_outcome_display()}")})
    _after(check)
    if upload is not None:
        _attach(actor, check, upload)        # HR's copy: replaces one the person sent, if any
    return check
