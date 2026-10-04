"""The reminder settings: one row, edited in place. The list goes straight
to it; it cannot be added to or deleted."""
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from unfold.admin import ModelAdmin

from compliance.models import ReminderSchedule


@admin.register(ReminderSchedule)
class ReminderScheduleAdmin(ModelAdmin):
    fields = ("start_days_before", "every_days_before", "every_days_overdue")

    def changelist_view(self, request, extra_context=None):
        row = ReminderSchedule.get()
        return HttpResponseRedirect(reverse("admin:compliance_reminderschedule_change", args=[row.pk]))

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
