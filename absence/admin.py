"""Unfold admin over the absence models. Policy set-up is edited here; pots
and their ledger are read-only, and the one action (recalculate) goes through
the ledger service. Absences are read-only but for a family-leave absence's
three dates, which an HR admin sets through bookings.set_family_dates."""

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from unfold.admin import ModelAdmin, TabularInline

from absence.models import (Absence, AbsenceType, BankHoliday, ClosedDay, EmailFailure, LedgerEntry,
                            Policy, PolicyTier, Pot)
from absence.services import bookings, ledger, year_end
from people.models import ContractType
from people.services import access, audit


@admin.register(AbsenceType)
class AbsenceTypeAdmin(ModelAdmin):
    list_display = ("name", "code", "paid", "uses_pot", "needs_approval", "self_certified",
                    "calendar_label", "payroll_reportable", "health_sensitive", "active")
    list_editable = ("active",)

    def get_readonly_fields(self, request, obj=None):
        # the services look types up by code (AL, BH, SICK, TOIL): settable
        # when a type is added, never changed after
        fields = tuple(super().get_readonly_fields(request, obj))
        return fields + ("code",) if obj is not None else fields


class PolicyTierInline(TabularInline):
    model = PolicyTier
    extra = 0


def _policy_snapshot(pk):
    """The policy's fields and tiers as strings, read fresh, for the audit."""
    if pk is None:
        return {}
    policy = Policy.objects.select_related("contract_type", "absence_type").get(pk=pk)
    out = {f.name: str(getattr(policy, f.name) if getattr(policy, f.name) is not None else "")
           for f in Policy._meta.concrete_fields if f.name != "id"}
    out["tiers"] = ", ".join(str(t) for t in policy.tiers.all())
    return out


@admin.register(Policy)
class PolicyAdmin(ModelAdmin):
    """A saved policy re-syncs the pots it can change once, after the tiers
    inline has saved too, as the admin who saved it. A pot that can no
    longer be synced (say, the only policy now ends mid-year) is shown as an
    error; the edit itself stands and the nightly reports the pot until a
    policy covers it."""
    list_display = ("contract_type", "absence_type", "effective_from", "effective_to", "weeks_per_year",
                    "leave_year_basis", "bank_holiday_handling")
    list_filter = ("contract_type", "absence_type")
    inlines = [PolicyTierInline]

    def save_model(self, request, obj, form, change):
        # read before the save: the audit's "before" and, if the form moved the
        # policy to another contract or absence type, the pots it used to cover
        obj._audit_before = _policy_snapshot(obj.pk if change else None)
        obj._pair_before = (Policy.objects.filter(pk=obj.pk).values_list("contract_type", "absence_type").first()
                            if change else None)
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        policy = form.instance
        before = getattr(policy, "_audit_before", {})
        after = _policy_snapshot(policy.pk)
        audit.record(request.user, policy, {k: (before.get(k, ""), v) for k, v in after.items()})
        pairs = {(policy.contract_type_id, policy.absence_type_id)}
        if getattr(policy, "_pair_before", None):
            pairs.add(policy._pair_before)
        revised, failed = 0, []
        for ct_id, type_id in sorted(pairs):
            result = ledger.resync_contract_type(
                ContractType.objects.get(pk=ct_id), AbsenceType.objects.get(pk=type_id),
                actor=request.user, cause=f"policy changed: {policy}")
            revised += result["revised"]
            failed += result["failed"]
        for line in failed:
            messages.error(request, line)
        messages.info(request, f"{revised} pot(s) revised.")


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
                year_end.check_open(pot)
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

    def change_view(self, request, object_id, form_url="", extra_context=None):
        # A health-sensitive absence shown is one viewed: audited like NI and
        # pay (people.admin), for the person it is shown to.
        if request.method == "GET":
            obj = self.get_object(request, object_id)
            if (obj is not None and obj.absence_type.health_sensitive
                    and self.has_view_permission(request, obj)):
                audit.viewed(request.user, obj, "health")
        return super().change_view(request, object_id, form_url, extra_context)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # HR admins change a family-leave absence's dates; nothing else
        if not access.can_view_restricted(request.user):
            return False
        return obj is None or obj.absence_type.is_family

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in Absence._meta.fields if f.name not in bookings.FAMILY_DATES]

    def save_model(self, request, obj, form, change):
        # never obj.save(): the service locks the row, checks the dates and audits
        dates = {f: form.cleaned_data.get(f) for f in bookings.FAMILY_DATES}
        try:
            bookings.set_family_dates(request.user, obj, **dates)
        except ValidationError as e:
            request._absence_not_saved = True
            messages.error(request, " ".join(e.messages))

    def log_change(self, request, obj, message):
        if getattr(request, "_absence_not_saved", False):
            return None                        # refused: nothing changed to log
        return super().log_change(request, obj, message)

    def response_change(self, request, obj):
        if getattr(request, "_absence_not_saved", False):
            return HttpResponseRedirect(request.path)
        return super().response_change(request, obj)


@admin.register(EmailFailure)
class EmailFailureAdmin(ModelAdmin):
    """The emails that did not go: listed, never added to, changed or deleted."""
    list_display = ("created_at", "subject", "error")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
