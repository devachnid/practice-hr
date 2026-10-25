"""The site's training pages, by role. Task 8: My record and Getting
started; Task 9 adds My team, the person page and sessions below."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone

from documents.models import File
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


@pytest.fixture
def fire():
    c = Course.objects.get(code="fire_safety")
    c.positions.add(titles.get_or_create("Receptionist"))
    return c


@pytest.fixture
def bls():
    c = Course.objects.get(code="basic_life_support")
    c.everyone = True
    c.save()
    return c


def _pdf(name="cert.pdf"):
    return SimpleUploadedFile(name, PDF)


def _receptionist(user=None, manager=None, days=400):
    e = make_employee(user=user)
    emp = make_employment(e, start=timezone.localdate() - timedelta(days=days))
    make_position(emp, title="Receptionist", manager=manager)
    return e


def _manager():
    m = make_employee(first="Mo", last="Khan", user=User.objects.create_user(email="mo@example.com", password="pw"))
    make_employment(m, start=timezone.localdate() - timedelta(days=800))
    c = Client()
    c.force_login(m.user)
    return m, c


# ---- Task 8: My record and Getting started -----------------------------------

def test_my_record_lists_training_with_the_record_form_and_no_note(fire, bls, hr_admin, employee_user, employee_client):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    r = training.record(hr_admin, e, fire, today - timedelta(days=5), upload=_pdf(), note="HR ONLY NOTE")
    body = employee_client.get("/people/me/").content.decode()
    assert "<h2>Training</h2>" in body and "Fire safety" in body and "Basic life support" in body
    assert "Current" in body and "Missing" in body and "HR ONLY NOTE" not in body
    assert f'href="/documents/file/{r.certificate_id}/"' in body
    assert 'action="/training/record/"' in body and 'name="course"' in body and 'name="file"' in body


def test_recording_your_own_online_course_needs_the_file_then_shows_awaiting(fire, employee_user, employee_client):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    r = employee_client.post("/training/record/", {"course": fire.pk, "done_on": today.isoformat()})
    assert r.status_code == 302 and r["Location"] == "/people/me/"
    body = employee_client.get("/people/me/").content.decode()
    assert "Upload your certificate for this course." in body and not TrainingRecord.objects.exists()
    r = employee_client.post("/training/record/", {"course": fire.pk, "done_on": today.isoformat(), "file": _pdf()})
    assert r.status_code == 302
    body = employee_client.get("/people/me/").content.decode()
    assert "Awaiting verification" in body and "HR or your manager will verify" in body
    rec = TrainingRecord.objects.get()
    assert rec.pending and rec.employee == e and rec.certificate.employee == e


def test_a_rejected_record_shows_its_note_until_the_next_upload(fire, hr_admin, employee_user, employee_client):
    today = timezone.localdate()
    _receptionist(user=employee_user)
    rec = training.self_record(employee_user, fire, today, upload=_pdf())
    training.reject(hr_admin, rec, "Wrong course entirely.")
    body = employee_client.get("/people/me/").content.decode()
    assert "Wrong course entirely." in body and "Missing" in body
    training.self_record(employee_user, fire, today, upload=_pdf())
    body = employee_client.get("/people/me/").content.decode()
    assert "Wrong course entirely." not in body and "Awaiting verification" in body


def test_the_record_post_is_post_only_login_only_and_validated(fire, employee_user, employee_client, client):
    _receptionist(user=employee_user)
    assert employee_client.get("/training/record/").status_code == 405
    r = client.post("/training/record/", {"course": fire.pk, "done_on": "2030-01-01"})
    assert r.status_code == 302 and "/login/" in r["Location"]
    r = employee_client.post("/training/record/", {"course": fire.pk, "done_on": "not a date", "file": _pdf()})
    assert r.status_code == 302
    body = employee_client.get("/people/me/").content.decode()
    assert "Enter a valid date." in body and not TrainingRecord.objects.exists() and not File.objects.exists()


def test_a_starter_records_training_from_getting_started_before_day_one(fire, employee_user, employee_client):
    today = timezone.localdate()
    e = make_employee(user=employee_user)
    make_position(make_employment(e, start=today + timedelta(days=7)), title="Receptionist")
    body = employee_client.get("/onboarding/").content.decode()
    assert "<h2>Training</h2>" in body and 'action="/training/record/"' in body
    assert "Missing" not in body                         # nothing is required before the start date
    r = employee_client.post("/training/record/", {"course": fire.pk, "done_on": today.isoformat(), "file": _pdf()})
    assert r.status_code == 302 and r["Location"] == "/onboarding/"
    assert TrainingRecord.objects.get().pending
    body = employee_client.get("/onboarding/").content.decode()
    assert "Awaiting verification" in body


def test_a_login_with_no_employee_record_is_told_so(fire, employee_client):
    r = employee_client.post("/training/record/", {"course": fire.pk, "done_on": timezone.localdate().isoformat(),
                                                   "file": _pdf()})
    assert r.status_code == 302
    body = employee_client.get("/people/me/").content.decode()
    assert "no employee record linked to your login" in body
    body = employee_client.get("/onboarding/").content.decode()
    assert "no employee record linked to your login" in body and 'action="/training/record/"' not in body


# ---- Task 9: My team, the person page, verify, reject, sessions --------------

def test_my_team_shows_counts_and_links_to_the_person_page_with_the_note(fire, bls, hr_admin, employee_user):
    today = timezone.localdate()
    m, mc = _manager()
    e = _receptionist(user=employee_user, manager=m)
    r = training.record(hr_admin, e, fire, today - timedelta(days=5), upload=_pdf(), note="Seen the cert")
    body = mc.get("/people/team/").content.decode()
    assert "1 current" in body and "1 missing" in body and f'href="/training/{e.pk}/"' in body
    assert 'href="/training/session/"' in body
    body = mc.get(f"/training/{e.pk}/").content.decode()
    assert "Fire safety" in body and "Seen the cert" in body and f'href="/documents/file/{r.certificate_id}/"' in body
    assert f'action="/training/{e.pk}/record/"' in body
    assert mc.get(f"/documents/file/{r.certificate_id}/").status_code == 200       # the manager opens the certificate


def test_the_person_sees_their_page_without_the_note_or_the_record_form(fire, hr_admin, employee_user, employee_client):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    training.record(hr_admin, e, fire, today - timedelta(days=5), upload=_pdf(), note="Seen the cert")
    body = employee_client.get(f"/training/{e.pk}/").content.decode()
    assert "Fire safety" in body and "Seen the cert" not in body and f'action="/training/{e.pk}/record/"' not in body
    other = _receptionist(user=User.objects.create_user(email="jo@example.com", password="pw"))
    assert employee_client.get(f"/training/{other.pk}/").status_code == 403
    assert employee_client.post(f"/training/{other.pk}/record/", {"course": fire.pk, "done_on": today.isoformat()}).status_code == 403


def test_a_manager_records_for_a_report_and_it_counts_at_once(fire, employee_user):
    today = timezone.localdate()
    m, mc = _manager()
    e = _receptionist(user=employee_user, manager=m)
    r = mc.post(f"/training/{e.pk}/record/", {"course": fire.pk, "done_on": (today - timedelta(days=2)).isoformat(),
                                               "file": _pdf(), "note": "Group session, I was there"})
    assert r.status_code == 302 and r["Location"] == f"/training/{e.pk}/"
    rec = TrainingRecord.objects.get()
    assert rec.counts and rec.verified_by == m.user and rec.note == "Group session, I was there"
    r = mc.post(f"/training/{e.pk}/record/", {"course": fire.pk, "done_on": (today + timedelta(days=1)).isoformat()})
    assert r.status_code == 302 and TrainingRecord.objects.count() == 1
    assert "cannot be after today" in mc.get(f"/training/{e.pk}/").content.decode()


def test_verify_is_a_post_and_reject_confirms_then_emails(fire, employee_user, employee_client, configured):
    from django.core import mail
    today = timezone.localdate()
    m, mc = _manager()
    e = _receptionist(user=employee_user, manager=m)
    first = training.self_record(employee_user, fire, today, upload=_pdf())
    body = mc.get(f"/training/{e.pk}/").content.decode()
    assert f'action="/training/records/{first.pk}/verify/"' in body and f'href="/training/records/{first.pk}/reject/"' in body
    assert mc.get(f"/training/records/{first.pk}/verify/").status_code == 405
    assert employee_client.post(f"/training/records/{first.pk}/verify/").status_code == 403
    r = mc.post(f"/training/records/{first.pk}/verify/")
    assert r.status_code == 302 and TrainingRecord.objects.get(pk=first.pk).counts
    second = training.self_record(employee_user, fire, today, upload=_pdf())
    body = mc.get(f"/training/records/{second.pk}/reject/").content.decode()
    assert 'name="note"' in body and not TrainingRecord.objects.get(pk=second.pk).rejected        # GET writes nothing
    r = mc.post(f"/training/records/{second.pk}/reject/", {"note": ""})
    assert r.status_code == 200 and "required" in r.content.decode().lower()
    r = mc.post(f"/training/records/{second.pk}/reject/", {"note": "Certificate is unreadable."})
    assert r.status_code == 302 and TrainingRecord.objects.get(pk=second.pk).rejected
    assert [msg.to for msg in mail.outbox] == [["sam@example.com"]] and "unreadable" in mail.outbox[0].body
    assert "The upload of" in mc.get(f"/training/{e.pk}/").content.decode()
    assert "was turned down: Certificate is unreadable." in mc.get(f"/training/{e.pk}/").content.decode()
    assert "was turned down: Certificate is unreadable." in employee_client.get(f"/training/{e.pk}/").content.decode()
    assert employee_client.get(f"/training/records/{second.pk}/reject/").status_code == 403


def test_the_session_form_lists_only_the_managers_reports_and_records_them(bls, employee_user):
    today = timezone.localdate()
    m, mc = _manager()
    e = _receptionist(user=employee_user, manager=m)
    other = _receptionist(user=User.objects.create_user(email="jo@example.com", password="pw"))
    body = mc.get("/training/session/").content.decode()
    # match the attendee checkboxes: the course <option> values are pks too and can collide
    assert f'name="attendees" value="{e.pk}"' in body and f'name="attendees" value="{other.pk}"' not in body
    r = mc.post("/training/session/", {"course": bls.pk, "held_on": today.isoformat(), "trainer": "Resus UK",
                                       "attendees": [e.pk], "file": _pdf("sheet.pdf")})
    assert r.status_code == 302 and r["Location"] == "/people/team/"
    rec = TrainingRecord.objects.get()
    assert rec.counts and rec.session.trainer == "Resus UK" and rec.session.attendance_sheet is not None
    assert mc.get(f"/documents/file/{rec.session.attendance_sheet_id}/").status_code == 200
    r = mc.post("/training/session/", {"course": bls.pk, "held_on": today.isoformat(), "attendees": [other.pk]})
    assert r.status_code == 200 and "valid choice" in r.content.decode()           # not in the manager's list
    # a day the report was not yet theirs: the form offers today's reports, the service checks the day
    r = mc.post("/training/session/", {"course": bls.pk, "held_on": (today - timedelta(days=500)).isoformat(),
                                       "attendees": [e.pk]})
    assert r.status_code == 200 and "report to you on that date" in r.content.decode()
    assert TrainingRecord.objects.count() == 1


def test_hr_records_a_session_for_anyone_and_a_non_manager_cannot_open_the_form(bls, hr_admin, admin_client,
                                                                                 employee_user, employee_client):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    assert employee_client.get("/training/session/").status_code == 403
    body = admin_client.get("/training/session/").content.decode()
    assert f'name="attendees" value="{e.pk}"' in body
    r = admin_client.post("/training/session/", {"course": bls.pk, "held_on": today.isoformat(), "attendees": [e.pk]})
    assert r.status_code == 302 and r["Location"] == "/admin/training/trainingsession/"
    assert TrainingRecord.objects.get().recorded_by == hr_admin


def test_the_digest_link_for_hr_is_the_person_page(fire, hr_admin, employee_user):
    from compliance.models import ReminderSchedule
    from django.urls import reverse

    from training.services import due
    e = _receptionist(user=employee_user)
    [item] = [i for i in due.due_items(timezone.localdate(), ReminderSchedule.get()) if i.recipient == "hr@example.com"]
    assert item.url.endswith(reverse("training:person", args=[e.pk]))


def test_the_back_link_goes_where_the_viewer_can_go(fire, hr_admin, admin_client, employee_user, employee_client):
    m, mc = _manager()
    e = _receptionist(user=employee_user, manager=m)
    own = employee_client.get(f"/training/{e.pk}/").content.decode()
    assert '<a href="/people/me/">Back</a>' in own and "/people/team/" not in own
    assert '<a href="/people/team/">Back</a>' in mc.get(f"/training/{e.pk}/").content.decode()
    assert f'<a href="/admin/people/employee/{e.pk}/change/">Back</a>' in admin_client.get(f"/training/{e.pk}/").content.decode()
