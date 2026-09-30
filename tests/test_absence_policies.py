from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from absence.models import PolicyTier
from absence.services import policies
from tests.factories import (absence_type, make_contract, make_contract_type, make_employment,
                             make_policy)


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


@pytest.mark.seeded_policies
def test_seeded_policies(db):
    # 0004/0007 seeded 5.6 weeks from 1 April; 0012 moved the hours types to the practice's
    # standard contract: 22 days (4.4 weeks) from 1 January, 23/25/27 days after 1/3/5 years,
    # earned in monthly twelfths, bank holidays as a pot in the same year
    from absence.models import Policy
    rows = {(p.contract_type.name, p.absence_type.code): p
            for p in Policy.objects.select_related("contract_type", "absence_type")}
    hours = {"Practice nurse", "HCA", "Reception", "Administration", "Management"}
    sessions = {"Partner", "Salaried GP", "GP trainee"}
    assert set(rows) == {(n, "AL") for n in hours | sessions} | {(n, "BH") for n in hours}
    for (name, code), p in rows.items():
        assert p.effective_from == date(2020, 1, 1) and p.effective_to is None
        assert p.leave_year_basis == "fixed" and p.carry_over_max_weeks is None
        tiers = [(t.after_years, t.extra_weeks) for t in p.tiers.all()]
        if code == "BH":
            # the bank-holiday pot comes from the calendar (accrual.bank_holiday_entitlement),
            # so the policy carries no weeks of its own
            assert (p.year_start_month, p.year_start_day) == (1, 1)
            assert (p.weeks_per_year, p.rounding, p.bank_holiday_handling) == (Decimal("0"), Decimal("0.25"), "pot")
            assert p.accrual == "daily" and tiers == []
        elif name in sessions:
            assert (p.year_start_month, p.year_start_day) == (4, 1)
            assert (p.weeks_per_year, p.rounding, p.bank_holiday_handling) == (Decimal("5.6"), Decimal("0.5"), "closed")
            assert p.accrual == "daily" and tiers == []
        else:
            assert (p.year_start_month, p.year_start_day) == (1, 1)
            assert (p.weeks_per_year, p.rounding, p.bank_holiday_handling) == (Decimal("4.4"), Decimal("0.25"), "pot")
            assert p.accrual == "monthly"
            assert tiers == [(1, Decimal("0.2")), (3, Decimal("0.6")), (5, Decimal("1.0"))]


@pytest.mark.seeded_policies
@pytest.mark.parametrize("start,annual,bank", [
    (date(2026, 1, 1), Decimal("165.00"), Decimal("60.00")),     # 12 twelfths of 4.4 × 37.5; 8 × 7.5
    (date(2026, 3, 15), Decimal("137.50"), Decimal("52.50")),    # 10 twelfths; 7 holidays from 3 April
])
def test_the_seeded_standard_contract_in_2026(db, start, annual, bank):
    from absence.services import accrual, pots
    from tests.factories import hours_employee
    emp = hours_employee(start=start)                    # the seeded Reception type and its policies
    assert accrual.entitlement(pots.for_day(emp, absence_type("AL"), start)) == annual
    assert accrual.bank_holiday_entitlement(pots.for_day(emp, absence_type("BH"), start)) == bank


def _reseed():
    from importlib import import_module

    from django.apps import apps
    import_module("absence.migrations.0012_seed_standard_contract").seed(apps, None)


def _back_to_0004(name, **al_changes):
    """Put a seeded hours type's policies back as 0004 and 0007 left them, with `al_changes`."""
    from absence.models import Policy
    rows = Policy.objects.filter(contract_type__name=name)
    for p in rows:
        p.tiers.all().delete()
    rows.update(year_start_month=4, year_start_day=1, accrual="daily")
    rows.filter(absence_type__code="AL").update(**{"weeks_per_year": Decimal("5.6"), **al_changes})


def _state(name):
    from absence.models import Policy
    return {p.absence_type.code: (p.weeks_per_year, p.year_start_month, p.year_start_day, p.accrual,
                                  [(t.after_years, t.extra_weeks) for t in p.tiers.all()])
            for p in Policy.objects.filter(contract_type__name=name).select_related("absence_type")}


STANDARD = {"AL": (Decimal("4.4"), 1, 1, "monthly", [(1, Decimal("0.2")), (3, Decimal("0.6")), (5, Decimal("1.0"))]),
            "BH": (Decimal("0"), 1, 1, "daily", [])}


@pytest.mark.seeded_policies
def test_reseed_moves_rows_still_as_seeded_and_is_idempotent(db):
    _back_to_0004("Reception")
    _reseed()
    assert _state("Reception") == STANDARD
    _reseed()
    assert _state("Reception") == STANDARD                 # no second set of tiers


@pytest.mark.seeded_policies
@pytest.mark.parametrize("edit", [{"weeks_per_year": Decimal("6")}, {"rounding": Decimal("0.5")},
                                  {"carry_over_max_weeks": Decimal("1")}, {"effective_to": date(2030, 3, 31)}])
def test_reseed_leaves_an_edited_policy_and_its_bank_holiday_policy_alone(db, edit):
    _back_to_0004("HCA", **edit)
    before = _state("HCA")
    _reseed()
    assert _state("HCA") == before
    assert before["BH"][1:3] == (4, 1)                        # the two pots keep sharing a year


@pytest.mark.seeded_policies
def test_reseed_skips_a_contract_type_whose_staff_already_have_pots(db):
    # real pots keep the April dates they were opened with: moving the type's year would let
    # the nightly open January pots overlapping them
    from absence.models import Pot
    from people.models import ContractType
    from tests.factories import make_contract, make_employment
    _back_to_0004("HCA")
    _back_to_0004("Reception")
    emp = make_employment(start=date(2026, 4, 1))
    make_contract(emp, ContractType.objects.get(name="HCA"))
    Pot.objects.create(employment=emp, absence_type=absence_type("BH"), year_start=date(2026, 4, 1),
                       year_end=date(2027, 3, 31), unit="hours")
    before = _state("HCA")
    _reseed()
    assert _state("HCA") == before
    assert _state("Reception") == STANDARD


@pytest.mark.seeded_policies
def test_reseed_moves_neither_policy_when_the_bank_holiday_one_was_edited(db):
    from absence.models import Policy
    _back_to_0004("Administration")
    Policy.objects.filter(contract_type__name="Administration", absence_type__code="BH").update(
        rounding=Decimal("0.5"))
    before = _state("Administration")
    _reseed()
    assert _state("Administration") == before              # both stay in the April year


@pytest.mark.seeded_policies
def test_reseed_leaves_a_policy_given_tiers_alone(db):
    from absence.models import Policy, PolicyTier
    _back_to_0004("Management")
    PolicyTier.objects.create(policy=Policy.objects.get(contract_type__name="Management", absence_type__code="AL"),
                              after_years=10, extra_weeks=Decimal("1"))
    before = _state("Management")
    _reseed()
    assert _state("Management") == before


@pytest.mark.parametrize("month,day,field", [(13, 1, "year_start_month"), (4, 31, "year_start_day"),
                                             (0, 1, "year_start_month"), (2, 30, "year_start_day")])
def test_leave_year_start_must_be_a_real_date(db, month, day, field):
    from absence.models import Policy
    p = Policy(contract_type=make_contract_type(), absence_type=absence_type("AL"),
               effective_from=date(2026, 4, 1), year_start_month=month, year_start_day=day)
    with pytest.raises(ValidationError) as e:
        p.full_clean()
    assert field in e.value.message_dict


def test_leave_year_start_on_a_real_date_is_accepted(db):
    from absence.models import Policy
    Policy(contract_type=make_contract_type(), absence_type=absence_type("AL"), effective_from=date(2026, 4, 1),
           year_start_month=1, year_start_day=31).full_clean()
