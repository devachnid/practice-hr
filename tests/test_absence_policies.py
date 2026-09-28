from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from absence.models import Policy, PolicyTier
from absence.services import policies
from tests.factories import (absence_type, make_contract, make_contract_type, make_employment,
                             make_policy)


@pytest.fixture(autouse=True)
def no_seeded_policies(db):
    """The migration seeds an AL policy per contract type; these tests build their own."""
    Policy.objects.all().delete()


def test_policy_for_reads_the_contract_type_on_the_day(db):
    emp = make_employment(start=date(2026, 4, 1))
    ct = make_contract_type()
    make_contract(emp, ct)
    p = make_policy(ct)
    assert policies.policy_for(emp, absence_type("AL"), date(2026, 6, 1)) == p


def test_missing_policy_names_it(db):
    emp = make_employment(start=date(2026, 4, 1))
    make_contract(emp, make_contract_type("HCA"))
    with pytest.raises(ValidationError) as e:
        policies.policy_for(emp, absence_type("AL"), date(2026, 6, 1))
    assert "HCA" in str(e.value) and "Annual leave" in str(e.value)


def test_no_contract_is_also_an_error(db):
    emp = make_employment()
    with pytest.raises(ValidationError):
        policies.policy_for(emp, absence_type("AL"), emp.start_date)


def test_effective_dated_policies(db):
    emp = make_employment(start=date(2020, 1, 1))
    ct = make_contract_type()
    make_contract(emp, ct)
    old = make_policy(ct, effective_from=date(2020, 1, 1), effective_to=date(2026, 3, 31))
    new = make_policy(ct, effective_from=date(2026, 4, 1), weeks_per_year=Decimal("6"))
    assert policies.policy_for(emp, absence_type("AL"), date(2026, 3, 31)) == old
    assert policies.policy_for(emp, absence_type("AL"), date(2026, 4, 1)) == new


def test_tier_extra_weeks_highest_reached(db):
    emp = make_employment(start=date(2026, 4, 1), continuous_service_date=date(2019, 10, 1))
    ct = make_contract_type()
    p = make_policy(ct)
    PolicyTier.objects.create(policy=p, after_years=5, extra_weeks=Decimal("1"))
    PolicyTier.objects.create(policy=p, after_years=10, extra_weeks=Decimal("2"))
    assert policies.tier_extra_weeks(p, emp, date(2024, 9, 30)) == Decimal("0")
    assert policies.tier_extra_weeks(p, emp, date(2024, 10, 1)) == Decimal("1")
    assert policies.tier_extra_weeks(p, emp, date(2029, 10, 1)) == Decimal("2")
