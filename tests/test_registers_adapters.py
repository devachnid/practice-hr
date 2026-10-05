"""The parsers against synthetic page text (the live pages are not reachable
from the sandbox; real pages, when captured, run through the same parse in
test_captured_fixtures_parse_as_their_file_name_says), the name rule, and
the proof that nothing here reaches the network."""
import socket
from pathlib import Path

import pytest

from registers import http, names
from registers.adapters import CODES, Result, gmc, gphc, lookup, mpl_wales, nmc, url, verified

FIXTURES = Path("registers/adapters/fixtures")


# ---- names ---------------------------------------------------------------------------------

@pytest.mark.parametrize("a,b,expected", [
    ("Patel", "patel", True),
    ("Ní Bhriain", "Ni Bhriain", True),
    ("Smith-Jones", "Smith", True),
    ("Smith", "Jones-Smith", True),
    ("O'Neill", "ONeill", True),
    ("Patel", "Patil", False),
    ("", "Patel", False),
    ("Smith", "", False),
])
def test_surnames_match_loosely_and_never_wrongly(a, b, expected):
    assert names.surnames_match(a, b) is expected


# ---- the network function --------------------------------------------------------------------

def test_the_user_agent_names_the_practice(settings):
    settings.SITE_URL = "https://hr.example.org/"
    assert http.user_agent() == "PracticeHR/1.0 (+https://hr.example.org; registration checks)"
    settings.SITE_URL = "/"
    assert http.user_agent() == "PracticeHR/1.0 (registration checks)"


def test_nothing_in_the_adapters_reaches_the_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("no network in tests")
    monkeypatch.setattr(socket, "create_connection", refuse)     # what urllib opens connections with
    with pytest.raises(http.FetchError):
        http.get("https://example.invalid/anything")
    for code in CODES:
        r = lookup(code, "1234567" if code != "nmc" else "12A3456B", "Patel")
        assert r.outcome == "unreadable" and r.page_hash == ""


# ---- parsers -------------------------------------------------------------------------------

GMC_CLEAR = """<html><body><h1>Dr Priya Patel</h1><p>GMC number: 1234567</p>
<dl><dt>Registration status</dt><dd>Registered with a licence to practise</dd>
<dt>GP Register</dt><dd>On the GP Register since 2015</dd></dl></body></html>"""
GMC_SUSPENDED = GMC_CLEAR.replace("Registered with a licence to practise", "Suspended")
GMC_NO_LICENCE = GMC_CLEAR.replace("Registered with a licence to practise", "Registered without a licence to practise")
GMC_NOT_GP = GMC_CLEAR.replace("<dt>GP Register</dt><dd>On the GP Register since 2015</dd>", "")
GMC_CONDITIONS = GMC_CLEAR.replace("</dl>", "<dt>Fitness to practise</dt><dd>Conditions on registration</dd></dl>")
GMC_NONE = "<html><body><h1>Search results</h1><p>No results were found for 1234567.</p></body></html>"
GMC_ODD = "<html><body><p>Something else entirely</p></body></html>"


@pytest.mark.parametrize("page,outcome,words", [
    (GMC_CLEAR, "clear", "Registered with a licence to practise"),
    (GMC_SUSPENDED, "problem", "Suspended"),
    (GMC_NO_LICENCE, "problem", "Registered without a licence"),
    (GMC_NOT_GP, "problem", "not on the GP Register"),
    (GMC_CONDITIONS, "problem", "Conditions"),
    (GMC_NONE, "not_found", ""),
    (GMC_ODD, "unreadable", ""),
])
def test_gmc_parse(page, outcome, words):
    got, status, name = gmc.parse(gmc.text_of(page))
    assert got == outcome and words in status
    if outcome in ("clear", "problem"):
        assert name == "Priya Patel"


MPL_PRESENT = """<html><body><table><tr><th>GMC No</th><th>Name</th><th>Status</th></tr>
<tr><td>1234567</td><td>PATEL, Priya</td><td>Included</td></tr></table></body></html>"""
MPL_SUSPENDED = MPL_PRESENT.replace("Included", "Suspended")
MPL_NONE = "<html><body><p>No performers match your search.</p></body></html>"


@pytest.mark.parametrize("page,outcome,words", [
    (MPL_PRESENT, "clear", "Included"),
    (MPL_SUSPENDED, "problem", "Suspended"),
    (MPL_NONE, "not_found", ""),
    (GMC_ODD, "unreadable", ""),
])
def test_mpl_wales_parse(page, outcome, words):
    got, status, name = mpl_wales.parse(mpl_wales.text_of(page), "1234567")
    assert got == outcome and words in status
    if outcome in ("clear", "problem"):
        assert name == "Priya PATEL"


NMC_CLEAR = """<html><body><h2>Priya Patel</h2><p>PIN 12A3456B</p>
<p>Registration status: Effective registration</p><p>Registered nurse - Adult</p></body></html>"""
NMC_LAPSED = NMC_CLEAR.replace("Effective registration", "Lapsed")
NMC_CONDITIONS = NMC_CLEAR.replace("</body>", "<p>Conditions of practice order</p></body>")
NMC_NONE = "<html><body><p>No registrant found with the PIN 12A3456B.</p></body></html>"


@pytest.mark.parametrize("page,outcome,words", [
    (NMC_CLEAR, "clear", "Effective registration"),
    (NMC_LAPSED, "problem", "Lapsed"),
    (NMC_CONDITIONS, "problem", "Conditions"),
    (NMC_NONE, "not_found", ""),
    (GMC_ODD, "unreadable", ""),
])
def test_nmc_parse(page, outcome, words):
    got, status, name = nmc.parse(nmc.text_of(page))
    assert got == outcome and words in status
    if outcome in ("clear", "problem"):
        assert name == "Priya Patel"


GPHC_CLEAR = """<html><body><h2>Priya Patel</h2><p>Registration number: 2012345</p>
<p>Status: Registered</p><p>Pharmacist</p></body></html>"""
GPHC_SUSPENDED = GPHC_CLEAR.replace("Registered", "Suspended")
GPHC_CONDITIONS = GPHC_CLEAR.replace("</body>", "<p>Conditions apply to this registration</p></body>")
GPHC_NONE = "<html><body><p>Your search returned no results.</p></body></html>"


@pytest.mark.parametrize("page,outcome,words", [
    (GPHC_CLEAR, "clear", "Registered"),
    (GPHC_SUSPENDED, "problem", "Suspended"),
    (GPHC_CONDITIONS, "problem", "Conditions"),
    (GPHC_NONE, "not_found", ""),
    (GMC_ODD, "unreadable", ""),
])
def test_gphc_parse(page, outcome, words):
    got, status, name = gphc.parse(gphc.text_of(page))
    assert got == outcome and words in status
    if outcome in ("clear", "problem"):
        assert name == "Priya Patel"


@pytest.mark.parametrize("code,page", [("gmc", GMC_NONE), ("mpl_wales", MPL_NONE), ("nmc", NMC_NONE),
                                       ("gphc", GPHC_NONE)])
def test_a_no_results_page_is_not_found(code, page, monkeypatch):
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (200, page))
    r = lookup(code, "1234567" if code != "nmc" else "12A3456B", "Patel")
    assert r.outcome == "not_found" and r.page_hash != ""


# ---- the shared flow -----------------------------------------------------------------------

def test_lookup_matches_the_name_hashes_the_page_and_never_raises(monkeypatch):
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (200, GMC_CLEAR))
    r = lookup("gmc", "1234567", "Patel")
    assert r == Result("clear", "Registered with a licence to practise", "Priya Patel", r.page_hash)
    assert len(r.page_hash) == 64
    assert lookup("gmc", "1234567", "Khan").outcome == "name_mismatch"
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (503, "down"))
    r = lookup("gmc", "1234567", "Patel")
    assert r.outcome == "unreadable" and r.status_text == "HTTP 503"

    def boom(url, timeout=10):
        raise http.FetchError("timed out")
    monkeypatch.setattr(http, "get", boom)
    r = lookup("gmc", "1234567", "Patel")
    assert r.outcome == "unreadable" and r.status_text == "FetchError"

    def worse(url, timeout=10):
        raise RuntimeError("Priya Patel 1234567")
    monkeypatch.setattr(http, "get", worse)
    r = lookup("gmc", "1234567", "Patel")
    assert r.outcome == "unreadable" and r.status_text == "RuntimeError"    # the class, never the message


def test_a_hit_without_a_name_is_unreadable_not_a_match(monkeypatch):
    page = GMC_CLEAR.replace("<h1>Dr Priya Patel</h1>", "")
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (200, page))
    assert lookup("gmc", "1234567", "Patel").outcome == "unreadable"


def test_urls_carry_the_number_and_only_the_number():
    assert url("gmc", "1234567").endswith("1234567")
    for code, number in (("mpl_wales", "1234567"), ("nmc", "12A3456B"), ("gphc", "2012345")):
        assert number in url(code, number) and " " not in url(code, number)


# ---- captured pages ------------------------------------------------------------------------

def _captured():
    out = []
    for code in CODES:
        for page in sorted((FIXTURES / code).glob("*.html")) if (FIXTURES / code).exists() else []:
            out.append(pytest.param(code, page, id=f"{code}/{page.name}"))
    return out


@pytest.mark.parametrize("code,page", _captured())
def test_captured_fixtures_parse_as_their_file_name_says(code, page, monkeypatch):
    """A saved page is named for its outcome (clear.html, problem.html,
    not_found.html, …); a sidecar <stem>.surname holds the surname to match."""
    expected = page.stem.split("-")[0]
    surname = (page.with_suffix(".surname").read_text().strip() if page.with_suffix(".surname").exists()
               else "Patel")
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (200, page.read_text()))
    r = lookup(code, "1234567" if code != "nmc" else "12A3456B", surname)
    assert r.outcome == expected, r


def test_verified_means_the_clear_and_not_found_pages_are_captured(tmp_path, monkeypatch):
    import registers.adapters as adapters
    monkeypatch.setattr(adapters, "FIXTURES", tmp_path)
    assert not verified("gmc")
    (tmp_path / "gmc").mkdir()
    (tmp_path / "gmc" / "clear.html").write_text("x")
    assert not verified("gmc")
    (tmp_path / "gmc" / "not_found.html").write_text("x")
    assert verified("gmc")
