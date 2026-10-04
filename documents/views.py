"""The download, and the person's policies: the list, and the sign page.

The download's bytes come from files.open, which applies the access rule
and writes the audit row; anyone else gets 403.

Signing re-authenticates here, every time, and policies.sign only records
how: the password typed again (recent_auth.confirm_password, through
authenticate(), so a wrong one counts towards the login lockout), or an
assertion from one of the signed-in person's own passkeys (checked as
theirs before it is verified; the options offer only theirs). A session left
signed in is not enough to sign, and neither is someone else's passkey. A
failed check writes nothing and shows the page again. The password is
never echoed, logged or kept."""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.signals import user_login_failed
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateformat import format as date_format
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods, require_POST, require_safe

from accounts import passkeys, recent_auth
from accounts.client_ip import client_ip
from documents.forms import SignForm
from documents.models import File, PolicyVersion, Signature
from documents.services import files, policies
from people.services import access

WRONG_PASSWORD = "That password is not right."
NO_PASSWORD = "Enter your password, or sign with a passkey."


@login_required
@require_GET          # not HEAD: each request is an audited view
def download(request, pk):
    f = get_object_or_404(File, pk=pk)
    return files.open(request.user, f)


@login_required
@require_safe
def policies_page(request):
    me = access.employee_for(request.user)
    rows = policies.state(me, timezone.localdate()) if me is not None else []
    return render(request, "documents/policies.html", {"employee": me, "rows": rows})


def _reauthenticate(request, form):
    """(method, "") if the signed-in person has just proved it is them;
    (None, the error to show) if not."""
    raw = request.POST.get("credential", "")
    if raw:
        try:
            credential = json.loads(raw)
        except ValueError:
            credential = None
        if not isinstance(credential, dict):
            return None, passkeys.MESSAGES["malformed"]
        try:
            # one of request.user's own passkeys, or refused before it is verified
            passkeys.verify_reauth(request, request.user, credential)
        except passkeys.PasskeyError as exc:
            if getattr(exc, "passkey", None) is not None:   # their own key, a bad assertion: as at the login page
                user_login_failed.send(sender=__name__, credentials={"username": request.user.email},
                                       request=request)
            return None, passkeys.MESSAGES[exc.code]
        return Signature.Method.PASSKEY, ""
    password = form.cleaned_data["password"]
    if not password:
        return None, NO_PASSWORD
    if not recent_auth.confirm_password(request, password):
        return None, WRONG_PASSWORD
    return Signature.Method.PASSWORD, ""


@login_required
@require_http_methods(["GET", "HEAD", "POST"])
@sensitive_post_parameters("password", "credential")
def sign(request, pk):
    """GET: the version, its Read link and the form. POST: the box ticked,
    the person re-authenticated, then policies.sign."""
    version = get_object_or_404(PolicyVersion.objects.select_related("policy", "file"), pk=pk)
    me = access.employee_for(request.user)
    today = timezone.localdate()
    if me is None or not policies.signable(me, version, today):
        raise Http404
    signed = Signature.objects.filter(employee=me, version=version).first()
    if signed is not None:
        when = date_format(timezone.localtime(signed.signed_at), "j M Y")
        messages.info(request, f"You signed {version} on {when}.")
        return redirect("documents:policies")
    form = SignForm(request.POST if request.method == "POST" else None, sentence=policies.confirmation(version))
    error = ""
    if request.method == "POST" and form.is_valid():
        method, error = _reauthenticate(request, form)
        if method is not None:
            try:
                policies.sign(request.user, version, method, client_ip(request))
            except ValidationError as e:       # signed meanwhile, in another tab
                messages.info(request, " ".join(e.messages))
            else:
                messages.success(request, f"Signed: {version}.")
            return redirect("documents:policies")
    return render(request, "documents/sign.html", {
        "version": version, "form": form, "error": error,
        "due_on": policies.due(version, me, today), "has_passkeys": request.user.passkeys.exists(),
    })


@login_required
@require_POST
def passkey_options(request):
    """The sign page's passkey button: a challenge for this session, offering
    only the signed-in person's own passkeys. POST, as the login page's: it
    writes the challenge to the session."""
    try:
        return JsonResponse(json.loads(passkeys.reauth_options(request, request.user)))
    except passkeys.PasskeyError as exc:
        return JsonResponse({"error": passkeys.MESSAGES[exc.code]}, status=400)
