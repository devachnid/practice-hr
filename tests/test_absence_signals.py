from datetime import date
from decimal import Decimal

from absence.models import LedgerEntry, PolicyTier
from absence.services import ledger, pots
from people.services import contracts, employments
from tests.factories import absence_type, hours_employee, make_contract_type

D = Decimal


def test_contract_add_resyncs_open_pot(db, hr_admin):
    emp = hours_employee(amount=D("18.75"))
    pot = pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    ledger.sync_entitlement(pot)
    contracts.add(hr_admin, emp, make_contract_type(), D("18.75"), date(2026, 10, 1))
    row = pot.entries.filter(kind=LedgerEntry.Kind.REVISION).get()
    assert "contract" in row.note.lower()


def test_employment_end_resyncs(db, hr_admin):
    emp = hours_employee()
    pot = pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    ledger.sync_entitlement(pot)
    employments.end(hr_admin, emp, date(2026, 9, 30), "resigned")
    assert ledger.entitlement_lines_total(pot) == D("105.25")


def test_tier_added_resyncs_every_pot_of_the_type(db):
    a = hours_employee(continuous_service_date=date(2015, 1, 1))
    b = hours_employee(continuous_service_date=date(2026, 4, 1))
    pa = pots.for_day(a, absence_type("AL"), date(2026, 6, 1))
    pb = pots.for_day(b, absence_type("AL"), date(2026, 6, 1))
    ledger.sync_entitlement(pa)
    ledger.sync_entitlement(pb)
    policy = a.contracts.first().contract_type.policies.get()
    PolicyTier.objects.create(policy=policy, after_years=5, extra_weeks=D("1"))
    assert ledger.entitlement_lines_total(pa) == D("247.50")   # 6.6 × 37.5
    assert ledger.entitlement_lines_total(pb) == D("210.00")
