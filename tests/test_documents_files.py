import io
import zipfile
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone

from documents.models import File
from documents.services import files
from people.models import AuditEntry
from tests.factories import make_employee, make_employment, make_position

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def _upload(name="contract.pdf", content=PDF, content_type="application/pdf"):
    return SimpleUploadedFile(name, content, content_type=content_type)


def test_add_stores_the_file_under_an_opaque_name_and_audits(hr_admin, media):
    e = make_employee()
    f = files.add(hr_admin, e, File.Category.CONTRACT, "Contract 2026", _upload())
    assert f.original_name == "contract.pdf" and f.content_type == "application/pdf"
    assert f.size == len(PDF) and len(f.sha256) == 64
    assert f.path.startswith("documents/") and f.path.endswith(".pdf") and "contract" not in f.path
    assert (media / f.path).read_bytes() == PDF
    assert AuditEntry.objects.filter(model="documents.file", object_id=f.pk, kind="change").exists()


def test_a_pdf_that_is_really_html_is_refused_and_nothing_written(hr_admin, media):
    e = make_employee()
    with pytest.raises(ValidationError, match="not a PDF"):
        files.add(hr_admin, e, File.Category.OTHER, "x", _upload(content=b"<html><body>hi</body></html>"))
    assert File.objects.count() == 0 and not any(media.rglob("*.pdf"))


def test_too_large_and_wrong_type_are_refused(hr_admin, settings):
    settings.DOCUMENT_MAX_BYTES = 100
    e = make_employee()
    with pytest.raises(ValidationError, match="10 MB|100 bytes"):
        files.add(hr_admin, e, File.Category.OTHER, "x", _upload(content=PDF + b"0" * 200))
    with pytest.raises(ValidationError, match="PDF, JPEG, PNG or DOCX"):
        files.add(hr_admin, e, File.Category.OTHER, "x", _upload(name="x.exe", content=b"MZ", content_type="x"))


def test_who_may_open(hr_admin, employee_user):
    e = make_employee(user=employee_user)
    other = make_employee(first="Jo", last="Bloggs")
    mgr = make_employee(first="Mo", last="Khan")
    make_position(make_employment(e), manager=mgr)
    f = files.add(hr_admin, e, File.Category.CONTRACT, "Contract", _upload())
    secret = files.add(hr_admin, e, File.Category.OCCUPATIONAL_HEALTH, "OH letter", _upload(), hr_only=True)
    assert files.open(employee_user, f).status_code == 200
    assert AuditEntry.objects.filter(model="documents.file", object_id=f.pk, kind="viewed").count() == 1
    with pytest.raises(PermissionDenied):
        files.open(employee_user, secret)
    from django.contrib.auth import get_user_model
    U = get_user_model()
    for who in (U.objects.create_user(email="jo@example.com", password="pw"),
                U.objects.create_user(email="mo@example.com", password="pw")):
        with pytest.raises(PermissionDenied):
            files.open(who, f)
    other.user = U.objects.get(email="jo@example.com"); other.save()
    mgr.user = U.objects.get(email="mo@example.com"); mgr.save()
    for who in (other.user, mgr.user):
        with pytest.raises(PermissionDenied):
            files.open(who, f)
    assert files.open(hr_admin, secret).status_code == 200


def test_download_view_streams_for_the_owner_and_404s_for_others(employee_client, admin_client, hr_admin, employee_user, client):
    e = make_employee(user=employee_user)
    f = files.add(hr_admin, e, File.Category.CONTRACT, "Contract", _upload())
    r = employee_client.get(f"/documents/file/{f.pk}/")
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    assert r["Content-Disposition"].startswith("attachment") and "contract.pdf" in r["Content-Disposition"]
    assert b"".join(r.streaming_content) == PDF
    assert client.get(f"/documents/file/{f.pk}/").status_code in (302, 403)
    assert admin_client.get(f"/documents/file/{f.pk}/").status_code == 200


def test_supersede_links_and_keeps_both(hr_admin):
    e = make_employee()
    old = files.add(hr_admin, e, File.Category.CONTRACT, "Contract", _upload())
    new = files.add(hr_admin, e, File.Category.CONTRACT, "Contract v2", _upload())
    files.supersede(hr_admin, old, new, "reissued with the new hours")
    old.refresh_from_db()
    assert old.superseded_by_id == new.pk and old.superseded_note == "reissued with the new hours"
    assert File.objects.count() == 2


def test_my_record_lists_own_files_but_not_hr_only_ones(employee_client, hr_admin, employee_user):
    e = make_employee(user=employee_user)
    files.add(hr_admin, e, File.Category.CONTRACT, "Contract 2026", _upload())
    files.add(hr_admin, e, File.Category.OCCUPATIONAL_HEALTH, "OH letter", _upload(), hr_only=True)
    body = employee_client.get("/people/me/").content.decode()
    assert "Contract 2026" in body and "OH letter" not in body


# ---- beyond the brief: the access matrix over HTTP, sniffing, cleanup, admin ----

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 32


def _docx_bytes(word=True):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        if word:
            z.writestr("word/document.xml", "<w:document/>")
        else:
            z.writestr("xl/workbook.xml", "<workbook/>")
    return buf.getvalue()


def _client_for(email):
    user = get_user_model().objects.create_user(email=email, password="pw")
    c = Client()
    c.force_login(user)
    return user, c


def test_download_refused_to_another_employee_and_to_the_manager(hr_admin, employee_user, employee_client, client):
    e = make_employee(user=employee_user)
    jo, jo_client = _client_for("jo@example.com")
    mo, mo_client = _client_for("mo@example.com")
    make_employee(first="Jo", last="Bloggs", user=jo)
    mgr = make_employee(first="Mo", last="Khan", user=mo)
    make_position(make_employment(e), manager=mgr)
    f = files.add(hr_admin, e, File.Category.CONTRACT, "Contract", _upload())
    secret = files.add(hr_admin, e, File.Category.OCCUPATIONAL_HEALTH, "OH", _upload(), hr_only=True)
    url = f"/documents/file/{f.pk}/"
    assert jo_client.get(url).status_code == 403
    assert mo_client.get(url).status_code == 403
    assert employee_client.get(f"/documents/file/{secret.pk}/").status_code == 403
    r = client.get(url)
    assert r.status_code == 302 and "/documents/" not in r["Location"].split("?")[0]
    assert not AuditEntry.objects.filter(model="documents.file", kind="viewed").exists()
    assert employee_client.get("/documents/file/999999/").status_code == 404


def test_download_for_a_starter_before_their_first_day_and_for_a_superuser(hr_admin, employee_user,
                                                                           employee_client, superuser_client):
    e = make_employee(user=employee_user)
    make_employment(e, start=timezone.localdate() + timedelta(days=14))
    f = files.add(hr_admin, e, File.Category.OFFER, "Offer", _upload())
    secret = files.add(hr_admin, e, File.Category.OCCUPATIONAL_HEALTH, "OH", _upload(), hr_only=True)
    assert employee_client.get(f"/documents/file/{f.pk}/").status_code == 200
    assert employee_client.get(f"/documents/file/{secret.pk}/").status_code == 403
    assert superuser_client.get(f"/documents/file/{secret.pk}/").status_code == 200
    assert AuditEntry.objects.filter(model="documents.file", kind="viewed").count() == 2


def test_a_file_with_no_person_is_hr_only_until_a_later_rule_says_otherwise(hr_admin, employee_user):
    make_employee(user=employee_user)
    f = files.add(hr_admin, None, File.Category.POLICY, "Policy", _upload())
    with pytest.raises(PermissionDenied):
        files.open(employee_user, f)
    assert files.open(hr_admin, f).status_code == 200


def test_download_view_only_answers_get(employee_client, hr_admin, employee_user):
    e = make_employee(user=employee_user)
    f = files.add(hr_admin, e, File.Category.CONTRACT, "Contract", _upload())
    assert employee_client.post(f"/documents/file/{f.pk}/").status_code == 405


def test_media_is_never_served(employee_client, admin_client, hr_admin, employee_user):
    e = make_employee(user=employee_user)
    f = files.add(hr_admin, e, File.Category.CONTRACT, "Contract", _upload())
    for c in (employee_client, admin_client):
        assert c.get(f"/media/{f.path}").status_code == 404
        assert c.get(f"/{f.path}").status_code == 404


def test_jpeg_png_and_docx_are_accepted_with_their_sniffed_type(hr_admin):
    e = make_employee()
    j = files.add(hr_admin, e, File.Category.IDENTITY, "Passport", _upload("passport.JPEG", JPEG, "text/plain"))
    p = files.add(hr_admin, e, File.Category.IDENTITY, "Scan", _upload("scan.png", PNG, "image/png"))
    d = files.add(hr_admin, e, File.Category.CORRESPONDENCE, "Letter", _upload("letter.docx", _docx_bytes(), "x"))
    assert (j.content_type, j.path[-4:]) == ("image/jpeg", ".jpg")
    assert (p.content_type, p.path[-4:]) == ("image/png", ".png")
    assert d.content_type.endswith("wordprocessingml.document") and d.path.endswith(".docx")


@pytest.mark.parametrize("name,content,claimed", [
    ("photo.jpg", PNG, "JPEG"),
    ("scan.png", JPEG, "PNG"),
    ("letter.docx", _docx_bytes(word=False), "DOCX"),
    ("letter.docx", b"PK\x03\x04 not really a zip", "DOCX"),
    ("letter.docx", PDF, "DOCX"),
    ("contract.pdf", b"", "PDF"),
])
def test_bytes_that_disagree_with_the_extension_are_refused(hr_admin, media, name, content, claimed):
    with pytest.raises(ValidationError, match=f"not a {claimed}"):
        files.add(hr_admin, make_employee(), File.Category.OTHER, "x", _upload(name, content, "x"))
    assert File.objects.count() == 0 and not any(p.is_file() for p in media.rglob("*"))


def test_a_name_with_no_extension_is_refused(hr_admin):
    with pytest.raises(ValidationError, match="PDF, JPEG, PNG or DOCX"):
        files.sniff(_upload(name="contract", content=PDF))


def test_a_row_that_fails_validation_leaves_nothing_on_disk(hr_admin, media):
    with pytest.raises(ValidationError):
        files.add(hr_admin, make_employee(), File.Category.OTHER, "x" * 500, _upload())
    with pytest.raises(ValidationError):
        files.add(hr_admin, make_employee(), "not-a-category", "x", _upload())
    assert File.objects.count() == 0 and not any(p.is_file() for p in media.rglob("*"))


def test_the_stored_path_ignores_the_upload_name(hr_admin):
    f = files.add(hr_admin, make_employee(), File.Category.OTHER, "x", _upload(name="../../etc/passwd.pdf"))
    assert ".." not in f.path and "passwd" not in f.path and f.path.startswith("documents/")


def test_download_names_the_original_file_even_when_awkward(employee_client, hr_admin, employee_user):
    e = make_employee(user=employee_user)
    f = files.add(hr_admin, e, File.Category.CONTRACT, "Contract", _upload(name='my "contract" é.pdf'))
    r = employee_client.get(f"/documents/file/{f.pk}/")
    assert r.status_code == 200 and r["Content-Disposition"].startswith("attachment")
    assert "\n" not in r["Content-Disposition"]
    assert "no-store" in r["Cache-Control"]


def test_superseding_twice_is_refused_and_audited_once(hr_admin):
    e = make_employee()
    old = files.add(hr_admin, e, File.Category.CONTRACT, "Contract", _upload())
    new = files.add(hr_admin, e, File.Category.CONTRACT, "Contract v2", _upload())
    files.supersede(hr_admin, old, new, "reissued")
    with pytest.raises(ValidationError):
        files.supersede(hr_admin, old, new, "again")
    assert AuditEntry.objects.filter(model="documents.file", object_id=old.pk, field="superseded_by").count() == 1


def test_supersede_updates_the_callers_instance_and_stays_within_one_person(hr_admin):
    e = make_employee()
    old = files.add(hr_admin, e, File.Category.CONTRACT, "Contract", _upload())
    new = files.add(hr_admin, e, File.Category.CONTRACT, "Contract v2", _upload())
    theirs = files.add(hr_admin, make_employee(first="Jo", last="Bloggs"), File.Category.CONTRACT, "C", _upload())
    with pytest.raises(ValidationError):
        files.supersede(hr_admin, old, theirs, "wrong person")
    with pytest.raises(ValidationError):
        files.supersede(hr_admin, old, old, "itself")
    assert files.supersede(hr_admin, old, new, "reissued") is old
    assert old.superseded_by == new and old.superseded_note == "reissued"


def test_my_record_hides_superseded_files_and_links_to_the_download(employee_client, hr_admin, employee_user):
    e = make_employee(user=employee_user)
    old = files.add(hr_admin, e, File.Category.CONTRACT, "Old contract", _upload())
    new = files.add(hr_admin, e, File.Category.CONTRACT, "New contract", _upload())
    files.supersede(hr_admin, old, new, "reissued")
    body = employee_client.get("/people/me/").content.decode()
    assert "New contract" in body and "Old contract" not in body
    assert f"/documents/file/{new.pk}/" in body
    assert not AuditEntry.objects.filter(kind="viewed", model="documents.file").exists()


def test_my_record_shows_nobody_elses_files(employee_client, hr_admin, employee_user):
    make_employee(user=employee_user)
    files.add(hr_admin, make_employee(first="Jo", last="Bloggs"), File.Category.CONTRACT, "Jo's contract", _upload())
    body = employee_client.get("/people/me/").content.decode()
    assert "Jo&#x27;s contract" not in body and "Jo's contract" not in body


def test_my_record_without_an_employee_still_renders(employee_client):
    assert employee_client.get("/people/me/").status_code == 200


# ---- admin ----

def test_admin_lists_files_and_offers_the_download(admin_client, hr_admin):
    f = files.add(hr_admin, make_employee(), File.Category.CONTRACT, "Contract", _upload())
    assert b"Contract" in admin_client.get("/admin/documents/file/").content
    page = admin_client.get(f"/admin/documents/file/{f.pk}/change/")
    assert page.status_code == 200 and f"/documents/file/{f.pk}/".encode() in page.content
    assert f.path.encode() not in page.content
    assert b"/admin/documents/file/" in admin_client.get("/admin/").content


def test_admin_search_finds_a_file_by_person_and_title(admin_client, hr_admin):
    files.add(hr_admin, make_employee(first="Priya", last="Shah"), File.Category.CONTRACT, "Contract", _upload())
    files.add(hr_admin, make_employee(first="Jo", last="Bloggs"), File.Category.OTHER, "Note", _upload())
    body = admin_client.get("/admin/documents/file/?q=Shah").content.decode()
    assert "Contract" in body and "Note" not in body
    assert "Note" in admin_client.get("/admin/documents/file/?q=note").content.decode()


def test_admin_upload_goes_through_the_service(admin_client, hr_admin):
    e = make_employee()
    r = admin_client.post("/admin/documents/file/add/", {
        "employee": e.pk, "category": File.Category.CONTRACT, "title": "Contract",
        "upload": _upload(), "hr_only": "on"})
    assert r.status_code == 302, r.content.decode()[:2000]
    f = File.objects.get()
    assert f.employee == e and f.hr_only and f.uploaded_by == hr_admin and f.sha256
    assert AuditEntry.objects.filter(model="documents.file", object_id=f.pk, kind="change").exists()


def test_admin_upload_of_a_mismatched_file_shows_the_error(admin_client, media):
    e = make_employee()
    r = admin_client.post("/admin/documents/file/add/", {
        "employee": e.pk, "category": File.Category.CONTRACT, "title": "Contract",
        "upload": _upload(content=b"<html></html>")})
    assert r.status_code == 200 and b"not a PDF" in r.content
    assert File.objects.count() == 0 and not any(p.is_file() for p in media.rglob("*"))


def test_admin_cannot_change_or_delete_a_file(admin_client, hr_admin):
    f = files.add(hr_admin, make_employee(), File.Category.CONTRACT, "Contract", _upload())
    assert admin_client.post(f"/admin/documents/file/{f.pk}/change/", {"title": "Changed"}).status_code == 403
    assert admin_client.post(f"/admin/documents/file/{f.pk}/delete/", {"post": "yes"}).status_code == 403
    f.refresh_from_db()
    assert f.title == "Contract" and File.objects.count() == 1


def test_admin_is_closed_to_employees(employee_client, hr_admin):
    f = files.add(hr_admin, make_employee(), File.Category.CONTRACT, "Contract", _upload())
    for url in ("/admin/documents/file/", f"/admin/documents/file/{f.pk}/change/", "/admin/documents/file/add/"):
        assert employee_client.get(url).status_code in (302, 403)
