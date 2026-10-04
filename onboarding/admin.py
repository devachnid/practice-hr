"""Unfold admin over checklist templates and checklists.

Templates (and their items) are edited here: what a starter or leaver
checklist holds, who owns each item, when it is due and what closes it
automatically. Checklists are read-only here: they are made by the
employment services, and their items are closed, added and removed on the
HR checklist page through onboarding.services.checklists."""
from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from onboarding.models import Checklist, ChecklistItem, ChecklistTemplate, TemplateItem
from onboarding.services import checklists


class TemplateItemInline(TabularInline):
    model = TemplateItem
    fields = ("order", "title", "owner", "due_rule", "due_days", "link", "instruction")
    extra = 0


@admin.register(ChecklistTemplate)
class ChecklistTemplateAdmin(ModelAdmin):
    list_display = ("name", "kind", "titles", "active")
    list_filter = ("kind", "active")
    search_fields = ("name",)
    fields = ("kind", "name", "positions", "active")
    filter_horizontal = ("positions",)
    inlines = [TemplateItemInline]

    @admin.display(description="Titles")
    def titles(self, obj):
        return ", ".join(str(t) for t in obj.positions.all()) or "Default (any title without its own)"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("positions")


class ChecklistItemInline(TabularInline):
    model = ChecklistItem
    fields = ("title", "owner", "owner_employee", "due_on", "link", "state", "done_by", "done_at", "note")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Checklist)
class ChecklistAdmin(ModelAdmin):
    list_display = ("employment", "kind", "created_at", "completed_at", "progress", "has_gaps")
    list_filter = ("kind", "completed_at")
    search_fields = ("employment__employee__first_name", "employment__employee__last_name",
                     "employment__employee__preferred_name")
    list_select_related = ("employment__employee",)
    fields = ("employment", "kind", "template", "created_at", "created_by", "completed_at", "gaps")
    readonly_fields = fields
    inlines = [ChecklistItemInline]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("items")   # summary() reads them per row

    @admin.display(description="Done")
    def progress(self, obj):
        s = checklists.summary(obj)
        return f"{s['done']} of {s['total']}" + (f", {s['overdue']} overdue" if s["overdue"] else "")

    @admin.display(description="Gaps", boolean=True)
    def has_gaps(self, obj):
        return bool(checklists.gaps(obj))

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
