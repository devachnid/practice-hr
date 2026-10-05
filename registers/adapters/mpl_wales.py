"""The All Wales medical performers list (NHS Wales Shared Services
Partnership), searched by GMC number. Clear is a row for the number whose
status is not suspended or conditional."""
from registers.adapters.base import find, text_of  # noqa: F401

PUBLIC = "http://www.primarycareservices.wales.nhs.uk/all-wales-medical-performers-list?gmc="
NOT_FOUND = ("no performers match", "no results", "no records found", "not found")
PROBLEM = ("Suspended", "Conditional", "Conditions", "Removed")


def url(number):
    return f"{PUBLIC}{number}"


def parse(lines, number):
    line, phrase = find(lines, NOT_FOUND)
    if phrase:
        return "not_found", line, ""
    rows = [i for i, line in enumerate(lines) if line.strip() == number]
    if not rows:
        return "unreadable", "", ""
    i = rows[0]
    name = lines[i + 1] if i + 1 < len(lines) else ""
    if "," in name:                       # the list writes "SURNAME, Given"
        last, first = name.split(",", 1)
        name = f"{first.strip()} {last.strip()}"
    status = lines[i + 2] if i + 2 < len(lines) else ""
    _, phrase = find([status], PROBLEM)
    return ("problem" if phrase else "clear"), status, name
