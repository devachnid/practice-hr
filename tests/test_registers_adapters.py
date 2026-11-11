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
    ("Grace Patel", "Grace", False),            # the given name is not a surname
    ("Luis De Souza", "De Silva", False),       # a particle alone is not a match
    ("Luis De Souza", "Souza", True),
    ("Priya Patel", "Patel", True),
    ("Priya Anne Patel", "Patel", True),
    ("Ian MacDonald", "Mac Donald", True),
    ("Mary Ann Lee", "Ann", False),             # a one-word surname is the register name's last word
    ("James Patel Smith", "Patel", False),
    ("Mary Ann Lee", "Lee", True),
    ("Priya Smith-Jones", "Smith", True),
    ("Priya Patel MBE", "Patel", True),         # post-nominals are not a surname
    ("Priya Patel FRCGP mrcp PhD", "Patel", True),
    ("Priya Patel MBE", "MBE", False),
])
def test_surnames_match_loosely_and_never_wrongly(a, b, expected):
    assert names.surnames_match(a, b) is expected


# ---- the network function --------------------------------------------------------------------

def test_the_user_agent_names_the_practice(settings):
    settings.SITE_URL = "https://hr.example.org/"
    assert http.user_agent() == "PracticeHR/1.0 (+https://hr.example.org; registration checks)"
    settings.SITE_URL = "/"
    assert http.user_agent() == "PracticeHR/1.0 (registration checks)"
    settings.SITE_URL = "httpfoo"
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


@pytest.mark.parametrize("size,ok", [(2_000_000, True), (2_000_001, False)])
def test_a_reply_over_two_megabytes_is_refused_not_cut_short(monkeypatch, size, ok):
    asked = []

    class Reply:
        status = 200

        class headers:
            @staticmethod
            def get_content_charset():
                return "utf-8"

        def read(self, amount=-1):
            asked.append(amount)
            return (b"x" * size)[:amount]

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False
    monkeypatch.setattr(http.urllib.request, "urlopen", lambda request, timeout: Reply())
    if ok:
        assert http.get("https://example.invalid/") == (200, "x" * size)
    else:
        with pytest.raises(http.FetchError, match="too large"):
            http.get("https://example.invalid/")
        r = lookup("gmc", "1234567", "Patel")
        assert r.outcome == "unreadable" and r.status_text == "FetchError"
    assert asked[0] == 2_000_001


# ---- parsers -------------------------------------------------------------------------------

GMC_CLEAR = """<html><body><h1>Dr Priya Patel</h1><p>GMC number: 1234567</p>
<dl><dt>Registration status</dt><dd>Registered with a licence to practise</dd>
<dt>GP Register</dt><dd>On the GP Register since 2015</dd></dl></body></html>"""
GMC_SUSPENDED = GMC_CLEAR.replace("Registered with a licence to practise", "Suspended")
GMC_NO_LICENCE = GMC_CLEAR.replace("Registered with a licence to practise", "Registered without a licence to practise")
GMC_NOT_GP = GMC_CLEAR.replace("<dt>GP Register</dt><dd>On the GP Register since 2015</dd>", "")
GMC_CONDITIONS = GMC_CLEAR.replace("Registered with a licence to practise",
                                   "Registered with a licence to practise, with Conditions on registration")
GMC_RESTRICTED = GMC_CLEAR.replace("</dl>", "<dt>Fitness to practise</dt><dd>Conditions on registration</dd></dl>")
GMC_RESTRICTION_NONE = GMC_CLEAR.replace("</dl>", "<dt>Fitness to practise</dt><dd>None</dd></dl>")
GMC_FOOTER = GMC_CLEAR.replace("</body>", "<footer><p>Terms and conditions</p></footer></body>")
GMC_NO_GP_VALUE = GMC_CLEAR.replace("On the GP Register since 2015", "Not on the GP Register")
GMC_NONE = "<html><body><h1>Search results</h1><p>No results were found for 1234567.</p></body></html>"
GMC_ODD = "<html><body><p>Something else entirely</p></body></html>"


@pytest.mark.parametrize("page,outcome,words", [
    (GMC_CLEAR, "clear", "Registered with a licence to practise"),
    (GMC_SUSPENDED, "problem", "Suspended"),
    (GMC_NO_LICENCE, "problem", "Registered without a licence"),
    (GMC_NOT_GP, "problem", "not on the GP Register"),
    (GMC_CONDITIONS, "problem", "Conditions"),
    (GMC_RESTRICTED, "problem", "Fitness to practise: Conditions on registration"),
    (GMC_RESTRICTION_NONE, "clear", "Registered with a licence to practise"),
    (GMC_NO_GP_VALUE, "problem", "not on the GP Register"),
    (GMC_FOOTER, "clear", "Registered with a licence to practise"),
    (GMC_NONE, "not_found", ""),
    (GMC_ODD, "unreadable", ""),
])
def test_gmc_parse(page, outcome, words):
    got, status, name = gmc.parse(gmc.text_of(page), "1234567")
    assert got == outcome and words in status
    if outcome in ("clear", "problem"):
        assert name == "Priya Patel"


def _mpl_reply(rows):
    """The endpoint's reply: a JSON object sent as a JSON string, one row per performer
    [chevron, number, name (surname first), type, health board, approved, status, locum, locum, ...]."""
    import json
    return json.dumps(json.dumps({"draw": 1, "recordsTotal": len(rows), "recordsFiltered": len(rows), "data": rows,
                                  "start": 0, "length": 10}))


def _mpl_row(number="1234567", name="Patel Priya Anne", status="Included"):
    return ["<span class='chevron-collapsable'></span>", number, name, "GP", "Cwm Taf Morgannwg HB", "06/03/2008",
            status, "", "", "1"]


MPL_PRESENT = _mpl_reply([_mpl_row()])
MPL_PRESENT_HTML_UNUSED = """<html><body><table><tr><th>GMC No</th><th>Name</th><th>Status</th></tr>
<tr><td>1234567</td><td>PATEL, Priya</td><td>Included</td></tr></table></body></html>"""
MPL_SUSPENDED = MPL_PRESENT.replace("Included", "Suspended")
MPL_NONE = _mpl_reply([])
MPL_SUBSTRING = _mpl_reply([_mpl_row(number="61234567")])          # the search matches substrings; the row must not
MPL_ODD_STATUS = MPL_PRESENT.replace("Included", "Awaiting review")
MPL_PENDING = MPL_PRESENT.replace("Included", "Pending review")


@pytest.mark.parametrize("page,outcome,words", [
    (MPL_PRESENT, "clear", "Included"),
    (MPL_SUSPENDED, "problem", "Suspended"),
    (MPL_NONE, "not_found", ""),
    (MPL_ODD_STATUS, "unreadable", ""),
    (MPL_PENDING, "problem", "Pending review"),
    (GMC_ODD, "unreadable", ""),
])
def test_mpl_wales_parse(page, outcome, words):
    got, status, name = mpl_wales.parse(page, "1234567")
    assert got == outcome and words in status
    if outcome in ("clear", "problem"):
        assert name == "Priya PATEL"


NMC_CLEAR = """<html><body><h2>Priya Patel</h2><p>PIN 12A3456B</p>
<p>Registration status: Effective registration</p><p>Registered nurse - Adult</p></body></html>"""
NMC_LAPSED = NMC_CLEAR.replace("Effective registration", "Lapsed")
NMC_CONDITIONS = NMC_CLEAR.replace("Effective registration", "Effective registration - Conditions of practice order")
NMC_RESTRICTED = NMC_CLEAR.replace("</body>", "<p>Conditions of practice: Must be supervised</p></body>")
NMC_RESTRICTION_NONE = NMC_CLEAR.replace("</body>", "<p>Restrictions: n/a</p></body>")
NMC_NO_STATUS_FIELD = "<html><body><p>Registered charity 123</p></body></html>"
NMC_NONE = "<html><body><p>No registrant found with the PIN 12A3456B.</p></body></html>"


@pytest.mark.parametrize("page,outcome,words", [
    (NMC_CLEAR, "clear", "Effective registration"),
    (NMC_LAPSED, "problem", "Lapsed"),
    (NMC_CONDITIONS, "problem", "Conditions"),
    (NMC_RESTRICTED, "problem", "Conditions of practice: Must be supervised"),
    (NMC_RESTRICTION_NONE, "clear", "Effective registration"),
    (NMC_NONE, "not_found", ""),
    (NMC_NO_STATUS_FIELD, "unreadable", ""),
    (GMC_ODD, "unreadable", ""),
])
def test_nmc_parse(page, outcome, words):
    got, status, name = nmc.parse(nmc.text_of(page), "12A3456B")
    assert got == outcome and words in status
    if outcome in ("clear", "problem"):
        assert name == "Priya Patel"


def test_mpl_wales_matches_the_number_exactly_and_puts_the_surname_last():
    got, status, name = mpl_wales.parse(MPL_PRESENT, "1234567")
    assert (got, status, name) == ("clear", "Included", "Priya Anne Patel")
    assert mpl_wales.parse(MPL_SUBSTRING, "1234567") == ("not_found", "no performer with this number", "")
    assert mpl_wales.parse(_mpl_reply([_mpl_row(name="Patel")]), "1234567")[2] == "Patel"
    import json
    with pytest.raises(json.JSONDecodeError):
        mpl_wales.parse("<html>not json</html>", "1234567")


def test_mpl_wales_posts_the_pages_own_search_and_links_to_the_public_page(monkeypatch):
    sent = []

    def post(url, data, timeout=10):
        sent.append((url, data))
        return 200, MPL_PRESENT
    monkeypatch.setattr(http, "post", post)
    monkeypatch.setattr(http, "get", lambda url, timeout=10: pytest.fail("the Welsh list is not fetched with GET"))
    r = lookup("mpl_wales", "1234567", "Patel")
    assert r.outcome == "clear" and r.name_on_register == "Priya Anne Patel" and len(r.page_hash) == 64
    [(sent_url, data)] = sent
    assert sent_url == mpl_wales.ENDPOINT and data["search[value]"] == "1234567"
    assert data["selectedTypeOfPerformer"] == "GP,GP%20Registrar" and data["showLocumsOnly"] == "0"
    assert data["selectedLHB"].startswith("All,") and "Powys%20Teaching%20LHB" in data["selectedLHB"]
    assert url("mpl_wales", "1234567") == mpl_wales.PUBLIC and "1234567" not in mpl_wales.PUBLIC
    assert lookup("mpl_wales", "1234567", "Khan").outcome == "name_mismatch"


def test_http_post_sends_a_urlencoded_form_and_reads_the_reply(monkeypatch):
    seen = {}

    class Reply:
        status = 200

        class headers:
            @staticmethod
            def get_content_charset():
                return "utf-8"

        def read(self, amount=-1):
            return b'"{\\"data\\":[]}"'

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def urlopen(request, timeout):
        seen.update(method=request.get_method(), data=request.data, url=request.full_url,
                    content_type=request.get_header("Content-type"), agent=request.get_header("User-agent"))
        return Reply()
    monkeypatch.setattr(http.urllib.request, "urlopen", urlopen)
    status, body = http.post("https://example.invalid/list?method=x", {"search[value]": "1234567", "a b": "c&d"})
    assert (status, body) == (200, '"{\\"data\\":[]}"')
    assert seen["method"] == "POST" and seen["url"] == "https://example.invalid/list?method=x"
    assert seen["data"] == b"search%5Bvalue%5D=1234567&a+b=c%26d"
    assert seen["content_type"] == "application/x-www-form-urlencoded" and seen["agent"].startswith("PracticeHR/1.0")


GPHC_CLEAR = """<html><body><h2>Priya Patel</h2><p>Registration number: 2012345</p>
<p>Status: Registered</p><p>Pharmacist</p></body></html>"""
GPHC_SUSPENDED = GPHC_CLEAR.replace("Registered", "Suspended")
GPHC_CONDITIONS = GPHC_CLEAR.replace("Registered", "Registered with Conditions")
GPHC_RESTRICTED = GPHC_CLEAR.replace("</body>", "<p>Conditions</p><p>Conditions apply to this registration</p></body>")
GPHC_RESTRICTION_NONE = GPHC_CLEAR.replace("</body>", "<p>Conditions: None</p></body>")
GPHC_UNREGISTERED = GPHC_CLEAR.replace("Registered", "Unregistered")
GPHC_NONE = "<html><body><p>Your search returned no results.</p></body></html>"


@pytest.mark.parametrize("page,outcome,words", [
    (GPHC_CLEAR, "clear", "Registered"),
    (GPHC_SUSPENDED, "problem", "Suspended"),
    (GPHC_CONDITIONS, "problem", "Conditions"),
    (GPHC_UNREGISTERED, "problem", "Unregistered"),
    (GPHC_RESTRICTED, "problem", "Conditions: Conditions apply to this registration"),
    (GPHC_RESTRICTION_NONE, "clear", "Registered"),
    (GPHC_NONE, "not_found", ""),
    (GMC_ODD, "unreadable", ""),
])
def test_gphc_parse(page, outcome, words):
    got, status, name = gphc.parse(gphc.text_of(page), "2012345")
    assert got == outcome and words in status
    if outcome in ("clear", "problem"):
        assert name == "Priya Patel"


@pytest.mark.parametrize("code,page", [("gmc", GMC_NONE), ("mpl_wales", MPL_NONE), ("nmc", NMC_NONE),
                                       ("gphc", GPHC_NONE)])
def test_a_no_results_page_is_not_found(code, page, monkeypatch):
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (200, page))
    monkeypatch.setattr(http, "post", lambda url, data, timeout=10: (200, page))
    r = lookup(code, "1234567" if code != "nmc" else "12A3456B", "Patel")
    assert r.outcome == "not_found" and r.page_hash != ""


# ---- the shared flow -----------------------------------------------------------------------

def test_an_http_error_reply_keeps_its_body_and_status(monkeypatch):
    """The GMC answers a number that is not on its register with a 404 and
    its own page: the body of an error reply is read, bounded as a 200's is."""
    import io
    import urllib.error
    from email.message import Message

    def raising(request, timeout):
        headers = Message()
        headers["Content-Type"] = "text/html; charset=utf-8"
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", headers, io.BytesIO(b"<p>No such doctor \xc3\xbc</p>"))
    monkeypatch.setattr(http.urllib.request, "urlopen", raising)
    assert http.get("https://www.gmc-uk.org/doctors/1234567") == (404, "<p>No such doctor \u00fc</p>")

    def huge(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", Message(), io.BytesIO(b"x" * (http.MAX_BYTES + 1)))
    monkeypatch.setattr(http.urllib.request, "urlopen", huge)
    with pytest.raises(http.FetchError, match="too large"):
        http.get("https://www.gmc-uk.org/doctors/1234567")


def test_a_404_is_not_found_for_the_gmc_and_unreadable_for_the_others(monkeypatch):
    from registers import adapters
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (404, "<h1>Page not found</h1>"))
    monkeypatch.setattr(http, "post", lambda url, data, timeout=10: (404, "<h1>Page not found</h1>"))
    r = lookup("gmc", "1234567", "Patel")
    assert r.outcome == "not_found" and r.status_text == "HTTP 404: no page for this number"
    assert len(r.page_hash) == 64 and r.name_on_register == ""
    for code, number in (("nmc", "12A3456B"), ("gphc", "2012345"), ("mpl_wales", "1234567")):
        r = lookup(code, number, "Patel")
        assert r.outcome == "unreadable" and r.status_text == "HTTP 404", code
    assert adapters.not_found_statuses("gmc") == (404,) and adapters.not_found_statuses("nmc") == ()


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


@pytest.mark.parametrize("code", CODES)
def test_a_page_that_is_neither_a_result_nor_a_not_found_page_is_unreadable(code, monkeypatch):
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (200, GMC_ODD))
    monkeypatch.setattr(http, "post", lambda url, data, timeout=10: (200, GMC_ODD))
    r = lookup(code, "1234567" if code != "nmc" else "12A3456B", "Patel")
    assert r.outcome == "unreadable" and r.page_hash != ""


def test_a_non_200_reply_carries_no_page_hash(monkeypatch):
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (503, "down"))
    assert lookup("gmc", "1234567", "Patel").page_hash == ""


def test_page_furniture_before_the_number_is_not_taken_for_a_name(monkeypatch):
    page = GMC_CLEAR.replace("<h1>Dr Priya Patel</h1>", "<p>Home Search Register</p>")
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (200, page))
    r = lookup("gmc", "1234567", "Patel")
    assert r.outcome == "unreadable" and r.name_on_register == ""


def test_the_name_is_the_line_just_before_the_number_not_the_top_of_the_page(monkeypatch):
    page = NMC_CLEAR.replace("<h2>", "<p>Home Search Register</p><h2>")
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (200, page))
    assert lookup("nmc", "12A3456B", "Patel").outcome == "clear"


def test_a_hit_without_a_name_is_unreadable_not_a_match(monkeypatch):
    page = GMC_CLEAR.replace("<h1>Dr Priya Patel</h1>", "")
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (200, page))
    assert lookup("gmc", "1234567", "Patel").outcome == "unreadable"


def test_a_problem_without_a_name_stays_a_problem(monkeypatch):
    page = GMC_SUSPENDED.replace("<h1>Dr Priya Patel</h1>", "")
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (200, page))
    r = lookup("gmc", "1234567", "Patel")
    assert (r.outcome, r.status_text, r.name_on_register) == ("problem", "Suspended", "")


def test_a_wrong_name_is_a_mismatch_only_when_a_name_was_found(monkeypatch):
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (200, GMC_SUSPENDED))
    assert lookup("gmc", "1234567", "Khan").outcome == "name_mismatch"
    assert lookup("gmc", "1234567", "Patel").outcome == "problem"
    page = GMC_SUSPENDED.replace("<h1>Dr Priya Patel</h1>", "")
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (200, page))
    assert lookup("gmc", "1234567", "Khan").outcome == "problem"


def test_urls_carry_the_number_and_only_the_number():
    assert url("gmc", "1234567").endswith("1234567")
    for code, number in (("nmc", "12A3456B"), ("gphc", "2012345")):
        assert number in url(code, number) and " " not in url(code, number)
    # the Welsh list has no page per number: On the register opens its search page
    assert url("mpl_wales", "1234567") == mpl_wales.PUBLIC


# ---- an unknown or qualified wording is never good news ----------------------------------------

def _page(code, status, extra=""):
    if code == "gmc":
        return GMC_CLEAR.replace("Registered with a licence to practise", status).replace("</dl>", extra + "</dl>")
    if code == "nmc":
        return NMC_CLEAR.replace("Effective registration", status)
    if code == "gphc":
        return GPHC_CLEAR.replace("<p>Status: Registered</p>", f"<p>Status: {status}</p>")
    return _mpl_reply([_mpl_row(status=status)])


NEVER_CLEAR = [
    ("nmc", "Effective registration - interim suspension order"),
    ("nmc", "Effective registration (under investigation)"),
    ("nmc", "Registered with restrictions"),
    ("gphc", "Registered (removal pending)"),
    ("gphc", "Registered - suspension"),
    ("gphc", "Registered, condition imposed"),
    ("gphc", "Previously registered"),
    ("mpl_wales", "Previously included"),
    ("mpl_wales", "Included - suspension pending"),
    ("gmc", "Registered with a licence to practise - suspension pending"),
    ("gmc", "Registered with a licence to practise; interim orders apply"),
]


@pytest.mark.parametrize("code,status", NEVER_CLEAR)
def test_a_qualified_status_is_never_clear(code, status, monkeypatch):
    module = {"gmc": gmc, "nmc": nmc, "gphc": gphc, "mpl_wales": mpl_wales}[code]
    number = "12A3456B" if code == "nmc" else "1234567"
    body = _page(code, status)
    got, words, _ = module.parse(body if getattr(module, "RAW", False) else module.text_of(body), number)
    assert got in ("problem", "unreadable") and status in words
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (200, body))
    monkeypatch.setattr(http, "post", lambda url, data, timeout=10: (200, body))
    assert lookup(code, number, "Patel").outcome == "problem"


@pytest.mark.parametrize("gp", ["No", "Suspended", "Removed 2024", "On the GP Register since 2010 - suspended",
                                "On the GP Register since 2010 (conditions)", "On the GP Register since",
                                "On the GP Register since 2010, under investigation"])
def test_a_gp_register_value_other_than_a_known_yes_is_a_problem(gp):
    page = GMC_CLEAR.replace("On the GP Register since 2015", gp)
    got, words, _ = gmc.parse(gmc.text_of(page), "1234567")
    assert got == "problem" and words == "Registered with a licence to practise; not on the GP Register"


@pytest.mark.parametrize("gp", ["Yes", "On the GP Register", "GP Register", "Included", "On the GP Register since 2015",
                                "yes.", "On the GP Register since 1 January 2010", "On the GP Register since 01/02/2010",
                                "On the GP Register since 1 Jan. 2010"])
def test_a_known_gp_register_value_stays_clear(gp):
    page = GMC_CLEAR.replace("On the GP Register since 2015", gp)
    assert gmc.parse(gmc.text_of(page), "1234567")[0] == "clear"


@pytest.mark.parametrize("code,page", [
    ("gmc", GMC_CLEAR.replace("</dl>", "<dt>Warning</dt><dd>Final warning issued</dd></dl>")),
    ("gmc", GMC_CLEAR.replace("</dl>", "<dt>Condition</dt><dd>Supervised practice</dd></dl>")),
    ("gmc", GMC_CLEAR.replace("</dl>", "<dt>Undertaking</dt><dd>Not to prescribe</dd></dl>")),
    ("nmc", NMC_CLEAR.replace("</body>", "<p>Restriction: Must be supervised</p></body>")),
    ("nmc", NMC_CLEAR.replace("</body>", "<p>Sanction: Caution order</p></body>")),
    ("gphc", GPHC_CLEAR.replace("</body>", "<p>Condition: Must be supervised</p></body>")),
    ("gphc", GPHC_CLEAR.replace("</body>", "<p>Sanction: Warning</p></body>")),
])
def test_a_restriction_label_matches_singular_and_plural(code, page):
    module = {"gmc": gmc, "nmc": nmc, "gphc": gphc}[code]
    got, words, _ = module.parse(module.text_of(page), "12A3456B" if code == "nmc" else "1234567")
    assert got == "problem" and ": " in words.split("; ", 1)[1]


def test_a_singular_warning_restriction_is_named_in_the_words():
    page = GMC_CLEAR.replace("</dl>", "<dt>Warning</dt><dd>Final warning issued</dd></dl>")
    assert gmc.parse(gmc.text_of(page), "1234567")[1] == \
        "Registered with a licence to practise; Warning: Final warning issued"


@pytest.mark.parametrize("value,expected", [
    ("Registered with a licence to practise", "clear"),
    ("  registered with a licence to practise. ", "clear"),
    ("Registered with a licence to practise, pending review", "problem"),
    ("Not registered", "problem"),
    ("Something new", "unreadable"),
])
def test_classify_is_clear_only_on_an_exact_phrase(value, expected):
    from registers.adapters.base import classify
    assert classify(value, gmc.CLEAR, gmc.PROBLEM) == expected


# ---- captured pages ------------------------------------------------------------------------

def _captured():
    out = []
    for code in CODES:
        folder = FIXTURES / code
        pages = [p for suffix in (".html", ".json") for p in folder.glob(f"*{suffix}")] if folder.exists() else []
        for page in sorted(pages):
            out.append(pytest.param(code, page, id=f"{code}/{page.name}"))
    return out


@pytest.mark.parametrize("code,page", _captured())
def test_captured_fixtures_parse_as_their_file_name_says(code, page, monkeypatch):
    """A saved page is named for its outcome (clear.html, problem.html,
    not_found.html, …); a sidecar <stem>.surname holds the surname to match and <stem>.number the number."""
    expected = page.stem.split("-")[0]
    surname = (page.with_suffix(".surname").read_text().strip() if page.with_suffix(".surname").exists()
               else "Patel")
    number_file = page.with_suffix(".number")
    number = number_file.read_text().strip() if number_file.exists() else ("1234567" if code != "nmc" else "12A3456B")
    status_file = page.with_suffix(".status")            # registers_fetch writes it for a not-found reply
    status = int(status_file.read_text().strip()) if status_file.exists() else 200
    monkeypatch.setattr(http, "get", lambda url, timeout=10: (status, page.read_text()))
    monkeypatch.setattr(http, "post", lambda url, data, timeout=10: (status, page.read_text()))
    r = lookup(code, number, surname)
    assert r.outcome == expected, r


def test_verified_means_the_clear_not_found_and_a_problem_page_are_captured(tmp_path, monkeypatch):
    import registers.adapters as adapters
    monkeypatch.setattr(adapters, "FIXTURES", tmp_path)
    assert not verified("gmc")
    (tmp_path / "gmc").mkdir()
    (tmp_path / "gmc" / "clear.html").write_text("x")
    assert not verified("gmc")
    (tmp_path / "gmc" / "not_found.html").write_text("x")
    assert not verified("gmc")                       # the problem path is the one that matters
    (tmp_path / "gmc" / "problem.surname").write_text("Patel")
    assert not verified("gmc")
    (tmp_path / "gmc" / "problem-suspended.html").write_text("x")
    assert verified("gmc")
    # the Welsh list saves JSON replies: the same stems with a .json suffix count
    (tmp_path / "mpl_wales").mkdir()
    for name in ("clear.json", "not_found.json", "problem.json"):
        (tmp_path / "mpl_wales" / name).write_text("{}")
    assert verified("mpl_wales")
