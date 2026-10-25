"""Unfold admin over training. Courses are set up here (the titles that
need each, or everyone). Records are append-only: the add page is the
record form (training.record); an existing row is shown read-only but for
the expiry of a verified record (training.set_expiry), never deleted, and
a pending one has two actions through the service: Verify and Reject.
Sessions: the add page records a group (sessions.record_session); a row is
read-only. Files download through documents:download (files.open, audited)."""
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from unfold.admin import ModelAdmin
from unfold.decorators import action

from people.services import access
from training.admin_forms import AdminRecordForm, AdminRejectForm, AdminSessionForm
from training.models import Course, TrainingRecord, TrainingSession
from training.services import sessions, training

SHOWN = ("employee", "course", "done_on", "expires_on", "note", "session", "recorded_by", "recorded_at",
         "verified_by", "verified_at", "rejected_at", "rejected_note")
SESSION_SHOWN = ("course", "held_on", "trainer", "note", "recorded_by", "recorded_at")


def _file_link(file):
    if file is None:
        return "-"
    return format_html('<a href="{}">{}</a>', reverse("documents:download", args=[file.pk]), file.original_name)


@admin.register(Course)
class CourseAdmin(ModelAdmin):
    list_display = ("name", "delivery", "validity_months", "everyone", "active")
    list_editable = ("active",)
    list_filter = ("delivery", "everyone", "active")
    filter_horizontal = ("positions",)

    def get_readonly_fields(self, request, obj=None):
        # the services and the reminder keys name a course by its code:
        # settable when a course is added, never changed after
        fields = tuple(super().get_readonly_fields(request, obj))
        return fields + ("code",) if obj is not None else fields

    def has_delete_permission(self, request, obj=None):
        return False                      # make it inactive instead: records point at it


class StatusFilter(admin.SimpleListFilter):
    title = "status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return [("pending", "Awaiting verification"), ("verified", "Verified"), ("rejected", "Rejected")]

    def queryset(self, request, queryset):
        if self.value() == "pending":
            return queryset.filter(verified_at__isnull=True, rejected_at__isnull=True)
        if self.value() == "verified":
            return queryset.filter(verified_at__isnull=False, rejected_at__isnull=True)
        if self.value() == "rejected":
            return queryset.filter(rejected_at__isnull=False)
        return queryset


class _Refusable:
    """A service refusal at save is a message and a redirect back, not a 500."""

    def log_addition(self, request, obj, message):
        if getattr(request, "_training_not_saved", False):
            return None
        return super().log_addition(request, obj, message)

    def log_change(self, request, obj, message):
        if getattr(request, "_training_not_saved", False):
            return None
        return super().log_change(request, obj, message)

    def response_add(self, request, obj, post_url_continue=None):
        if getattr(request, "_training_not_saved", False):
            return HttpResponseRedirect(request.path)
        return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        if getattr(request, "_training_not_saved", False):
            return HttpResponseRedirect(request.path)
        return super().response_change(request, obj)

    def _refuse(self, request, error):
        request._training_not_saved = True
        messages.error(request, " ".join(error.messages))

    def _page(self, request, template, title, **ctx):
        return render(request, template, {**self.admin_site.each_context(request), "title": title,
                                          "opts": self.model._meta, **ctx})


@admin.register(TrainingRecord)
class TrainingRecordAdmin(_Refusable, ModelAdmin):
    list_display = ("employee", "course", "done_on", "expires_on", "state")
    list_filter = ("course", StatusFilter)
    search_fields = ("employee__first_name", "employee__last_name", "employee__preferred_name")
    list_select_related = ("employee", "course")
    actions_detail = ["verify_record", "reject_record"]

    @admin.display(description="State")
    def state(self, obj):
        return "Awaiting verification" if obj.pending else "Rejected" if obj.rejected else "Verified"

    @admin.display(description="Certificate")
    def certificate_link(self, obj):
        return _file_link(obj.certificate)

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs["form"] = AdminRecordForm
        return super().get_form(request, obj, **kwargs)

    def get_fields(self, request, obj=None):
        if obj is None:
            return list(AdminRecordForm.base_fields)
        return [*SHOWN, "state", "certificate_link"]

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        editable = {"expires_on"} if obj.counts else set()
        return tuple(f for f in (*SHOWN, "state", "certificate_link") if f not in editable)

    def has_change_permission(self, request, obj=None):
        # a pending or rejected record counts for nothing, so there is nothing
        # on it to change: it is view-only, with Verify / Reject beside it
        return obj is None or obj.counts

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change and "expires_on" not in form.cleaned_data:
            return                          # nothing editable was on the form
        # never obj.save(): the service validates, defaults the expiry, audits
        # and stores an upload last
        d = form.cleaned_data
        try:
            with transaction.atomic():
                if change:
                    training.set_expiry(request.user, TrainingRecord.objects.get(pk=obj.pk), d["expires_on"])
                else:
                    r = training.record(request.user, d["employee"], d["course"], d["done_on"],
                                        upload=d.get("upload") or None, expires_on=d["expires_on"], note=d["note"])
                    obj.pk = r.pk
        except ValidationError as e:
            self._refuse(request, e)

    # ---- actions ---------------------------------------------------------

    def has_verify_permission(self, request, object_id=None):
        r = TrainingRecord.objects.filter(pk=object_id).select_related("employee").first()
        return r is not None and r.pending and access.may_verify(request.user, r)

    @action(description="Verify", url_path="verify", permissions=["verify"])
    def verify_record(self, request, object_id):
        """GET asks; only the POST verifies (training.verify)."""
        record = get_object_or_404(TrainingRecord.objects.select_related("employee", "course"), pk=object_id)
        if request.method == "POST":
            try:
                training.verify(request.user, record)
            except ValidationError as e:
                messages.error(request, " ".join(e.messages))
            else:
                messages.success(request, f"{record}: verified.")
            return HttpResponseRedirect(reverse("admin:training_trainingrecord_change", args=[record.pk]))
        return self._page(request, "training/admin/verify.html", f"Verify: {record}", record=record)

    @action(description="Reject", url_path="reject", permissions=["verify"])
    def reject_record(self, request, object_id):
        """GET asks why; the POST rejects (training.reject, which emails the person)."""
        record = get_object_or_404(TrainingRecord.objects.select_related("employee", "course"), pk=object_id)
        form = AdminRejectForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            try:
                training.reject(request.user, record, form.cleaned_data["note"])
            except ValidationError as e:
                form.add_error(None, e.messages)
            else:
                messages.success(request, f"{record}: turned down; {record.employee} has been told why.")
                return HttpResponseRedirect(reverse("admin:training_trainingrecord_change", args=[record.pk]))
        return self._page(request, "training/admin/reject.html", f"Reject: {record}", record=record, form=form)


@admin.register(TrainingSession)
class TrainingSessionAdmin(_Refusable, ModelAdmin):
    list_display = ("course", "held_on", "trainer", "attended")
    list_filter = ("course",)
    list_select_related = ("course",)

    @admin.display(description="Attended")
    def attended(self, obj):
        return obj.records.count()

    @admin.display(description="Who attended")
    def attendees(self, obj):
        rows = obj.records.select_related("employee").order_by("employee__last_name", "employee__first_name")
        if not rows:
            return "-"
        return format_html_join(", ", '<a href="{}">{}</a>',
                                ((reverse("admin:training_trainingrecord_change", args=[r.pk]), r.employee.name)
                                 for r in rows))

    @admin.display(description="Attendance sheet")
    def sheet_link(self, obj):
        return _file_link(obj.attendance_sheet)

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs["form"] = AdminSessionForm
        return super().get_form(request, obj, **kwargs)

    def get_fields(self, request, obj=None):
        if obj is None:
            return list(AdminSessionForm.base_fields)
        return [*SESSION_SHOWN, "attendees", "sheet_link"]

    def get_readonly_fields(self, request, obj=None):
        return () if obj is None else (*SESSION_SHOWN, "attendees", "sheet_link")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        d = form.cleaned_data
        try:
            with transaction.atomic():
                s = sessions.record_session(request.user, d["course"], d["held_on"], list(d["attendees"]),
                                            trainer=d["trainer"], note=d["note"], upload=d.get("upload") or None)
        except ValidationError as e:
            self._refuse(request, e)
            return
        obj.pk = s.pk
