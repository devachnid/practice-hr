import os
import subprocess
import sys
from pathlib import Path

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

def _database_name(extra_env):
    """A fresh interpreter, the way tests/test_deploy_units.py in the rota
    checks the same thing — DATABASES is built at import time, so the
    running test process (already configured) can't be reused for this."""
    env = {k: v for k, v in os.environ.items() if k != "DB_PATH"}
    env.update({"DEBUG": "1", "DJANGO_SETTINGS_MODULE": "config.settings", **extra_env})
    return subprocess.run(
        [sys.executable, "-c",
         "import django; django.setup(); from django.conf import settings; "
         "print(settings.DATABASES['default']['NAME'])"],
        env=env, cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()


def test_db_path_moves_the_database():
    assert _database_name({"DB_PATH": "/var/lib/practice-hr/db.sqlite3"}) == "/var/lib/practice-hr/db.sqlite3"


def test_without_db_path_the_database_sits_beside_manage_py():
    assert _database_name({}) == str(ROOT / "db.sqlite3")
