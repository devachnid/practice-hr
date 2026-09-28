import hmac
import logging
from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

log = logging.getLogger("hr.api")


def _valid(token):
    """Whether the token is one of HR_API_TOKENS. Every configured token is
    compared, in constant time, so the time taken says nothing about which
    of them a guess was close to. Bytes, because compare_digest refuses a
    str with a non-ASCII character in it."""
    given = token.encode()
    matched = False
    for known in settings.HR_API_TOKENS:
        matched |= hmac.compare_digest(given, known.encode())
    return matched


def token_required(view):
    """Only a request with `Authorization: Bearer <token>`, the token one of
    HR_API_TOKENS, reaches the view. No session, no CSRF: the rota is a
    server, not a signed-in person, so the view is exempt from
    CsrfViewMiddleware (nothing here reads the session or a cookie) and a
    wrong-method request reaches the JSON 405 rather than Django's CSRF page.
    The scheme is case-insensitive (RFC 7235). With no tokens configured nothing gets
    in. The refusal names no reason, and neither it nor anything here logs
    the header (config.middleware.RequestLogMiddleware logs the request line,
    without a query string or headers). Only GET, after the token: anything
    else is a JSON 405, not Django's HTML one.

    Every response leaves as `Cache-Control: no-store`: this is people's
    names, their addresses and when they are away."""
    @csrf_exempt
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        header = request.headers.get("Authorization", "")
        token = header[len("Bearer "):] if header[:7].lower() == "bearer " else ""
        if token and _valid(token):
            if request.method == "GET":
                response = view(request, *args, **kwargs)
            else:
                response = JsonResponse({"error": "method not allowed"}, status=405)
                response["Allow"] = "GET"
        else:
            log.warning("API request refused: %s %s", request.method, request.path)
            response = JsonResponse({"error": "unauthorised"}, status=401)
            response["WWW-Authenticate"] = "Bearer"
        response["Cache-Control"] = "no-store"
        return response
    return wrapped
