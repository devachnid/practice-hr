from datetime import date
from decimal import Decimal

from absence.models import LedgerEntry
from absence.services import ledger, pots
from people.services import contracts
from tests.factories import absence_type, hours_employee, make_contract_type

D = Decimal


def test_first_sync_writes_entitlement(db):
    pot = pots.for_day(hours_employee(), absence_type("AL"), date(2026, 6, 1))
    row = ledger.sync_entitlement(pot, cause="pot created")
    assert row.kind == LedgerEntry.Kind.ENTITLEMENT and row.units == D("210.00")
    assert row.note == "pot created"


def test_second_sync_is_a_no_op(db):
    pot = pots.for_day(hours_employee(), absence_type("AL"), date(2026, 6, 1))
    ledger.sync_entitlement(pot)
    assert ledger.sync_entitlement(pot) is None
    assert pot.entries.count() == 1


def test_contract_change_writes_one_revision(db, hr_admin):
    emp = hours_employee(amount=D("18.75"))
    pot = pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    ledger.sync_entitlement(pot)
    contracts.add(hr_admin, emp, make_contract_type(), D("18.75"), date(2026, 10, 1))
    row = ledger.sync_entitlement(pot, hr_admin, cause="contract added 1 Oct")
    assert row.kind == LedgerEntry.Kind.REVISION
    # 105 + 5.6 × 18.75 × 182/365 = 105 + 52.36 → 157.25 total; revision is the difference
    assert ledger.entitlement_lines_total(pot) == D("157.25")
    assert row.units == D("52.25") and row.note == "contract added 1 Oct"


def test_change_that_rounds_to_nothing_writes_nothing(db, hr_admin):
    emp = hours_employee()
    pot = pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    ledger.sync_entitlement(pot)
    contracts.add(hr_admin, emp, make_contract_type(), D("0.01"), date(2027, 3, 31))
    assert ledger.sync_entitlement(pot) is None
