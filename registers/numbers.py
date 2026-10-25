"""Registration number formats, refused on the form and by the service
before anything is sent to a register. The Welsh medical performers list
is keyed by the GMC number, so it shares that format and that field."""
import re

from django.core.exceptions import ValidationError

# body code -> (regex, the format in words)
FORMATS = {
    "gmc": (r"[0-9]{7}\Z", "seven digits"),
    "nmc": (r"[0-9]{2}[A-Z][0-9]{4}[A-Z]\Z", "two digits, a letter, four digits and a letter"),
    "gphc": (r"[0-9]{7}\Z", "seven digits"),
}
SHARES_NUMBER_WITH = {"mpl_wales": "gmc"}
FORMATS["mpl_wales"] = FORMATS["gmc"]
MAX_LENGTH = 20


def normalise(value):
    """Whitespace out, letters upper-cased; "" for blank."""
    return re.sub(r"\s+", "", value or "").upper()


def check(code, value):
    """Raise unless `value` (already normalised) is in the body's format."""
    regex, words = FORMATS[code]
    if not re.match(regex, value):
        raise ValidationError(f"A {label(code)} number is {words}.", code="format")


def label(code):
    return {"gmc": "GMC", "mpl_wales": "GMC", "nmc": "NMC PIN", "gphc": "GPhC"}[code]
