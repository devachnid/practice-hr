"""The admin guide's and the user guides' pages exist, are reachable from
their index, and every relative link and anchor in them (and the README's)
resolves."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "admin"
PAGES = ("people.md", "sign-in.md", "absence.md", "year-end.md", "payroll.md", "api.md")
GUIDES = ROOT / "docs" / "guides"
GUIDE_PAGES = ("manager.md", "hr-administrator.md")
LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)\)")


def _slug(heading):
    """GitHub's anchor for a heading: lower case, backticks and punctuation
    dropped (underscores and hyphens kept), spaces to hyphens."""
    text = heading.strip().lower().replace("`", "")
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def _anchors(path):
    in_code, out = False, set()
    for line in path.read_text().splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        m = None if in_code else re.match(r"#{1,6}\s+(.*)", line)
        if m:
            out.add(_slug(m.group(1)))
    return out


def _links(path):
    text = re.sub(r"```.*?```", "", path.read_text(), flags=re.S)
    text = re.sub(r"`[^`\n]*`", "", text)
    return LINK.findall(text)


def test_every_guide_page_exists_and_is_linked_from_the_index():
    index = (DOCS / "README.md").read_text()
    for page in PAGES:
        assert (DOCS / page).exists(), page
        assert f"]({page})" in index, page


def test_every_user_guide_exists_and_is_linked_from_its_index():
    index = (GUIDES / "README.md").read_text()
    for page in GUIDE_PAGES:
        assert (GUIDES / page).exists(), page
        assert f"]({page})" in index, page


@pytest.mark.parametrize("source", [DOCS / name for name in ("README.md",) + PAGES] + [ROOT / "README.md"]
                         + [GUIDES / name for name in ("README.md",) + GUIDE_PAGES],
                         ids=lambda p: str(p.relative_to(ROOT)))
def test_every_relative_link_and_anchor_resolves(source):
    for target in _links(source):
        if re.match(r"[a-z][a-z0-9+.-]*:", target):     # https:, mailto:
            continue
        name, _, anchor = target.partition("#")
        dest = (source.parent / name).resolve() if name else source
        assert dest.exists(), f"{source.name}: {target} points at a file that is not there"
        if anchor:
            assert dest.suffix == ".md" and anchor in _anchors(dest), \
                f"{source.name}: {target} points at a heading that is not there"


def test_the_link_checker_catches_a_broken_anchor(tmp_path):
    page = tmp_path / "a.md"
    page.write_text("# Title\n\n## Carry over (`carry_over_max_weeks`)\n")
    assert _anchors(page) == {"title", "carry-over-carry_over_max_weeks"}
    assert "nope" not in _anchors(page)


def test_absence_guide_names_every_policy_field():
    text = (DOCS / "absence.md").read_text()
    for field in ("weeks_per_year", "carry_over_max_weeks", "carry_over_expires_after_days", "rounding",
                  "bank_holiday_handling", "earned_expires_after_days", "leave_year_basis", "accrual",
                  "days_per_year", "carry_over_days"):
        assert field in text, field


def test_absence_guide_covers_the_standard_contract():
    text = " ".join((DOCS / "absence.md").read_text().split())
    for phrase in ("part month counts as a full month", "starters and leavers", "one working day",
                   "TUPE", "its own policy", "Full-time days per year"):
        assert phrase in text, phrase


def test_the_environment_settings_are_documented_in_the_readme():
    text = (ROOT / "README.md").read_text()
    for name in ("SITE_URL", "HR_API_TOKENS", "API_RATE_LIMIT_PER_MINUTE", "CHASE_AFTER_WORKING_DAYS", "MEDIA_ROOT", "RETENTION_DAYS_PERSONAL",
                 "RETENTION_DAYS_AUDIT"):
        assert name in text, name
    assert "MEDIA_ROOT=/var/lib/practice-hr/media" in text
