"""The NMC's public register search by PIN. Clear is a "Registration
status" of "Effective registration" with no restriction, condition or order
in that field. Status is read only from the labelled field; a page with
none and no result-specific no-results wording is unreadable."""
import re

from registers.adapters.base import classify, find, name_near, status_value, text_of  # noqa: F401

PUBLIC = "https://www.nmc.org.uk/registration/search-the-register/?pin="
NOT_FOUND = ("no registrant found", "no results were found for")
LABELS = ("Registration status", "Status")
CLEAR = ("Effective registration", "Registered")
PROBLEM = ("Lapsed", "Suspended", "Struck off", "Conditions of practice", "Caution order", "Interim order",
           "Restriction", "Not registered", "Unregistered")
NAME_MARKER = re.compile(r"\bPIN\b")          # case-sensitive: "pin" is an ordinary word


def url(number):
    return f"{PUBLIC}{number}"


def parse(lines, number):
    value = status_value(lines, LABELS)
    if value:
        return classify(value, CLEAR, PROBLEM), value, name_near(lines, NAME_MARKER)
    line, phrase = find(lines, NOT_FOUND)
    if phrase:
        return "not_found", line, ""
    return "unreadable", "", ""
