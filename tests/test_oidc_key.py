"""The OIDC signing key: read from a file of its own in production, and a
deploy check that refuses a key that is not a PEM RSA private key (review
I6 — systemd's EnvironmentFile parser turns an unquoted \\n into "n")."""

import os
import subprocess
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from hr.checks import oidc_signing_key

ROOT = Path(__file__).resolve().parent.parent


def _pem(key):
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()).decode()


def _rsa_pem():
    return _pem(rsa.generate_private_key(public_exponent=65537, key_size=2048))


def _env(extra):
    env = {k: v for k, v in os.environ.items()
           if k not in ("DEBUG", "SECRET_KEY", "OIDC_RSA_PRIVATE_KEY", "OIDC_RSA_PRIVATE_KEY_FILE")}
    env.update({"DJANGO_SETTINGS_MODULE": "config.settings", **extra})
    return env


def _settings(extra, expr):
    """A setting as a fresh, non-pytest process sees it."""
    return subprocess.run(
        [sys.executable, "-c", f"from config import settings as s; print({expr})"],
        env=_env({"DEBUG": "1", **extra}), cwd=ROOT, capture_output=True, text=True)


# --- where the key comes from -----------------------------------------------------------

def test_the_key_file_is_read_as_it_is(tmp_path):
    pem = _rsa_pem()
    (tmp_path / "oidc.pem").write_text(pem)
    r = _settings({"OIDC_RSA_PRIVATE_KEY_FILE": str(tmp_path / "oidc.pem")},
                  "repr(s.OIDC_RSA_PRIVATE_KEY), s.OAUTH2_PROVIDER['OIDC_ENABLED']")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == f"{pem!r} True"


def test_a_named_file_that_cannot_be_read_stops_the_app(tmp_path):
    r = _settings({"OIDC_RSA_PRIVATE_KEY_FILE": str(tmp_path / "missing.pem")}, "1")
    assert r.returncode != 0
    assert "OIDC_RSA_PRIVATE_KEY_FILE is set but" in r.stderr


def test_the_one_line_form_still_works_for_development():
    pem = _rsa_pem()
    r = _settings({"OIDC_RSA_PRIVATE_KEY": pem.replace("\n", "\\n")},
                  "repr(s.OIDC_RSA_PRIVATE_KEY)")
    assert r.stdout.strip() == repr(pem)


def test_no_key_no_provider():
    r = _settings({}, "s.OAUTH2_PROVIDER['OIDC_ENABLED']")
    assert r.stdout.strip() == "False"


# --- the deploy check ---------------------------------------------------------------------

def _with_key(settings, key, enabled=True):
    settings.OAUTH2_PROVIDER = {**settings.OAUTH2_PROVIDER, "OIDC_ENABLED": enabled,
                                "OIDC_RSA_PRIVATE_KEY": key}


def test_a_good_key_passes(settings):
    _with_key(settings, _rsa_pem())
    assert oidc_signing_key(None) == []


def test_the_systemd_mangled_key_fails(settings):
    mangled = _rsa_pem().replace("\n", "n")
    _with_key(settings, mangled)
    (error,) = oidc_signing_key(None)
    assert error.id == "hr.E001"


def test_a_key_that_is_not_rsa_fails(settings):
    _with_key(settings, _pem(ec.generate_private_key(ec.SECP256R1())))
    assert [e.id for e in oidc_signing_key(None)] == ["hr.E001"]


def test_provider_off_nothing_to_check(settings):
    _with_key(settings, "", enabled=False)
    assert oidc_signing_key(None) == []


def test_check_deploy_fails_on_a_bad_key(tmp_path):
    """End to end, as `deploy/manage check --deploy` runs it."""
    (tmp_path / "oidc.pem").write_text(_rsa_pem().replace("\n", "n"))
    r = subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy"],
        env=_env({"DEBUG": "0", "SECRET_KEY": "x" * 60, "ALLOWED_HOSTS": "hr.example",
                  "DB_PATH": str(tmp_path / "db.sqlite3"),
                  "OIDC_RSA_PRIVATE_KEY_FILE": str(tmp_path / "oidc.pem")}),
        cwd=ROOT, capture_output=True, text=True)
    assert r.returncode != 0
    assert "hr.E001" in r.stderr + r.stdout
