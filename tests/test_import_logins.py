"""import_logins: the rota's logins, moved here once so everyone signs in
through this system. The file is what the rota's export_logins writes."""
import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.management import CommandError, call_command
from oauth2_provider.models import Application

from accounts.models import AppRole
from people.models import AuditEntry
from tests.factories import make_employee

User = get_user_model()

PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="module")
def hashed():
    return make_password(PASSWORD)


@pytest.fixture
def rota(db):
    return Application.objects.create(
        name="rota", redirect_uris="https://rota.example/cb/",
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE)


def _login(email, password="!unusable", is_active=True, is_rota_admin=False, is_superuser=False):
    return {"email": email, "password": password, "is_active": is_active,
            "is_rota_admin": is_rota_admin, "is_superuser": is_superuser}


def _file(tmp_path, *logins, **top):
    path = tmp_path / "logins.json"
    path.write_text(json.dumps({"exported_at": "2026-10-04T09:00:00+00:00", "logins": list(logins),
                                **top}))
    return path


def _run(capsys, path, **options):
    call_command("import_logins", file=str(path), **options)
    return capsys.readouterr().out


def _counts(out):
    return dict(line.split(": ") for line in out.splitlines()
                if line.split(":")[0] in {"created", "passwords_set", "password_kept", "linked", "admins"})


def test_creates_and_links(capsys, tmp_path, rota, hashed):
    e = make_employee(email="jo.bloggs@example.org")
    out = _run(capsys, _file(tmp_path, _login("Jo.Bloggs@Example.org", hashed, is_active=False)))
    user = User.objects.get(email__iexact="jo.bloggs@example.org")
    assert not user.is_active
    e.refresh_from_db()
    assert e.user == user
    assert _counts(out) == {"created": "1", "passwords_set": "1", "password_kept": "0",
                            "linked": "1", "admins": "0"}
    # the link goes through the employee service, so it is in the audit log
    assert AuditEntry.objects.filter(object_id=e.pk, field="user", actor=None).exists()


def test_sets_a_password_only_where_none_is_set_and_it_then_checks(capsys, tmp_path, rota, hashed):
    invited = User.objects.create_user(email="new@example.com")  # invited, never set one
    assert not invited.has_usable_password()
    _run(capsys, _file(tmp_path, _login("new@example.com", hashed)))
    invited.refresh_from_db()
    assert invited.password == hashed          # stored as it is, never re-hashed
    assert invited.check_password(PASSWORD)
    assert check_password(PASSWORD, invited.password)


def test_keeps_a_password_chosen_here(capsys, tmp_path, rota, hashed, employee_user):
    before = employee_user.password
    out = _run(capsys, _file(tmp_path, _login("SAM@example.com", hashed)))
    employee_user.refresh_from_db()
    assert employee_user.password == before and employee_user.check_password("pw")
    assert _counts(out)["password_kept"] == "1" and _counts(out)["passwords_set"] == "0"
    assert User.objects.filter(email__iexact="sam@example.com").count() == 1


def test_an_unusable_imported_password_leaves_none(capsys, tmp_path, rota):
    out = _run(capsys, _file(tmp_path, _login("new@example.com", "!abcdefghijklmnop")))
    assert not User.objects.get(email="new@example.com").has_usable_password()
    assert _counts(out)["passwords_set"] == "0"


def test_sets_and_clears_the_admin_role(capsys, tmp_path, rota, employee_user):
    out = _run(capsys, _file(tmp_path, _login("sam@example.com", is_rota_admin=True),
                             _login("other@example.com")))
    assert AppRole.objects.get(user=employee_user, application=rota).is_admin
    assert not AppRole.objects.get(user__email="other@example.com", application=rota).is_admin
    assert _counts(out)["admins"] == "1"
    out = _run(capsys, _file(tmp_path, _login("sam@example.com", is_rota_admin=False)))
    assert not AppRole.objects.get(user=employee_user, application=rota).is_admin
    assert AppRole.objects.filter(user=employee_user).count() == 1
    assert _counts(out)["admins"] == "0"


def test_the_role_is_for_the_app_named(capsys, tmp_path, rota):
    other = Application.objects.create(
        name="other", redirect_uris="https://other.example/cb/",
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE)
    _run(capsys, _file(tmp_path, _login("new@example.com", is_rota_admin=True)), app="other")
    assert AppRole.objects.get().application == other


def test_superuser_in_the_file_is_ignored(capsys, tmp_path, rota):
    _run(capsys, _file(tmp_path, _login("boss@example.com", is_superuser=True)))
    user = User.objects.get(email="boss@example.com")
    assert not user.is_superuser and not user.is_hr_admin and not user.is_staff


def test_unmatched_and_already_linked_employees_are_reported_not_changed(capsys, tmp_path, rota,
                                                                         employee_user):
    taken = make_employee(email="taken@example.org", user=employee_user)
    out = _run(capsys, _file(tmp_path, _login("taken@example.org"), _login("nobody@example.org")))
    taken.refresh_from_db()
    assert taken.user == employee_user
    assert _counts(out)["linked"] == "0"
    assert "No matching employee:\n  nobody@example.org" in out
    assert "Employee already linked to another login:\n  taken@example.org" in out


def test_a_login_already_linked_is_left_as_it_is(capsys, tmp_path, rota, employee_user):
    make_employee(email="sam@example.com", user=employee_user)
    out = _run(capsys, _file(tmp_path, _login("sam@example.com")))
    assert _counts(out)["linked"] == "0"
    assert "No matching employee" not in out and "already linked" not in out


def test_dry_run_writes_nothing(capsys, tmp_path, rota, hashed):
    invited = User.objects.create_user(email="new@example.com")
    e = make_employee(email="jo@example.org")
    out = _run(capsys, _file(tmp_path, _login("new@example.com", hashed, is_rota_admin=True),
                             _login("jo@example.org", hashed)), dry_run=True)
    assert _counts(out) == {"created": "1", "passwords_set": "2", "password_kept": "0",
                            "linked": "1", "admins": "1"}
    assert "Dry run: nothing was written." in out
    invited.refresh_from_db()
    e.refresh_from_db()
    assert not invited.has_usable_password() and e.user is None
    assert not User.objects.filter(email="jo@example.org").exists()
    assert not AppRole.objects.exists() and not AuditEntry.objects.exists()


def test_an_unknown_app_is_refused(capsys, tmp_path, employee_user):
    path = _file(tmp_path, _login("new@example.com"))
    with pytest.raises(CommandError, match="No registered client is named 'rota'"):
        _run(capsys, path)
    Application.objects.create(  # someone's own client is not a registered one
        name="rota", user=employee_user, redirect_uris="https://rota.example/cb/",
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE)
    with pytest.raises(CommandError, match="No registered client is named 'rota'"):
        _run(capsys, path)
    assert not User.objects.filter(email="new@example.com").exists()


@pytest.mark.parametrize("content", [
    "not json",
    "[]",
    json.dumps({"logins": []}),
    json.dumps({"exported_at": "2026-10-04T09:00:00+00:00"}),
    json.dumps({"exported_at": "yesterday", "logins": []}),
    json.dumps({"exported_at": "2026-10-04T09:00:00+00:00", "logins": {}}),
    json.dumps({"exported_at": "2026-10-04T09:00:00+00:00", "logins": ["a@example.com"]}),
    json.dumps({"exported_at": "2026-10-04T09:00:00+00:00", "logins": [
        {"email": "a@example.com", "password": "!x", "is_active": True, "is_rota_admin": False}]}),
    json.dumps({"exported_at": "2026-10-04T09:00:00+00:00", "logins": [
        {**_login("a@example.com"), "is_rota_admin": "yes"}]}),
    json.dumps({"exported_at": "2026-10-04T09:00:00+00:00", "logins": [
        {**_login("a@example.com"), "extra": 1}]}),
    json.dumps({"exported_at": "2026-10-04T09:00:00+00:00", "logins": [_login("not an email")]}),
    json.dumps({"exported_at": "2026-10-04T09:00:00+00:00", "logins": [_login(7)]}),
    json.dumps({"exported_at": "2026-10-04T09:00:00+00:00", "logins": [_login("a@example.com", None)]}),
], ids=["not-json", "a-list", "no-exported-at", "no-logins", "exported-at-not-iso", "logins-not-a-list",
        "login-not-an-object", "a-key-missing", "a-flag-not-a-bool", "an-unknown-key", "a-bad-email",
        "an-email-not-text", "a-password-not-text"])
def test_a_file_not_of_the_documented_shape_is_refused(capsys, tmp_path, rota, content):
    path = tmp_path / "logins.json"
    path.write_text(content)
    with pytest.raises(CommandError, match="logins.json"):
        _run(capsys, path)
    assert not User.objects.exists()


def test_a_password_that_is_not_a_hash_is_refused_and_not_repeated(capsys, tmp_path, rota, hashed):
    """A plaintext password in the file must never be stored as if it were
    a hash, nor echoed back. Nothing is written for the good row either."""
    path = _file(tmp_path, _login("good@example.com", hashed), _login("bad@example.com", "hunter2"))
    with pytest.raises(CommandError) as raised:
        _run(capsys, path)
    assert "hunter2" not in str(raised.value) and "not a password hash" in str(raised.value)
    assert not User.objects.exists()


def test_a_missing_file_is_refused(capsys, tmp_path, rota):
    with pytest.raises(CommandError, match="missing.json"):
        _run(capsys, tmp_path / "missing.json")


def test_nothing_printed_contains_a_hash(capsys, tmp_path, rota, hashed, employee_user):
    make_employee(email="taken@example.org", user=employee_user)
    User.objects.create_user(email="invited@example.com")
    call_command("import_logins", file=str(_file(
        tmp_path, _login("new@example.com", hashed, is_rota_admin=True),
        _login("invited@example.com", hashed), _login("sam@example.com", hashed),
        _login("taken@example.org", hashed))))
    call_command("import_logins", file=str(_file(tmp_path, _login("x@example.com", hashed))),
                 dry_run=True)
    printed = capsys.readouterr()
    for stream in (printed.out, printed.err):
        assert hashed not in stream
        assert hashed.split("$")[-1] not in stream and hashed.split("$")[-2] not in stream
        assert "pbkdf2" not in stream and PASSWORD not in stream
    assert "created: 2" in printed.out
