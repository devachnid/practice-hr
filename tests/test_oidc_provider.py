from django.core.management import call_command
from django.test import Client
from oauth2_provider.models import Application

from accounts.models import AppRole
from accounts.oidc import Validator
from tests.factories import make_employee


def test_discovery_document(client):
    r = client.get("/o/.well-known/openid-configuration/")
    assert r.status_code == 200
    doc = r.json()
    assert "authorization_endpoint" in doc and "jwks_uri" in doc


def test_register_client_prints_credentials_once(db, capsys):
    call_command("register_oidc_client", name="rota", redirect_uri="https://rota.example/oidc/callback/")
    out = capsys.readouterr().out
    app = Application.objects.get(name="rota")
    assert app.client_id in out and "client_secret=" in out
    assert app.skip_authorization and app.algorithm == "RS256"
    assert app.client_type == Application.CLIENT_CONFIDENTIAL
    assert app.authorization_grant_type == Application.GRANT_AUTHORIZATION_CODE


def test_reregister_keeps_secret_unless_rotate(db, capsys):
    call_command("register_oidc_client", name="rota", redirect_uri="https://a.example/cb/")
    first = Application.objects.get(name="rota").client_secret
    call_command("register_oidc_client", name="rota", redirect_uri="https://b.example/cb/")
    app = Application.objects.get(name="rota")
    assert app.client_secret == first and app.redirect_uris == "https://b.example/cb/"
    assert "Secret unchanged" in capsys.readouterr().out
    call_command("register_oidc_client", name="rota", redirect_uri="https://b.example/cb/", rotate=True)
    assert Application.objects.get(name="rota").client_secret != first
    assert "Secret rotated" in capsys.readouterr().out


def _app(name="rota"):
    return Application.objects.create(
        name=name, redirect_uris=f"https://{name}.example/cb/",
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE)


def _claims(user, client):
    """The oauthlib request as the provider hands it over: the signed-in
    login, and the client (the Application) the token is for."""
    return Validator().get_additional_claims(type("R", (), {"user": user, "client": client})())


def test_claims_carry_email_and_employee_id(employee_user):
    e = make_employee(user=employee_user)
    claims = _claims(employee_user, _app())
    assert claims == {"email": "sam@example.com", "employee_id": e.pk, "admin": False}


def test_claims_without_employee(employee_user):
    assert _claims(employee_user, _app()) == {
        "email": "sam@example.com", "employee_id": None, "admin": False}


def test_the_admin_claim_is_the_login_s_role_in_the_requesting_app(employee_user):
    rota, other = _app("rota"), _app("other")
    AppRole.objects.create(user=employee_user, application=rota, is_admin=True)
    AppRole.objects.create(user=employee_user, application=other, is_admin=False)
    assert _claims(employee_user, rota)["admin"] is True
    assert _claims(employee_user, other)["admin"] is False
    AppRole.objects.filter(application=rota).update(is_admin=False)
    assert _claims(employee_user, rota)["admin"] is False


def test_no_role_is_no_admin(employee_user, hr_admin):
    """An HR admin is not thereby an admin of the rota: the role is per app."""
    rota = _app()
    AppRole.objects.create(user=employee_user, application=rota, is_admin=True)
    assert _claims(hr_admin, rota)["admin"] is False


# --- only the provider's endpoints are mounted (review C1) -------------------------

import base64  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
from urllib.parse import parse_qs, urlsplit  # noqa: E402

import pytest  # noqa: E402
from django.conf import settings  # noqa: E402
from django.core.management import CommandError  # noqa: E402

REDIRECT = "https://rota.example/oidc/callback/"


def _register(capsys, **extra):
    call_command("register_oidc_client", name="rota", redirect_uri=REDIRECT, **extra)
    out = capsys.readouterr().out
    return (re.search(r"client_id=(\S+)", out).group(1),
            (re.search(r"client_secret=(\S+)", out) or [None, None])[1])


@pytest.mark.parametrize("url", ["/o/applications/", "/o/applications/register/",
                                 "/o/authorized_tokens/", "/o/introspect/",
                                 "/o/device-authorization/", "/o/register/"])
def test_client_management_is_not_mounted(employee_client, url):
    """A signed-in employee could register a client of their own at
    /o/applications/register/ when the whole of oauth2_provider.urls was
    mounted."""
    assert employee_client.get(url).status_code == 404
    assert employee_client.post(url, {"name": "mine"}).status_code == 404
    assert not Application.objects.exists()


def test_the_password_grant_is_refused(db, capsys, employee_user):
    client_id, secret = _register(capsys)
    Application.objects.filter(client_id=client_id).update(
        authorization_grant_type=Application.GRANT_PASSWORD)
    r = Client().post("/o/token/", {"grant_type": "password", "username": employee_user.email,
                                    "password": "pw", "client_id": client_id,
                                    "client_secret": secret, "scope": "openid"})
    assert r.status_code in (400, 401)
    assert "access_token" not in r.content.decode()


def test_update_reasserts_the_fixed_fields(db, capsys):
    client_id, _ = _register(capsys)
    Application.objects.filter(client_id=client_id).update(
        client_type=Application.CLIENT_PUBLIC, authorization_grant_type=Application.GRANT_IMPLICIT,
        algorithm=Application.HS256_ALGORITHM, skip_authorization=False)
    _register(capsys)
    app = Application.objects.get(client_id=client_id)
    assert app.client_type == Application.CLIENT_CONFIDENTIAL
    assert app.authorization_grant_type == Application.GRANT_AUTHORIZATION_CODE
    assert app.algorithm == Application.RS256_ALGORITHM and app.skip_authorization
    Application.objects.filter(client_id=client_id).update(skip_authorization=False)
    _register(capsys, rotate=True)
    assert Application.objects.get(client_id=client_id).skip_authorization


def test_a_client_someone_owns_is_never_taken_over(db, capsys, employee_user):
    theirs = Application.objects.create(
        name="rota", user=employee_user, redirect_uris="https://evil.example/cb/",
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE)
    _register(capsys)
    theirs.refresh_from_db()
    assert theirs.redirect_uris == "https://evil.example/cb/"
    assert Application.objects.filter(name="rota", user__isnull=True).count() == 1


def test_two_clients_of_one_name_are_refused(db, capsys):
    _register(capsys)
    Application.objects.create(name="rota", redirect_uris=REDIRECT,
                               client_type=Application.CLIENT_CONFIDENTIAL,
                               authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE)
    with pytest.raises(CommandError, match="More than one client is named 'rota'"):
        _register(capsys)


def test_the_command_validates_the_redirect_uri(db, settings):
    from oauth2_provider.settings import oauth2_settings
    settings.OAUTH2_PROVIDER = {**settings.OAUTH2_PROVIDER, "ALLOWED_REDIRECT_URI_SCHEMES": ["https"]}
    try:
        with pytest.raises(CommandError):
            call_command("register_oidc_client", name="rota",
                         redirect_uri="http://rota.example/oidc/callback/")
    finally:
        oauth2_settings.reload()
    assert not Application.objects.exists()


# --- signing out, and how long a session lasts (review I7) ------------------------

def test_post_logout_redirect_defaults_to_the_rota_login(db, capsys):
    _register(capsys)
    assert Application.objects.get(name="rota").post_logout_redirect_uris == \
        "https://rota.example/accounts/login/"
    _register(capsys, post_logout_redirect_uri="https://rota.example/bye/")
    assert Application.objects.get(name="rota").post_logout_redirect_uris == "https://rota.example/bye/"


def test_sessions_end_with_the_browser_and_the_working_day():
    assert settings.SESSION_EXPIRE_AT_BROWSER_CLOSE is True
    assert settings.SESSION_COOKIE_AGE == 12 * 60 * 60
    assert settings.OAUTH2_PROVIDER["OIDC_RP_INITIATED_LOGOUT_ENABLED"] is True
    assert settings.OAUTH2_PROVIDER["OIDC_RP_INITIATED_LOGOUT_ALWAYS_PROMPT"] is False


def test_the_end_session_endpoint_exists(db, client):
    doc = client.get("/o/.well-known/openid-configuration/").json()
    assert doc["end_session_endpoint"].endswith("/o/logout/")
    assert client.get("/o/logout/").status_code != 404


# --- the code flow, end to end ---------------------------------------------------------

def _b64url_json(segment):
    return json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))


def _signed_in_flow(capsys, client, user, is_admin=None):
    """Sign `user` in to a freshly registered rota, to the tokens. With
    `is_admin`, the login holds that role in the rota first."""
    client_id, secret = _register(capsys)
    if is_admin is not None:
        AppRole.objects.create(user=user, application=Application.objects.get(client_id=client_id),
                               is_admin=is_admin)
    verifier = "v" * 64
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    r = client.get("/o/authorize/", {
        "response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT,
        "scope": "openid email", "state": "st", "nonce": "nn",
        "code_challenge": challenge, "code_challenge_method": "S256"})
    assert r.status_code == 302, r.content[:500]
    query = parse_qs(urlsplit(r["Location"]).query)
    assert r["Location"].startswith(REDIRECT) and query["state"] == ["st"]
    r = Client().post("/o/token/", {
        "grant_type": "authorization_code", "code": query["code"][0], "redirect_uri": REDIRECT,
        "client_id": client_id, "client_secret": secret, "code_verifier": verifier})
    assert r.status_code == 200, r.content[:500]
    return client_id, r.json()


# Protocol claims every ID token carries; everything else is about the person.
PROTOCOL = {"iss", "aud", "exp", "iat", "auth_time", "jti", "nonce", "at_hash", "azp"}


@pytest.mark.parametrize("role, admin", [(None, False), (False, False), (True, True)],
                         ids=["no-role", "user", "admin"])
def test_the_code_flow_gives_exactly_sub_email_employee_id_and_admin(
        capsys, employee_client, employee_user, role, admin):
    """Both ways a claim leaves: the ID token from the token endpoint, and
    the userinfo endpoint read with the access token. `admin` is read from
    the client each request names, so this proves both paths carry it."""
    e = make_employee(user=employee_user)
    client_id, tokens = _signed_in_flow(capsys, employee_client, employee_user, is_admin=role)
    claims = _b64url_json(tokens["id_token"].split(".")[1])
    assert set(claims) - PROTOCOL == {"sub", "email", "employee_id", "admin"}
    assert (claims["sub"], claims["email"], claims["employee_id"], claims["admin"]) == (
        str(employee_user.pk), "sam@example.com", e.pk, admin)
    assert claims["aud"] == client_id and claims["nonce"] == "nn"
    info = Client().get("/o/userinfo/", HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}")
    assert info.status_code == 200
    assert info.json() == {"sub": str(employee_user.pk), "email": "sam@example.com",
                           "employee_id": e.pk, "admin": admin}


def test_the_code_flow_needs_pkce(capsys, employee_client):
    client_id, _ = _register(capsys)
    r = employee_client.get("/o/authorize/", {
        "response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT,
        "scope": "openid email", "state": "st"})
    assert "code=" not in r.get("Location", "")


def test_an_inactive_login_cannot_refresh(capsys, employee_client, employee_user):
    """Review minor: the refresh token outlives the ten-minute tokens, so
    deactivating a login must stop it too."""
    client_id, tokens = _signed_in_flow(capsys, employee_client, employee_user)
    # _signed_in_flow keeps its secret to itself; rotating gives one to use here.
    call_command("register_oidc_client", name="rota", redirect_uri=REDIRECT, rotate=True)
    secret = re.search(r"client_secret=(\S+)", capsys.readouterr().out).group(1)

    def refresh(token):
        return Client().post("/o/token/", {"grant_type": "refresh_token", "refresh_token": token,
                                           "client_id": client_id, "client_secret": secret})

    r = refresh(tokens["refresh_token"])
    assert r.status_code == 200, r.content[:300]
    employee_user.is_active = False
    employee_user.save()
    r = refresh(r.json()["refresh_token"])
    assert r.status_code in (400, 401)
    assert "access_token" not in r.content.decode()


def test_the_rotas_sign_out_ends_the_session_here_without_a_prompt(capsys, employee_client,
                                                                    employee_user):
    """What the rota sends after its own logout: the ID token as
    id_token_hint, so no "are you sure" page, and back to its login page."""
    client_id, tokens = _signed_in_flow(capsys, employee_client, employee_user)
    r = employee_client.get("/o/logout/", {
        "id_token_hint": tokens["id_token"], "client_id": client_id,
        "post_logout_redirect_uri": "https://rota.example/accounts/login/"})
    assert r.status_code == 302 and r["Location"].startswith("https://rota.example/accounts/login/")
    assert "_auth_user_id" not in employee_client.session


def test_a_sign_out_to_an_unregistered_address_is_refused(capsys, employee_client, employee_user):
    client_id, tokens = _signed_in_flow(capsys, employee_client, employee_user)
    r = employee_client.get("/o/logout/", {
        "id_token_hint": tokens["id_token"], "client_id": client_id,
        "post_logout_redirect_uri": "https://evil.example/"})
    assert not r.get("Location", "").startswith("https://evil.example")
