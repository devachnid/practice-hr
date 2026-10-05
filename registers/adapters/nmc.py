"""The NMC's public register search by PIN. Clear is "Effective
registration" with no restriction, condition or order noted."""
from registers.adapters.base import find, name_near, text_of  # noqa: F401

PUBLIC = "https://www.nmc.org.uk/registration/search-the-register/?pin="
NOT_FOUND = ("no registrant found", "no results", "not found", "no match")
CLEAR = ("Effective registration", "Registered")
PROBLEM = ("Lapsed", "Suspended", "Struck off", "Conditions of practice", "Caution order", "Interim order",
           "Restriction", "Not registered")


def url(number):
    return f"{PUBLIC}{number}"


def parse(lines):
    line, phrase = find(lines, NOT_FOUND)
    if phrase:
        return "not_found", line, ""
    name = name_near(lines, "PIN")
    line, phrase = find(lines, PROBLEM)
    if phrase:
        return "problem", line, name
    line, phrase = find(lines, CLEAR)
    if phrase:
        return "clear", line, name
    return "unreadable", "", ""
