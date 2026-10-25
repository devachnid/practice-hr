"""The All Wales medical performers list (NHS Wales Shared Services
Partnership), searched by GMC number. A row for the number carries the name
and the status cell, which is classified like every other register's status:
exactly Included, Active or Current is clear, a suspension, condition or
any other problem stem is a problem, anything else is unreadable."""
from registers.adapters.base import classify, find, text_of  # noqa: F401

PUBLIC = "http://www.primarycareservices.wales.nhs.uk/all-wales-medical-performers-list?gmc="
NOT_FOUND = ("no performers match", "no records found")
CLEAR = ("Included", "Active", "Current")
PROBLEM = ("Suspended", "Conditional", "Conditions", "Removed")


def url(number):
    return f"{PUBLIC}{number}"


def parse(lines, number):
    rows = [i for i, line in enumerate(lines) if line.strip() == number]
    if rows:
        i = rows[0]
        name = lines[i + 1] if i + 1 < len(lines) else ""
        if "," in name:                       # the list writes "SURNAME, Given"
            last, first = name.split(",", 1)
            name = f"{first.strip()} {last.strip()}"
        status = lines[i + 2] if i + 2 < len(lines) else ""
        return classify(status, CLEAR, PROBLEM), status, name
    line, phrase = find(lines, NOT_FOUND)
    if phrase:
        return "not_found", line, ""
    return "unreadable", "", ""
