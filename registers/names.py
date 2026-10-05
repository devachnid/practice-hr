"""Loose surname matching: the register's name against the record's surname.
Case, accents, apostrophes and punctuation are ignored. The register shows a
full name ("Priya Patel"). A one-word surname on the record is compared
with the register name's last word only, so a middle name is never taken
for a surname; a surname of several words ("De Souza") is compared with
every word of the register name but the first (the given name). Either part
of a hyphenated surname matches, on either side; particles ("de", "van",
"al", ...) never match on their own. Never the preferred name:
the register shows legal names."""
import re
import unicodedata

PARTICLES = {"de", "van", "von", "der", "den", "da", "di", "la", "le", "du", "al", "el", "bin", "binti",
             "o", "mac", "mc"}


def _words(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = text.replace("'", "").replace("\u2019", "").replace(",", " ").replace(".", " ")
    return text.split()


def _tokens(words):
    return [t for w in words for t in re.split(r"-+", w) if t]


def _without_particles(tokens):
    kept = [t for t in tokens if t not in PARTICLES]
    return kept or tokens


def surnames_match(register_name, surname):
    register_words, record_words = _words(register_name), _words(surname)
    if len(record_words) == 1:
        register_words = register_words[-1:]           # a one-word surname: the register name's last word
    elif len(register_words) > 1:
        register_words = register_words[1:]            # the given name
    register, record = _tokens(register_words), _tokens(record_words)
    if not register or not record:
        return False
    if "".join(register) == "".join(record):
        return True
    register_kept, record_kept = _without_particles(register), _without_particles(record)
    return "".join(register_kept) == "".join(record_kept) or bool(set(register_kept) & set(record_kept))
