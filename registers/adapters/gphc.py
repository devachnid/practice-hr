"""The GPhC's public register search by registration number. Clear is a
"Status" of exactly "Registered" with no condition or interim order in that field.
Status is read only from the labelled field; a page with none and no
result-specific no-results wording is unreadable."""
import re

from registers.adapters.base import classify, find, name_near, restriction, status_value, text_of  # noqa: F401

PUBLIC = "https://www.pharmacyregulation.org/registers/pharmacist/registrationnumber/"
NOT_FOUND = ("returned no results", "no results were found")
LABELS = ("Status", "Registration status")
RESTRICTION_LABELS = ("Conditions", "Condition", "Fitness to practise", "Sanctions", "Sanction")
CLEAR = ("Registered",)
PROBLEM = ("Suspended", "Removed", "Conditions", "Interim order", "Not registered", "Unregistered", "Lapsed")
NAME_MARKER = re.compile(r"\bRegistration number\b", re.I)


def url(number):
    return f"{PUBLIC}{number}"


def parse(lines, number):
    value = status_value(lines, LABELS)
    if value:
        outcome, name = classify(value, CLEAR, PROBLEM), name_near(lines, NAME_MARKER)
        if outcome == "clear":
            label, restricted = restriction(lines, RESTRICTION_LABELS)
            if label:
                return "problem", f"{value}; {label}: {restricted}", name
        return outcome, value, name
    line, phrase = find(lines, NOT_FOUND)
    if phrase:
        return "not_found", line, ""
    return "unreadable", "", ""
