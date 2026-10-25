from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from people.models import AuditEntry
from people.services import titles
from tests.factories import make_employee, make_employment, make_position, make_team
from training.models import Course, TrainingRecord, TrainingSession
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


def _receptionist(user=None, team=None, first="Sam", last="Patel"):
    e = make_employee(first=first, last=last, user=user)
    emp = make_employment(e, start=timezone.localdate() - timedelta(days=400))
    make_position(emp, title="Receptionist", team=team)
    return e


def test_the_add_page_records_through_the_service_and_stores_the_certificate(fire, hr_admin, admin_client):
    today = timezone.localdate()
    e = _receptionist()
    r = admin_client.post("/admin/training/trainingrecord/add/", {
        "employee": e.pk, "course": fire.pk, "done_on": (today - timedelta(days=3)).isoformat(), "expires_on": "",
        "note": "Seen it", "upload": _pdf()})
    assert r.status_code == 302
    rec = TrainingRecord.objects.get()
    assert rec.counts and rec.recorded_by == hr_admin and rec.certificate is not None and rec.note == "Seen it"
    assert rec.expires_on == training.validity.expires_from(today - timedelta(days=3), 12)
    r = admin_client.post("/admin/training/trainingrecord/add/", {
        "employee": e.pk, "course": fire.pk, "done_on": (today + timedelta(days=1)).isoformat(), "expires_on": "",
        "note": ""})
    assert r.status_code == 200 and "cannot be after today" in r.content.decode()
    assert TrainingRecord.objects.count() == 1


def test_the_change_page_is_read_only_but_for_the_expiry_of_a_verified_record(fire, hr_admin, admin_client, employee_user):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    rec = training.record(hr_admin, e, fire, today - timedelta(days=3), upload=_pdf())
    body = admin_client.get(f"/admin/training/trainingrecord/{rec.pk}/change/").content.decode()
    assert 'name="expires_on"' in body and 'name="done_on"' not in body and 'name="note"' not in body
    assert f'href="/documents/file/{rec.certificate_id}/"' in body
    r = admin_client.post(f"/admin/training/trainingrecord/{rec.pk}/change/",
                          {"expires_on": (today + timedelta(days=5)).isoformat()})
    assert r.status_code == 302
    rec.refresh_from_db()
    assert rec.expires_on == today + timedelta(days=5)
    assert AuditEntry.objects.filter(model="training.trainingrecord", object_id=rec.pk, field="expires_on").exists()
    pending = training.self_record(employee_user, fire, today, upload=_pdf())
    body = admin_client.get(f"/admin/training/trainingrecord/{pending.pk}/change/").content.decode()
    assert 'name="expires_on"' not in body and "Awaiting verification" in body
    assert admin_client.get(f"/admin/training/trainingrecord/{rec.pk}/delete/").status_code == 403


def test_verify_and_reject_confirm_on_get_and_act_on_post(fire, hr_admin, admin_client, employee_user, configured):
    from django.core import mail
    today = timezone.localdate()
    _receptionist(user=employee_user)
    first = training.self_record(employee_user, fire, today, upload=_pdf())
    body = admin_client.get(f"/admin/training/trainingrecord/{first.pk}/change/").content.decode()
    assert f"/admin/training/trainingrecord/{first.pk}/verify/" in body
    assert admin_client.get(f"/admin/training/trainingrecord/{first.pk}/verify/").status_code == 200
    assert TrainingRecord.objects.get(pk=first.pk).pending                          # GET wrote nothing
    r = admin_client.post(f"/admin/training/trainingrecord/{first.pk}/verify/")
    assert r.status_code == 302 and TrainingRecord.objects.get(pk=first.pk).counts
    assert admin_client.get(f"/admin/training/trainingrecord/{first.pk}/verify/").status_code == 403   # nothing to verify
    second = training.self_record(employee_user, fire, today, upload=_pdf())
    body = admin_client.get(f"/admin/training/trainingrecord/{second.pk}/reject/").content.decode()
    assert 'name="note"' in body
    r = admin_client.post(f"/admin/training/trainingrecord/{second.pk}/reject/", {"note": "Unreadable scan."})
    assert r.status_code == 302 and TrainingRecord.objects.get(pk=second.pk).rejected
    assert [m.to for m in mail.outbox] == [["sam@example.com"]]


def test_the_status_filter_and_the_list(fire, hr_admin, admin_client, employee_user):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    training.record(hr_admin, e, fire, today - timedelta(days=3), upload=_pdf())
    p = training.self_record(employee_user, fire, today, upload=_pdf())
    body = admin_client.get("/admin/training/trainingrecord/?status=pending").content.decode()
    assert f'href="/admin/training/trainingrecord/{p.pk}/change/' in body and body.count("Fire safety") >= 1
    assert "Awaiting verification" in body
    body = admin_client.get("/admin/training/trainingrecord/?status=verified").content.decode()
    assert f'href="/admin/training/trainingrecord/{p.pk}/change/' not in body


def test_the_session_add_page_records_everyone_ticked(bls, hr_admin, admin_client):
    today = timezone.localdate()
    a, b = _receptionist(), _receptionist(first="Ann", last="Brown")
    r = admin_client.post("/admin/training/trainingsession/add/", {
        "course": bls.pk, "held_on": today.isoformat(), "trainer": "Resus UK", "note": "",
        "attendees": [a.pk, b.pk], "upload": _pdf("sheet.pdf")})
    assert r.status_code == 302
    s = TrainingSession.objects.get()
    assert s.records.count() == 2 and s.attendance_sheet is not None
    body = admin_client.get(f"/admin/training/trainingsession/{s.pk}/change/").content.decode()
    assert "Ann Brown" in body and "Sam Patel" in body and f'href="/documents/file/{s.attendance_sheet_id}/"' in body
    assert admin_client.get(f"/admin/training/trainingsession/{s.pk}/delete/").status_code == 403


def test_the_compliance_tab_lists_training_with_links(fire, bls, hr_admin, admin_client, employee_user):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    rec = training.record(hr_admin, e, fire, today - timedelta(days=3), upload=_pdf())
    p = training.self_record(employee_user, bls, today)
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert ">Training</h3>" in body
    assert f'href="/admin/training/trainingrecord/{rec.pk}/change/"' in body
    assert f'href="/admin/training/trainingrecord/{p.pk}/change/"' in body and "Verify or reject" in body
    fire.positions.clear()
    bls.everyone = False
    bls.save()
    other = _receptionist(first="Jo", last="Bloggs")
    body = admin_client.get(f"/admin/people/employee/{other.pk}/change/").content.decode()
    assert "needs no training" in body


def test_the_matrix_page_filters_escapes_and_downloads(fire, bls, hr_admin, admin_client, employee_client, employee_user):
    today = timezone.localdate()
    reception, nursing = make_team(name="Reception"), make_team(name="Nursing")
    sam = _receptionist(user=employee_user, team=reception)
    nia = make_employee(first="Nia", last="Evans")
    make_position(make_employment(nia, start=today - timedelta(days=400)), title="Practice Nurse", team=nursing)
    training.record(hr_admin, sam, fire, today - timedelta(days=3), upload=_pdf(), note="HR ONLY NOTE")
    assert employee_client.get("/training/matrix/").status_code == 403
    assert employee_client.get("/training/matrix.csv").status_code == 403
    body = admin_client.get("/training/matrix/").content.decode()
    assert "Sam Patel" in body and "Nia Evans" in body and "Fire safety" in body and "HR ONLY NOTE" not in body
    assert f'href="/training/{sam.pk}/"' in body
    body = admin_client.get(f"/training/matrix/?team={nursing.pk}").content.decode()
    assert "Nia Evans" in body and "Sam Patel" not in body
    body = admin_client.get("/training/matrix/?q=%3Cb%3Epat%3C%2Fb%3E").content.decode()
    assert "<b>pat</b>" not in body and "&lt;b&gt;pat&lt;/b&gt;" in body
    body = admin_client.get("/training/matrix/?show=problems").content.decode()
    assert "Nia Evans" in body and "Sam Patel" in body            # both are missing Basic life support
    r = admin_client.get(f"/training/matrix.csv?course={fire.pk}&show=problems")
    assert r.status_code == 200 and r["Content-Type"].startswith("text/csv")
    assert r["Content-Disposition"] == f'attachment; filename="training-matrix-fire_safety-problems-{today.isoformat()}.csv"'
    assert r.content.decode().splitlines()[0] == "Person,Fire safety"
    body = admin_client.get("/training/matrix/?course=999").content.decode()
    assert "Sam Patel" in body                                   # an unknown filter value is ignored, not a 500


def test_the_filter_text_is_escaped_on_the_page(hr_admin, admin_client):
    body = admin_client.get("/training/matrix/?q=%22%3E%3Cscript%3Ex%3C%2Fscript%3E").content.decode()
    assert "<script>x</script>" not in body


def test_the_dashboard_counts_training_and_links_to_the_matrix(fire, bls, hr_admin, admin_client, employee_user):
    today = timezone.localdate()
    sam = _receptionist(user=employee_user)
    training.record(hr_admin, sam, fire, today - timedelta(days=400), upload=_pdf())      # lapsed
    training.self_record(employee_user, bls, today)                                      # to verify
    from absence.admin_dashboard import compliance_counts
    counts = compliance_counts(today)
    assert counts["training_problems"] == 1 and counts["training_to_verify"] == 1
    body = admin_client.get("/admin/").content.decode()
    assert "Training lapsed or missing" in body and "Training to verify" in body
    assert 'href="/training/matrix/?show=problems"' in body and 'href="/training/matrix/?show=to_verify"' in body
    body = admin_client.get("/admin/people/employee/?compliance=training_problems").content.decode()
    assert "Sam Patel" in body


def test_the_matrix_is_in_the_compliance_sidebar(admin_client):
    from django.test import RequestFactory

    from hr.admin_site import navigation
    request = RequestFactory().get("/admin/")
    request.user = type("U", (), {"is_active": True, "is_hr_admin": True, "is_superuser": False})()
    group = next(g for g in navigation(request) if g["title"] == "Compliance")
    titles_ = [i["title"] for i in group["items"]]
    assert titles_.index("Training sessions") + 1 == titles_.index("Training matrix")
