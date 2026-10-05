"""One adapter per register body: url(number) for the public page and
parse(lines, number) -> (outcome, status_text, name). lookup() is the only
entry point the services use; verified() says whether a body's parser has
saved real pages to test against (the fixtures folder; its README arrives
with the capture command)."""
from dataclasses import dataclass
from pathlib import Path

from registers.adapters import base, gmc, gphc, mpl_wales, nmc

CODES = ("gmc", "mpl_wales", "nmc", "gphc")
MODULES = {"gmc": gmc, "mpl_wales": mpl_wales, "nmc": nmc, "gphc": gphc}
FIXTURES = Path(__file__).parent / "fixtures"
REQUIRED_FIXTURES = ("clear.html", "not_found.html")


@dataclass(frozen=True)
class Result:
    outcome: str            # clear | problem | not_found | name_mismatch | unreadable
    status_text: str        # the register's own words, or the error class
    name_on_register: str
    page_hash: str          # "" when nothing was fetched


def url(code, number):
    return MODULES[code].url(number)


def lookup(code, number, surname):
    module = MODULES[code]
    return base.run(module.url(number), module.parse, number, surname)


def verified(code):
    folder = FIXTURES / code
    return all((folder / name).exists() for name in REQUIRED_FIXTURES)
