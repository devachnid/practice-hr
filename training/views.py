"""The site's training pages. Every write is a service's (training,
sessions); a GET writes nothing. Recording your own (self_record) returns
to My record, or to Getting started before your first day."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from people.services import access
from training.forms import SelfRecordForm
from training.services import training


def _own_page(request):
    if access.is_pre_start(request.user, timezone.localdate()):
        return redirect("onboarding:getting_started")
    return redirect("people:me")


def _form_errors(form):
    return " ".join(e for errors in form.errors.values() for e in errors)


@login_required
@require_POST
def self_record(request):
    form = SelfRecordForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, _form_errors(form))
        return _own_page(request)
    d = form.cleaned_data
    try:
        training.self_record(request.user, d["course"], d["done_on"], upload=d.get("file") or None)
    except PermissionDenied:
        messages.error(request, "There is no employee record linked to your login yet. Ask the practice manager.")
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    else:
        messages.success(request, f"Recorded. HR or your manager will verify your {d['course']} training.")
    return _own_page(request)
