"""Unfold admin over the people models. Every save posts through a
service so the audit log and the rules hold whether a change comes from
here or from a page."""

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.html import format_html, format_html_join
from unfold.admin import ModelAdmin, StackedInline, TabularInline

from people import admin_forms
from people.models import (AuditEntry, Contract, ContractType, EmergencyContact, Employee,
                           Employment, PatternDay, PayRecord, Position, PositionTitle, Team, WorkingPattern)
from people.services import access, audit, contracts, employees, employments, pay, positions


class EmergencyContactInline(TabularInline):
    model = EmergencyContact
    extra = 0


class EmploymentInline(TabularInline):
    model = Employment
    formset = admin_forms.EmploymentInlineFormSet
    extra = 0
    fields = ("start_date", "end_date", "leaving_reason", "continuous_service_date")
    show_change_link = True
    can_delete = False


BANK_FIELDS = ("bank_account_name", "bank_sort_code", "bank_account_number")


class ComplianceFilter(admin.SimpleListFilter):
    """The people behind each number on the dashboard's Compliance card."""
    title = "Compliance"
    parameter_name = "compliance"

    def lookups(self, request, model_admin):
        from absence.admin_dashboard import COMPLIANCE
        return COMPLIANCE

    def queryset(self, request, queryset):
        from absence.admin_dashboard import compliance_people
        if self.value() is None:
            return queryset
        pks = compliance_people(timezone.localdate()).get(self.value(), [])
        return queryset.filter(pk__in=set(pks))


def _table(head, rows, empty):
    if not rows:
        return format_html('<p class="mb-4">{}</p>', empty)
    return format_html(
        '<table class="mb-4 w-full text-left"><thead><tr>{}</tr></thead><tbody>{}</tbody></table>',
        format_html_join("", '<th class="pr-4 font-semibold">{}</th>', ((h,) for h in head)),
        format_html_join("", "<tr>{}</tr>", ((format_html_join("", '<td class="pr-4">{}</td>',
                                                              ((c,) for c in r)),) for r in rows)))


def _link(url, text):
    return format_html('<a class="underline" href="{}">{}</a>', url, text)


def _day(d):
    return date_format(d, "j M Y") if d else ""


def _as_of(employee, today):
    """(current employment, upcoming employment, the day the Compliance tab
    shows). Someone not started yet is shown as they will stand on their
    first day: what their title will need, and whether it will be current."""
    employed = employments.current(employee, today)
    upcoming = None if employed else employee.employments.filter(start_date__gt=today).order_by("start_date").first()
    return employed, upcoming, (upcoming.start_date if upcoming else today)


@admin.register(Employee)
class EmployeeAdmin(ModelAdmin):
    form = admin_forms.EmployeeForm
    list_display = ("name", "work_email", "current_position")
    list_filter = (ComplianceFilter,)
    search_fields = ("first_name", "last_name", "preferred_name", "work_email")
    inlines = [EmergencyContactInline, EmploymentInline]

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if not access.can_view_restricted(request.user):
            for restricted in ("ni_number", *BANK_FIELDS):
                fields.remove(restricted)
        return fields

    def get_readonly_fields(self, request, obj=None):
        return ("compliance_summary",) if obj is not None else ()

    def get_fieldsets(self, request, obj=None):
        # An existing person's page has two tabs: their details, and the
        # read-only Compliance summary.
        fields = [f for f in self.get_fields(request, obj) if f != "compliance_summary"]
        if obj is None:
            return [(None, {"fields": fields})]
        return [("Details", {"classes": ["tab"], "fields": fields}),
                ("Compliance", {"classes": ["tab"], "fields": ["compliance_summary"]})]

    @admin.display(description="Compliance")
    def compliance_summary(self, obj):
        """Their checks (checks.state), their policies (policies.state) and
        the open items of their checklists, each with a link to act on it.
        Reads only; change_view audits the view of the checks."""
        from checks.services import checks
        from documents.services import policies
        from onboarding.models import ChecklistItem

        today = timezone.localdate()
        employed, upcoming, as_of = _as_of(obj, today)
        check_rows = []
        for r in checks.state(obj, as_of):
            if r.latest is not None and not r.latest.awaiting:
                link = _link(reverse("admin:checks_check_change", args=[r.latest.pk]), "Open")
            elif r.asked is not None:
                link = _link(reverse("admin:checks_check_change", args=[r.asked.pk]), "Open the request")
            else:
                link = _link(f"{reverse('admin:checks_check_add')}?employee={obj.pk}&check_type={r.check_type.pk}",
                             "Record")
            check_rows.append((r.check_type, r.label, _day(r.expires_on), link))
        policy_rows = []
        for r in policies.state(obj, today):
            if r["signature"] is not None:
                status = f"Signed on {_day(timezone.localtime(r['signature'].signed_at).date())}"
                link = _link(reverse("admin:documents_signature_change", args=[r["signature"].pk]), "Open")
            else:
                status = r["label"]
                link = _link(reverse("admin:documents_policy_change", args=[r["policy"].pk]), "Open the policy")
            policy_rows.append((r["policy"], r["version"].label, status, _day(r["due_on"]), link))
        items = (ChecklistItem.objects.filter(checklist__employment__employee=obj, state=ChecklistItem.State.OPEN)
                 .select_related("checklist").order_by("due_on", "order", "pk"))
        item_rows = [(i.title, i.checklist.get_kind_display(), i.get_owner_display(),
                      _day(i.due_on) + (" (overdue)" if i.due_on < today else ""),
                      _link(reverse("onboarding:hr_detail", args=[i.checklist_id]), "Open the checklist"))
                     for i in items]
        starts = (format_html('<p class="mb-2">They start on {}: their checks are shown as they will stand '
                              'that day.</p>', _day(as_of)) if upcoming else "")
        return format_html(
            '<h3 class="font-semibold mb-2">Checks</h3>{}{}'
            '<h3 class="font-semibold mb-2">Policies</h3>{}'
            '<h3 class="font-semibold mb-2">Open checklist items</h3>{}',
            starts,
            _table(("Check", "Status", "Expires", ""), check_rows,
                   "Their position needs no checks, and none are recorded." if employed or upcoming
                   else "None recorded, and none are needed of someone not employed."),
            _table(("Policy", "Version", "Status", "Sign by", ""), policy_rows, "No policies apply to them."),
            _table(("Item", "Checklist", "Owner", "Due", ""), item_rows, "No open checklist items."))

    @admin.display(description="Position")
    def current_position(self, obj):
        today = timezone.localdate()
        emp = employments.current(obj, today)
        pos = positions.primary_on(emp, today) if emp else None
        return f"{pos.title}, {pos.team}" if pos else ""

    def has_delete_permission(self, request, obj=None):
        return False

    def change_view(self, request, object_id, form_url="", extra_context=None):
        # An NI number or bank details shown are viewed: audited like pay.
        # Only for someone the fields are shown to (get_fields), and only
        # when there is something to see.
        if access.can_view_restricted(request.user) and request.method == "GET":
            obj = self.get_object(request, object_id)
            if obj is not None and self.has_view_permission(request, obj):
                if obj.ni_number:
                    audit.viewed(request.user, obj, "ni_number")
                if obj.bank_account_number or obj.bank_sort_code:
                    audit.viewed(request.user, obj, "bank")
        # The Compliance tab shows their checks: a view of them, audited as
        # opening a check is (CheckAdmin), when there is any row to see.
        if request.method == "GET":
            obj = self.get_object(request, object_id)
            if obj is not None and self.has_view_permission(request, obj):
                from checks.services import checks
                if checks.state(obj, _as_of(obj, timezone.localdate())[2]):
                    audit.viewed(request.user, obj, "checks")
        return super().change_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        if change:
            data = {k: form.cleaned_data[k] for k in form.changed_data if k in employees.EDITABLE}
            fresh = Employee.objects.get(pk=obj.pk)
            employees.update(request.user, fresh, **data)
            obj.refresh_from_db()
        else:
            new = employees.create(request.user, **form.cleaned_data)
            obj.pk = new.pk
        user = form.cleaned_data.get("user")
        if user is not None and user.email.casefold() != form.cleaned_data["work_email"].casefold():
            # Not an error — a login may use another address — but sign-in
            # sends the login's email to the rota, not this one, so say so.
            messages.warning(request, f"The linked login account's email ({user.email}) is not "
                                      f"the work email ({form.cleaned_data['work_email']}). The "
                                      "rota receives the login account's email when they sign in.")

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        changed_by_pk = {obj.pk: changed for obj, changed in formset.changed_objects}
        for inst in instances:
            if isinstance(inst, Employment):
                if inst.pk is None:
                    # Checked already by EmploymentInlineFormSet.clean(); the
                    # service checks again as it writes.
                    try:
                        employments.start(request.user, form.instance, inst.start_date,
                                          inst.continuous_service_date, inst.end_date,
                                          inst.leaving_reason)
                    except ValidationError as e:
                        messages.error(request, "; ".join(e.messages))
                    continue
                changed = changed_by_pk.get(inst.pk, [])
                fresh = Employment.objects.get(pk=inst.pk)
                try:
                    if "end_date" in changed or "leaving_reason" in changed:
                        employments.end(request.user, fresh, inst.end_date, inst.leaving_reason)
                    if "start_date" in changed or "continuous_service_date" in changed:
                        employments.amend(request.user, fresh, inst.start_date,
                                          inst.continuous_service_date)
                except ValidationError as e:
                    messages.error(request, "; ".join(e.messages))
            else:
                is_new = inst.pk is None
                if is_new:
                    inst.save()
                    audit.record(request.user, form.instance,
                                {"emergency_contact": ("", str(inst))})
                else:
                    fresh = EmergencyContact.objects.get(pk=inst.pk)
                    changes = {f"emergency_contact.{f}": (getattr(fresh, f), getattr(inst, f))
                              for f in ("name", "relationship", "phone", "priority")}
                    inst.save()
                    audit.record(request.user, form.instance, changes)
        for inst in formset.deleted_objects:
            if isinstance(inst, EmergencyContact):
                audit.record(request.user, form.instance, {"emergency_contact": (str(inst), "")})
                inst.delete()


class PositionInline(TabularInline):
    model = Position
    form = admin_forms.PositionForm
    formset = admin_forms.PositionInlineFormSet
    extra = 0
    can_delete = False


class ContractInline(TabularInline):
    model = Contract
    form = admin_forms.ContractForm
    formset = admin_forms.ContractInlineFormSet
    extra = 0
    can_delete = False


class PatternDayInline(TabularInline):
    model = PatternDay
    extra = 0
    fields = ("weekday", "am_units", "pm_units")


class WorkingPatternInline(StackedInline):
    """Read-only here: a pattern needs its days, which only the
    WorkingPattern page's PatternDayInline can set. Add and edit there;
    this inline is for seeing what exists and following the link."""
    model = WorkingPattern
    extra = 0
    fields = ("effective_from",)
    readonly_fields = ("effective_from",)
    show_change_link = True
    can_delete = False
    verbose_name_plural = "Working pattern versions (add on the pattern page)"

    def has_add_permission(self, request, obj):
        return False


class PayRecordInline(TabularInline):
    model = PayRecord
    extra = 0
    can_delete = False


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

    def get_readonly_fields(self, request, obj=None):
        # The employee a spell belongs to is fixed at start(); a change
        # here would silently move history to a different person.
        return ["employee"] if obj else []

    def has_delete_permission(self, request, obj=None):
        return False

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if access.can_view_restricted(request.user) and request.method == "GET":
            obj = self.get_object(request, object_id)
            if obj is not None and self.has_view_permission(request, obj) and obj.pay_records.exists():
                audit.viewed(request.user, obj, "pay")
        return super().change_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        if change:
            # obj already carries the form's new values (ModelForm._post_
            # clean copied them on); a fresh row from the database is what
            # end()/amend() need to compute a correct before/after diff.
            obj_fresh = Employment.objects.get(pk=obj.pk)
            try:
                if "end_date" in form.changed_data or "leaving_reason" in form.changed_data:
                    employments.end(request.user, obj_fresh, form.cleaned_data["end_date"],
                                    form.cleaned_data["leaving_reason"])
                if "start_date" in form.changed_data or "continuous_service_date" in form.changed_data:
                    employments.amend(request.user, obj_fresh, form.cleaned_data.get("start_date"),
                                      form.cleaned_data.get("continuous_service_date"))
            except ValidationError as e:
                messages.error(request, "; ".join(e.messages))
            obj.refresh_from_db()
        else:
            # EmploymentForm.clean() has run employments.check_start() over
            # these dates, so a refusal re-rendered the form instead.
            new = employments.start(request.user, obj.employee, obj.start_date,
                                    obj.continuous_service_date, obj.end_date,
                                    obj.leaving_reason)
            obj.pk = new.pk

    def save_formset(self, request, form, formset, change):
        # PositionInlineFormSet and ContractInlineFormSet have run these
        # rules in clean(), so a refused row re-rendered the page. The
        # messages below are a backstop for a clash that arrived between
        # the check and the write.
        instances = formset.save(commit=False)
        changed_by_pk = {obj.pk: changed for obj, changed in formset.changed_objects}
        for inst in instances:
            try:
                if isinstance(inst, Position):
                    if inst.pk is None:
                        positions.add(request.user, form.instance, inst.title, inst.team,
                                      inst.line_manager, inst.from_date, inst.primary, inst.to_date)
                    elif set(changed_by_pk.get(inst.pk, [])) - {"to_date"}:
                        messages.error(request, admin_forms.ONLY_END)
                    else:
                        fresh = Position.objects.get(pk=inst.pk)
                        positions.end(request.user, fresh, inst.to_date)
                elif isinstance(inst, Contract):
                    if inst.pk is None:
                        contracts.add(request.user, form.instance, inst.contract_type,
                                      inst.weekly_amount, inst.from_date, inst.basis,
                                      inst.to_date, inst.notes)
                    elif set(changed_by_pk.get(inst.pk, [])) - {"to_date"}:
                        messages.error(request, admin_forms.ONLY_END)
                    else:
                        fresh = Contract.objects.get(pk=inst.pk)
                        contracts.end(request.user, fresh, inst.to_date)
                elif isinstance(inst, PayRecord):
                    if inst.pk is None:
                        pay.add(request.user, form.instance, inst.from_date, inst.basis,
                                inst.amount, inst.to_date, inst.reason)
                    else:
                        pay.amend(request.user, inst, **{f: getattr(inst, f) for f in pay.FIELDS})
            except ValidationError as e:
                messages.error(request, "; ".join(e.messages))


@admin.register(WorkingPattern)
class WorkingPatternAdmin(ModelAdmin):
    list_display = ("employment", "effective_from")
    inlines = [PatternDayInline]

    def has_delete_permission(self, request, obj=None):
        return False

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

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PositionTitle)
class PositionTitleAdmin(ModelAdmin):
    list_display = ("name", "display_order")
    search_fields = ("name",)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ContractType)
class ContractTypeAdmin(ModelAdmin):
    list_display = ("name", "unit", "full_time_weekly", "display_order")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditEntry)
class AuditEntryAdmin(ModelAdmin):
    list_display = ("at", "actor_email", "kind", "model", "object_id", "field", "before", "after")
    list_filter = ("kind", "model")
    search_fields = ("actor_email", "field", "before", "after", "note")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
