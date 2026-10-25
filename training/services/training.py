"""The only writer of TrainingRecord rows (sessions.py writes them too,
through the same helpers) and the one reader of a person's training
status. A course is required by the title of the person's current primary
position, or of everyone; state() gives one row per required course, plus
one per other course the person has a record of, each with its counting
record, any pending one, and a status. Pages, the digest, the dashboard
and the matrix all read state() or build_row()."""
from dataclasses import dataclass
from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from absence import mail
from accounts.mail import email_is_configured
from compliance import validity
from compliance.due import active_email, link
from documents.models import File
from documents.services import files
from people.services import access, audit, employments, positions
from training.models import Course, TrainingRecord

LABELS = {"current": "Current", "due_soon": "Due soon", "lapsed": "Lapsed", "missing": "Missing",
          "not_required": "Not required", "awaiting_verification": "Awaiting verification"}
STATUSES = tuple(LABELS)
PROBLEMS = ("due_soon", "lapsed", "missing")


@dataclass
class Row:
    course: Course
    latest: TrainingRecord | None          # the counting record (verified, not rejected), newest done_on
    pending: TrainingRecord | None         # the newest unverified, unrejected record
    rejected: TrainingRecord | None        # the newest rejected record, by date done, when more recent than the counting one and no resubmission waits
    status: str
    expires_on: date | None

    @property
    def label(self):
        return LABELS[self.status]


# ---- reading -----------------------------------------------------------------

def required_for(employee, today):
    """Active courses required of everyone, plus those the title of the
    current primary position needs. No current employment: nothing."""
    emp = employments.current(employee, today)
    if emp is None:
        return []
    pos = positions.primary_on(emp, today)
    q = Q(everyone=True)
    if pos is not None:
        q |= Q(positions=pos.title)
    return list(Course.objects.filter(q, active=True).distinct().order_by("display_order", "name"))


def build_row(course, records, required, today, window_days):
    """`records`: this person's records of `course`, newest done_on first."""
    latest = next((r for r in records if r.counts), None)
    pending = next((r for r in records if r.pending), None)
    # records are newest done_on first, so "more recent than the counting one" is
    # "sorts before it": a backdated rejected upload must not mark a current course
    ahead = records if latest is None else records[:records.index(latest)]
    rejected = None if pending is not None else next((r for r in ahead if r.rejected), None)
    expires_on = latest.expires_on if latest is not None else None
    status = validity.status(expires_on, latest is not None, required, today, window_days)
    # An unverified record stands in for a course nothing counts for (whether or
    # not it is required: a starter before day one has none required) and for a
    # lapsed one. A course that still has a current counting record keeps its
    # status, even a not-required one with a renewal waiting.
    if pending is not None and (latest is None or status == "lapsed"):
        status = "awaiting_verification"
    return Row(course, latest, pending, rejected, status, expires_on)


def _records_by_course(employee):
    out = {}
    for r in (TrainingRecord.objects.filter(employee=employee).select_related("certificate", "session")
              .order_by("-done_on", "-id")):
        out.setdefault(r.course_id, []).append(r)
    return out


def state(employee, today, window_days=validity.WINDOW_DAYS):
    required = required_for(employee, today)
    required_ids = {c.pk for c in required}
    extra = (Course.objects.filter(records__employee=employee).exclude(pk__in=required_ids).distinct()
             .order_by("display_order", "name"))
    by_course = _records_by_course(employee)
    return [build_row(c, by_course.get(c.pk, []), c.pk in required_ids, today, window_days)
            for c in [*required, *extra]]


def summary(employee, today, window_days=validity.WINDOW_DAYS):
    rows = state(employee, today, window_days)
    counts = {k: sum(1 for r in rows if r.status == k) for k in STATUSES}
    expiries = [r.expires_on for r in rows if r.expires_on and r.status in ("current", "due_soon")]
    counts["next_expiry"] = min(expiries) if expiries else None
    return counts


def to_verify(today):
    """Pending records of people employed today, oldest first."""
    employed = employments.active_on(today).values("employee_id")
    return (TrainingRecord.objects.filter(verified_at__isnull=True, rejected_at__isnull=True,
                                          employee_id__in=employed)
            .select_related("employee", "course").order_by("recorded_at", "pk"))


# ---- the rules the writers share ---------------------------------------------

def check_course(course):
    if not course.active:
        raise ValidationError(f"{course} is no longer in use.")


def check_date(done_on, today, what="done"):
    if done_on is None:
        raise ValidationError(f"Enter the date the training was {what}.")
    if done_on > today:
        raise ValidationError(f"The date {what} cannot be after today.")


def attach(actor, record, upload):
    """Store `upload` as the record's certificate: the person's file,
    category Certificate, never HR-only. files.add is the last fallible
    step: its bytes are not rolled back with the transaction, so every
    writer calls this after the row is saved."""
    f = files.add(actor, record.employee, File.Category.CERTIFICATE, f"{record.course} certificate", upload)
    record.certificate = f
    record.save(update_fields=["certificate"])
    audit.record(actor, record, {"certificate": ("", f.pk)})
    return record


def new_record(employee, course, done_on, actor, expires_on=None, note="", verified=False, session=None):
    now = timezone.now()
    r = TrainingRecord(employee=employee, course=course, done_on=done_on, note=note, session=session,
                       expires_on=expires_on or validity.expires_from(done_on, course.validity_months),
                       recorded_by=actor, verified_by=actor if verified else None,
                       verified_at=now if verified else None)
    r.full_clean()
    r.save()
    return r


# ---- writing -----------------------------------------------------------------

@transaction.atomic
def record(actor, employee, course, done_on, upload=None, expires_on=None, note=""):
    """HR, or the person's line manager today, records a completion:
    verified at once. `upload`, a certificate, is stored last."""
    today = timezone.localdate()
    if not access.may_record_training_for(actor, employee, today):
        raise PermissionDenied
    check_course(course)
    check_date(done_on, today)
    if upload is not None:
        files.sniff(upload)
    r = new_record(employee, course, done_on, actor, expires_on=expires_on, note=note, verified=True)
    audit.record(actor, r, {"recorded": ("", f"{course}: done {done_on:%d %b %Y}")})
    if upload is not None:
        attach(actor, r, upload)
    return r


@transaction.atomic
def self_record(actor, course, done_on, upload=None):
    """The person records their own completion: pending until HR or their
    manager verifies it. An online course needs its certificate."""
    me = access.employee_for(actor)
    if me is None:
        raise PermissionDenied
    today = timezone.localdate()
    check_course(course)
    check_date(done_on, today)
    if upload is None and course.delivery == Course.Delivery.ONLINE:
        raise ValidationError("Upload your certificate for this course.")
    if upload is not None:
        files.sniff(upload)
    r = new_record(me, course, done_on, actor)
    audit.record(actor, r, {"self_recorded": ("", f"{course}: done {done_on:%d %b %Y}")})
    if upload is not None:
        attach(actor, r, upload)
    return r


def _pending_only(record):
    if not record.pending:
        raise ValidationError("This record is not waiting to be verified.")


@transaction.atomic
def verify(actor, record):
    if not access.may_verify(actor, record):
        raise PermissionDenied
    _pending_only(record)
    record.verified_by, record.verified_at = actor, timezone.now()
    record.save(update_fields=["verified_by", "verified_at"])
    audit.record(actor, record, {"verified": ("", f"{record.course}: done {record.done_on:%d %b %Y}")})
    return record


@transaction.atomic
def reject(actor, record, note):
    """Turn a pending record down with a note; the person is emailed the
    note and where to record again. The record stays, counting for nothing."""
    if not access.may_verify(actor, record):
        raise PermissionDenied
    _pending_only(record)
    note = (note or "").strip()[:200]
    if not note:
        raise ValidationError("Say why, so the person knows what to put right.")
    record.rejected_at, record.rejected_note = timezone.now(), note
    record.save(update_fields=["rejected_at", "rejected_note"])
    audit.record(actor, record, {"rejected": ("", note)})
    _tell_rejected(record)
    return record


def _tell_rejected(record):
    """Never raises and records no failure when there is no relay: the page
    says the record was turned down either way."""
    to = active_email(record.employee)
    if not to or not email_is_configured():
        return
    body = render_to_string("email/training_rejected.txt",
                            {"record": record, "url": link(reverse("people:me"))})
    mail.send(f"Practice HR: your {record.course} training record", body, [to])


@transaction.atomic
def set_expiry(actor, record, expires_on):
    """HR's one edit after the fact: the expiry of a verified record."""
    if not access.can_view_restricted(actor):
        raise PermissionDenied
    if not record.counts:
        raise ValidationError("Only a verified record has an expiry to change.")
    before = record.expires_on
    record.expires_on = expires_on
    record.full_clean()
    record.save(update_fields=["expires_on"])
    audit.record(actor, record, {"expires_on": (before, expires_on)})
    return record
