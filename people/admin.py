"""Unfold admin over the people models. Every save posts through a
service so the audit log and the rules hold whether a change comes from
here or from a page."""

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from unfold.admin import ModelAdmin, StackedInline, TabularInline

from people import admin_forms
from people.models import (AuditEntry, Contract, ContractType, EmergencyContact, Employee,
                           Employment, PatternDay, PayRecord, Position, Team, WorkingPattern)
from people.services import access, audit, contracts, employees, employments, positions


class EmergencyContactInline(TabularInline):
    model = EmergencyContact
    extra = 0


class EmploymentInline(TabularInline):
    model = Employment
    extra = 0
    fields = ("start_date", "end_date", "leaving_reason", "continuous_service_date")
    show_change_link = True


@admin.register(Employee)
class EmployeeAdmin(ModelAdmin):
    form = admin_forms.EmployeeForm
    list_display = ("name", "work_email", "current_position")
    search_fields = ("first_name", "last_name", "preferred_name", "work_email")
    inlines = [EmergencyContactInline, EmploymentInline]

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if not access.can_view_restricted(request.user):
            fields.remove("ni_number")
        return fields

    @admin.display(description="Position")
    def current_position(self, obj):
        from datetime import date
        emp = employments.current(obj, date.today())
        pos = positions.primary_on(emp, date.today()) if emp else None
        return f"{pos.title}, {pos.team}" if pos else ""

    def save_model(self, request, obj, form, change):
        data = {k: form.cleaned_data[k] for k in form.changed_data}
        if change:
            employees.update(request.user, obj, **data)
        else:
            new = employees.create(request.user, **form.cleaned_data)
            obj.pk = new.pk

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for inst in instances:
            if isinstance(inst, Employment):
                if inst.pk is None:
                    try:
                        employments.start(request.user, form.instance, inst.start_date,
                                          inst.continuous_service_date)
                    except ValidationError as e:
                        messages.error(request, "; ".join(e.messages))
                    continue
                inst.full_clean()
                inst.save()
                audit.record(request.user, inst, {"end_date": ("", inst.end_date)})
            else:
                inst.save()
        for inst in formset.deleted_objects:
            if not isinstance(inst, Employment):
                inst.delete()


class PositionInline(TabularInline):
    model = Position
    form = admin_forms.PositionForm
    extra = 0


class ContractInline(TabularInline):
    model = Contract
    form = admin_forms.ContractForm
    extra = 0


class PatternDayInline(TabularInline):
    model = PatternDay
    extra = 0
    fields = ("weekday", "am_units", "pm_units")


class WorkingPatternInline(StackedInline):
    model = WorkingPattern
    extra = 0
    fields = ("effective_from",)
    show_change_link = True


class PayRecordInline(TabularInline):
    model = PayRecord
    extra = 0


@admin.register(Employment)
class EmploymentAdmin(ModelAdmin):
    form = admin_forms.EmploymentForm
    list_display = ("employee", "start_date", "end_date", "leaving_reason")
    list_select_related = ("employee",)
    search_fields = ("employee__first_name", "employee__last_name")

    def get_inlines(self, request, obj):
        inlines = [PositionInline, ContractInline, WorkingPatternInline]
        if access.can_view_restricted(request.user):
            inlines.append(PayRecordInline)
        return inlines

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if access.can_view_restricted(request.user) and request.method == "GET":
            obj = self.get_object(request, object_id)
            if obj is not None and obj.pay_records.exists():
                audit.viewed(request.user, obj, "pay")
        return super().change_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        if change:
            changes = {k: (form.initial.get(k), form.cleaned_data[k]) for k in form.changed_data}
            obj.full_clean()
            obj.save()
            audit.record(request.user, obj, changes)
        else:
            new = employments.start(request.user, obj.employee, obj.start_date,
                                    obj.continuous_service_date)
            obj.pk = new.pk

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for inst in instances:
            try:
                if isinstance(inst, Position) and inst.pk is None:
                    positions.add(request.user, form.instance, inst.title, inst.team,
                                  inst.line_manager, inst.from_date, inst.primary, inst.to_date)
                elif isinstance(inst, Contract) and inst.pk is None:
                    contracts.add(request.user, form.instance, inst.contract_type, inst.weekly_amount,
                                  inst.from_date, inst.basis, inst.to_date, inst.notes)
                elif isinstance(inst, PayRecord):
                    inst.save()
                    audit.record(request.user, inst, {"amount": ("", inst.amount)})
                else:
                    inst.full_clean()
                    inst.save()
                    audit.record(request.user, inst, {"saved": ("", str(inst))})
            except ValidationError as e:
                messages.error(request, "; ".join(e.messages))
        for inst in formset.deleted_objects:
            messages.error(request, f"{inst} was not deleted: rows here end, they are not removed.")


@admin.register(WorkingPattern)
class WorkingPatternAdmin(ModelAdmin):
    list_display = ("employment", "effective_from")
    inlines = [PatternDayInline]

    def save_formset(self, request, form, formset, change):
        from decimal import Decimal
        from people.services import patterns
        formset.save(commit=False)
        days = {}
        for f in formset.forms:
            if f.cleaned_data and not f.cleaned_data.get("DELETE"):
                d = f.cleaned_data
                days[d["weekday"]] = (d.get("am_units") or Decimal("0"), d.get("pm_units") or Decimal("0"))
        _, warning = patterns.set_pattern(request.user, form.instance.employment,
                                          form.instance.effective_from, days)
        if warning:
            messages.warning(request, warning)


@admin.register(Team)
class TeamAdmin(ModelAdmin):
    list_display = ("name", "display_order", "min_present")


@admin.register(ContractType)
class ContractTypeAdmin(ModelAdmin):
    list_display = ("name", "unit", "full_time_weekly", "display_order")


@admin.register(AuditEntry)
class AuditEntryAdmin(ModelAdmin):
    list_display = ("at", "actor", "kind", "model", "object_id", "field", "before", "after")
    list_filter = ("kind", "model")
    search_fields = ("field", "before", "after", "note")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
