"""The GMC's public register: one page per doctor at /doctors/<number>.
Clear is a "Registration status" of "Registered with a licence to practise",
a "GP Register" entry that is not a negative and no restriction field
(fitness to practise, conditions, undertakings, warnings) with a value. Status is read only from
those labelled fields; a page with no status field and no result-specific
no-results wording is unreadable, never not found."""
import re

from registers.adapters.base import (  # noqa: F401 - text_of re-exported for the tests
    classify, find, has_word, name_near, restriction, status_value, text_of)

PUBLIC = "https://www.gmc-uk.org/doctors/"
NOT_FOUND = ("no results were found", "could not find a doctor", "no doctor found")
LABELS = ("Registration status",)
GP_LABELS = ("GP Register",)
RESTRICTION_LABELS = ("Fitness to practise", "Conditions", "Undertakings", "Warnings")
CLEAR = ("Registered with a licence to practise",)
PROBLEM = ("Registered without a licence", "Provisionally registered", "Suspended", "Erased", "Interim order",
           "Conditions", "Undertakings", "Administrative erasure", "Not registered")
NAME_MARKER = re.compile(r"\bGMC number\b", re.I)


def url(number):
    return f"{PUBLIC}{number}"


def parse(lines, number):
    value = status_value(lines, LABELS)
    if value:
        name = name_near(lines, NAME_MARKER)
        outcome = classify(value, CLEAR, PROBLEM)
        if outcome == "clear":
            gp = status_value(lines, GP_LABELS)
            if not gp or has_word(gp, "not"):
                return "problem", f"{value}; not on the GP Register", name
            label, restricted = restriction(lines, RESTRICTION_LABELS)
            if label:
                return "problem", f"{value}; {label}: {restricted}", name
        return outcome, value, name
    line, phrase = find(lines, NOT_FOUND)
    if phrase:
        return "not_found", line, ""
    return "unreadable", "", ""
