from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from compliance import validity
from documents.models import File
from people.models import AuditEntry
from tests.factories import make_employee, make_employment, make_position
from training.models import Course, TrainingRecord, TrainingSession
from training.services import sessions, training

pytestmark = pytest.mark.django_db
User = get_user_model()
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def bls():
    c = Course.objects.get(code="basic_life_support")
    c.everyone = True
    c.save()
    return c


def _team():
    """A manager with two reports, and a third person on another team."""
    today = timezone.localdate()
    m = make_employee(first="Mo", last="Khan", user=User.objects.create_user(email="mo@example.com", password="pw"))
    make_employment(m, start=today - timedelta(days=800))
    reports = []
    for first in ("Sam", "Ann"):
        e = make_employee(first=first, last="Patel")
        make_position(make_employment(e, start=today - timedelta(days=400)), manager=m)
        reports.append(e)
    other = make_employee(first="Jo", last="Bloggs")
    make_position(make_employment(other, start=today - timedelta(days=400)))
    return m, reports, other


def test_a_session_makes_one_verified_record_per_attendee_sharing_the_sheet(bls, hr_admin):
    today = timezone.localdate()
    m, (sam, ann), other = _team()
    held = today - timedelta(days=3)
    s = sessions.record_session(hr_admin, bls, held, [sam, ann, other, ann], trainer="Resus UK", note="Hall",
                                upload=SimpleUploadedFile("sheet.pdf", PDF))
    assert s.trainer == "Resus UK" and s.recorded_by == hr_admin
    recs = list(TrainingRecord.objects.filter(session=s).order_by("employee__first_name"))
    assert [r.employee for r in recs] == [ann, other, sam]                     # the duplicate is one record
    assert all(r.counts and r.done_on == held and r.recorded_by == hr_admin and r.certificate is None for r in recs)
    assert all(r.expires_on == validity.expires_from(held, 12) for r in recs)
    assert s.attendance_sheet.employee is None and s.attendance_sheet.category == File.Category.CERTIFICATE
    assert s.attendance_sheet.title == f"Basic life support attendance sheet, {held:%d %b %Y}"
    assert AuditEntry.objects.filter(model="training.trainingrecord", field="session_recorded").count() == 3
    [row] = [x for x in training.state(sam, today) if x.course == bls]
    assert row.status == "current" and row.latest.session == s


def test_a_manager_records_a_session_for_their_own_reports(bls):
    today = timezone.localdate()
    m, (sam, ann), other = _team()
    s = sessions.record_session(m.user, bls, today, [sam, ann])            # no sheet: fine
    assert s.attendance_sheet is None and TrainingRecord.objects.filter(session=s).count() == 2


def test_one_outsider_refuses_the_whole_session_and_writes_nothing(bls):
    today = timezone.localdate()
    m, (sam, ann), other = _team()
    with pytest.raises(PermissionDenied):
        sessions.record_session(m.user, bls, today, [sam, other], upload=SimpleUploadedFile("s.pdf", PDF))
    assert not TrainingSession.objects.exists() and not TrainingRecord.objects.exists()
    assert not File.objects.exists()
    with pytest.raises(PermissionDenied):
        sessions.record_session(m.user, bls, today, [m])                      # never yourself
    stranger = User.objects.create_user(email="jo@example.com", password="pw")
    with pytest.raises(PermissionDenied):
        sessions.record_session(stranger, bls, today, [sam])


def test_the_sessions_rules(bls, hr_admin):
    today = timezone.localdate()
    m, (sam, ann), other = _team()
    with pytest.raises(ValidationError, match="at least one"):
        sessions.record_session(hr_admin, bls, today, [])
    with pytest.raises(ValidationError, match="after today"):
        sessions.record_session(hr_admin, bls, today + timedelta(days=1), [sam])
    bls.active = False
    bls.save()
    with pytest.raises(ValidationError, match="no longer"):
        sessions.record_session(hr_admin, bls, today, [sam])
    bls.active = True
    bls.save()
    with pytest.raises(ValidationError):
        sessions.record_session(hr_admin, bls, today, [sam], upload=SimpleUploadedFile("s.pdf", b"<html></html>"))
    assert not TrainingSession.objects.exists()


def test_recording_the_session_again_adds_the_person_left_off(bls, hr_admin):
    today = timezone.localdate()
    m, (sam, ann), other = _team()
    first = sessions.record_session(hr_admin, bls, today, [sam])
    second = sessions.record_session(hr_admin, bls, today, [ann])
    assert first != second and TrainingRecord.objects.filter(course=bls).count() == 2
    assert str(second) == f"Basic life support on {today:%d %b %Y}"
