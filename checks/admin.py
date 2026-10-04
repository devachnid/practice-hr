"""Unfold admin over checks. Check types are set up here (the titles that
need each). Checks are append-only: the add page is the record form
(checks.record); an existing row is shown read-only, never changed or
deleted, and its two actions go through the service: "Ask the person for
evidence" (checks.ask) and, on an awaiting check, "Record the result"
(checks.complete). "Ask for evidence" on the list asks anyone for any type.
Evidence downloads through documents:download (files.open, audited)."""
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import action

from checks.forms import AskForm, CompleteForm, RecordForm
from checks.models import Check, CheckType
from checks.services import checks
from people.services import access, audit

SHOWN = ("employee", "check_type", "done_on", "expires_on", "outcome", "reference", "note", "dbs_level",
         "dbs_update_service", "awaiting", "recorded_by", "recorded_at")


@admin.register(CheckType)
class CheckTypeAdmin(ModelAdmin):
    list_display = ("name", "validity_months", "evidence", "remind_person", "active")
    list_editable = ("active",)
    filter_horizontal = ("positions",)

    def get_readonly_fields(self, request, obj=None):
        # the services look types up by code (dbs, right_to_work): settable
        # when a type is added, never changed after
        fields = tuple(super().get_readonly_fields(request, obj))
        return fields + ("code",) if obj is not None else fields

    def has_delete_permission(self, request, obj=None):
        return False                      # make it inactive instead: checks point at it


@admin.register(Check)
class CheckAdmin(ModelAdmin):
    list_display = ("employee", "check_type", "done_on", "expires_on", "outcome", "awaiting")
    list_filter = ("check_type", "outcome", "awaiting")
    search_fields = ("employee__first_name", "employee__last_name", "employee__preferred_name")
    list_select_related = ("employee", "check_type")
    add_form = RecordForm
    actions_list = ["ask_for_evidence"]
    actions_detail = ["ask_person", "record_result"]

    # ---- the add page is the record form; rows are read-only -------------

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs["form"] = self.add_form
        return super().get_form(request, obj, **kwargs)

    def get_fields(self, request, obj=None):
        if obj is None:
            return list(RecordForm.base_fields)
        return [*SHOWN, "evidence_link"]

    def get_readonly_fields(self, request, obj=None):
        return () if obj is None else (*SHOWN, "evidence_link")

    @admin.display(description="Evidence")
    def evidence_link(self, obj):
        if obj.evidence_id is None:
            return "-"
        return format_html('<a href="{}">{}</a>', reverse("documents:download", args=[obj.evidence_id]),
                           obj.evidence.original_name)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        # never obj.save(): the service validates, defaults the expiry, audits
        # and runs the hooks; an upload is stored last, through upload_evidence
        d = form.cleaned_data
        with transaction.atomic():
            c = checks.record(request.user, d["employee"], d["check_type"], d["done_on"], d["outcome"],
                              expires_on=d["expires_on"], reference=d["reference"], note=d["note"],
                              dbs_level=d["dbs_level"], dbs_update_service=d["dbs_update_service"])
            if d.get("upload"):
                checks.upload_evidence(request.user, c, d["upload"])
        obj.pk = c.pk

    def change_view(self, request, object_id, form_url="", extra_context=None):
        # an HR view of a person's check is audited, like their bank details
        if request.method == "GET":
            obj = self.get_object(request, object_id)
            if obj is not None and self.has_view_permission(request, obj):
                audit.viewed(request.user, obj, "check")
        return super().change_view(request, object_id, form_url, extra_context)

    # ---- actions ---------------------------------------------------------

    def has_ask_permission(self, request, object_id=None):
        if not access.can_view_restricted(request.user):
            return False
        if object_id is None:
            return True
        c = Check.objects.filter(pk=object_id).first()
        return c is not None and not Check.objects.filter(employee_id=c.employee_id, check_type_id=c.check_type_id,
                                                          awaiting=True).exists()

    def has_complete_permission(self, request, object_id=None):
        return (access.can_view_restricted(request.user)
                and Check.objects.filter(pk=object_id, awaiting=True).exists())

    def _page(self, request, template, title, **ctx):
        return render(request, template, {**self.admin_site.each_context(request), "title": title,
                                          "opts": self.model._meta, **ctx})

    def _ask(self, request, employee, check_type):
        try:
            c = checks.ask(request.user, employee, check_type)
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
            return None
        messages.success(request, f"{employee} has been asked for their {check_type} evidence. "
                                  f"They see it on My record.")
        return c

    @action(description="Ask for evidence", url_path="ask", permissions=["ask"])
    def ask_for_evidence(self, request):
        """Anyone, any type: a form, then checks.ask."""
        form = AskForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            c = self._ask(request, form.cleaned_data["employee"], form.cleaned_data["check_type"])
            if c is not None:
                return HttpResponseRedirect(reverse("admin:checks_check_change", args=[c.pk]))
        return self._page(request, "checks/admin/ask.html", "Ask for evidence", form=form, check=None)

    @action(description="Ask the person for evidence", url_path="ask-person", permissions=["ask"])
    def ask_person(self, request, object_id):
        """The same person, the same type (a renewal): confirm, then checks.ask."""
        check = get_object_or_404(Check.objects.select_related("employee", "check_type"), pk=object_id)
        if request.method != "POST":
            return self._page(request, "checks/admin/ask.html", f"Ask for evidence: {check}", form=None,
                              check=check)
        c = self._ask(request, check.employee, check.check_type)
        return HttpResponseRedirect(reverse("admin:checks_check_change", args=[(c or check).pk]))

    @action(description="Record the result", url_path="complete", permissions=["complete"])
    def record_result(self, request, object_id):
        """An awaiting check's result: the form, then checks.complete, and
        an upload (if any) through checks.upload_evidence, last."""
        check = get_object_or_404(Check.objects.select_related("employee", "check_type", "evidence"), pk=object_id)
        form = CompleteForm(request.POST or None, request.FILES or None, instance=check)
        if request.method == "POST" and form.is_valid():
            d = form.cleaned_data
            fresh = Check.objects.select_related("employee", "check_type").get(pk=check.pk)
            try:
                with transaction.atomic():
                    checks.complete(request.user, fresh, d["done_on"], d["outcome"], expires_on=d["expires_on"],
                                    reference=d["reference"], note=d["note"], dbs_level=d["dbs_level"],
                                    dbs_update_service=d["dbs_update_service"])
                    if d.get("upload"):
                        checks.upload_evidence(request.user, fresh, d["upload"])
            except ValidationError as e:
                form.add_error(None, e.messages)
            else:
                messages.success(request, f"{fresh}: recorded.")
                return HttpResponseRedirect(reverse("admin:checks_check_change", args=[fresh.pk]))
        return self._page(request, "checks/admin/complete.html", f"Record the result: {check}", form=form,
                          check=check)
