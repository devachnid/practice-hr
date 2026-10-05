"""Register bodies (which titles need each; Unpause after a site change)
and the read-only lookup log. Bodies are code plus a seed: never added or
deleted here, made inactive instead."""
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from unfold.admin import ModelAdmin
from unfold.decorators import action

from registers.models import Lookup, RegisterBody
from registers.services import lookups


@admin.register(RegisterBody)
class RegisterBodyAdmin(ModelAdmin):
    list_display = ("name", "code", "active", "verified", "is_paused")
    list_editable = ("active",)
    filter_horizontal = ("positions",)
    fields = ("name", "code", "positions", "active", "display_order", "verified", "paused")
    readonly_fields = ("code", "verified", "paused")
    actions_detail = ["unpause"]

    @admin.display(description="Paused", boolean=True)
    def is_paused(self, obj):
        return obj.paused

    @admin.display(description="Paused")
    def paused(self, obj):
        return f"Since {obj.paused_at:%d %b %Y %H:%M}" if obj.paused else "No"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @action(description="Unpause", url_path="unpause", permissions=["change"])
    def unpause(self, request, object_id):
        """GET asks; only the POST unpauses (through lookups.unpause)."""
        body = get_object_or_404(RegisterBody, pk=object_id)
        if request.method == "POST":
            lookups.unpause(body)
            messages.success(request, f"{body} unpaused: its scheduled checks run again tonight.")
            return HttpResponseRedirect(reverse("admin:registers_registerbody_change", args=[body.pk]))
        return render(request, "registers/admin/unpause.html", {
            **self.admin_site.each_context(request), "title": f"Unpause: {body}",
            "opts": self.model._meta, "body": body})


@admin.register(Lookup)
class LookupAdmin(ModelAdmin):
    list_display = ("run_at", "person", "body", "outcome", "status_text", "trigger")
    list_filter = ("registration__body", "outcome", "trigger")
    search_fields = ("registration__employee__first_name", "registration__employee__last_name",
                     "registration__employee__preferred_name")
    list_select_related = ("registration__employee", "registration__body", "requested_by")
    readonly_fields = ("registration", "run_at", "trigger", "requested_by", "outcome", "status_text",
                       "name_on_register", "page_hash", "error")

    @admin.display(description="Person", ordering="registration__employee__last_name")
    def person(self, obj):
        return obj.registration.employee.name

    @admin.display(description="Body", ordering="registration__body__display_order")
    def body(self, obj):
        return obj.registration.body.name

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
