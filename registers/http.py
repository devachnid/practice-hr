"""The one function that touches the network. Tests replace it; nothing
else in the app opens a connection. A fetch problem is a FetchError with a
short reason (no URL, no body): the caller records the class name only."""
import socket
import urllib.error
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


def get(url, timeout=TIMEOUT):
    """(HTTP status, body as text). Raises FetchError when no reply came, or one larger than MAX_BYTES."""
    request = urllib.request.Request(url, headers={"User-Agent": user_agent(), "Accept": "text/html"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:   # noqa: S310 - https URLs built by the adapters
            data = reply.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise FetchError("too large")      # never parse a page that was cut short
            return reply.status, data.decode(reply.headers.get_content_charset() or "utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except (urllib.error.URLError, socket.timeout, OSError, ValueError) as exc:
        raise FetchError(exc.__class__.__name__) from None
