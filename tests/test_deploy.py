import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy"


def test_units_use_env_file_and_loopback():
    unit = (DEPLOY / "gunicorn.service").read_text()
    assert "EnvironmentFile=/etc/practice-hr.env" in unit
    assert "--bind 127.0.0.1:" in unit
    assert "SECRET_KEY" not in unit.split("EnvironmentFile")[1]


def test_nightly_timer_exists():
    assert "hr_nightly" in (DEPLOY / "hr-nightly.service").read_text()
    assert "OnCalendar" in (DEPLOY / "hr-nightly.timer").read_text()


def test_backup_copies_media_too():
    assert "media" in (DEPLOY / "backup.sh").read_text()


def test_gunicorn_runs_as_its_own_sandboxed_user():
    unit = (DEPLOY / "gunicorn.service").read_text()
    assert "User=practice-hr" in unit
    assert "ProtectSystem=strict" in unit


def test_gunicorn_keeps_only_the_state_directory_writable():
    """The code tree is read-only to the app; only its state directory
    (the database, backups, and media once there is any) is writable."""
    unit = (DEPLOY / "gunicorn.service").read_text()
    assert "ReadWritePaths=/var/lib/practice-hr" in unit
    assert "ReadWritePaths=/srv/practice-hr" not in unit


# --- settings --------------------------------------------------------------

def _setting(expression, extra_env):
    """A fresh interpreter, the way tests/test_deploy_units.py in the rota
    checks the same thing — DATABASES is built at import time, so the
    running test process (already configured) can't be reused for this."""
    env = {k: v for k, v in os.environ.items() if k not in ("DB_PATH", "MEDIA_ROOT")}
    env.update({"DEBUG": "1", "DJANGO_SETTINGS_MODULE": "config.settings", **extra_env})
    return subprocess.run(
        [sys.executable, "-c",
         f"import django; django.setup(); from django.conf import settings; print({expression})"],
        env=env, cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()


def _database_name(extra_env):
    return _setting("settings.DATABASES['default']['NAME']", extra_env)


def test_db_path_moves_the_database():
    assert _database_name({"DB_PATH": "/var/lib/practice-hr/db.sqlite3"}) == "/var/lib/practice-hr/db.sqlite3"


def test_without_db_path_the_database_sits_beside_manage_py():
    assert _database_name({}) == str(ROOT / "db.sqlite3")


def test_media_root_moves_into_the_state_directory():
    assert _setting("settings.MEDIA_ROOT", {"MEDIA_ROOT": "/var/lib/practice-hr/media"}) == "/var/lib/practice-hr/media"


def test_without_media_root_media_sits_beside_manage_py():
    assert _setting("settings.MEDIA_ROOT", {}) == str(ROOT / "media")
    assert _setting("settings.MEDIA_ROOT", {"MEDIA_ROOT": ""}) == str(ROOT / "media")


def test_production_environment_sets_media_root_in_the_state_directory():
    """The code tree is read-only under ProtectSystem=strict, so the payroll
    reports go beside the database. The env file recipe (in the unit and the
    README) names it next to DB_PATH."""
    for text in ((DEPLOY / "gunicorn.service").read_text(), (ROOT / "README.md").read_text()):
        assert "DB_PATH=/var/lib/practice-hr/db.sqlite3" in text
        assert "MEDIA_ROOT=/var/lib/practice-hr/media" in text


# --- hr.W002: emailed links need the site's address -------------------------

@pytest.mark.parametrize("value", ["", "/"])
def test_check_warns_when_site_url_is_unset_outside_debug(settings, value):
    from hr.checks import site_url
    settings.DEBUG = False
    settings.SITE_URL = value
    (warning,) = site_url(None)
    assert warning.id == "hr.W002" and warning.level == 30


@pytest.mark.parametrize("debug, value", [(False, "https://hr.example.org"), (True, "/")])
def test_check_quiet_with_a_site_url_or_in_debug(settings, debug, value):
    from hr.checks import site_url
    settings.DEBUG = debug
    settings.SITE_URL = value
    assert site_url(None) == []


def test_site_url_check_is_registered_for_deploy():
    from django.core import checks
    from hr.checks import site_url
    assert site_url in checks.registry.registry.deployment_checks


# --- off-site backup to the Proxmox Backup Server --------------------------

def _service_directives(name):
    out = {}
    in_service = False
    for line in (DEPLOY / name).read_text().splitlines():
        line = line.strip()
        if line.startswith("["):
            in_service = line == "[Service]"
        elif in_service and "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            out.setdefault(key, []).append(value)
    return out


def test_the_pbs_secrets_stay_out_of_the_app_users_reach():
    """The token comes from a root-read env file and the encryption key as a
    credential, so the practice-hr user (and the web process) never reads
    either."""
    d = _service_directives("hr-pbs.service")
    assert d["EnvironmentFile"] == ["/etc/pbs-backup/practice-hr.env"]
    assert d["LoadCredential"] == ["pbs.key:/etc/pbs-backup/practice-hr.key"]
    assert d["ExecStart"] == ["/srv/practice-hr/deploy/pbs-push.sh"]
    assert d["User"] == ["practice-hr"] and d["Group"] == ["practice-hr"]
    assert d["StateDirectory"] == ["practice-hr"] and d["UMask"] == ["0077"]


def test_the_pbs_unit_carries_the_backup_units_sandbox():
    """Everything from the Sandbox comment on is the same as hr-backup's."""
    def sandbox(name):
        text = (DEPLOY / name).read_text()
        return text[text.index("# Sandbox"):].split("\n", 1)[1]
    assert sandbox("hr-pbs.service") == sandbox("hr-backup.service")


def test_the_pbs_push_script_is_executable_and_valid_shell():
    script = DEPLOY / "pbs-push.sh"
    assert os.access(script, os.X_OK)
    try:
        subprocess.run(["sh", "-n", str(script)], check=True, capture_output=True)
    except FileNotFoundError:
        pytest.skip("no sh")


def test_the_pbs_push_script_sends_the_copies_encrypted_to_its_own_namespace():
    text = (DEPLOY / "pbs-push.sh").read_text()
    live = " ".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    assert "$state/backups" in live, "the finished copies, not the live database"
    assert "db.sqlite3" not in live
    assert "--ns practice-hr" in live and "--keyfile" in live
    assert "PBS_PASSWORD" not in text, "the token belongs in the root-only env file"


def test_the_pbs_dropin_runs_the_push_after_a_successful_backup():
    live = [ln for ln in (DEPLOY / "hr-backup-pbs.conf").read_text().splitlines()
            if ln.strip() and not ln.startswith("#")]
    assert live == ["[Unit]", "OnSuccess=hr-pbs.service"]
