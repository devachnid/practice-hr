"""The payroll changes report: HR admins list past runs and generate a month,
which downloads. The file is streamed from MEDIA_ROOT here; Django never
serves media."""

from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from absence.forms import PayrollPeriodForm
from absence.models import PayrollRun
from absence.services import payroll
from people.services import access

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@login_required
@require_http_methods(["GET", "POST"])
def payroll_view(request):
    if not access.can_view_restricted(request.user):
        raise PermissionDenied
    form = PayrollPeriodForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            start, end = payroll.month(form.cleaned_data["period"])
        except ValueError:
            form.add_error("period", "Not a month.")
        else:
            run = payroll.run(request.user, start, end)
            return FileResponse((Path(settings.MEDIA_ROOT) / run.path).open("rb"), as_attachment=True,
                                filename=Path(run.path).name, content_type=XLSX)
    runs = PayrollRun.objects.select_related("generated_by")[:50]
    return render(request, "absence/payroll.html", {"form": form, "runs": runs})
