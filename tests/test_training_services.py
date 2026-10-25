from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from compliance import validity
from documents.models import File
from people.models import AuditEntry
from people.services import titles
from tests.factories import make_employee, make_employment, make_position
from training.models import Course, TrainingRecord
from training.services import training

pytestmark = pytest.mark.django_db
User = get_user_model()
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


def _pdf(name="cert.pdf"):
    return SimpleUploadedFile(name, PDF)


@pytest.fixture
def fire():
    c = Course.objects.get(code="fire_safety")            # online, 12 months
    c.positions.add(titles.get_or_create("Receptionist"))
    return c


@pytest.fixture
def bls():
    c = Course.objects.get(code="basic_life_support")     # face to face, 12 months
    c.everyone = True
    c.save()
    return c


def _receptionist(user=None, manager=None, days=400, title="Receptionist"):
    e = make_employee(user=user)
    emp = make_employment(e, start=timezone.localdate() - timedelta(days=days))
    make_position(emp, title=title, manager=manager)
    return e


def _manager():
    m = make_employee(first="Mo", last="Khan", user=User.objects.create_user(email="mo@example.com", password="pw"))
    make_employment(m, start=timezone.localdate() - timedelta(days=800))
    return m


def test_required_is_by_title_or_everyone_and_needs_an_employment(fire, bls):
    e = _receptionist()
    assert [c.code for c in training.required_for(e, timezone.localdate())] == ["basic_life_support", "fire_safety"]
    nurse = _receptionist(title="Practice Nurse")
    assert [c.code for c in training.required_for(nurse, timezone.localdate())] == ["basic_life_support"]
    nobody = make_employee(first="Jo", last="Bloggs")
    assert training.required_for(nobody, timezone.localdate()) == []
    fire.active = False
    fire.save()
    assert [c.code for c in training.required_for(e, timezone.localdate())] == ["basic_life_support"]


def test_everyone_courses_need_no_position_and_a_dropped_title_is_not_chased(fire, bls, hr_admin):
    today = timezone.localdate()
    e = make_employee()
    make_employment(e, start=today - timedelta(days=10))           # employed, no position yet
    assert [c.code for c in training.required_for(e, today)] == ["basic_life_support"]
    r = _receptionist()
    training.record(hr_admin, r, fire, today - timedelta(days=5), upload=_pdf())
    fire.positions.clear()
    rows = {row.course.code: row for row in training.state(r, today)}
    assert rows["fire_safety"].status == "not_required" and rows["fire_safety"].latest is not None
    assert rows["fire_safety"].label == "Not required"


def test_record_defaults_the_expiry_verifies_at_once_stores_the_certificate_and_audits(fire, hr_admin):
    today = timezone.localdate()
    e = _receptionist()
    done = today - timedelta(days=30)
    r = training.record(hr_admin, e, fire, done, upload=_pdf(), note="Seen the certificate")
    assert r.counts and r.verified_by == hr_admin and r.recorded_by == hr_admin
    assert r.expires_on == validity.expires_from(done, 12)
    assert r.certificate.category == File.Category.CERTIFICATE and r.certificate.employee == e
    assert r.certificate.title == "Fire safety certificate" and not r.certificate.hr_only
    kinds = set(AuditEntry.objects.filter(model="training.trainingrecord", object_id=r.pk)
                .values_list("field", flat=True))
    assert kinds == {"recorded", "certificate"}
    [row] = [x for x in training.state(e, today) if x.course == fire]
    assert row.status == "current" and row.latest == r and row.expires_on == r.expires_on


def test_status_table_and_a_renewal_wins(fire, hr_admin):
    today = timezone.localdate()
    e = _receptionist()
    assert [x.status for x in training.state(e, today) if x.course == fire] == ["missing"]
    old = training.record(hr_admin, e, fire, today - timedelta(days=400), upload=_pdf())
    assert [x.status for x in training.state(e, today) if x.course == fire] == ["lapsed"]
    TrainingRecord.objects.filter(pk=old.pk).update(expires_on=today + timedelta(days=30))
    assert [x.status for x in training.state(e, today, window_days=60) if x.course == fire] == ["due_soon"]
    assert [x.status for x in training.state(e, today, window_days=10) if x.course == fire] == ["current"]
    new = training.record(hr_admin, e, fire, today - timedelta(days=1), upload=_pdf())
    [row] = [x for x in training.state(e, today) if x.course == fire]
    assert row.latest == new and row.status == "current" and TrainingRecord.objects.filter(employee=e).count() == 2


def test_self_record_needs_a_certificate_for_an_online_course_only(fire, bls, employee_user):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    with pytest.raises(ValidationError, match="certificate"):
        training.self_record(employee_user, fire, today)
    r = training.self_record(employee_user, fire, today, upload=_pdf())
    assert r.pending and r.recorded_by == employee_user and r.certificate is not None
    s = training.self_record(employee_user, bls, today - timedelta(days=2))        # face to face: no file needed
    assert s.pending and s.certificate is None
    assert AuditEntry.objects.filter(model="training.trainingrecord", field="self_recorded").count() == 2
    rows = {x.course.code: x for x in training.state(e, today)}
    assert rows["fire_safety"].status == "awaiting_verification" and rows["fire_safety"].pending == r
    assert rows["fire_safety"].label == "Awaiting verification" and rows["fire_safety"].latest is None


def test_self_record_is_for_yourself_only_and_dates_are_checked(fire, employee_user, hr_admin):
    today = timezone.localdate()
    _receptionist(user=employee_user)
    with pytest.raises(ValidationError, match="after today"):
        training.self_record(employee_user, fire, today + timedelta(days=1), upload=_pdf())
    with pytest.raises(PermissionDenied):
        training.self_record(hr_admin, fire, today, upload=_pdf())          # HR with no employee record
    fire.active = False
    fire.save()
    with pytest.raises(ValidationError, match="no longer"):
        training.self_record(employee_user, fire, today, upload=_pdf())


def test_verify_makes_it_count_and_is_for_hr_or_the_manager(fire, employee_user, hr_admin):
    today = timezone.localdate()
    m = _manager()
    e = _receptionist(user=employee_user, manager=m)
    r = training.self_record(employee_user, fire, today - timedelta(days=3), upload=_pdf())
    with pytest.raises(PermissionDenied):
        training.verify(employee_user, r)
    other = User.objects.create_user(email="jo@example.com", password="pw")
    with pytest.raises(PermissionDenied):
        training.verify(other, r)
    training.verify(m.user, r)
    r.refresh_from_db()
    assert r.counts and r.verified_by == m.user and r.verified_at is not None
    assert [x.status for x in training.state(e, today) if x.course == fire] == ["current"]
    with pytest.raises(ValidationError, match="not waiting"):
        training.verify(hr_admin, r)
    assert AuditEntry.objects.filter(model="training.trainingrecord", object_id=r.pk, field="verified").exists()


def test_reject_needs_a_note_emails_the_person_and_counts_for_nothing(fire, employee_user, hr_admin, configured):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    r = training.self_record(employee_user, fire, today, upload=_pdf())
    with pytest.raises(ValidationError, match="why"):
        training.reject(hr_admin, r, "   ")
    training.reject(hr_admin, r, "This is last year's certificate.")
    r.refresh_from_db()
    assert r.rejected and r.rejected_note == "This is last year's certificate." and not r.counts
    [msg] = mail.outbox
    assert msg.to == ["sam@example.com"] and "Fire safety" in msg.subject
    assert "This is last year's certificate." in msg.body and "/people/me/" in msg.body
    [row] = [x for x in training.state(e, today) if x.course == fire]
    assert row.status == "missing" and row.rejected == r and row.pending is None
    with pytest.raises(ValidationError):
        training.reject(hr_admin, r, "again")


def test_a_rejected_record_counts_for_nothing_and_a_new_upload_clears_the_note(fire, employee_user, hr_admin):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    first = training.self_record(employee_user, fire, today, upload=_pdf())
    training.reject(hr_admin, first, "Wrong course.")        # no relay configured: no email, no failure row
    from absence.models import EmailFailure
    assert not EmailFailure.objects.exists()
    second = training.self_record(employee_user, fire, today, upload=_pdf())
    [row] = [x for x in training.state(e, today) if x.course == fire]
    assert row.status == "awaiting_verification" and row.pending == second and row.rejected is None
    training.verify(hr_admin, second)
    [row] = [x for x in training.state(e, today) if x.course == fire]
    assert row.status == "current" and row.latest.pk == second.pk and row.rejected is None


def test_summary_counts_and_next_expiry(fire, bls, hr_admin, employee_user):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    training.record(hr_admin, e, fire, today - timedelta(days=350), upload=_pdf())      # due soon (12 months)
    training.self_record(employee_user, bls, today)                                    # awaiting
    s = training.summary(e, today)
    assert (s["current"], s["due_soon"], s["lapsed"], s["missing"], s["awaiting_verification"]) == (0, 1, 0, 0, 1)
    assert s["next_expiry"] == validity.expires_from(today - timedelta(days=350), 12)


def test_summary_counts_a_pending_renewal_as_to_verify(fire, bls, hr_admin, employee_user):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    training.record(hr_admin, e, fire, today - timedelta(days=100), upload=_pdf())
    training.self_record(employee_user, fire, today, upload=_pdf())     # a renewal waiting: the course stays current
    s = training.summary(e, today)
    assert s["current"] == 1 and s["awaiting_verification"] == 1


def test_an_expiry_before_the_date_done_is_refused(fire, hr_admin, employee_user):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    with pytest.raises(ValidationError, match="cannot be before the date done"):
        training.record(hr_admin, e, fire, today - timedelta(days=5), expires_on=today - timedelta(days=6))
    assert TrainingRecord.objects.count() == 0
    r = training.record(hr_admin, e, fire, today - timedelta(days=5), expires_on=today - timedelta(days=5))
    with pytest.raises(ValidationError, match="cannot be before the date done"):
        training.set_expiry(hr_admin, r, today - timedelta(days=6))
    r.refresh_from_db()
    assert r.expires_on == today - timedelta(days=5)


def test_set_expiry_needs_an_expiry_on_a_course_with_a_validity_but_not_a_one_off(fire, hr_admin, employee_user):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    r = training.record(hr_admin, e, fire, today - timedelta(days=5))
    with pytest.raises(ValidationError, match="enter the expiry, or record it again"):
        training.set_expiry(hr_admin, r, None)
    r.refresh_from_db()
    assert r.expires_on is not None
    induction = Course.objects.create(name="Induction", code="induction", delivery=Course.Delivery.FACE_TO_FACE,
                                      validity_months=None)
    one_off = training.record(hr_admin, e, induction, today - timedelta(days=5))
    assert one_off.expires_on is None
    training.set_expiry(hr_admin, one_off, None)                          # blank is what a one-off has
    one_off.refresh_from_db()
    assert one_off.expires_on is None


def test_set_expiry_is_hrs_one_edit_and_audited(fire, hr_admin, employee_user):
    today = timezone.localdate()
    m = _manager()
    e = _receptionist(user=employee_user, manager=m)
    r = training.record(hr_admin, e, fire, today - timedelta(days=5), upload=_pdf())
    with pytest.raises(PermissionDenied):
        training.set_expiry(m.user, r, today + timedelta(days=10))
    training.set_expiry(hr_admin, r, today + timedelta(days=10))
    r.refresh_from_db()
    assert r.expires_on == today + timedelta(days=10)
    assert AuditEntry.objects.filter(model="training.trainingrecord", object_id=r.pk, field="expires_on").exists()
    p = training.self_record(employee_user, fire, today, upload=_pdf())
    with pytest.raises(ValidationError, match="verified"):
        training.set_expiry(hr_admin, p, today)


def test_record_is_refused_outside_the_managers_team_and_a_file_is_sniffed(fire, hr_admin, employee_user):
    today = timezone.localdate()
    m = _manager()
    e = _receptionist(user=employee_user)                          # nobody's report
    with pytest.raises(PermissionDenied):
        training.record(m.user, e, fire, today)
    with pytest.raises(ValidationError):
        training.record(hr_admin, e, fire, today, upload=SimpleUploadedFile("c.pdf", b"<html>not a pdf</html>"))
    assert not TrainingRecord.objects.exists() and not File.objects.exists()


def test_to_verify_lists_pending_records_of_people_employed_today(fire, hr_admin, employee_user):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    p = training.self_record(employee_user, fire, today, upload=_pdf())
    training.record(hr_admin, e, fire, today - timedelta(days=1), upload=_pdf())
    assert list(training.to_verify(today)) == [p]
    emp = e.employments.get()
    emp.end_date = today - timedelta(days=1)
    emp.save()
    assert list(training.to_verify(today)) == []


def test_a_backdated_rejection_does_not_mark_a_current_course_but_a_later_one_does(fire, employee_user, hr_admin):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    training.record(hr_admin, e, fire, today - timedelta(days=10), upload=_pdf())          # counts, lower id
    old = training.self_record(employee_user, fire, today - timedelta(days=380), upload=_pdf())   # higher id, older
    training.reject(hr_admin, old, "Last year's certificate.")
    [row] = [x for x in training.state(e, today) if x.course == fire]
    assert row.status == "current" and row.rejected is None
    later = training.self_record(employee_user, fire, today, upload=_pdf())                # dated after the counting one
    training.reject(hr_admin, later, "Not the right course.")
    [row] = [x for x in training.state(e, today) if x.course == fire]
    assert row.status == "current" and row.rejected == later


def test_a_pending_record_is_awaiting_when_nothing_counts_even_if_not_required(fire, employee_user, hr_admin):
    today = timezone.localdate()
    e = make_employee(user=employee_user)
    make_employment(e, start=today - timedelta(days=10))            # employed, no position: fire is not required
    training.self_record(employee_user, fire, today, upload=_pdf())
    [row] = [x for x in training.state(e, today) if x.course == fire]
    assert row.status == "awaiting_verification" and row.latest is None and row.pending is not None
    # the converse: a current counting record keeps "not required" while a renewal waits
    r = _receptionist(user=User.objects.create_user(email="rec@example.com", password="pw"))
    training.record(hr_admin, r, fire, today - timedelta(days=30), upload=_pdf())
    fire.positions.clear()
    training.self_record(r.user, fire, today, upload=_pdf())
    [row] = [x for x in training.state(r, today) if x.course == fire]
    assert row.status == "not_required" and row.latest is not None and row.pending is not None
