"""Unfold admin over the absence models. Policy set-up is edited here; pots,
their ledger and absences are read-only, and the one action (recalculate)
goes through the ledger service."""

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from unfold.admin import ModelAdmin, TabularInline

from absence.models import (Absence, AbsenceType, BankHoliday, ClosedDay, LedgerEntry, Policy,
                            PolicyTier, Pot)
from absence.services import ledger


@admin.register(AbsenceType)
class AbsenceTypeAdmin(ModelAdmin):
    list_display = ("name", "code", "paid", "uses_pot", "needs_approval", "self_certified",
                    "calendar_label", "payroll_reportable", "health_sensitive", "active")
    list_editable = ("active",)


class PolicyTierInline(TabularInline):
    model = PolicyTier
    extra = 0


@admin.register(Policy)
class PolicyAdmin(ModelAdmin):
    list_display = ("contract_type", "absence_type", "effective_from", "effective_to", "weeks_per_year",
                    "leave_year_basis", "bank_holiday_handling")
    list_filter = ("contract_type", "absence_type")
    inlines = [PolicyTierInline]


@admin.register(BankHoliday)
class BankHolidayAdmin(ModelAdmin):
    list_display = ("date", "name", "nation")


@admin.register(ClosedDay)
class ClosedDayAdmin(ModelAdmin):
    list_display = ("date", "reason")


class LedgerEntryInline(TabularInline):
    """The ledger is immutable: shown, never added to, changed or deleted."""
    model = LedgerEntry
    extra = 0
    can_delete = False
    fields = ("date", "kind", "units", "absence", "note", "actor")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Pot)
class PotAdmin(ModelAdmin):
    list_display = ("employment", "absence_type", "year_start", "year_end", "unit", "balance")
    list_filter = ("absence_type",)
    inlines = [LedgerEntryInline]
    actions = ["recalculate"]

    @admin.display(description="Balance")
    def balance(self, obj):
        return ledger.balance(obj)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Recalculate entitlement")
    def recalculate(self, request, queryset):
        n = 0
        for pot in queryset:
            try:
                if ledger.sync_entitlement(pot, request.user, "recalculated by admin"):
                    n += 1
            except ValidationError as e:
                messages.error(request, f"{pot}: {'; '.join(e.messages)}")
        messages.info(request, f"{n} pot(s) revised.")


@admin.register(Absence)
class AbsenceAdmin(ModelAdmin):
    list_display = ("employment", "absence_type", "status", "start_date", "end_date", "cost_units",
                    "auto_bank_holiday")
    list_filter = ("status", "absence_type", "auto_bank_holiday")
    date_hierarchy = "start_date"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
