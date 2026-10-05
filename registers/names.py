"""Loose surname matching: the register's spelling against the record's.
Case, accents, apostrophes, hyphens and spaces are ignored, and either part
of a double-barrelled surname on either side is enough. Never the preferred
name: the register shows legal names."""
import re
import unicodedata


def _parts(surname):
    text = unicodedata.normalize("NFKD", surname or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = text.replace("'", "").replace("’", "").replace(",", " ").replace(".", " ")
    return [p for p in re.split(r"[\s\-]+", text) if p]


def surnames_match(a, b):
    pa, pb = _parts(a), _parts(b)
    if not pa or not pb:
        return False
    if "".join(pa) == "".join(pb):
        return True
    return bool(set(pa) & set(pb))
