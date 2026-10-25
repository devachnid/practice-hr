import calendar
from datetime import date, timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from checks.models import Check, CheckType
from checks.services import checks
from people.services import titles
from tests.factories import make_employee, make_employment, make_position

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def dbs():
    t = CheckType.objects.get(code="dbs")          # seeded
    t.positions.add(titles.get_or_create("Receptionist"))
    return t


def _receptionist(user=None):
    e = make_employee(user=user)
    emp = make_employment(e, start=timezone.localdate() - timedelta(days=400))
    make_position(emp, title="Receptionist")
    return e


def test_seeded_types_exist_with_the_spec_defaults():
    by = {t.code: t for t in CheckType.objects.all()}
    assert set(by) >= {"right_to_work", "dbs", "references", "occupational_health", "hep_b", "indemnity",
                       "professional_registration"}
    assert by["dbs"].validity_months == 36 and by["dbs"].remind_person and by["dbs"].evidence == "reference"
    assert by["right_to_work"].validity_months is None and by["right_to_work"].evidence == "file"
    assert by["references"].validity_months is None and by["references"].evidence == "none"


def test_required_follows_the_primary_position_title(dbs):
    e = _receptionist()
    assert [t.code for t in checks.required_for(e, timezone.localdate())] == ["dbs"]
    other = make_employee(first="Jo", last="Bloggs")
    make_position(make_employment(other, start=timezone.localdate() - timedelta(days=10)), title="Practice Nurse")
    assert checks.required_for(other, timezone.localdate()) == []


def test_status_missing_current_due_soon_lapsed(dbs, hr_admin):
    today = timezone.localdate()
    e = _receptionist()
    assert checks.state(e, today)[0].status == "missing"
    done = today - timedelta(days=30)
    c = checks.record(hr_admin, e, dbs, done, Check.Outcome.CLEAR, reference="001234567890",
                      dbs_level=Check.DbsLevel.ENHANCED)
    assert c.expires_on == checks.expires_from(done, dbs)          # 36 calendar months on
    assert c.expires_on.year == done.year + 3 and c.expires_on.month == done.month
    assert checks.state(e, today)[0].status == "current"
    c.expires_on = today + timedelta(days=10); c.save()
    assert checks.state(e, today, window_days=60)[0].status == "due_soon"
    c.expires_on = today - timedelta(days=1); c.save()
    assert checks.state(e, today)[0].status == "lapsed"


def test_expiry_is_calendar_months_clipped_to_the_month_end(dbs):
    year = timezone.localdate().year + 1
    indemnity = CheckType.objects.get(code="indemnity")                    # 12 months
    assert checks.expires_from(date(year, 1, 31), indemnity) == date(year + 1, 1, 31)
    dbs.validity_months = 1
    assert checks.expires_from(date(year, 1, 31), dbs) == date(year, 2, 29 if calendar.isleap(year) else 28)
    dbs.validity_months = 13
    assert checks.expires_from(date(year, 12, 15), dbs) == date(year + 2, 1, 15)
    assert checks.expires_from(date(year, 1, 31), CheckType.objects.get(code="references")) is None


def test_a_renewal_is_a_new_row_and_the_latest_wins(dbs, hr_admin):
    today = timezone.localdate()
    e = _receptionist()
    checks.record(hr_admin, e, dbs, today - timedelta(days=1200), Check.Outcome.CLEAR, reference="1", dbs_level="enhanced")
    checks.record(hr_admin, e, dbs, today - timedelta(days=5), Check.Outcome.CLEAR, reference="2", dbs_level="enhanced")
    assert Check.objects.filter(employee=e).count() == 2
    assert checks.state(e, today)[0].latest.reference == "2"


def test_dbs_needs_its_level_and_a_future_done_on_is_refused(dbs, hr_admin):
    today = timezone.localdate()
    e = _receptionist()
    with pytest.raises(ValidationError, match="disclosure level"):
        checks.record(hr_admin, e, dbs, today, Check.Outcome.CLEAR, reference="1")
    with pytest.raises(ValidationError, match="after today"):
        checks.record(hr_admin, e, dbs, today + timedelta(days=1), Check.Outcome.CLEAR, reference="1", dbs_level="basic")


def test_ask_then_the_person_uploads_then_hr_completes(hr_admin, employee_user):
    rtw = CheckType.objects.get(code="right_to_work")
    rtw.positions.add(titles.get_or_create("Receptionist"))
    e = _receptionist(user=employee_user)
    today = timezone.localdate()
    c = checks.ask(hr_admin, e, rtw)
    assert c.awaiting and checks.state(e, today)[0].status == "awaiting"
    checks.upload_evidence(employee_user, c, SimpleUploadedFile("passport.pdf", PDF, content_type="application/pdf"))
    c.refresh_from_db()
    assert c.evidence is not None and c.evidence.category == "identity"
    with pytest.raises(PermissionDenied):
        checks.upload_evidence(employee_user, Check.objects.create(employee=make_employee(first="Jo", last="B"),
                                                                   check_type=rtw, awaiting=True), SimpleUploadedFile("p.pdf", PDF))
    done = checks.complete(hr_admin, c, today, Check.Outcome.CLEAR)
    assert not done.awaiting and checks.state(e, today)[0].status == "current"


def test_a_type_no_longer_required_is_kept_but_not_chased(dbs, hr_admin):
    today = timezone.localdate()
    e = _receptionist()
    checks.record(hr_admin, e, dbs, today - timedelta(days=5), Check.Outcome.CLEAR, reference="1", dbs_level="basic")
    dbs.positions.clear()
    rows = checks.state(e, today)
    assert [r.status for r in rows] == ["not_required"]


def test_pages_by_role(dbs, hr_admin, employee_user, employee_client, admin_client, client):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    checks.record(hr_admin, e, dbs, today - timedelta(days=5), Check.Outcome.CLEAR, reference="REFXQ77", dbs_level="basic",
                  note="HR only note")
    body = employee_client.get("/people/me/").content.decode()
    assert "DBS" in body and "Current" in body and "HR only note" not in body and "REFXQ77" not in body
    mgr_user = type(employee_user).objects.create_user(email="mo@example.com", password="pw")
    mgr = make_employee(first="Mo", last="Khan", user=mgr_user)
    pos = e.employments.first().positions.first(); pos.line_manager = mgr; pos.save()
    client.force_login(mgr_user)
    body = client.get("/people/team/").content.decode()
    assert "1 current" in body and "REFXQ77" not in body and "DBS" not in body and "HR only note" not in body
    assert f"next expiry {checks.expires_from(today - timedelta(days=5), dbs):%d %b %Y}" in body


# ---- beyond the brief: the service's edges -----------------------------------

def test_recorded_hooks_run_for_a_clear_check_only(dbs, hr_admin, monkeypatch):
    seen = []
    monkeypatch.setattr(checks, "RECORDED_HOOKS", [seen.append])
    today = timezone.localdate()
    e = _receptionist()
    checks.record(hr_admin, e, dbs, today, Check.Outcome.NOT_CLEAR)
    assert seen == []
    c = checks.record(hr_admin, e, dbs, today, Check.Outcome.CLEAR_WITH_NOTES, reference="1", dbs_level="basic")
    assert seen == [c]
    rtw = CheckType.objects.get(code="right_to_work")
    asked = checks.ask(hr_admin, e, rtw)
    assert seen == [c]
    checks.complete(hr_admin, asked, today, Check.Outcome.CLEAR, upload=SimpleUploadedFile("p.pdf", PDF))
    assert seen == [c, asked]


def test_not_clear_counts_as_missing_and_a_recorded_check_outranks_an_ask(dbs, hr_admin):
    today = timezone.localdate()
    e = _receptionist()
    checks.record(hr_admin, e, dbs, today, Check.Outcome.NOT_CLEAR)
    assert checks.state(e, today)[0].status == "missing"
    checks.record(hr_admin, e, dbs, today, Check.Outcome.CLEAR, reference="1", dbs_level="basic")
    checks.ask(hr_admin, e, dbs)
    assert checks.state(e, today)[0].status == "current"


def test_ask_twice_and_complete_twice_are_refused(dbs, hr_admin):
    today = timezone.localdate()
    e = _receptionist()
    c = checks.ask(hr_admin, e, dbs)
    with pytest.raises(ValidationError, match="Already asked"):
        checks.ask(hr_admin, e, dbs)
    with pytest.raises(ValidationError, match="reference number"):
        checks.complete(hr_admin, c, today, Check.Outcome.CLEAR, dbs_level="basic")
    checks.complete(hr_admin, c, today, Check.Outcome.CLEAR, reference="1", dbs_level="basic")
    with pytest.raises(ValidationError, match="still waiting"):
        checks.complete(hr_admin, c, today, Check.Outcome.CLEAR, reference="1", dbs_level="basic")


def test_evidence_is_refused_for_a_type_that_keeps_no_file(dbs, hr_admin, employee_user):
    e = _receptionist(user=employee_user)
    c = checks.ask(hr_admin, e, dbs)
    with pytest.raises(ValidationError, match="takes no file"):
        checks.upload_evidence(employee_user, c, SimpleUploadedFile("dbs.pdf", PDF))
    from documents.models import File
    assert not File.objects.exists()


def test_the_person_cannot_upload_to_a_recorded_check(dbs, hr_admin, employee_user):
    rtw = CheckType.objects.get(code="right_to_work")
    e = _receptionist(user=employee_user)
    c = checks.record(hr_admin, e, rtw, timezone.localdate(), Check.Outcome.NOT_CLEAR)
    with pytest.raises(ValidationError, match="not waiting"):
        checks.upload_evidence(employee_user, c, SimpleUploadedFile("p.pdf", PDF))
    checks.upload_evidence(hr_admin, c, SimpleUploadedFile("p.pdf", PDF))       # HR, on one with no evidence yet
    c.refresh_from_db()
    assert c.evidence.employee == e


def test_summary_counts_and_next_expiry(dbs, hr_admin):
    today = timezone.localdate()
    e = _receptionist()
    indemnity = CheckType.objects.get(code="indemnity")
    indemnity.positions.add(titles.get_or_create("Receptionist"))
    assert checks.summary(e, today) == {"current": 0, "due_soon": 0, "lapsed": 0, "missing": 2, "awaiting": 0,
                                        "next_expiry": None}
    checks.record(hr_admin, e, dbs, today, Check.Outcome.CLEAR, reference="1", dbs_level="basic")
    checks.record(hr_admin, e, indemnity, today, Check.Outcome.CLEAR, expires_on=today + timedelta(days=20),
                  upload=SimpleUploadedFile("i.pdf", PDF))
    assert checks.summary(e, today) == {"current": 1, "due_soon": 1, "lapsed": 0, "missing": 0, "awaiting": 0,
                                        "next_expiry": today + timedelta(days=20)}


def test_nothing_is_required_without_a_current_employment(dbs):
    e = make_employee()
    make_position(make_employment(e, start=timezone.localdate() + timedelta(days=30)), title="Receptionist")
    assert checks.required_for(e, timezone.localdate()) == []
    assert checks.state(e, timezone.localdate()) == []


def test_can_view_checks(hr_admin, employee_user):
    from people.services import access
    e = make_employee(user=employee_user)
    other = make_employee(first="Jo", last="B")
    assert access.can_view_checks(hr_admin, e)
    assert access.can_view_checks(employee_user, e)
    assert not access.can_view_checks(employee_user, other)


# ---- the upload page ---------------------------------------------------------

def test_the_person_uploads_from_my_record(hr_admin, employee_user, employee_client):
    rtw = CheckType.objects.get(code="right_to_work")
    rtw.positions.add(titles.get_or_create("Receptionist"))
    e = _receptionist(user=employee_user)
    c = checks.ask(hr_admin, e, rtw)
    body = employee_client.get("/people/me/").content.decode()
    assert f'action="/checks/{c.pk}/upload/"' in body and "Awaiting" in body
    assert employee_client.get(f"/checks/{c.pk}/upload/").status_code == 405
    r = employee_client.post(f"/checks/{c.pk}/upload/", {"file": SimpleUploadedFile("p.pdf", PDF)})
    assert r.status_code == 302 and r["Location"] == "/people/me/"
    c.refresh_from_db()
    assert c.evidence is not None
    body = employee_client.get("/people/me/").content.decode()
    assert "Sent. HR will record it." in body and f'action="/checks/{c.pk}/upload/"' not in body


def test_a_refused_upload_is_a_message_and_someone_elses_is_403(hr_admin, employee_user, employee_client):
    rtw = CheckType.objects.get(code="right_to_work")
    e = _receptionist(user=employee_user)
    c = checks.ask(hr_admin, e, rtw)
    r = employee_client.post(f"/checks/{c.pk}/upload/", {"file": SimpleUploadedFile("p.pdf", b"not a pdf")},
                             follow=True)
    assert "This file is not a PDF." in r.content.decode()
    c.refresh_from_db()
    assert c.evidence is None
    theirs = checks.ask(hr_admin, make_employee(first="Jo", last="B"), rtw)
    assert employee_client.post(f"/checks/{theirs.pk}/upload/",
                                {"file": SimpleUploadedFile("p.pdf", PDF)}).status_code == 403


# ---- the admin ---------------------------------------------------------------

def test_admin_lists_and_shows_a_check_read_only_and_audits_the_view(dbs, hr_admin, admin_client):
    from people.models import AuditEntry
    e = _receptionist()
    c = checks.record(hr_admin, e, dbs, timezone.localdate(), Check.Outcome.CLEAR, reference="1",
                      dbs_level="basic")
    assert admin_client.get("/admin/checks/check/").status_code == 200
    assert admin_client.get("/admin/checks/checktype/").status_code == 200
    assert admin_client.get(f"/admin/checks/checktype/{dbs.pk}/change/").status_code == 200
    r = admin_client.get(f"/admin/checks/check/{c.pk}/change/")
    assert r.status_code == 200 and 'name="done_on"' not in r.content.decode()
    assert AuditEntry.objects.filter(model="checks.check", object_id=c.pk, kind="viewed").count() == 1
    assert admin_client.post(f"/admin/checks/check/{c.pk}/delete/").status_code == 403
    assert admin_client.post(f"/admin/checks/check/{c.pk}/change/", {"done_on": "2000-01-01"}).status_code == 403
    c.refresh_from_db()
    assert c.done_on == timezone.localdate()


def test_admin_add_page_records_through_the_service(dbs, hr_admin, admin_client):
    from people.models import AuditEntry
    e = _receptionist()
    today = timezone.localdate()
    data = {"employee": e.pk, "check_type": dbs.pk, "done_on": today.isoformat(), "outcome": "clear",
            "reference": "123", "note": "", "dbs_level": "enhanced"}
    assert admin_client.get("/admin/checks/check/add/").status_code == 200
    r = admin_client.post("/admin/checks/check/add/", {**data, "dbs_level": ""})
    assert r.status_code == 200 and "disclosure level" in r.content.decode()
    r = admin_client.post("/admin/checks/check/add/", {**data, "upload": SimpleUploadedFile("c.pdf", PDF)})
    assert r.status_code == 200 and "takes no file" in r.content.decode()
    assert not Check.objects.exists()
    r = admin_client.post("/admin/checks/check/add/", data)
    assert r.status_code == 302
    c = Check.objects.get()
    assert c.expires_on == checks.expires_from(today, dbs) and c.recorded_by == hr_admin
    assert AuditEntry.objects.filter(model="checks.check", object_id=c.pk, field="recorded").exists()


def test_admin_add_page_stores_evidence_for_a_file_type(hr_admin, admin_client):
    rtw = CheckType.objects.get(code="right_to_work")
    e = _receptionist()
    r = admin_client.post("/admin/checks/check/add/", {
        "employee": e.pk, "check_type": rtw.pk, "done_on": timezone.localdate().isoformat(), "outcome": "clear",
        "upload": SimpleUploadedFile("passport.pdf", PDF)})
    assert r.status_code == 302
    c = Check.objects.get()
    assert c.evidence.category == "identity" and c.evidence.employee == e
    assert f"/documents/file/{c.evidence.pk}/" in admin_client.get(f"/admin/checks/check/{c.pk}/change/") \
        .content.decode()


def test_admin_asks_then_records_the_result(hr_admin, admin_client):
    rtw = CheckType.objects.get(code="right_to_work")
    e = _receptionist()
    assert admin_client.get("/admin/checks/check/ask/").status_code == 200
    r = admin_client.post("/admin/checks/check/ask/", {"employee": e.pk, "check_type": rtw.pk})
    c = Check.objects.get()
    assert r.status_code == 302 and c.awaiting
    # asked already: the detail action is not offered, and refused if forced
    assert admin_client.post(f"/admin/checks/check/{c.pk}/ask-person/").status_code == 403
    assert admin_client.get(f"/admin/checks/check/{c.pk}/complete/").status_code == 200
    r = admin_client.post(f"/admin/checks/check/{c.pk}/complete/", {
        "done_on": timezone.localdate().isoformat(), "outcome": "clear",
        "upload": SimpleUploadedFile("passport.pdf", PDF)})
    assert r.status_code == 302
    c.refresh_from_db()
    assert not c.awaiting and c.outcome == "clear" and c.evidence is not None and c.recorded_by == hr_admin
    # completed: no longer completable; asking again (a renewal) is
    assert admin_client.get(f"/admin/checks/check/{c.pk}/complete/").status_code == 403
    assert admin_client.get(f"/admin/checks/check/{c.pk}/ask-person/").status_code == 200
    assert Check.objects.count() == 1                        # a GET writes nothing
    assert admin_client.post(f"/admin/checks/check/{c.pk}/ask-person/").status_code == 302
    assert Check.objects.filter(awaiting=True).count() == 1


def test_admin_pages_are_hr_only(dbs, hr_admin, employee_client):
    c = checks.ask(hr_admin, _receptionist(), dbs)
    for url in ("/admin/checks/check/", "/admin/checks/check/add/", "/admin/checks/check/ask/",
                f"/admin/checks/check/{c.pk}/complete/"):
        assert employee_client.get(url).status_code in (302, 403), url


def test_compliance_sidebar_lists_check_types_and_checks(admin_client):
    from django.test import RequestFactory

    from hr.admin_site import navigation
    request = RequestFactory().get("/admin/")
    request.user = type("U", (), {"is_active": True, "is_hr_admin": True, "is_superuser": False})()
    group = next(g for g in navigation(request) if g["title"] == "Compliance")
    assert [i["title"] for i in group["items"]][:5] == [
        "Check types", "Checks", "Register bodies", "Registration lookups", "Files"]


# ---- review fixes ------------------------------------------------------------

@pytest.mark.parametrize("code", ["occupational_health", "hep_b"])
def test_health_evidence_is_filed_as_occupational_health(code, hr_admin):
    t = CheckType.objects.get(code=code)
    c = checks.ask(hr_admin, _receptionist(), t)
    checks.upload_evidence(hr_admin, c, SimpleUploadedFile("oh.pdf", PDF))
    c.refresh_from_db()
    assert c.evidence.category == "occupational_health" and not c.evidence.hr_only


def test_other_file_evidence_is_a_certificate(hr_admin):
    c = checks.ask(hr_admin, _receptionist(), CheckType.objects.get(code="indemnity"))
    checks.upload_evidence(hr_admin, c, SimpleUploadedFile("i.pdf", PDF))
    c.refresh_from_db()
    assert c.evidence.category == "certificate"


def test_an_hr_admin_records_their_own_check_with_evidence(hr_admin, admin_client):
    rtw = CheckType.objects.get(code="right_to_work")
    e = _receptionist(user=hr_admin)
    r = admin_client.post("/admin/checks/check/add/", {
        "employee": e.pk, "check_type": rtw.pk, "done_on": timezone.localdate().isoformat(), "outcome": "clear",
        "upload": SimpleUploadedFile("passport.pdf", PDF)})
    assert r.status_code == 302
    c = Check.objects.get()
    assert c.evidence is not None and c.evidence.employee == e


def test_an_hr_admin_records_the_result_of_their_own_awaiting_check(hr_admin, admin_client):
    rtw = CheckType.objects.get(code="right_to_work")
    e = _receptionist(user=hr_admin)
    c = checks.ask(hr_admin, e, rtw)
    r = admin_client.post(f"/admin/checks/check/{c.pk}/complete/", {
        "done_on": timezone.localdate().isoformat(), "outcome": "clear",
        "upload": SimpleUploadedFile("passport.pdf", PDF)})
    assert r.status_code == 302
    c.refresh_from_db()
    assert not c.awaiting and c.evidence is not None


def test_a_refusal_at_save_is_a_message_not_a_500(hr_admin, admin_client, monkeypatch):
    from django.core.exceptions import ValidationError as VE
    rtw = CheckType.objects.get(code="right_to_work")
    e = _receptionist()

    def refuse(*a, **kw):
        raise VE("Refused at save.")
    monkeypatch.setattr(checks, "_attach", refuse)
    r = admin_client.post("/admin/checks/check/add/", {
        "employee": e.pk, "check_type": rtw.pk, "done_on": timezone.localdate().isoformat(), "outcome": "clear",
        "upload": SimpleUploadedFile("passport.pdf", PDF)}, follow=True)
    assert r.status_code == 200 and "Refused at save." in r.content.decode()
    assert not Check.objects.exists()                     # the record rolled back with it
    c = checks.ask(hr_admin, e, rtw)
    r = admin_client.post(f"/admin/checks/check/{c.pk}/complete/", {
        "done_on": timezone.localdate().isoformat(), "outcome": "clear",
        "upload": SimpleUploadedFile("passport.pdf", PDF)})
    assert r.status_code == 200 and "Refused at save." in r.content.decode()
    c.refresh_from_db()
    assert c.awaiting


def test_a_renewal_request_shows_the_upload_form_and_takes_the_file(hr_admin, employee_user, employee_client):
    indemnity = CheckType.objects.get(code="indemnity")
    indemnity.positions.add(titles.get_or_create("Receptionist"))
    e = _receptionist(user=employee_user)
    today = timezone.localdate()
    clear = checks.record(hr_admin, e, indemnity, today - timedelta(days=360), Check.Outcome.CLEAR,
                          upload=SimpleUploadedFile("old.pdf", PDF))
    first_evidence = clear.evidence_id
    asked = checks.ask(hr_admin, e, indemnity)
    row = checks.state(e, today)[0]
    assert row.status == "due_soon" and row.latest == clear and row.asked == asked
    body = employee_client.get("/people/me/").content.decode()
    assert "Due soon" in body and f'action="/checks/{asked.pk}/upload/"' in body
    employee_client.post(f"/checks/{asked.pk}/upload/", {"file": SimpleUploadedFile("i.pdf", PDF)})
    asked.refresh_from_db(); clear.refresh_from_db()
    assert asked.evidence is not None and clear.evidence_id == first_evidence
    assert checks.state(e, today)[0].asked == asked
    assert f'action="/checks/{asked.pk}/upload/"' not in employee_client.get("/people/me/").content.decode()


def test_the_person_cannot_upload_twice(hr_admin, employee_user):
    rtw = CheckType.objects.get(code="right_to_work")
    c = checks.ask(hr_admin, _receptionist(user=employee_user), rtw)
    checks.upload_evidence(employee_user, c, SimpleUploadedFile("p.pdf", PDF))
    with pytest.raises(ValidationError, match="Already uploaded"):
        checks.upload_evidence(employee_user, c, SimpleUploadedFile("p.pdf", PDF))


def test_summary_counts_awaiting_and_the_team_line_shows_it(dbs, hr_admin, employee_user, client):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    checks.ask(hr_admin, e, dbs)
    assert checks.summary(e, today)["awaiting"] == 1
    mgr_user = type(employee_user).objects.create_user(email="mo@example.com", password="pw")
    mgr = make_employee(first="Mo", last="Khan", user=mgr_user)
    pos = e.employments.first().positions.first(); pos.line_manager = mgr; pos.save()
    client.force_login(mgr_user)
    assert "1 awaiting" in client.get("/people/team/").content.decode()


def test_validity_months_cannot_be_zero():
    t = CheckType(name="Zero", code="zero", validity_months=0)
    with pytest.raises(ValidationError):
        t.full_clean()


# ---- final review I6/M3: evidence files ------------------------------------------------------

def test_a_clear_check_of_a_file_type_needs_its_file(hr_admin, employee_user):
    rtw = CheckType.objects.get(code="right_to_work")
    e = _receptionist(user=employee_user)
    today = timezone.localdate()
    with pytest.raises(ValidationError, match="Right to work needs its evidence file."):
        checks.record(hr_admin, e, rtw, today, Check.Outcome.CLEAR)
    with pytest.raises(ValidationError, match="Right to work needs its evidence file."):
        checks.validate(rtw, today, Check.Outcome.CLEAR, {}, today)
    assert not Check.objects.exists()
    checks.record(hr_admin, e, rtw, today, Check.Outcome.NOT_CLEAR)              # not clear: nothing to keep
    c = checks.record(hr_admin, e, rtw, today, Check.Outcome.CLEAR, upload=SimpleUploadedFile("p.pdf", PDF))
    assert c.evidence.category == "identity"
    asked = checks.ask(hr_admin, e, rtw)
    with pytest.raises(ValidationError, match="needs its evidence file"):
        checks.complete(hr_admin, asked, today, Check.Outcome.CLEAR)
    checks.upload_evidence(employee_user, asked, SimpleUploadedFile("p.pdf", PDF))
    asked.refresh_from_db()
    checks.complete(hr_admin, asked, today, Check.Outcome.CLEAR)                 # the person's upload counts
    with pytest.raises(ValidationError, match="takes no file"):
        checks.record(hr_admin, e, CheckType.objects.get(code="references"), today, Check.Outcome.CLEAR,
                      upload=SimpleUploadedFile("p.pdf", PDF))


def test_the_admin_forms_refuse_a_clear_file_check_without_its_file(hr_admin, admin_client):
    rtw = CheckType.objects.get(code="right_to_work")
    e = _receptionist()
    today = timezone.localdate().isoformat()
    r = admin_client.post("/admin/checks/check/add/", {"employee": e.pk, "check_type": rtw.pk, "done_on": today,
                                                       "outcome": "clear"})
    assert r.status_code == 200 and "Right to work needs its evidence file." in r.content.decode()
    assert not Check.objects.exists()
    c = checks.ask(hr_admin, e, rtw)
    r = admin_client.post(f"/admin/checks/check/{c.pk}/complete/", {"done_on": today, "outcome": "clear"})
    assert r.status_code == 200 and "Right to work needs its evidence file." in r.content.decode()
    c.refresh_from_db()
    assert c.awaiting


def test_hr_cannot_repoint_a_recorded_checks_evidence(hr_admin):
    rtw = CheckType.objects.get(code="right_to_work")
    e = _receptionist()
    c = checks.record(hr_admin, e, rtw, timezone.localdate(), Check.Outcome.CLEAR,
                      upload=SimpleUploadedFile("p.pdf", PDF))
    first = c.evidence_id
    with pytest.raises(ValidationError, match="This check already has its evidence."):
        checks.upload_evidence(hr_admin, c, SimpleUploadedFile("q.pdf", PDF))
    c.refresh_from_db()
    assert c.evidence_id == first
    asked = checks.ask(hr_admin, e, rtw)                       # an awaiting check: HR may upload, again too
    checks.upload_evidence(hr_admin, asked, SimpleUploadedFile("r.pdf", PDF))
    checks.upload_evidence(hr_admin, asked, SimpleUploadedFile("s.pdf", PDF))
