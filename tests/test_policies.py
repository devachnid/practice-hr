import json
import logging
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.utils import timezone

from documents.models import File, Policy, PolicyVersion, Signature
from documents.services import files, policies
from people.models import AuditEntry
from people.services import titles
from tests.factories import make_employee, make_employment, make_position
from tests.soft_authenticator import SoftAuthenticator

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


def _policy(hr_admin, title="Information governance", positions=(), label="v1", days=14):
    p = Policy.objects.create(title=title)
    for name in positions:
        p.positions.add(titles.get_or_create(name))
    policies.issue(hr_admin, p, label, SimpleUploadedFile("ig.pdf", PDF, content_type="application/pdf"),
                   timezone.localdate(), days)
    return p


def _staff(user=None, title="Receptionist", start_offset=-100):
    e = make_employee(user=user)
    make_position(make_employment(e, start=timezone.localdate() + timedelta(days=start_offset)), title=title)
    return e


def test_a_policy_with_no_positions_applies_to_everyone_and_is_owed(hr_admin):
    p = _policy(hr_admin)
    e = _staff()
    today = timezone.localdate()
    assert policies.applies_to(e, today) == [p]
    owed = policies.owed(e, today)
    assert len(owed) == 1 and owed[0].state == "awaiting" and owed[0].due_on == today + timedelta(days=14)


def test_a_policy_by_title_applies_only_to_that_title(hr_admin):
    _policy(hr_admin, positions=["Practice Nurse"])
    assert policies.owed(_staff(title="Receptionist"), timezone.localdate()) == []
    assert len(policies.owed(_staff(title="Practice Nurse"), timezone.localdate())) == 1


def test_signing_records_the_exact_sentence_and_closes_the_debt(hr_admin, employee_user):
    p = _policy(hr_admin)
    e = _staff(user=employee_user)
    v = p.versions.get()
    s = policies.sign(employee_user, v, "password", "203.0.113.5")
    assert s.confirmation_text == "I confirm I have read and understood Information governance (v1)."
    assert s.method == "password" and policies.owed(e, timezone.localdate()) == []
    with pytest.raises(ValidationError, match="already signed"):
        policies.sign(employee_user, v, "password", "")
    s.confirmation_text = "x"
    with pytest.raises(ValidationError):
        s.save()


def test_only_the_person_signs_for_themselves(hr_admin, employee_user):
    p = _policy(hr_admin)
    _staff(user=employee_user)
    with pytest.raises(PermissionDenied):
        policies.sign(hr_admin, p.versions.get(), "password", "")


def test_a_new_version_is_owed_again_and_the_old_one_never_is(hr_admin, employee_user):
    p = _policy(hr_admin)
    e = _staff(user=employee_user)
    v1 = p.versions.get()
    policies.sign(employee_user, v1, "password", "")
    policies.issue(hr_admin, p, "v2", SimpleUploadedFile("ig2.pdf", PDF, content_type="application/pdf"),
                   timezone.localdate(), 14)
    owed = policies.owed(e, timezone.localdate())
    assert [o.version.label for o in owed] == ["v2"]
    unsigned = make_employee(first="Jo", last="Bloggs")
    make_position(make_employment(unsigned, start=timezone.localdate() - timedelta(days=5)), title="Receptionist")
    assert [o.version.label for o in policies.owed(unsigned, timezone.localdate())] == ["v2"]


def test_overdue_after_the_sign_by_period_and_a_starter_counts_from_their_start(hr_admin):
    today = timezone.localdate()
    p = _policy(hr_admin, days=7)
    v = p.versions.get(); v.issued_on = today - timedelta(days=10); v.save()
    assert policies.owed(_staff(), today)[0].state == "overdue"
    starter = _staff(start_offset=5)
    o = policies.owed(starter, today)[0]
    assert o.state == "awaiting" and o.due_on == today + timedelta(days=5 + 7)


def test_sign_page_needs_the_password_and_a_wrong_one_writes_nothing(hr_admin, employee_user, employee_client):
    p = _policy(hr_admin)
    _staff(user=employee_user)
    v = p.versions.get()
    body = employee_client.get(f"/documents/policies/{v.pk}/sign/").content.decode()
    assert "I confirm I have read and understood" in body and 'name="password"' in body
    r = employee_client.post(f"/documents/policies/{v.pk}/sign/", {"confirm": "on", "password": "wrong"})
    assert r.status_code == 200 and Signature.objects.count() == 0
    r = employee_client.post(f"/documents/policies/{v.pk}/sign/", {"confirm": "on", "password": "pw"})
    assert r.status_code == 302 and Signature.objects.get().method == "password"


def test_policies_page_lists_state(hr_admin, employee_user, employee_client):
    _policy(hr_admin)
    _staff(user=employee_user)
    body = employee_client.get("/documents/policies/").content.decode()
    assert "Information governance" in body and "Awaiting signature" in body and "Sign" in body


# ---- beyond the brief: re-authentication -----------------------------------

SIGN = "/documents/policies/{}/sign/"
OPTIONS = "/documents/policies/passkey-options/"


def _enrol(client):
    """A passkey for the client's user, through the account endpoints (a
    fresh session needs no password)."""
    auth = SoftAuthenticator()
    options = client.post("/accounts/passkeys/register/options/", data="{}", content_type="application/json").json()
    r = client.post("/accounts/passkeys/register/", data=json.dumps({"credential": auth.create(options), "name": "x"}),
                    content_type="application/json")
    assert r.status_code == 200
    return auth


def _assertion(client, auth):
    options = client.post(OPTIONS)
    assert options.status_code == 200
    return json.dumps(auth.get(options.json()))


def test_the_page_shows_the_exact_sentence_and_a_read_link(hr_admin, employee_user, employee_client):
    p = _policy(hr_admin)
    _staff(user=employee_user)
    v = p.versions.get()
    body = employee_client.get(SIGN.format(v.pk)).content.decode()
    assert "I confirm I have read and understood Information governance (v1)." in body
    assert f'href="/documents/file/{v.file_id}/"' in body
    assert "documents/sign.js" in body
    assert Signature.objects.count() == 0      # a GET writes nothing


def test_the_box_must_be_ticked_even_with_the_right_password(hr_admin, employee_user, employee_client):
    v = _policy(hr_admin).versions.get()
    _staff(user=employee_user)
    r = employee_client.post(SIGN.format(v.pk), {"password": "pw"})
    assert r.status_code == 200 and Signature.objects.count() == 0


def test_a_wrong_or_missing_password_says_so_and_is_not_echoed(hr_admin, employee_user, employee_client, caplog):
    v = _policy(hr_admin).versions.get()
    _staff(user=employee_user)
    caplog.set_level(logging.DEBUG)
    r = employee_client.post(SIGN.format(v.pk), {"confirm": "on", "password": "Secret-guess-9917"})
    body = r.content.decode()
    assert r.status_code == 200 and "That password is not right." in body
    assert "Secret-guess-9917" not in body and "Secret-guess-9917" not in caplog.text
    r = employee_client.post(SIGN.format(v.pk), {"confirm": "on"})
    assert r.status_code == 200 and "Enter your password" in r.content.decode()
    assert Signature.objects.count() == 0


@override_settings(AXES_ENABLED=True, PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
def test_wrong_passwords_here_count_towards_the_login_lockout(hr_admin, employee_user, employee_client):
    from axes.models import AccessAttempt
    v = _policy(hr_admin).versions.get()
    _staff(user=employee_user)
    for g in range(5):
        employee_client.post(SIGN.format(v.pk), {"confirm": "on", "password": f"guess-{g}"})
    assert AccessAttempt.objects.filter(username=employee_user.email).exists()
    r = employee_client.post(SIGN.format(v.pk), {"confirm": "on", "password": "pw"})
    assert r.status_code == 429 and Signature.objects.count() == 0


def test_signing_with_the_persons_own_passkey(hr_admin, employee_user, employee_client):
    v = _policy(hr_admin).versions.get()
    _staff(user=employee_user)
    auth = _enrol(employee_client)
    r = employee_client.post(SIGN.format(v.pk), {"confirm": "on", "credential": _assertion(employee_client, auth)})
    assert r.status_code == 302
    s = Signature.objects.get()
    assert s.method == "passkey" and s.employee.user == employee_user


def test_someone_elses_passkey_does_not_sign_and_is_left_untouched(hr_admin, employee_user, employee_client,
                                                                   caplog):
    """A borrowed session with the borrower's own passkey: refused before it
    is verified, so their key's counter and last use do not move."""
    from accounts.models import Passkey
    v = _policy(hr_admin).versions.get()
    _staff(user=employee_user)
    _enrol(employee_client)                       # the person has a passkey, so the button is offered
    other = get_user_model().objects.create_user(email="jo@example.com", password="pw2")
    oc = Client()
    oc.force_login(other)
    theirs = _enrol(oc)
    row = Passkey.objects.get(user=other)
    caplog.set_level(logging.INFO)
    credential = _assertion(employee_client, theirs)
    r = employee_client.post(SIGN.format(v.pk), {"confirm": "on", "credential": credential})
    assert r.status_code == 200 and Signature.objects.count() == 0
    assert "not yours" in r.content.decode()
    after = Passkey.objects.get(pk=row.pk)
    assert (after.sign_count, after.last_used_at) == (row.sign_count, row.last_used_at)
    refused = [rec for rec in caplog.records if rec.levelno == logging.WARNING and "another account" in rec.getMessage()]
    assert refused and theirs.id not in caplog.text
    # the challenge was spent all the same: the same assertion cannot be tried again
    r = employee_client.post(SIGN.format(v.pk), {"confirm": "on", "credential": credential})
    assert "no passkey request is in progress" in r.content.decode()


def test_the_sign_pages_passkey_options_list_only_the_persons_own_keys(hr_admin, employee_user, employee_client):
    v = _policy(hr_admin).versions.get()
    _staff(user=employee_user)
    assert employee_client.post(OPTIONS).status_code == 400        # no passkeys: nothing to offer
    assert 'id="sign-passkey"' not in employee_client.get(SIGN.format(v.pk)).content.decode()
    mine = [_enrol(employee_client), _enrol(employee_client)]
    other = get_user_model().objects.create_user(email="jo@example.com", password="pw2")
    oc = Client()
    oc.force_login(other)
    _enrol(oc)
    options = employee_client.post(OPTIONS).json()
    assert sorted(c["id"] for c in options["allowCredentials"]) == sorted(a.id for a in mine)
    assert 'id="sign-passkey"' in employee_client.get(SIGN.format(v.pk)).content.decode()


def test_a_bad_assertion_or_junk_credential_writes_nothing(hr_admin, employee_user, employee_client):
    v = _policy(hr_admin).versions.get()
    _staff(user=employee_user)
    auth = _enrol(employee_client)
    forger = SoftAuthenticator()
    forger.credential_id = auth.credential_id
    r = employee_client.post(SIGN.format(v.pk), {"confirm": "on", "credential": _assertion(employee_client, forger)})
    assert r.status_code == 200 and "could not be verified" in r.content.decode()
    r = employee_client.post(SIGN.format(v.pk), {"confirm": "on", "credential": "not json"})
    assert r.status_code == 200 and "Malformed request." in r.content.decode()
    r = employee_client.post(SIGN.format(v.pk), {"confirm": "on", "credential": json.dumps(auth.get(
        {"challenge": "AAAA", "rpId": "testserver"}))})
    assert r.status_code == 200          # no options fetched: no challenge in the session
    assert Signature.objects.count() == 0


def test_passkey_options_need_a_post_and_a_signed_in_person(client, employee_client):
    assert employee_client.get(OPTIONS).status_code == 405
    _enrol(employee_client)
    assert "challenge" in employee_client.post(OPTIONS).json()
    assert client.post(OPTIONS).status_code == 302


def test_a_version_that_is_not_theirs_to_sign_is_404(hr_admin, employee_user, employee_client):
    nurses = _policy(hr_admin, title="Cold chain", positions=["Practice Nurse"]).versions.get()
    p = _policy(hr_admin)
    old = p.versions.get()
    policies.issue(hr_admin, p, "v2", SimpleUploadedFile("ig2.pdf", PDF, content_type="application/pdf"),
                   timezone.localdate(), 14)
    _staff(user=employee_user)
    for v in (nurses, old):
        assert employee_client.get(SIGN.format(v.pk)).status_code == 404
        assert employee_client.post(SIGN.format(v.pk), {"confirm": "on", "password": "pw"}).status_code == 404
    with pytest.raises(PermissionDenied):
        policies.sign(employee_user, nurses, "password", "")
    assert Signature.objects.count() == 0


def test_signing_twice_through_the_page_keeps_one_signature(hr_admin, employee_user, employee_client):
    v = _policy(hr_admin).versions.get()
    _staff(user=employee_user)
    assert employee_client.post(SIGN.format(v.pk), {"confirm": "on", "password": "pw"}).status_code == 302
    r = employee_client.post(SIGN.format(v.pk), {"confirm": "on", "password": "pw"})
    assert r.status_code == 302 and Signature.objects.count() == 1
    assert "Signed on" in employee_client.get("/documents/policies/").content.decode()


def test_someone_with_no_employee_record_signs_nothing(hr_admin, admin_client):
    v = _policy(hr_admin).versions.get()
    assert admin_client.get(SIGN.format(v.pk)).status_code == 404
    assert "no employee record" in admin_client.get("/documents/policies/").content.decode()


def test_the_signature_records_method_ip_and_is_audited_and_hooked(hr_admin, employee_user, employee_client,
                                                                  monkeypatch):
    seen = []
    monkeypatch.setattr(policies, "SIGNED_HOOKS", [seen.append])
    v = _policy(hr_admin).versions.get()
    e = _staff(user=employee_user)
    employee_client.post(SIGN.format(v.pk), {"confirm": "on", "password": "pw"}, REMOTE_ADDR="198.51.100.7")
    s = Signature.objects.get()
    assert s.ip_address == "198.51.100.7" and seen == [e]
    assert AuditEntry.objects.filter(model="documents.signature", object_id=s.pk).exists()


def test_a_bad_method_is_refused(hr_admin, employee_user):
    v = _policy(hr_admin).versions.get()
    _staff(user=employee_user)
    with pytest.raises(ValueError):
        policies.sign(employee_user, v, "magic", "")


# ---- beyond the brief: issuing, reading -------------------------------------

def test_a_refused_version_leaves_no_bytes_and_no_row(hr_admin, tmp_path):
    p = _policy(hr_admin)
    before = sorted(tmp_path.rglob("*.pdf"))
    with pytest.raises(ValidationError):          # the label is taken
        policies.issue(hr_admin, p, "v1", SimpleUploadedFile("x.pdf", PDF, content_type="application/pdf"),
                       timezone.localdate(), 14)
    with pytest.raises(ValidationError):          # not a PDF
        policies.issue(hr_admin, p, "v2", SimpleUploadedFile("x.pdf", b"<html>", content_type="application/pdf"),
                       timezone.localdate(), 14)
    assert sorted(tmp_path.rglob("*.pdf")) == before
    assert PolicyVersion.objects.count() == 1 and File.objects.count() == 1


def test_the_version_file_has_no_person_and_any_employee_may_read_it(hr_admin, employee_user, employee_client, client):
    v = _policy(hr_admin).versions.get()
    assert v.file.employee_id is None and v.file.category == File.Category.POLICY
    _staff(user=employee_user)
    r = employee_client.get(f"/documents/file/{v.file_id}/")
    assert r.status_code == 200 and b"".join(r.streaming_content) == PDF
    nobody = get_user_model().objects.create_user(email="x@example.com", password="pw")
    client.force_login(nobody)                      # signed in, but not an employee
    assert client.get(f"/documents/file/{v.file_id}/").status_code == 403


def test_a_persons_file_filed_as_policy_stays_theirs(hr_admin, employee_user):
    """The policy rule is for policy versions (no person); a person's own
    file under the Policy category keeps the ordinary rule."""
    someone = make_employee(first="Jo", last="Bloggs")
    f = files.add(hr_admin, someone, File.Category.POLICY, "Their signed copy",
                  SimpleUploadedFile("c.pdf", PDF, content_type="application/pdf"), hr_only=True)
    _staff(user=employee_user)
    from people.services import access
    assert not access.can_view_file(employee_user, f)


def test_the_admin_issues_a_version_and_shows_signatures_read_only(hr_admin, admin_client, employee_user):
    p = Policy.objects.create(title="Chaperoning")
    assert admin_client.get(f"/admin/documents/policy/{p.pk}/issue/").status_code == 200
    r = admin_client.post(f"/admin/documents/policy/{p.pk}/issue/", {
        "label": "Spring edition", "issued_on": timezone.localdate().isoformat(), "sign_within_days": 10,
        "upload": SimpleUploadedFile("c.pdf", PDF, content_type="application/pdf")})
    assert r.status_code == 302
    v = p.versions.get()
    assert v.label == "Spring edition" and v.sign_within_days == 10 and v.issued_by == hr_admin
    r = admin_client.post(f"/admin/documents/policy/{p.pk}/issue/", {
        "label": "Spring edition", "issued_on": timezone.localdate().isoformat(), "sign_within_days": 10,
        "upload": SimpleUploadedFile("c.pdf", PDF, content_type="application/pdf")})
    assert r.status_code == 200 and p.versions.count() == 1
    body = admin_client.get(f"/admin/documents/policy/{p.pk}/change/").content.decode()
    assert "Spring edition" in body and f"/documents/file/{v.file_id}/" in body
    _staff(user=employee_user)
    s = policies.sign(employee_user, v, "password", "")
    assert admin_client.get("/admin/documents/signature/").status_code == 200
    assert admin_client.get(f"/admin/documents/signature/{s.pk}/change/").status_code == 200
    assert admin_client.post(f"/admin/documents/signature/{s.pk}/delete/").status_code == 403
    assert admin_client.get("/admin/documents/signature/add/").status_code == 403
    body = admin_client.get("/admin/").content.decode()
    assert 'href="/admin/documents/policy/"' in body and 'href="/admin/documents/signature/"' in body


def test_the_nav_has_policies_after_balances_and_in_more(employee_user, employee_client):
    _staff(user=employee_user)
    body = employee_client.get("/documents/policies/").content.decode()
    desktop, tabbar = body.split('<nav class="tabbar"')
    assert 'href="/documents/policies/" class="nav-link is-active"' in desktop
    assert desktop.index('href="/absence/balances/"') < desktop.index('href="/documents/policies/"')
    sheet = tabbar.split('<div class="tabbar-sheet">')[1]
    assert 'href="/documents/policies/" class="tabbar-link"' in sheet
    assert "/documents/policies/" not in tabbar.split('<div class="tabbar-sheet">')[0]


def test_a_version_cannot_be_dated_ahead_of_today_or_behind_the_current_one(hr_admin, tmp_path):
    """The newest by issue date is the one owed: a future-dated version would
    be owed before it takes effect, and a back-dated one would never be."""
    p = _policy(hr_admin)
    today = timezone.localdate()
    before = sorted(tmp_path.rglob("*.pdf"))
    for when, words in ((today + timedelta(days=1), "after today"), (today - timedelta(days=1), "before")):
        with pytest.raises(ValidationError, match=words):
            policies.issue(hr_admin, p, "v2", SimpleUploadedFile("x.pdf", PDF, content_type="application/pdf"),
                           when, 14)
    assert sorted(tmp_path.rglob("*.pdf")) == before and p.versions.count() == 1


def test_a_long_title_and_label_still_issue(hr_admin):
    p = Policy.objects.create(title="T" * 120)
    v = policies.issue(hr_admin, p, "L" * 40, SimpleUploadedFile("x.pdf", PDF, content_type="application/pdf"),
                       timezone.localdate(), 14)
    assert len(v.file.title) <= 120 and policies.confirmation(v).endswith("(" + "L" * 40 + ").")


# ---- every role on the pages --------------------------------------------------

def test_anonymous_is_sent_to_sign_in(hr_admin, client):
    v = _policy(hr_admin).versions.get()
    for url in ("/documents/policies/", SIGN.format(v.pk)):
        for r in (client.get(url), client.post(url, {"confirm": "on", "password": "pw"})):
            assert r.status_code == 302 and r["Location"].startswith("/accounts/login/"), url
    assert Signature.objects.count() == 0


def test_a_line_manager_sees_only_their_own_policies(hr_admin, employee_user):
    everyone = _policy(hr_admin).versions.get()
    reception = _policy(hr_admin, title="Front desk", positions=["Receptionist"]).versions.get()
    boss_user = get_user_model().objects.create_user(email="boss@example.com", password="pw")
    boss = _staff(user=boss_user, title="Practice Manager")
    report = make_employee(first="Ria", last="Shah", user=employee_user)
    make_position(make_employment(report, start=timezone.localdate() - timedelta(days=50)), manager=boss)
    policies.sign(employee_user, reception, "password", "")
    c = Client()
    c.force_login(boss_user)
    body = c.get("/documents/policies/").content.decode()
    assert "Information governance" in body and "Front desk" not in body and "Signed on" not in body
    assert c.get(SIGN.format(everyone.pk)).status_code == 200
    assert c.get(SIGN.format(reception.pk)).status_code == 404
    assert c.post(SIGN.format(reception.pk), {"confirm": "on", "password": "pw"}).status_code == 404
    assert Signature.objects.count() == 1


def test_a_superuser_with_no_employee_record_is_treated_as_the_hr_admin_is(hr_admin, superuser_client):
    v = _policy(hr_admin).versions.get()
    assert "no employee record" in superuser_client.get("/documents/policies/").content.decode()
    assert superuser_client.get(SIGN.format(v.pk)).status_code == 404
    assert superuser_client.post(SIGN.format(v.pk), {"confirm": "on", "password": "pw"}).status_code == 404
    assert Signature.objects.count() == 0



def test_the_manager_guides_own_section_names_what_the_pages_show(hr_admin, employee_user, employee_client):
    """Final review I7: every bold label in the guide's "Your own policies,
    checks and documents" section is text the pages produce."""
    import re
    from pathlib import Path

    from checks.models import CheckType
    from checks.services import checks
    from people.services import employments, positions
    from tests.factories import make_team
    guide = (Path(__file__).resolve().parent.parent / "docs" / "guides" / "manager.md").read_text()
    section = guide.split("## Your own policies, checks and documents", 1)[1].split("\n## ", 1)[0]
    labels = set(re.findall(r"\*\*([^*]+)\*\*", section))
    assert {"Policies", "Sign with my password", "Checks", "Upload"} <= labels
    today = timezone.localdate()
    e = make_employee(user=employee_user)
    emp = employments.start(hr_admin, e, today - timedelta(days=25))        # a starter: Your checklist
    positions.add(hr_admin, emp, titles.get_or_create("Receptionist"), make_team(), None, emp.start_date)
    late = Policy.objects.create(title="Chaperoning")
    policies.issue(hr_admin, late, "v1", SimpleUploadedFile("c.pdf", PDF, content_type="application/pdf"),
                   today - timedelta(days=30), 7)                           # overdue
    version = _policy(hr_admin).versions.get()                              # awaiting signature
    checks.ask(hr_admin, e, CheckType.objects.get(code="right_to_work"))
    files.add(hr_admin, e, File.Category.CONTRACT, "Contract", SimpleUploadedFile("c.pdf", PDF))
    _enrol(employee_client)                                                 # offers Sign with a passkey
    pages = "".join(employee_client.get(url).content.decode() for url in (
        "/documents/policies/", f"/documents/policies/{version.pk}/sign/", "/people/me/", "/onboarding/"))
    policies.sign(employee_user, version, Signature.Method.PASSWORD, "127.0.0.1")
    pages += employee_client.get("/documents/policies/").content.decode()
    for label in labels:
        assert label in pages, label
