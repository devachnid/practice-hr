"""The person's evidence upload on an awaiting check, from My record's
Checks card. The rules (own awaiting check, or HR on any) and the write are
checks.upload_evidence's; this page only reports the result."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from checks.models import Check
from checks.services import checks


@login_required
@require_POST
def upload(request, pk):
    check = get_object_or_404(Check.objects.select_related("check_type", "employee"), pk=pk)
    upload_ = request.FILES.get("file")
    if upload_ is None:
        messages.error(request, "Choose a file to upload.")
        return redirect("people:me")
    try:
        checks.upload_evidence(request.user, check, upload_)
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    else:
        messages.success(request, f"Uploaded. HR will record your {check.check_type} check.")
    return redirect("people:me")
