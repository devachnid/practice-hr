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
    assert "outcome: name_mismatch" in out.getvalue() and "surname matches: no" in out.getvalue()


def test_registers_parse_reports_what_a_lookup_would_record(tmp_path):
    page = tmp_path / "clear.html"
    page.write_text(PAGE.replace("<h1>Dr Priya Patel</h1>", ""))       # clear words, but no name: unreadable
    out = StringIO()
    call_command("registers_parse", "gmc", str(page), "--surname", "Patel", stdout=out)
    text = out.getvalue()
    assert "outcome: unreadable" in text and "status text: name not found on the page" in text
    assert "surname matches: no name found" in text and "lines of text: 3" in text


def test_registers_fetch_saves_what_the_app_fetches_and_prints_only_the_status_and_size(tmp_path, monkeypatch):
    from registers import adapters, http
    asked = []

    def get(url, timeout=10):
        asked.append(url)
        return 200, "<p>Priya Patel ü</p>"
    monkeypatch.setattr(http, "get", get)
    target = tmp_path / "clear.html"
    out = StringIO()
    call_command("registers_fetch", "gmc", " 1234567 ", str(target), stdout=out)
    assert asked == [adapters.url("gmc", "1234567")]
    assert target.read_text(encoding="utf-8") == "<p>Priya Patel ü</p>"
    assert out.getvalue() == f"HTTP 200, {len('<p>Priya Patel ü</p>'.encode())} bytes\n"


def test_registers_fetch_refuses_a_bad_number_and_reports_a_failed_fetch(tmp_path, monkeypatch):
    from django.core.management.base import CommandError

    from registers import http
    monkeypatch.setattr(http, "get", lambda url, timeout=10: pytest.fail("fetched a bad number"))
    with pytest.raises(CommandError, match="A GMC number is seven digits."):
        call_command("registers_fetch", "gmc", "12345", str(tmp_path / "x.html"))

    def down(url, timeout=10):
        raise http.FetchError("URLError")
    monkeypatch.setattr(http, "get", down)
    with pytest.raises(CommandError, match="could not fetch the page"):
        call_command("registers_fetch", "nmc", "12a3456b", str(tmp_path / "x.html"))
    assert not (tmp_path / "x.html").exists()


def test_the_fixture_readme_names_every_body_and_outcome():
    text = (ROOT / "registers/adapters/fixtures/README.md").read_text()
    for code in ("gmc", "mpl_wales", "nmc", "gphc"):
        assert f"`{code}/`" in text
    for outcome in ("clear.html", "problem.html", "not_found.html"):
        assert outcome in text
    assert "registers_parse" in text and ".surname" in text and ".number" in text
    assert "registers_fetch" in text and "curl -A" in text and "problem*.html" in text
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
