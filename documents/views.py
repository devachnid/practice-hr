"""The one download. The bytes come from files.open, which applies the
access rule and writes the audit row; anyone else gets 403."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_safe

from documents.models import File
from documents.services import files


@login_required
@require_safe
def download(request, pk):
    f = get_object_or_404(File, pk=pk)
    return files.open(request.user, f)
