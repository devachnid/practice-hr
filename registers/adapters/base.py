"""What every adapter shares: HTML to plain lines, the status vocabulary
match, and the fetch → parse → name-check flow. An adapter supplies url()
and parse(lines, number); parse works on the page's text lines, never on markup, so a
change of layout that keeps the words still reads."""
import hashlib
import re
from html.parser import HTMLParser

from registers import http, names


class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "head"}
    BLOCK = {"p", "div", "li", "tr", "td", "th", "dt", "dd", "h1", "h2", "h3", "h4", "br", "table", "section"}

    def __init__(self):
        super().__init__()
        self.lines, self.buf, self.skip = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self._flush()

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK:
            self._flush()

    def handle_data(self, data):
        if not self.skip:
            self.buf.append(data)

    def _flush(self):
        line = re.sub(r"\s+", " ", "".join(self.buf)).strip()
        if line:
            self.lines.append(line)
        self.buf = []

    def close(self):
        super().close()
        self._flush()


def text_of(html):
    """The page as a list of non-empty text lines, block by block."""
    p = _Text()
    p.feed(html)
    p.close()
    return p.lines


def has_word(value, phrase):
    """Whether `phrase` occurs in `value` as whole words, case-insensitively."""
    return re.search(r"\b" + re.escape(phrase) + r"\b", value, re.I) is not None


def find(lines, phrases):
    """The first (line, phrase) whose line contains the phrase, case-insensitively; else (None, None)."""
    for line in lines:
        low = line.lower()
        for phrase in phrases:
            if phrase.lower() in low:
                return line, phrase
    return None, None


def status_value(lines, labels):
    """The value of a labelled field: for the first line that starts with
    one of `labels` (whole words, any case), the rest of that line after
    the label and an optional colon or, if nothing follows, the next line.
    "" when no line carries a label. Status is read only from here, never
    from wording elsewhere on the page (a footer's "Terms and conditions"
    is not a condition on a registration)."""
    for i, line in enumerate(lines):
        for label in labels:
            m = re.match(r"\s*" + re.escape(label) + r"\b\s*:?\s*(.*)", line, re.I)
            if m:
                value = m.group(1).strip()
                if not value and i + 1 < len(lines):
                    value = lines[i + 1]
                return value
    return ""


def classify(value, clear, problem):
    """clear, problem or unreadable for a status value, on whole words:
    a problem phrase first, then a clear phrase, and a value with "not" or
    "without" in it is never clear."""
    if any(has_word(value, p) for p in problem):
        return "problem"
    if any(has_word(value, c) for c in clear):
        return "problem" if has_word(value, "not") or has_word(value, "without") else "clear"
    return "unreadable"


_NAME = re.compile(r"[A-Za-z\u00c0-\u024f'.\-]+(?: [A-Za-z\u00c0-\u024f'.\-]+)+")
_FURNITURE = {"home", "search", "register", "menu", "login", "contact", "skip"}   # navigation, not a name


def name_near(lines, marker, titles=("Dr", "Professor", "Mr", "Mrs", "Ms", "Miss", "Mx")):
    """The person's name: the line before the first line matching the
    compiled regex `marker` (the number's label), stripped of a leading
    title. "" unless it looks like a name (two or more words of letters, at
    most 80 characters, no navigation words), so page furniture is never
    taken for one."""
    for i, line in enumerate(lines):
        if marker.search(line):
            if i == 0:
                return ""
            candidate = lines[i - 1].strip()
            for t in titles:
                if candidate.startswith(t + " "):
                    candidate = candidate[len(t) + 1:].strip()
                    break
            if len(candidate) > 80 or not _NAME.fullmatch(candidate):
                return ""
            if any(w.lower() in _FURNITURE for w in candidate.split()):
                return ""
            return candidate
    return ""


def run(url, parse, number, surname):
    """Fetch the page, parse it, check the name. Returns a Result; never
    raises (an unexpected error is an unreadable result naming its class)."""
    from registers.adapters import Result
    try:
        status, body = http.get(url)
    except http.FetchError:
        return Result("unreadable", "FetchError", "", "")
    except Exception as exc:  # noqa: BLE001 - the class only; the message may carry the number or a name
        return Result("unreadable", exc.__class__.__name__, "", "")
    if status != 200:
        return Result("unreadable", f"HTTP {status}", "", "")
    page_hash = hashlib.sha256(body.encode("utf-8", "replace")).hexdigest()
    try:
        outcome, status_text, name = parse(text_of(body), number)
    except Exception as exc:  # noqa: BLE001 - as above
        return Result("unreadable", exc.__class__.__name__, "", page_hash)
    if outcome in ("clear", "problem"):
        if not name:
            return Result("unreadable", "name not found on the page", "", page_hash)
        if not names.surnames_match(name, surname):
            outcome = "name_mismatch"
    return Result(outcome, status_text[:200], name[:120], page_hash)
