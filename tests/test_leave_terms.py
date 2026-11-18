"""Leave terms on contract types and contracts (Shift Central's allowance
spec, section 4): what the models hold, and the practice's 8-session week."""
from decimal import Decimal as D

import pytest
from django.db import IntegrityError, transaction

from people.models import Contract, ContractLeaveStep, ContractType, ContractTypeLeaveStep
from tests.factories import make_contract, make_contract_type, make_employment

pytestmark = pytest.mark.django_db


def test_a_new_contract_takes_the_usual_terms_and_holds_none_of_its_own():
    c = make_contract(make_employment())
    assert c.leave_terms == Contract.LeaveTerms.USUAL == "usual"
    assert c.leave_base is None and not c.leave_steps.exists()
    assert c.contract_type.leave_base is None and not c.contract_type.leave_steps.exists()


def test_steps_are_kept_in_order_of_years_one_per_year():
    ct = make_contract_type()
    ContractTypeLeaveStep.objects.create(contract_type=ct, after_years=5, total=D("25"))
    ContractTypeLeaveStep.objects.create(contract_type=ct, after_years=1, total=D("23"))
    assert [s.after_years for s in ct.leave_steps.all()] == [1, 5]
    with pytest.raises(IntegrityError), transaction.atomic():
        ContractTypeLeaveStep.objects.create(contract_type=ct, after_years=5, total=D("26"))
    c = make_contract(make_employment(), ct)
    ContractLeaveStep.objects.create(contract=c, after_years=3, total=D("24"))
    with pytest.raises(IntegrityError), transaction.atomic():
        ContractLeaveStep.objects.create(contract=c, after_years=3, total=D("25"))


def test_the_seeded_gp_types_are_full_time_at_8_sessions():
    for name in ("Partner", "Salaried GP", "GP trainee"):
        assert ContractType.objects.get(name=name).full_time_weekly == D("8"), name
    assert ContractType.objects.get(name="Reception").full_time_weekly == D("37.5")


# --- the service ---------------------------------------------------------------------------------

from django.core.exceptions import ValidationError  # noqa: E402

from people.models import AuditEntry  # noqa: E402
from people.services import leave_terms  # noqa: E402


def test_check_sorts_good_steps():
    assert leave_terms.check(D("22"), [(5, D("25")), (1, D("23"))]) == [(1, D("23")), (5, D("25"))]
    assert leave_terms.check(None, []) == [] and leave_terms.check(D("0.5"), []) == []


@pytest.mark.parametrize("base,steps,says", [
    (None, [(1, D("23"))], "need the figure they step up from"),
    (D("0"), [], "More than 0"),
    (D("99.5"), [], "at most 99"),
    (D("22"), [(0, D("23"))], "at least 1 complete year"),
    (D("22"), [(1, D("23")), (1, D("24"))], "same number of years"),
    (D("22"), [(1, D("22"))], "more than the figure before it"),
    (D("22"), [(1, D("24")), (5, D("23"))], "more than the figure before it"),
    (D("22"), [(1, D("100"))], "at most 99"),
])
def test_check_refuses(base, steps, says):
    with pytest.raises(ValidationError) as e:
        leave_terms.check(base, steps)
    assert says in "; ".join(e.value.messages)


def test_setting_a_types_terms_replaces_them_and_is_audited(hr_admin):
    ct = make_contract_type()
    leave_terms.set_type_terms(hr_admin, ct, D("22"), [(1, D("23")), (5, D("25"))])
    ct.refresh_from_db()
    assert ct.leave_base == D("22") and [(s.after_years, s.total) for s in ct.leave_steps.all()] == [(1, D("23")), (5, D("25"))]
    rows = {a.field: (a.before, a.after) for a in AuditEntry.objects.filter(model="people.contracttype", object_id=ct.pk)}
    assert rows == {"leave_base": ("", "22"), "leave_steps": ("", "23 after 1 year; 25 after 5 years")}
    AuditEntry.objects.all().delete()
    leave_terms.set_type_terms(hr_admin, ct, D("22.00"), [(5, D("25")), (1, D("23"))])      # the same again
    assert not AuditEntry.objects.exists()
    leave_terms.set_type_terms(hr_admin, ct, None)
    ct.refresh_from_db()
    assert ct.leave_base is None and not ct.leave_steps.exists()


def test_a_refused_change_writes_nothing(hr_admin):
    ct = make_contract_type()
    leave_terms.set_type_terms(hr_admin, ct, D("22"), [(1, D("23"))])
    AuditEntry.objects.all().delete()
    with pytest.raises(ValidationError):
        leave_terms.set_type_terms(hr_admin, ct, D("25"), [(1, D("24"))])
    ct.refresh_from_db()
    assert ct.leave_base == D("22") and ct.leave_steps.count() == 1 and not AuditEntry.objects.exists()


def test_a_contracts_own_terms_and_what_clears_them(hr_admin):
    c = make_contract(make_employment())
    with pytest.raises(ValidationError) as e:
        leave_terms.set_contract_terms(hr_admin, c, "own")
    assert "need a figure" in "; ".join(e.value.messages)
    with pytest.raises(ValidationError):
        leave_terms.set_contract_terms(hr_admin, c, "sometimes")
    leave_terms.set_contract_terms(hr_admin, c, "own", D("27"), [(10, D("30"))])
    c.refresh_from_db()
    assert (c.leave_terms, c.leave_base, c.leave_steps.count()) == ("own", D("27"), 1)
    fields = set(AuditEntry.objects.filter(model="people.contract", object_id=c.pk).values_list("field", flat=True))
    assert fields == {"leave_terms", "leave_base", "leave_steps"}
    leave_terms.set_contract_terms(hr_admin, c, "none", D("27"), [(10, D("30"))])       # a figure sent with another choice is dropped
    c.refresh_from_db()
    assert (c.leave_terms, c.leave_base, c.leave_steps.count()) == ("none", None, 0)


def test_resolved_and_describe_for_each_choice(hr_admin):
    reception = make_contract_type()
    trainee = make_contract_type("GP trainee", "sessions", D("8"))
    partner = make_contract_type("Partner", "sessions", D("8"))
    leave_terms.set_type_terms(hr_admin, reception, D("22"), [(1, D("23")), (5, D("25"))])
    leave_terms.set_type_terms(hr_admin, partner, D("8"))
    usual = make_contract(make_employment(), reception)
    assert leave_terms.resolved(usual) == {"base": D("22"), "steps": [(1, D("23")), (5, D("25"))]}
    assert leave_terms.describe(usual) == "Usual for Reception: 22 days; 23 after 1 year; 25 after 5 years"
    gp = make_contract(make_employment(), partner, D("6"))
    assert leave_terms.describe(gp) == "Usual for Partner: 8 weeks"
    blank = make_contract(make_employment(), trainee, D("8"))
    assert leave_terms.resolved(blank) is None
    assert leave_terms.describe(blank) == "Usual for GP trainee: none set, so not worked out"
    own = make_contract(make_employment(), reception)
    leave_terms.set_contract_terms(hr_admin, own, "own", D("27.5"))
    assert leave_terms.resolved(own) == {"base": D("27.5"), "steps": []}
    assert leave_terms.describe(own) == "Own: 27.5 days"
    leave_terms.set_contract_terms(hr_admin, own, "none")
    assert leave_terms.resolved(own) is None and leave_terms.describe(own) == "Not worked out"


def test_a_step_reads_plainly():
    assert str(ContractTypeLeaveStep(after_years=1, total=D("23.00"))) == "23 after 1 year"
    assert str(ContractTypeLeaveStep(after_years=5, total=D("25"))) == "25 after 5 years"
    assert str(ContractTypeLeaveStep(after_years=10, total=D("27.50"))) == "27.5 after 10 years"


@pytest.mark.parametrize("base,steps", [(D("22.005"), []), (D("22"), [(1, D("23.005"))])])
def test_check_refuses_more_than_two_decimal_places(base, steps):
    with pytest.raises(ValidationError, match="At most 2 decimal places"):
        leave_terms.check(base, steps)
    assert leave_terms.check(D("22.01"), [(1, D("23.50"))]) == [(1, D("23.50"))]


def test_migration_0019_leaves_a_gp_type_someone_already_changed():
    import importlib

    from django.apps import apps
    migration = importlib.import_module("people.migrations.0019_gp_full_time_week_is_8")
    for name, week in (("Partner", D("9")), ("Salaried GP", D("7")), ("GP trainee", D("9"))):
        ContractType.objects.update_or_create(name=name, defaults={"unit": "sessions", "full_time_weekly": week})
    migration.to_eight(apps, None)
    weeks = dict(ContractType.objects.filter(name__in=migration.GP_TYPES).values_list("name", "full_time_weekly"))
    assert weeks == {"Partner": D("8"), "Salaried GP": D("7"), "GP trainee": D("8")}
