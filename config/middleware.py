import logging
import re
import secrets
import time
from urllib.parse import urlsplit

from django.conf import settings
from django.utils.cache import add_never_cache_headers

from accounts.client_ip import client_ip

access_log = logging.getLogger("hr.access")

# A password link's path is the credential until it is used: /reset/<uid>/<token>/.
_RESET_TOKEN = re.compile(r"^(/accounts/reset/)[^/]+/[^/]+/")


class RequestLogMiddleware:
    """One line per request to the journal: who (Cloudflare's address for
    them, and the account if signed in), what, and how it ended. Behind the
    tunnel gunicorn only ever sees 127.0.0.1, and Django logs nothing about
    ordinary requests, so without this there is no record to look back at
    after an incident.

    The path is logged without its query string, and a password link's
    token is replaced: the log must not become a place to collect working
    links from. (The OIDC endpoints carry their codes and tokens in query
    strings and bodies, never in the path.) Static files never reach here
    (WhiteNoise sits above)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.monotonic()
        response = self.get_response(request)
        user = getattr(request, "user", None)
        who = f"user={user.pk}" if user is not None and user.is_authenticated else "anon"
        path = _RESET_TOKEN.sub(r"\1<redacted>/", request.path)
        access_log.info("%s %s %s %s %s %dms", client_ip(request) or "-", who,
                        request.method, path, response.status_code,
                        (time.monotonic() - started) * 1000)
        return response



class PrivatePagesMiddleware:
    """Signed-in pages are not kept by the browser, and signing out clears
    what it kept.

    Practice HR is used on shared practice PCs. A page served with no
    Cache-Control could be shown again from the back button or history after
    the person who opened it had signed out: their record, their team, the
    Account page with their email. So every response to a signed-in request
    gets Django's never-cache headers (no-store, private) unless the view
    set its own policy — the OIDC provider's JWKS does. Static files never
    reach here: WhiteNoise answers them earlier in the stack.

    Signing out — the app's logout or the admin's — adds Clear-Site-Data:
    "cache", so a copy stored before this change, or by a browser that kept
    one anyway, goes too. Sits after AuthenticationMiddleware, which gives
    it request.user.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        signed_in = request.user.is_authenticated
        response = self.get_response(request)
        if signed_in and not response.has_header("Cache-Control"):
            add_never_cache_headers(response)
        if signed_in and not request.user.is_authenticated:
            response["Clear-Site-Data"] = '"cache"'
        return response


# No script runs but the app's own files: nothing inline, no eval, nothing
# from another origin. Styles may be inline — {% palette_css %} is a <style>
# block and the passkey cards start style="display:none" — which lets a
# style be injected but not a script. The nonce is for Cloudflare, not for
# us: the app has no inline script, but Cloudflare injects one (its bot
# detection) and stamps it with the nonce it finds in this header, which is
# the one way to allow that script without 'unsafe-inline'. Its follow-up
# script is under /cdn-cgi/ on this host, so 'self' covers it.
POLICY = "; ".join((
    "default-src 'self'",
    "script-src 'self' 'nonce-{nonce}'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'{relying_parties}",
    "frame-ancestors 'none'",
))


def _relying_party_origins():
    """The origins of the registered relying parties (the rota), for
    form-action. Browsers hold the redirects that follow a form post to
    form-action too, and two of this app's form posts end at a relying
    party: signing in (the login form, on to /o/authorize/, on to the
    rota's callback) and the provider's sign-out confirmation (on to the
    rota's login page). With 'self' alone, a person not already signed in
    here could never finish signing in to the rota."""
    if not settings.OAUTH2_PROVIDER.get("OIDC_ENABLED"):
        return ""
    from oauth2_provider.models import get_application_model
    origins = set()
    for row in get_application_model().objects.values_list(
            "redirect_uris", "post_logout_redirect_uris"):
        for uri in " ".join(row).split():
            parts = urlsplit(uri)
            if parts.scheme in ("http", "https") and parts.netloc:
                origins.add(f"{parts.scheme}://{parts.netloc}")
    return "".join(f" {origin}" for origin in sorted(origins))


class ContentSecurityPolicyMiddleware:
    """A Content-Security-Policy on every page the app renders, with a fresh
    nonce each time (request.csp_nonce).

    So an escaping bug somewhere in future — a name or a note rendered raw —
    lands as inert text rather than as a script running in a colleague's
    session. The admin is left out, as in the rota: django-unfold's pages run
    Alpine, which needs eval, and the admin is a smaller audience behind its
    own login. Only HTML carries the header; it governs documents, and JSON
    and static files need none.

    form-action is 'self' plus the registered relying parties' origins
    (_relying_party_origins, above), so the redirects that end a sign-in or
    a sign-out at the rota are not blocked.

    CSP_REPORT_ONLY=1 in /etc/practice-hr.env sends the same policy as
    Content-Security-Policy-Report-Only: the browser reports what it would
    have blocked, in its console, and blocks nothing. That is the way back
    if something the policy did not foresee breaks after a deploy, without
    a code change.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(18)
        response = self.get_response(request)
        if (request.path.startswith("/admin/")
                or not response.get("Content-Type", "").startswith("text/html")
                or response.has_header("Content-Security-Policy")):
            return response
        header = ("Content-Security-Policy-Report-Only" if settings.CSP_REPORT_ONLY
                  else "Content-Security-Policy")
        response[header] = POLICY.format(nonce=request.csp_nonce,
                                         relying_parties=_relying_party_origins())
        return response
