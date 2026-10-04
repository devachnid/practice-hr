"""Unfold admin over stored files. Read-only: an HR admin adds a file on the
add page (documents.forms.UploadForm, saved by files.add) and downloads one
through documents:download (files.open, which audits). Files are never
changed or deleted here; a replacement supersedes."""
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from documents.forms import UploadForm
from documents.models import File
from documents.services import files

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
