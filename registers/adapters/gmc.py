"""The GMC's public register: one page per doctor at /doctors/<number>.

The page (as captured in November 2026) carries no field labels: the
doctor's name sits a few lines above "GMC reference number:", the number is
on the next line, the registration status is the bare line after that
("Registered with a licence to practise"), then "This doctor is on the GP
Register" or "This doctor is not on the GP Register". Clear is exactly a
CLEAR status, on the GP Register, and no restriction field (fitness to
practise, conditions, undertakings, warnings) with a value among the
details below the number; the site's menus above the name are never read
(one says "Fitness to Practise Liaison Service"). An older labelled layout
("Registration status: …", "GP Register: …") is read as before when the
page has no such anchor. A page with neither, and no no-results wording, is
unreadable, never not found. The one exception is the reply itself: a
number that is not on the register answers HTTP 404 (NOT_FOUND_STATUSES),
which is not found."""
import re

from registers.adapters.base import (  # noqa: F401 - text_of re-exported for the tests
    PROBLEM_STEMS, as_name, classify, find, name_near, plain, restriction, status_value, text_of)

PUBLIC = "https://www.gmc-uk.org/doctors/"
NOT_FOUND = ("no results were found", "could not find a doctor", "no doctor found")
NOT_FOUND_STATUSES = (404,)
LABELS = ("Registration status",)
GP_LABELS = ("GP Register",)
GP_REGISTER_CLEAR = ("Yes", "On the GP Register", "GP Register", "Included")
GP_REGISTER_SINCE = "On the GP Register since"
RESTRICTION_LABELS = ("Fitness to practise", "Conditions", "Condition", "Undertakings", "Undertaking",
                      "Warnings", "Warning")
CLEAR = ("Registered with a licence to practise",)
PROBLEM = ("Registered without a licence", "Provisionally registered", "Suspended", "Erased", "Interim order",
           "Conditions", "Undertakings", "Administrative erasure", "Not registered")
NAME_MARKER = re.compile(r"\bGMC (reference )?number\b", re.I)
GP_SENTENCE = re.compile(r"\bThis doctor is (not )?on the GP Register\b", re.I)
HISTORY = re.compile(r"^Registrant history$", re.I)      # the details end where the history table begins
NAME_LINES_ABOVE = 4                                     # "Doctor" and an explanatory line sit between


def url(number):
    return f"{PUBLIC}{number}"


_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov",
           "dec")
_DATE = re.compile(r"(?:[0-9/.\- ]|" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")+\Z", re.I)


def on_gp_register(value):
    """The GP Register field read like a status: only a known positive is
    yes; missing or anything else is no. "On the GP Register since ..." is
    yes only when what follows "since" is a date and nothing more."""
    if plain(value) in {plain(c) for c in GP_REGISTER_CLEAR}:
        return True
    m = re.match(r"\s*" + re.escape(GP_REGISTER_SINCE) + r"\b(.*)\Z", value or "", re.I | re.S)
    if m is None:
        return False
    rest = m.group(1).strip()
    low = rest.lower() + " "
    return bool(rest) and _DATE.match(rest) is not None and not any(stem in low for stem in PROBLEM_STEMS)


def _details(lines, start):
    """The doctor's details: from the number's marker to the history table."""
    for j in range(start, len(lines)):
        if HISTORY.match(lines[j].strip()):
            return lines[start:j]
    return lines[start:]


def _name_above(lines, i):
    for k in range(i - 1, max(i - 1 - NAME_LINES_ABOVE, -1), -1):
        name = as_name(lines[k])
        if name:
            return name
    return ""


def _anchored(lines, number):
    """The register's own page layout, or None when the page is not laid
    out that way (no marker line of its own followed by the number)."""
    for i, line in enumerate(lines):
        if NAME_MARKER.search(line):
            break
    else:
        return None
    if i + 2 >= len(lines) or not lines[i + 1].strip().isdigit():
        return None
    if number and lines[i + 1].strip() != number:
        return "unreadable", "the page is for another number", ""
    status, name, details = lines[i + 2].strip(), _name_above(lines, i), _details(lines, i)
    outcome = classify(status, CLEAR, PROBLEM)
    if outcome == "clear":
        gp = next((m for m in (GP_SENTENCE.search(d) for d in details) if m), None)
        if gp is None or gp.group(1):
            return "problem", f"{status}; not on the GP Register", name
        label, restricted = restriction(details, RESTRICTION_LABELS)
        if label:
            return "problem", f"{status}; {label}: {restricted}", name
    return outcome, status, name


def parse(lines, number):
    anchored = _anchored(lines, number)
    if anchored is not None:
        return anchored
    value = status_value(lines, LABELS)
    if value:
        name = name_near(lines, NAME_MARKER)
        outcome = classify(value, CLEAR, PROBLEM)
        if outcome == "clear":
            if not on_gp_register(status_value(lines, GP_LABELS)):
                return "problem", f"{value}; not on the GP Register", name
            label, restricted = restriction(lines, RESTRICTION_LABELS)
            if label:
                return "problem", f"{value}; {label}: {restricted}", name
        return outcome, value, name
    line, phrase = find(lines, NOT_FOUND)
    if phrase:
        return "not_found", line, ""
    return "unreadable", "", ""
