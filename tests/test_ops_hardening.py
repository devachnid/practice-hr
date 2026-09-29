"""The rota's 4e36ac5, ported: an HTTPS redirect of the app's own, no
published development key, a request log that keeps password links out of
it, and security events that reach the journal."""

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.test import Client

ROOT = Path(__file__).resolve().parents[1]
TUNNEL = "127.0.0.1"


def _settings_value(expr, env):
    """A setting as a production process sees it: a fresh interpreter that is
    not running pytest, so config/settings.py's _TESTING is false."""
    base = {k: v for k, v in os.environ.items()
            if k not in ("DEBUG", "SECRET_KEY", "DB_PATH", "OIDC_RSA_PRIVATE_KEY",
                         "OIDC_RSA_PRIVATE_KEY_FILE")}
    base.update({"DJANGO_SETTINGS_MODULE": "config.settings", **env})
    return subprocess.run(
        [sys.executable, "-c", f"from config import settings as s; print(repr({expr}))"],
        env=base, cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()


# --- settings ---------------------------------------------------------------------

def test_production_redirects_http_to_https_itself():
    """Not left to the Cloudflare zone's "Always Use HTTPS" alone."""
    assert _settings_value("s.SECURE_SSL_REDIRECT",
                           {"DEBUG": "0", "SECRET_KEY": "x" * 50}) == "True"


def test_the_dev_key_is_private_to_the_checkout(tmp_path, monkeypatch):
    """It was the constant "dev-insecure-key", published in this repository:
    a server run with DEBUG=1 and no SECRET_KEY could have every session
    forged. Now a random key per checkout, kept across restarts."""
    from config import settings as s
    assert "dev-insecure-key" not in (ROOT / "config" / "settings.py").read_text()
    monkeypatch.setattr(s, "BASE_DIR", tmp_path)
    first = s._dev_secret_key()
    assert len(first) >= 50
    key_file = tmp_path / ".dev_secret_key"
    assert key_file.stat().st_mode & 0o077 == 0
    assert s._dev_secret_key() == first
    assert ".dev_secret_key" in (ROOT / ".gitignore").read_text()


def test_the_development_key_is_only_reachable_with_debug_explicitly_on():
    src = (ROOT / "config" / "settings.py").read_text()
    i = src.index("_dev_secret_key()", src.index("SECRET_KEY = os.environ.get"))
    assert "_TESTING" in src[i - 200:i], "the development SECRET_KEY is no longer guarded"
    assert "SECURE_SSL_REDIRECT = not _TESTING" in src[src.index("if not DEBUG:"):]


def test_django_is_5_2_17_or_later():
    import django
    assert django.VERSION[:3] >= (5, 2, 17)
    assert "Django==5.2.17" in (ROOT / "requirements.txt").read_text()


# --- the request log ------------------------------------------------------------------

@pytest.fixture
def access(caplog):
    caplog.set_level(logging.INFO, logger="hr.access")
    return lambda: [r.getMessage() for r in caplog.records if r.name == "hr.access"]


@pytest.mark.django_db
def test_each_request_is_logged_with_the_real_client_address(access, employee_client, employee_user):
    employee_client.get("/people/me/?week=2026-09-28", REMOTE_ADDR=TUNNEL,
                        HTTP_CF_CONNECTING_IP="198.51.100.20")
    (line,) = [m for m in access() if " /people/me/ " in m]
    assert line.startswith(f"198.51.100.20 user={employee_user.pk} GET /people/me/ 200 ")
    assert "week=" not in line, "query strings are not logged"


@pytest.mark.django_db
def test_a_password_links_token_never_reaches_the_log(access):
    Client().get("/accounts/reset/MQ/cyb2kd-0123456789abcdef0123456789abcdef/")
    lines = access()
    assert any("/accounts/reset/<redacted>/" in m for m in lines)
    assert not any("0123456789abcdef" in m or "MQ" in m for m in lines)


@pytest.mark.django_db
def test_an_authorization_code_never_reaches_the_log(access):
    """The OIDC endpoints carry codes in query strings, which are not logged."""
    Client().get("/o/authorize/?code=SECRETCODE123&state=x")
    assert not any("SECRETCODE123" in m for m in access())


@pytest.mark.django_db
def test_a_csrf_failure_reaches_the_security_log(caplog):
    caplog.set_level(logging.INFO, logger="django.security")
    Client(enforce_csrf_checks=True).post("/accounts/login/", {"username": "x", "password": "y"})
    assert any(r.name == "django.security.csrf" for r in caplog.records)
