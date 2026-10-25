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
