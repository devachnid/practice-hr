"""The one function that touches the network. Tests replace it; nothing
else in the app opens a connection. A fetch problem is a FetchError with a
short reason (no URL, no body): the caller records the class name only."""
import socket
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

TIMEOUT = 10
MAX_BYTES = 2_000_000          # a register page is far smaller; never read an unbounded reply


class FetchError(Exception):
    pass


def user_agent():
    site = settings.SITE_URL.rstrip("/")
    if site.startswith(("http://", "https://")):
        return f"PracticeHR/1.0 (+{site}; registration checks)"
    return "PracticeHR/1.0 (registration checks)"


def _text(reply):
    data = reply.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise FetchError("too large")      # never parse a page that was cut short
    return data.decode(reply.headers.get_content_charset() or "utf-8", "replace")


def get(url, timeout=TIMEOUT):
    """(HTTP status, body as text), for an error reply too: the GMC answers
    a number that is not on its register with a 404 and its own page.
    Raises FetchError when no reply came, or one larger than MAX_BYTES."""
    return _send(urllib.request.Request(url, headers={"User-Agent": user_agent(), "Accept": "text/html"}), timeout)


def post(url, data, timeout=TIMEOUT):
    """As get(), for a form POST: `data` is a dict of field -> value, sent
    urlencoded (the Welsh performers list answers a search this way)."""
    body = urllib.parse.urlencode(data).encode("ascii")
    headers = {"User-Agent": user_agent(), "Accept": "application/json, text/html",
               "Content-Type": "application/x-www-form-urlencoded"}
    return _send(urllib.request.Request(url, data=body, headers=headers, method="POST"), timeout)


def _send(request, timeout):
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:   # noqa: S310 - https URLs built by the adapters
            return reply.status, _text(reply)
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, _text(exc)
        except FetchError:
            raise
        except (OSError, ValueError):
            return exc.code, ""                 # an error reply whose body cannot be read: the status still can
    except (urllib.error.URLError, socket.timeout, OSError, ValueError) as exc:
        raise FetchError(exc.__class__.__name__) from None
