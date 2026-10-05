"""The GMC's public register: one page per doctor at /doctors/<number>.
Clear is "Registered with a licence to practise" and on the GP Register.
Vocabulary from the GMC's status wording; a page with none of it is
unreadable, never not found."""
from registers.adapters.base import find, name_near, text_of  # noqa: F401 - text_of re-exported for the tests

PUBLIC = "https://www.gmc-uk.org/doctors/"
NOT_FOUND = ("no results were found", "no results found", "no doctor found", "not on the register",
             "could not find a doctor")
CLEAR = ("Registered with a licence to practise",)
PROBLEM = ("Registered without a licence", "Provisionally registered", "Suspended", "Erased", "Interim order",
           "Conditions", "Undertakings", "Administrative erasure", "Not registered")
GP_REGISTER = ("GP Register",)


def url(number):
    return f"{PUBLIC}{number}"


def parse(lines):
    line, phrase = find(lines, NOT_FOUND)
    if phrase:
        return "not_found", line, ""
    name = name_near(lines, "GMC number")
    line, phrase = find(lines, PROBLEM)
    if phrase:
        return "problem", line, name
    line, phrase = find(lines, CLEAR)
    if phrase:
        gp, _ = find(lines, GP_REGISTER)
        if gp is None:
            return "problem", f"{line}; not on the GP Register", name
        return "clear", line, name
    return "unreadable", "", ""
