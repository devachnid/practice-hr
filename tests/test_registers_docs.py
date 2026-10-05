"""The parse command a person uses while capturing pages, and the docs'
bold labels against the UI."""
import re
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db
ROOT = Path(__file__).resolve().parent.parent

PAGE = """<html><body><h1>Dr Priya Patel</h1><p>GMC number: 1234567</p>
<p>Registration status: Registered with a licence to practise</p><p>GP Register: yes</p></body></html>"""


def test_registers_parse_prints_the_outcome_and_the_name_match(tmp_path):
    page = tmp_path / "clear.html"
    page.write_text(PAGE)
    out = StringIO()
    call_command("registers_parse", "gmc", str(page), "--surname", "Patel", stdout=out)
    text = out.getvalue()
    assert "outcome: clear" in text and "name: Priya Patel" in text and "surname matches: yes" in text
    out = StringIO()
    call_command("registers_parse", "gmc", str(page), "--surname", "Khan", stdout=out)
    assert "surname matches: no" in out.getvalue()


def test_the_fixture_readme_names_every_body_and_outcome():
    text = (ROOT / "registers/adapters/fixtures/README.md").read_text()
    for code in ("gmc", "mpl_wales", "nmc", "gphc"):
        assert f"`{code}/`" in text
    for outcome in ("clear.html", "problem.html", "not_found.html"):
        assert outcome in text
    assert "registers_parse" in text and ".surname" in text and ".number" in text
    for name in ("LABELS", "RESTRICTION_LABELS", "NOT_FOUND", "CLEAR", "PROBLEM", "NAME_MARKER"):
        assert f"`{name}`" in text, name


def _bold(path):
    text = re.sub(r"```.*?```", "", path.read_text(), flags=re.S)
    return set(re.findall(r"\*\*([^*]+)\*\*", text))


def test_the_guides_name_the_ui_labels_that_exist():
    labels = _bold(ROOT / "docs/guides/hr-administrator.md") | _bold(ROOT / "docs/guides/manager.md")
    for label in ("Register bodies", "Registration lookups", "Check now", "On the register",
                  "Check professional registrations every (days)", "Unpause", "GMC number"):
        assert label in labels, label
