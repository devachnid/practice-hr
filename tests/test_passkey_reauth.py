"""A passkey is a way in that survives a password change, so adding one must
not be open to anyone who finds a signed-in browser (accounts/recent_auth.py).
And the owner hears about each one, and can take them all back with a
password reset."""

import json
import time

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.mail.backends.locmem import EmailBackend as Locmem
from django.test import Client, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts import recent_auth
from accounts.models import Passkey
from tests.soft_authenticator import SoftAuthenticator

pytestmark = pytest.mark.django_db
User = get_user_model()
REG_OPTIONS = "/accounts/passkeys/register/options/"
REGISTER = "/accounts/passkeys/register/"
LOGIN_OPTIONS = "/accounts/passkeys/login/options/"
LOGIN = "/accounts/passkeys/login/"
NEW_PW = "Brand-new-pass-4471"


def _post_json(client, url, payload=None, **extra):
    return client.post(url, data=json.dumps(payload or {}),
                       content_type="application/json", **extra)


def _stale(client):
    """The session signed in longer ago than the window."""
    session = client.session
    session["hr_auth_at"] = int(time.time()) - recent_auth.WINDOW - 1
    session.save()


def _enrol(client, auth, name="my phone", password=None):
    options = _post_json(client, REG_OPTIONS, {"password": password} if password else None)
    if options.status_code != 200:
        return options
    return _post_json(client, REGISTER, {"credential": auth.create(options.json()), "name": name})


# --- adding one -----------------------------------------------------------------

def test_a_fresh_sign_in_adds_a_passkey_without_the_password(employee_client, employee_user):
    assert _enrol(employee_client, SoftAuthenticator()).status_code == 200
    assert Passkey.objects.filter(user=employee_user).count() == 1


def test_a_borrowed_session_cannot_add_one(employee_client, employee_user):
    """A practice PC left signed in, found later by someone else."""
    _stale(employee_client)
    resp = _post_json(employee_client, REG_OPTIONS)
    assert resp.status_code == 403 and resp.json()["password"] is True
    assert not Passkey.objects.filter(user=employee_user).exists()


def test_the_register_step_checks_too(employee_client, employee_user):
    """Options fetched while the session was fresh do not carry a stale one
    through: the save is checked as well."""
    auth = SoftAuthenticator()
    options = _post_json(employee_client, REG_OPTIONS).json()
    _stale(employee_client)
    resp = _post_json(employee_client, REGISTER, {"credential": auth.create(options), "name": "x"})
    assert resp.status_code == 403
    assert not Passkey.objects.filter(user=employee_user).exists()


def test_typing_the_password_again_allows_it(employee_client, employee_user):
    _stale(employee_client)
    assert _enrol(employee_client, SoftAuthenticator(), password="pw").status_code == 200
    assert Passkey.objects.filter(user=employee_user).count() == 1


def test_a_wrong_password_is_refused(employee_client, employee_user):
    _stale(employee_client)
    resp = _post_json(employee_client, REG_OPTIONS, {"password": "not-it"})
    assert resp.status_code == 403
    assert resp.json()["error"] == "That password isn't right."
    # and the session is no fresher for it
    assert 'name="password"' in employee_client.get("/accounts/account/").content.decode()


@override_settings(AXES_ENABLED=True,
                   PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
def test_wrong_passwords_here_count_towards_the_login_lockout(employee_client, employee_user):
    """Otherwise a borrowed session would be an unlimited password-guessing
    oracle: it goes through authenticate(), as the login page does."""
    from axes.models import AccessAttempt
    _stale(employee_client)
    for g in range(5):
        _post_json(employee_client, REG_OPTIONS, {"password": f"guess-{g}"})
    assert AccessAttempt.objects.filter(username=employee_user.email).exists()
    resp = _post_json(employee_client, REG_OPTIONS, {"password": "pw"})
    assert resp.status_code == 429
    assert resp.json()["error"] == "Too many wrong attempts. Try again in an hour."


def test_changing_the_password_counts_as_proving_it(employee_client):
    _stale(employee_client)
    resp = employee_client.post("/accounts/password_change/", {
        "old_password": "pw", "new_password1": NEW_PW, "new_password2": NEW_PW})
    assert resp.status_code == 302
    assert _enrol(employee_client, SoftAuthenticator()).status_code == 200


# --- the pages ---------------------------------------------------------------------

def test_the_account_page_asks_for_the_password_only_when_it_will_be_needed(employee_client):
    fresh = employee_client.get("/accounts/account/").content.decode()
    assert 'name="password"' not in fresh
    _stale(employee_client)
    stale = employee_client.get("/accounts/account/").content.decode()
    assert 'name="password"' in stale and 'autocomplete="current-password"' in stale


def test_the_nudge_is_offered_only_just_after_signing_in(employee_client):
    assert 'id="passkey-nudge"' in employee_client.get("/accounts/account/").content.decode()
    _stale(employee_client)
    assert 'id="passkey-nudge"' not in employee_client.get("/accounts/account/").content.decode()


def test_signing_in_by_any_route_starts_the_window(employee_user):
    """The receiver is on user_logged_in, so the password form, a passkey
    and a password link all count."""
    c = Client()
    c.post("/accounts/login/", {"username": employee_user.email, "password": "pw"})
    assert isinstance(c.session.get("hr_auth_at"), int)


# --- telling the owner ---------------------------------------------------------------

def test_the_owner_is_emailed_when_a_passkey_is_added(employee_client, employee_user, configured):
    mail.outbox.clear()
    assert _enrol(employee_client, SoftAuthenticator(), name="Reception PC").status_code == 200
    (msg,) = mail.outbox
    assert msg.to == [employee_user.email]
    assert "passkey" in msg.subject.lower()
    assert '"Reception PC"' in msg.body
    assert "http://testserver/accounts/password_reset/" in msg.body
    assert "Also remove all my passkeys" in msg.body


def test_no_relay_means_no_email_and_no_error(employee_client):
    mail.outbox.clear()
    assert _enrol(employee_client, SoftAuthenticator()).status_code == 200
    assert mail.outbox == []


class _Broken(Locmem):
    def send_messages(self, messages):
        raise OSError("relay down")


def test_a_failed_notice_does_not_undo_the_passkey(employee_client, employee_user, configured, settings):
    settings.EMAIL_BACKEND = f"{__name__}._Broken"
    assert _enrol(employee_client, SoftAuthenticator()).status_code == 200
    assert Passkey.objects.filter(user=employee_user).count() == 1


# --- taking them back with a reset ---------------------------------------------------

def _reset_form(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    c = Client()
    resp = c.get(f"/accounts/reset/{uid}/{token}/")
    return c, resp["Location"]


def test_the_reset_form_offers_removal_only_to_an_account_with_passkeys(employee_client, employee_user):
    c, url = _reset_form(employee_user)
    assert "remove_passkeys" not in c.get(url).content.decode()
    _enrol(employee_client, SoftAuthenticator())
    c, url = _reset_form(employee_user)
    assert "Also remove all my passkeys" in c.get(url).content.decode()


def test_ticking_it_removes_every_passkey_and_they_stop_working(employee_client, employee_user):
    thief = SoftAuthenticator()
    _enrol(employee_client, thief, name="not mine")
    _enrol(employee_client, SoftAuthenticator(), name="mine")
    c, url = _reset_form(employee_user)
    resp = c.post(url, {"new_password1": NEW_PW, "new_password2": NEW_PW,
                        "remove_passkeys": "on"}, follow=True)
    assert "every passkey removed" in resp.content.decode()
    assert not Passkey.objects.filter(user=employee_user).exists()
    anon = Client()
    options = _post_json(anon, LOGIN_OPTIONS).json()
    assert _post_json(anon, LOGIN, {"credential": thief.get(options)}).status_code == 400


def test_leaving_it_keeps_them(employee_client, employee_user):
    _enrol(employee_client, SoftAuthenticator())
    c, url = _reset_form(employee_user)
    assert c.post(url, {"new_password1": NEW_PW, "new_password2": NEW_PW}).status_code == 302
    assert Passkey.objects.filter(user=employee_user).count() == 1
