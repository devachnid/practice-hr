"""The All Wales medical performers list (NHS Wales Shared Services
Partnership). The public page is a search widget over a JSON endpoint; a
lookup posts the same search the page does, with the GMC number as the
search text, and reads the one row whose registration number is exactly
the number (the search itself matches substrings). The row's status cell
is classified like every other register's status: exactly Included, Active
or Current is clear, a suspension, condition or any other problem stem is a
problem, anything else is unreadable. No row for the number is not found.
The list writes names surname first ("Hodges Thomas Stephen"), so the
surname is moved to the end for the name check."""
import json

from registers import http
from registers.adapters.base import classify

PUBLIC = ("https://nwssp.nhs.wales/ourservices/primary-care-services/our-services/gp-services/"
          "all-wales-medical-performers-list-and-all-wales-locum-register/")
ENDPOINT = ("https://nwssp.nhs.wales/modules/collection/layouts/performersList/model/remote/performersList.cfc"
            "?method=getPerformersList")
# The page sends its health boards and performer types already percent-encoded; the endpoint expects that.
HEALTH_BOARDS = ("All,Aneurin%20Bevan%20LHB,Betsi%20Cadwaladr%20ULHB,Cardiff%20%26%20Vale%20LHB,"
                 "Cwm%20Taf%20Morgannwg%20HB,Hywel%20Dda%20LHB,Powys%20Teaching%20LHB,Swansea%20Bay%20ULHB")
PERFORMER_TYPES = "GP,GP%20Registrar"
CLEAR = ("Included", "Active", "Current")
PROBLEM = ("Suspended", "Conditional", "Conditions", "Removed")
RAW = True                      # parse() reads the JSON reply, not text lines
NUMBER, NAME, STATUS = 1, 2, 6  # the row's cells: [chevron, number, name, type, health board, approved, status, ...]


def url(number):
    """The public page: it has no address per number (the number goes in its search box)."""
    return PUBLIC


def fetch(number):
    """The search the page posts for `number`, restricted to GPs and GP registrars across every health board."""
    return http.post(ENDPOINT, {
        "draw": "1", "start": "0", "length": "10", "search[value]": number, "search[regex]": "false",
        "selectedLHB": HEALTH_BOARDS, "selectedTypeOfPerformer": PERFORMER_TYPES, "showLocumsOnly": "0"})


def _rows(body):
    """The reply is a JSON object, sent as a JSON string: decode twice when needed."""
    obj = json.loads(body)
    if isinstance(obj, str):
        obj = json.loads(obj)
    return obj["data"]


def _surname_last(name):
    """"Hodges Thomas Stephen" -> "Thomas Stephen Hodges": the list writes the surname first."""
    words = (name or "").split()
    return " ".join(words[1:] + words[:1]) if len(words) > 1 else (name or "")


def parse(body, number):
    rows = [r for r in _rows(body) if len(r) > STATUS and str(r[NUMBER]).strip() == number]
    if not rows:
        return "not_found", "no performer with this number", ""
    row = rows[0]
    status, name = str(row[STATUS]).strip(), _surname_last(str(row[NAME]).strip())
    return classify(status, CLEAR, PROBLEM), status, name
