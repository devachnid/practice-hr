"""One adapter per register body: url(number) for the public page, parse()
-> (outcome, status_text, name), and optionally fetch(number) -> (status,
body) where the register is not a GET of that page (the Welsh list's search
endpoint), RAW when parse() wants the body rather than its text lines (a
JSON reply), and NOT_FOUND_STATUSES for a status that means "not on the
register" (the GMC's 404). lookup() is the only entry point the services
use; verified() says whether a body's parser has saved real replies to
test against (the fixtures folder and its README)."""
from dataclasses import dataclass
from pathlib import Path

from registers import http
from registers.adapters import base, gmc, gphc, mpl_wales, nmc

CODES = ("gmc", "mpl_wales", "nmc", "gphc")
MODULES = {"gmc": gmc, "mpl_wales": mpl_wales, "nmc": nmc, "gphc": gphc}
FIXTURES = Path(__file__).parent / "fixtures"
REQUIRED_FIXTURES = ("clear", "not_found")        # stems: saved as .html (a page) or .json (a reply)
FIXTURE_SUFFIXES = (".html", ".json")


@dataclass(frozen=True)
class Result:
    outcome: str            # clear | problem | not_found | name_mismatch | unreadable
    status_text: str        # the register's own words, or the error class
    name_on_register: str
    page_hash: str          # "" when nothing was fetched


def url(code, number):
    return MODULES[code].url(number)


def not_found_statuses(code):
    """The HTTP statuses that mean "not on the register" for a body (the GMC's 404); none for most."""
    return tuple(getattr(MODULES[code], "NOT_FOUND_STATUSES", ()))


def raw(code):
    """Whether the body's parse() takes the reply body itself (JSON) rather than its text lines."""
    return bool(getattr(MODULES[code], "RAW", False))


def fetch(code, number):
    """(HTTP status, body) for the number, as a lookup fetches it: the body's
    own fetch() where it has one, else a GET of its page for the number."""
    module = MODULES[code]
    if hasattr(module, "fetch"):
        return module.fetch(number)
    return http.get(module.url(number))


def lookup(code, number, surname):
    module = MODULES[code]
    return base.run(lambda: fetch(code, number), module.parse, number, surname, not_found_statuses(code),
                    raw=raw(code))


def _saved(folder, stem):
    return any((folder / f"{stem}{suffix}").exists() for suffix in FIXTURE_SUFFIXES)


def verified(code):
    """A clear reply, a not-found reply and at least one problem reply
    (problem*) are saved, as .html pages or .json replies."""
    folder = FIXTURES / code
    return (all(_saved(folder, stem) for stem in REQUIRED_FIXTURES)
            and any(p for suffix in FIXTURE_SUFFIXES for p in folder.glob(f"problem*{suffix}")))
