"""The Content-Security-Policy (config/middleware.py), ported from the
rota's 6f3196e: on every page the app renders, no script but the app's own
files, and nothing in the app's own pages that the policy would have to be
loosened for."""

import re
from pathlib import Path

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db
ROOT = Path(__file__).resolve().parents[1]
INLINE_HANDLER = re.compile(r"""\son[a-z]+\s*=""", re.I)
INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>", re.I)


def _policy(resp):
    return {d.split()[0]: d.split()[1:] for d in resp["Content-Security-Policy"].split("; ")}


# --- the header -----------------------------------------------------------------

def test_app_pages_carry_the_policy(employee_client):
    policy = _policy(employee_client.get("/people/me/"))
    scripts = policy["script-src"]
    assert scripts[0] == "'self'" and scripts[1].startswith("'nonce-")
    assert len(scripts) == 2, "nothing but the app's own scripts and Cloudflare's nonce"
    for directive in ("object-src", "base-uri"):
        assert policy[directive] == ["'none'"]
    assert policy["frame-ancestors"] == ["'none'"]
    assert policy["form-action"] == ["'self'"]


def test_signed_out_pages_carry_it_too():
    assert "Content-Security-Policy" in Client().get("/accounts/login/")


def test_the_nonce_is_new_every_time(employee_client):
    first = _policy(employee_client.get("/people/me/"))["script-src"][1]
    second = _policy(employee_client.get("/people/me/"))["script-src"][1]
    assert first != second


def test_the_admin_renders_and_is_left_alone(admin_client):
    """unfold's admin runs Alpine, which needs eval; the rota leaves the
    admin out of the policy, and so does this app."""
    for url in ("/admin/", "/admin/people/employee/", "/admin/people/employee/add/"):
        resp = admin_client.get(url)
        assert resp.status_code == 200, url
        assert "Content-Security-Policy" not in resp, url


def test_non_html_is_left_alone(client):
    assert "Content-Security-Policy" not in client.get("/o/.well-known/openid-configuration/")


def test_report_only_is_the_way_back(employee_client, settings):
    settings.CSP_REPORT_ONLY = True
    resp = employee_client.get("/people/me/")
    assert "Content-Security-Policy" not in resp
    assert "script-src 'self' 'nonce-" in resp["Content-Security-Policy-Report-Only"]


# --- nothing in the app needs the policy loosened -------------------------------------

def _templates():
    base = ROOT / "templates"
    for path in base.rglob("*.html"):
        if "admin" in path.relative_to(base).parts:
            continue
        yield path


def test_no_template_has_inline_script_or_handlers():
    bad = []
    for path in _templates():
        text = path.read_text()
        for pattern, what in ((INLINE_HANDLER, "inline handler"), (INLINE_SCRIPT, "inline <script>")):
            for m in pattern.finditer(text):
                bad.append(f"{path.relative_to(ROOT)}: {what}: {text[m.start():m.start() + 60]!r}")
    assert not bad, bad


def test_the_passkey_forms_are_guarded_by_the_script():
    """Enter in a passkey name field must not submit its form (with the
    CSRF token) as a GET; that was an inline onsubmit."""
    js = (ROOT / "static" / "js" / "passkeys.js").read_text()
    assert "#passkey-form, #passkey-nudge-form" in js
    assert js.index('addEventListener("submit"') < js.index("if (!window.PublicKeyCredential)")


def test_rendered_pages_hold_no_inline_script(employee_client, employee_user):
    from tests.factories import make_employee
    make_employee(user=employee_user)
    urls = [(employee_client, u) for u in ("/people/me/", "/accounts/account/",
                                           "/accounts/password_change/")]
    urls += [(Client(), u) for u in ("/accounts/login/", "/accounts/password_reset/",
                                     "/accounts/password_reset/done/")]
    bad = []
    for client, url in urls:
        resp = client.get(url)
        assert resp.status_code == 200, (url, resp.status_code)
        html = resp.content.decode()
        for pattern, what in ((INLINE_HANDLER, "handler"), (INLINE_SCRIPT, "script")):
            bad += [f"{url}: {what}: {html[m.start():m.start() + 60]!r}"
                    for m in pattern.finditer(html)]
    assert not bad, bad


def test_the_providers_sign_out_page_holds_no_inline_script(employee_client):
    """django-oauth-toolkit's own template, shown when a relying party
    signs someone out without an ID token."""
    resp = employee_client.get("/o/logout/")
    assert resp.status_code == 200
    assert "Content-Security-Policy" in resp
    html = resp.content.decode()
    assert not INLINE_SCRIPT.search(html) and not INLINE_HANDLER.search(html)


def test_form_action_lets_sign_in_and_sign_out_finish_at_the_rota(db, capsys):
    """Browsers apply form-action to the redirects after a form post: the
    login form's post ends at the rota's callback (via /o/authorize/), and
    the provider's sign-out confirmation at the rota's login page."""
    from django.core.management import call_command
    call_command("register_oidc_client", name="rota",
                 redirect_uri="https://rota.example/oidc/callback/")
    policy = _policy(Client().get("/accounts/login/"))
    assert policy["form-action"] == ["'self'", "https://rota.example"]


def test_form_action_is_self_alone_with_no_client(db):
    assert _policy(Client().get("/accounts/login/"))["form-action"] == ["'self'"]
