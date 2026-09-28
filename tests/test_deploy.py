from pathlib import Path

DEPLOY = Path(__file__).resolve().parent.parent / "deploy"


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
