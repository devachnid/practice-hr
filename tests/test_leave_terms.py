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
