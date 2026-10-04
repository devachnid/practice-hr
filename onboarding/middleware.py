"""The pre-start gate. Before their start date a starter signs in to a
practice that has not taken them on yet: they see Getting started and what
it links to (their details, the policies and their downloads, their account
and passkeys) and nothing else. Anyone else, HR admins with no employee
record included, is never stopped here (access.is_pre_start).

Sits after AuthenticationMiddleware and axes' middleware, which give it
request.user."""
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from people.services import access

ALLOWED_PREFIXES = ("/onboarding/", "/documents/", "/accounts/", "/static/", "/admin/login/")


def pre_start(request):
    """Whether the signed-in person is a pre-start starter, once per request."""
    if not hasattr(request, "_pre_start"):
        user = getattr(request, "user", None)
        request._pre_start = bool(user is not None and user.is_authenticated
                                  and access.is_pre_start(user, timezone.localdate()))
    return request._pre_start


class PreStartGate:
    """Before their start date a starter sees Getting started (and the pages
    it links to) and nothing else."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(ALLOWED_PREFIXES) and pre_start(request):
            return redirect(reverse("onboarding:getting_started"))
        return self.get_response(request)
