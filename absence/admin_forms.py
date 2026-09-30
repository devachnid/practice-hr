"""The policy admin's forms. A policy stores its entitlement, carry-over cap
and tiers in weeks (multiplied by the contracted weekly amount); for an
hours contract type they are entered here as full-time days instead, at
five days to a full-time week, and stored as days ÷ 5. A sessions contract
type (GPs) keeps its weeks fields. A bank-holiday policy has neither: its
pot is counted from the calendar (accrual.bank_holiday_entitlement), and
the page says what that comes to instead.

The form's shape follows the policy it edits (`mode`): the saved policy's
contract type on its change page, both inputs on the add page until a
contract type is chosen and saved. PolicyAdmin.get_fields reads the same
`mode`, so the fields rendered are the fields the form has."""

from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from unfold.widgets import UnfoldAdminDecimalFieldWidget

from absence.models import Policy, PolicyTier, Pot
from absence.services import accrual, leave_year
from people.models import ContractType

DAYS_PER_WEEK = Decimal("5")
HUNDREDTH = Decimal("0.01")          # weeks are stored to two places, so days go in steps of 0.05

DAYS, WEEKS, EITHER, BANK_HOLIDAY = "days", "weeks", "either", "bank_holiday"


def plain(value):
    """A decimal without trailing zeros or an exponent: 22.00 → "22", 4.40 → "4.4"."""
    return f"{Decimal(value).normalize():f}"


def as_days(weeks):
    return Decimal(plain(weeks * DAYS_PER_WEEK))


def mode(policy):
    """How `policy`'s entitlement is entered: DAYS for an hours contract
    type, WEEKS for a sessions one, BANK_HOLIDAY (not at all: it comes from
    the calendar) for the bank-holiday pot's policy, EITHER on the add page
    (no saved policy, so no contract type yet)."""
    if policy is None or policy.pk is None:
        return EITHER
    if policy.absence_type.code == "BH":
        return BANK_HOLIDAY
    return DAYS if policy.contract_type.unit == ContractType.Unit.HOURS else WEEKS


def _year_label(start, end):
    return str(start.year) if (start.month, start.day) == (1, 1) else f"{start.year}/{end:%y}"


def bank_holiday_summary(policy, today):
    """What a bank-holiday policy's pot holds (accrual.bank_holiday_entitlement),
    in words, for its leave year containing `today`."""
    tail = "one working day each, pro rata to contracted hours"
    if policy.leave_year_basis == Policy.Basis.ANNIVERSARY:
        return f"The bank holidays in each person's leave year (from their start date), {tail}"
    start, end = leave_year.bounds(policy, None, today)
    n = accrual.bank_holidays_between(start, end).count()
    return f"{n} bank holiday{'' if n == 1 else 's'} in {_year_label(start, end)}, {tail}"


def to_weeks(days, allow_zero=False):
    """Full-time days as weeks, refusing what the weeks field cannot hold."""
    if days < 0 or (days == 0 and not allow_zero):
        raise ValidationError("Enter more than zero days." if not allow_zero else "Enter zero days or more.")
    weeks = days / DAYS_PER_WEEK
    if weeks != weeks.quantize(HUNDREDTH):
        raise ValidationError("Enter the days as a multiple of 0.05: they are stored as weeks (days ÷ 5) "
                              "to two decimal places.")
    if weeks >= 100:
        raise ValidationError("Enter fewer than 500 days.")
    return weeks.quantize(HUNDREDTH)


def _days_field(label, help_text, required=False):
    return forms.DecimalField(label=label, required=required, max_digits=6, decimal_places=2,
                              help_text=help_text, widget=UnfoldAdminDecimalFieldWidget)


class _Stores:
    def store(self, name, value):
        """Set a model field the form computed: through cleaned_data when the
        form has the field (construct_instance would overwrite it otherwise),
        on the instance when it does not."""
        if name in self.fields:
            self.cleaned_data[name] = value
        else:
            setattr(self.instance, name, value)


def _hours_chosen(mode_, contract_type, absence_type):
    """Whether this save takes days: always on an hours policy's page; on
    the add page, when the chosen contract type is in hours."""
    if mode_ != EITHER:
        return mode_ == DAYS
    return (contract_type is not None and contract_type.unit == ContractType.Unit.HOURS
            and not (absence_type is not None and absence_type.code == "BH"))


YEAR_FIELDS = ("leave_year_basis", "year_start_month", "year_start_day")
YEAR_LOCKED = ("This type has leave pots on the current year. End this policy and add a new one from the "
               "new year's first day instead (see the admin guide).")
NOT_FOR_SESSIONS = "Days are for hours contracts: enter a sessions contract's entitlement in weeks."


class PolicyForm(_Stores, forms.ModelForm):
    days_per_year = _days_field(
        "Full-time days per year",
        "Hours contracts: the days a year someone full time gets (22, say), before bank holidays. "
        "Stored as weeks, days ÷ 5, and multiplied by each person's contracted weekly hours.")
    carry_over_days = _days_field(
        "Carry over max days",
        "Hours contracts: the most full-time days that carry into the next year, stored as weeks "
        "(days ÷ 5). Blank means nothing carries.")

    class Meta:
        model = Policy
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mode = mode(self.instance)
        if self.mode == DAYS:
            self.fields["days_per_year"].required = True
            self.initial.setdefault("days_per_year", as_days(self.instance.weeks_per_year))
            if self.instance.carry_over_max_weeks is not None:
                self.initial.setdefault("carry_over_days", as_days(self.instance.carry_over_max_weeks))
        elif self.mode in (WEEKS, BANK_HOLIDAY):
            self.fields.pop("days_per_year")
            self.fields.pop("carry_over_days")
        if self.mode == EITHER and "weeks_per_year" in self.fields:
            self.fields["weeks_per_year"].required = False
            self.fields["weeks_per_year"].help_text = "Sessions contracts: the entitlement in weeks."
            self.fields["days_per_year"].help_text = (
                "Hours contracts: the days a year someone full time gets (22, say). Leave blank for sessions.")

    def clean(self):
        data = super().clean()
        self._check_year_unchanged()
        if self.mode in (WEEKS, BANK_HOLIDAY):
            return data
        absence_type = data.get("absence_type")
        if self.mode == EITHER and absence_type is not None and absence_type.code == "BH":
            self.store("weeks_per_year", Decimal("0"))      # its pot comes from the calendar; never read
            return data
        hours = _hours_chosen(self.mode, data.get("contract_type"), absence_type)
        if hours:
            self._clean_days(data)
        elif self.mode == EITHER:
            self._clean_weeks(data)
        return data

    def _check_year_unchanged(self):
        """A pot keeps the leave year it was opened with, and a day counts only
        towards the pot of the year its policy puts it in (accrual): moving a
        policy's year while its type has pots would leave those pots earning
        nothing and open overlapping ones. Such a policy is ended and a new one
        added from the new year's first day instead (docs: moving a type in use
        to a January year). A policy whose type has no pots of its absence type
        is edited freely. Checked against the saved contract and absence type,
        before anything is saved, so a refused save writes nothing."""
        if self.instance.pk is None or not set(YEAR_FIELDS) & set(self.changed_data):
            return
        if Pot.objects.filter(absence_type_id=self.instance.absence_type_id,
                              employment__contracts__contract_type_id=self.instance.contract_type_id).exists():
            raise ValidationError(YEAR_LOCKED)

    def _clean_days(self, data):
        if "days_per_year" not in self.errors:
            if data.get("days_per_year") is None:
                self.add_error("days_per_year", "Enter the full-time days per year: an hours contract's "
                                                "entitlement is entered in days.")
            else:
                try:
                    self.store("weeks_per_year", to_weeks(data["days_per_year"]))
                except ValidationError as e:
                    self.add_error("days_per_year", e)
        if "carry_over_days" in self.errors:
            return
        carry = data.get("carry_over_days")
        if carry is None and self.mode == EITHER:
            return                            # the add page's weeks field, if given, stands
        try:
            self.store("carry_over_max_weeks", None if carry is None else to_weeks(carry, allow_zero=True))
        except ValidationError as e:
            self.add_error("carry_over_days", e)

    def _clean_weeks(self, data):
        """The add page, a sessions contract type: weeks, as the model has them."""
        if data.get("weeks_per_year") is None and "weeks_per_year" not in self.errors:
            self.add_error("weeks_per_year", "This field is required.")
        for name in ("days_per_year", "carry_over_days"):
            if data.get(name) is not None:
                self.add_error(name, NOT_FOR_SESSIONS)


class PolicyTierForm(_Stores, forms.ModelForm):
    days = _days_field(
        "Full-time days",
        "The new total a year from this many years' service (23, say), not the extra. "
        "Stored as extra weeks over the policy's own days.")

    class Meta:
        model = PolicyTier
        fields = "__all__"

    def setup(self, policy):
        """Called by the formset once the form exists, with the policy form's
        own instance: its mode decides whether the tier takes days, and by
        the time the tier is cleaned it carries the base just entered."""
        self.policy = policy
        self.mode = mode(policy)
        self._stored_extra = self.instance.extra_weeks
        if self.mode == DAYS:
            self.fields["days"].required = True
            if self.instance.pk is not None:
                self.initial.setdefault("days", as_days(policy.weeks_per_year + self.instance.extra_weeks))
        elif self.mode in (WEEKS, BANK_HOLIDAY):
            self.fields.pop("days")
        if self.mode == EITHER and "extra_weeks" in self.fields:
            self.fields["extra_weeks"].required = False
            self.fields["extra_weeks"].help_text = "Sessions contracts: the total extra weeks."
            self.fields["days"].help_text = "Hours contracts: the new total full-time days (23, say)."

    def has_changed(self):
        """A tier's days are a total over the policy's base: a new base with
        the same total is a new extra, so the row is saved though its own
        field was not touched."""
        return super().has_changed() or (self.instance.pk is not None
                                         and self.instance.extra_weeks != self._stored_extra)

    def clean(self):
        data = super().clean()
        if self.mode in (WEEKS, BANK_HOLIDAY):
            return data
        policy = self.policy
        contract_type = policy.contract_type if policy.contract_type_id else None
        absence_type = policy.absence_type if policy.absence_type_id else None
        if not _hours_chosen(self.mode, contract_type, absence_type):
            if data.get("extra_weeks") is None and "extra_weeks" not in self.errors:
                self.add_error("extra_weeks", "This field is required.")
            if data.get("days") is not None:
                self.add_error("days", NOT_FOR_SESSIONS)
            return data
        if "days" in self.errors:
            return data
        if data.get("days") is None:
            self.add_error("days", "Enter the full-time days a year after this many years.")
            return data
        base = policy.weeks_per_year * DAYS_PER_WEEK
        if data["days"] < base:
            self.add_error("days", f"A tier gives at least the {plain(base)} full-time days of the policy itself.")
            return data
        try:
            self.store("extra_weeks", to_weeks(data["days"] - base, allow_zero=True))
        except ValidationError as e:
            self.add_error("days", e)
        return data


class PolicyTierFormSet(BaseInlineFormSet):
    """Hands each tier form its policy: the policy form's own instance. The
    admin (unfold) builds the tier forms before it validates the policy
    form, but cleans them after, so by then that instance carries the weeks
    from the days just entered and a tier's days are measured against the
    new base (and its initial days, shown on the page, against the old)."""

    def _construct_form(self, i, **kwargs):
        form = super()._construct_form(i, **kwargs)
        form.setup(self.instance)
        return form

    @property
    def empty_form(self):
        form = super().empty_form
        form.setup(self.instance)
        return form

    def clean(self):
        """Tiers in days go up with the years: a later tier never gives fewer
        days than an earlier one."""
        super().clean()
        rows = []
        for form in self.forms:
            if getattr(form, "mode", WEEKS) in (WEEKS, BANK_HOLIDAY) or not form.is_valid() or not form.cleaned_data:
                continue
            if (self.can_delete and self._should_delete_form(form)) or form.cleaned_data.get("days") is None:
                continue
            rows.append((form.cleaned_data["after_years"], form.cleaned_data["days"]))
        rows.sort()
        for (_, earlier), (_, later) in zip(rows, rows[1:]):
            if later < earlier:
                raise ValidationError("A tier for more years cannot give fewer days than an earlier tier.")
