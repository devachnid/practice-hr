from datetime import timedelta
from decimal import Decimal

from absence.models import LedgerEntry, PolicyTier
from absence.services import accrual, ledger, pots
from people.services import contracts, employments
from tests.factories import absence_type, current_leave_year, hours_employee, make_contract_type

D = Decimal


def test_contract_add_resyncs_open_pot(db, hr_admin):
    start, _ = current_leave_year()
    emp = hours_employee(start=start, amount=D("18.75"))
    pot = pots.for_day(emp, absence_type("AL"), start + timedelta(days=61))
    ledger.sync_entitlement(pot)
    contracts.add(hr_admin, emp, make_contract_type(), D("18.75"), start + timedelta(days=183))
    row = pot.entries.filter(kind=LedgerEntry.Kind.REVISION).get()
    assert "contract" in row.note.lower()


def test_employment_end_resyncs(db, hr_admin):
    start, _ = current_leave_year()
    emp = hours_employee(start=start)
    pot = pots.for_day(emp, absence_type("AL"), start + timedelta(days=61))
    ledger.sync_entitlement(pot)
    full_year = ledger.entitlement_lines_total(pot)
    employments.end(hr_admin, emp, start + timedelta(days=182), "resigned")
    assert ledger.entitlement_lines_total(pot) == accrual.entitlement(pot)
    assert ledger.entitlement_lines_total(pot) < full_year


def test_tier_added_resyncs_every_pot_of_the_type(db):
    start, _ = current_leave_year()
    day = start + timedelta(days=61)
    a = hours_employee(start=start, continuous_service_date=start.replace(year=start.year - 11))
    b = hours_employee(start=start, continuous_service_date=start)
    pa = pots.for_day(a, absence_type("AL"), day)
    pb = pots.for_day(b, absence_type("AL"), day)
    ledger.sync_entitlement(pa)
    ledger.sync_entitlement(pb)
    policy = a.contracts.first().contract_type.policies.get()
    PolicyTier.objects.create(policy=policy, after_years=5, extra_weeks=D("1"))
    assert ledger.entitlement_lines_total(pa) == D("6.6") * D("37.5")
    assert ledger.entitlement_lines_total(pb) == D("5.6") * D("37.5")

