"""A face-to-face group recorded once: one TrainingSession and one verified
TrainingRecord per attendee, in one transaction. HR records anyone; a
manager only their direct reports on the day, and one outsider refuses the
whole call before anything is written. The attendance sheet, if any, is a
file with no person (stored last, as every upload is)."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from documents.models import File
from documents.services import files
from people.services import access, audit
from training.models import TrainingSession
from training.services import training


@transaction.atomic
def record_session(actor, course, held_on, attendees, trainer="", note="", upload=None):
    today = timezone.localdate()
    attendees = list({e.pk: e for e in attendees}.values())           # a name ticked twice is one record
    if not attendees:
        raise ValidationError("Choose at least one person who attended.")
    training.check_course(course)
    training.check_date(held_on, today, what="held")
    if not access.can_view_restricted(actor):
        me = access.employee_for(actor)
        reports = {emp.employee_id for emp in access.direct_reports(me, held_on)} if me is not None else set()
        if any(e.pk not in reports for e in attendees):
            raise PermissionDenied
    if upload is not None:
        files.sniff(upload)
    s = TrainingSession(course=course, held_on=held_on, trainer=trainer, note=note, recorded_by=actor)
    s.full_clean()
    s.save()
    for e in attendees:
        r = training.new_record(e, course, held_on, actor, verified=True, session=s)
        audit.record(actor, r, {"session_recorded": ("", f"{course}: session on {held_on:%d %b %Y}")})
    if upload is not None:
        f = files.add(actor, None, File.Category.CERTIFICATE, f"{course} attendance sheet, {held_on:%d %b %Y}",
                      upload)
        s.attendance_sheet = f
        s.save(update_fields=["attendance_sheet"])
    return s
