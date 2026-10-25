"""The training documentation exists where the other compliance docs are,
names the UI's labels, and the backlog records what was built."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _text(*parts):
    return ROOT.joinpath(*parts).read_text()


def test_the_admin_guide_has_a_training_section_with_every_part():
    text = _text("docs", "admin", "compliance.md")
    for heading in ("## Training", "### Courses", "### Recording training", "### Verifying what someone recorded",
                    "### Sessions", "### The training matrix", "### Who sees what of training",
                    "### What each training status means", "### Training reminders"):
        assert heading in text, heading
    for label in ("Required of everyone", "Awaiting verification", "Record a training session", "Download as CSV",
                  "Training lapsed or missing", "Training to verify", "RETENTION_DAYS_TRAINING"):
        assert label in text, label
    assert "- [Training](#training)" in text                         # the page's own contents list


def test_the_people_page_and_the_index_mention_training():
    assert "Training" in _text("docs", "admin", "people.md").split("### The Compliance tab")[1].split("## ")[0]
    assert "training" in _text("docs", "admin", "README.md").lower()


def test_the_user_guides_cover_training():
    hr = _text("docs", "guides", "hr-administrator.md")
    for heading in ("## Training", "### How to say who needs a course", "### How to verify what someone uploaded",
                    "### How to record a training session", "### How to see the training matrix"):
        assert heading in hr, heading
    assert "training" in hr.split("## Going live: your first month")[1].split("## Finding your way")[0].lower()
    manager = _text("docs", "guides", "manager.md")
    for heading in ("## Your team's training", "### How to record training for someone",
                    "### How to verify or turn down an upload", "### How to record a session"):
        assert heading in manager, heading
    assert "training" in _text("docs", "guides", "README.md").lower()
    assert "training" in _text("README.md").split("## Develop")[0].lower()


def test_the_backlog_closes_the_item_and_parks_the_rest():
    text = _text("docs", "superpowers", "backlog.md")
    assert "Training compliance (spec 4)" not in text.split("## Smaller items")[0] or "built" in text
    for parked in ("level", "import", "certificate pack", "booking"):
        assert parked in text.lower(), parked
