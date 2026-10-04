"""Unfold admin over stored files, policies and signatures.

Files are read-only: an HR admin adds a file on the add page
(documents.forms.UploadForm, saved by files.add) and downloads one through
documents:download (files.open, which audits). Files are never changed or
deleted here; a replacement supersedes.

A policy's title, titles and active flag are edited here; its versions are
listed read-only and a new one is added by the "Issue new version" action
(documents.forms.IssueForm, saved by policies.issue). Signatures are
read-only: only the person signs, on their own sign page."""
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action

from documents.forms import IssueForm, UploadForm
from documents.models import File, Policy, PolicyVersion, Signature
from documents.services import files, policies
from people.services import access

SHOWN = ("title", "employee", "category", "hr_only", "original_name", "content_type", "size", "sha256",
         "uploaded_by", "uploaded_at", "superseded_by", "superseded_note")


@admin.register(File)
class FileAdmin(ModelAdmin):
    list_display = ("title", "employee", "category", "uploaded_at", "hr_only")
    list_filter = ("category", "hr_only")
    search_fields = ("title", "employee__first_name", "employee__last_name", "employee__preferred_name")
    list_select_related = ("employee",)
    add_form = UploadForm

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs["form"] = self.add_form
        return super().get_form(request, obj, **kwargs)

    def get_fields(self, request, obj=None):
        if obj is None:
            return list(UploadForm.Meta.fields)
        return [*SHOWN, "download"]

    def get_readonly_fields(self, request, obj=None):
        return () if obj is None else (*SHOWN, "download")

    @admin.display(description="Download")
    def download(self, obj):
        return format_html('<a href="{}">{}</a>', reverse("documents:download", args=[obj.pk]), obj.original_name)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        # never obj.save(): the service sniffs, stores under an opaque name and audits
        data = form.cleaned_data
        stored = files.add(request.user, data["employee"], data["category"], data["title"], data["upload"],
                           hr_only=data["hr_only"])
        obj.pk = stored.pk


class PolicyVersionInline(TabularInline):
    model = PolicyVersion
    fields = ("label", "issued_on", "sign_within_days", "issued_by", "download")
    readonly_fields = fields
    extra = 0
    can_delete = False
    verbose_name_plural = "versions (newest first; the newest is the one people sign)"

    @admin.display(description="File")
    def download(self, obj):
        return format_html('<a href="{}">{}</a>', reverse("documents:download", args=[obj.file_id]),
                           obj.file.original_name)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Policy)
class PolicyAdmin(ModelAdmin):
    list_display = ("title", "current_version", "active")
    list_filter = ("active",)
    search_fields = ("title",)
    filter_horizontal = ("positions",)
    fields = ("title", "positions", "active")
    inlines = [PolicyVersionInline]
    actions_detail = ["issue_version"]

    @admin.display(description="Current version")
    def current_version(self, obj):
        v = policies.current(obj)
        return v.label if v else "-"

    def has_delete_permission(self, request, obj=None):
        return False                      # make it inactive instead: versions and signatures point at it

    def has_issue_permission(self, request, object_id=None):
        return access.can_view_restricted(request.user)

    @action(description="Issue new version", url_path="issue", permissions=["issue"])
    def issue_version(self, request, object_id):
        """The form, then policies.issue (which stores the file last)."""
        policy = get_object_or_404(Policy, pk=object_id)
        form = IssueForm(request.POST or None, request.FILES or None, policy=policy)
        if request.method == "POST" and form.is_valid():
            d = form.cleaned_data
            try:
                v = policies.issue(request.user, policy, d["label"], d["upload"], d["issued_on"],
                                   d["sign_within_days"])
            except ValidationError as e:
                form.add_error(None, e.messages)
            else:
                messages.success(request, f"{v} issued. Everyone it applies to is asked to sign it.")
                return HttpResponseRedirect(reverse("admin:documents_policy_change", args=[policy.pk]))
        return render(request, "documents/admin/issue.html", {
            **self.admin_site.each_context(request), "title": f"Issue a new version: {policy}",
            "opts": self.model._meta, "form": form, "policy": policy})


@admin.register(Signature)
class SignatureAdmin(ModelAdmin):
    list_display = ("employee", "version", "signed_at", "method")
    list_filter = ("method", "version__policy")
    search_fields = ("employee__first_name", "employee__last_name", "employee__preferred_name",
                     "version__policy__title")
    list_select_related = ("employee", "version__policy")
    fields = ("employee", "version", "signed_at", "method", "confirmation_text", "ip_address")
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
