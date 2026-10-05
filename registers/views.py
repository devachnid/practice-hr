"""Check now: HR looks a registration up this minute. GET is a confirmation
page (a page never writes on GET); POST runs the lookup through
lookups.run, audits the view of the person's checks as the Compliance tab
does, and goes back to their page with the register's words."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from people.services import access, audit
from registers.models import Lookup, Registration
from registers.services import lookups

WORDS = {"clear": "{body}: {status} ({name})", "problem": "{body}: {status} ({name})",
         "not_found": "{body}: the number was not found on the register.",
         "name_mismatch": "{body}: the register shows {name}, not this person.",
         "unreadable": "{body}: the page could not be read ({status}). Try again later; if it keeps failing, "
                       "the register's page may have changed."}


@login_required
@require_http_methods(["GET", "POST"])
def check_now(request, pk):
    if not access.can_view_restricted(request.user):
        raise PermissionDenied
    reg = get_object_or_404(Registration.objects.select_related("employee", "body"), pk=pk)
    back = reverse("admin:people_employee_change", args=[reg.employee_id])
    if request.method == "GET":
        return render(request, "registers/check_now.html", {"registration": reg, "back": back})
    lk = lookups.run(reg, Lookup.Trigger.ON_DEMAND, request.user)
    audit.viewed(request.user, reg.employee, "checks")
    text = WORDS[lk.outcome].format(body=reg.body.name, status=lk.status_text, name=lk.name_on_register)
    if not reg.body.verified:
        text += " This register's parser is not yet verified: read the result with care."
    (messages.success if lk.outcome == "clear" else messages.warning)(request, text)
    return redirect(back)
