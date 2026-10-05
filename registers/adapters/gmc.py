"""The GMC's public register: one page per doctor at /doctors/<number>.
Clear is a "Registration status" of exactly "Registered with a licence to
practise", a "GP Register" entry that is exactly one of GP_REGISTER_CLEAR (or
"On the GP Register since ..."), and no restriction field (fitness to
practise, conditions, undertakings, warnings) with a value. Status is read only from
those labelled fields; a page with no status field and no result-specific
no-results wording is unreadable, never not found."""
import re

from registers.adapters.base import (  # noqa: F401 - text_of re-exported for the tests
    PROBLEM_STEMS, classify, find, name_near, plain, restriction, status_value, text_of)

PUBLIC = "https://www.gmc-uk.org/doctors/"
NOT_FOUND = ("no results were found", "could not find a doctor", "no doctor found")
LABELS = ("Registration status",)
GP_LABELS = ("GP Register",)
GP_REGISTER_CLEAR = ("Yes", "On the GP Register", "GP Register", "Included")
GP_REGISTER_SINCE = "On the GP Register since"
RESTRICTION_LABELS = ("Fitness to practise", "Conditions", "Condition", "Undertakings", "Undertaking",
                      "Warnings", "Warning")
CLEAR = ("Registered with a licence to practise",)
PROBLEM = ("Registered without a licence", "Provisionally registered", "Suspended", "Erased", "Interim order",
           "Conditions", "Undertakings", "Administrative erasure", "Not registered")
NAME_MARKER = re.compile(r"\bGMC number\b", re.I)


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


def parse(lines, number):
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
