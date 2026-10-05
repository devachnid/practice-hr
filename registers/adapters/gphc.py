"""The GPhC's public register search by registration number. Clear is
"Registered" with no conditions or interim order."""
from registers.adapters.base import find, name_near, text_of  # noqa: F401

PUBLIC = "https://www.pharmacyregulation.org/registers/pharmacist/registrationnumber/"
NOT_FOUND = ("no results", "returned no results", "not found", "no match")
CLEAR = ("Registered",)
PROBLEM = ("Suspended", "Removed", "Conditions", "Interim order", "Not registered", "Lapsed")


def url(number):
    return f"{PUBLIC}{number}"


def parse(lines):
    line, phrase = find(lines, NOT_FOUND)
    if phrase:
        return "not_found", line, ""
    name = name_near(lines, "Registration number")
    line, phrase = find(lines, PROBLEM)
    if phrase:
        return "problem", line, name
    line, phrase = find(lines, CLEAR)
    if phrase:
        return "clear", line, name
    return "unreadable", "", ""
