from datetime import date, timedelta
from decimal import Decimal

from absence.models import LedgerEntry
from absence.services import accrual, ledger, pots
from people.services import contracts
from tests.factories import absence_type, current_leave_year, hours_employee, make_contract_type

D = Decimal


def test_first_sync_writes_entitlement(db):
    pot = pots.for_day(hours_employee(), absence_type("AL"), date(2026, 6, 1), sync=False)
    row = ledger.sync_entitlement(pot, cause="pot created")
    assert row.kind == LedgerEntry.Kind.ENTITLEMENT and row.units == D("210.00")
    assert row.note == "pot created"


def test_second_sync_is_a_no_op(db):
    pot = pots.for_day(hours_employee(), absence_type("AL"), date(2026, 6, 1))
    ledger.sync_entitlement(pot)
    assert ledger.sync_entitlement(pot) is None
    assert pot.entries.count() == 1


def test_contract_change_writes_one_revision(db, hr_admin):
    start, _ = current_leave_year()
    emp = hours_employee(start=start, amount=D("18.75"))
    pot = pots.for_day(emp, absence_type("AL"), start + timedelta(days=61))
    ledger.sync_entitlement(pot)
    contracts.add(hr_admin, emp, make_contract_type(), D("18.75"), start + timedelta(days=183))
    # the contract signal has already re-synced; a further sync finds nothing to do
    row = pot.entries.filter(kind=LedgerEntry.Kind.REVISION).get()
    assert ledger.sync_entitlement(pot) is None
    # 105 for the first contract's year, plus the second contract's part-year on top
    assert ledger.entitlement_lines_total(pot) == accrual.entitlement(pot)
    assert D("105.00") < ledger.entitlement_lines_total(pot) < D("210.00")
    assert row.units == ledger.entitlement_lines_total(pot) - D("105.00")
    assert row.note.startswith("contract added")


def test_change_that_rounds_to_nothing_writes_nothing(db, hr_admin):
    start, end = current_leave_year()
    emp = hours_employee(start=start)
    pot = pots.for_day(emp, absence_type("AL"), start + timedelta(days=61))
    ledger.sync_entitlement(pot)
    contracts.add(hr_admin, emp, make_contract_type(), D("0.01"), end)
    assert ledger.sync_entitlement(pot) is None
    assert pot.entries.count() == 1   # the signal wrote nothing either


def test_bank_holiday_pot_syncs_from_its_own_formula(db):
    from absence.models import Policy
    from tests.factories import make_policy
    emp = hours_employee(amount=D("18.75"))
    ct = emp.contracts.first().contract_type
    ct.policies.filter(absence_type__code="AL").update(bank_holiday_handling=Policy.BankHolidays.PRO_RATA_POT)
    make_policy(ct, "BH", bank_holiday_handling="pot")
    pot = pots.for_day(emp, absence_type("BH"), date(2026, 6, 1), sync=False)
    row = ledger.sync_entitlement(pot, cause="pot created")
    assert row.kind == LedgerEntry.Kind.ENTITLEMENT
    assert row.units == accrual.bank_holiday_entitlement(pot) == D("37.50")   # ten holidays / 5 × 18.75


def test_line_dates(db, hr_admin):
    from django.utils import timezone
    start, _ = current_leave_year()
    emp = hours_employee(start=start, amount=D("18.75"))
    pot = pots.for_day(emp, absence_type("AL"), start + timedelta(days=61), sync=False)
    first = ledger.sync_entitlement(pot)
    assert first.date == pot.year_start
    contracts.add(hr_admin, emp, make_contract_type(), D("18.75"), start + timedelta(days=183))
    revision = pot.entries.filter(kind=LedgerEntry.Kind.REVISION).get()   # written by the signal
    assert revision.date == timezone.localdate()


def test_resync_contract_type_touches_only_open_pots_of_that_type_and_contract_type(db, hr_admin):
    from absence.models import Policy
    from tests.factories import make_contract, make_employment, make_pattern, make_policy
    start, _ = current_leave_year()
    reception = make_contract_type()
    other = make_contract_type("Other")
    ours = hours_employee(start=start)                        # Reception all year
    theirs = make_employment(start=start)                     # Other only
    make_contract(theirs, other)
    make_policy(other)
    make_pattern(theirs)
    last_year = hours_employee(start=start.replace(year=start.year - 1))   # Reception, a closed pot too
    al = absence_type("AL")
    open_pots = [pots.for_day(e, al, start) for e in (ours, theirs, last_year)]
    closed = pots.for_day(last_year, al, start - timedelta(days=1))
    Policy.objects.filter(contract_type=reception).update(weeks_per_year=D("6"))
    result = ledger.resync_contract_type(reception, al, actor=hr_admin, cause="policy changed")
    assert result == {"revised": 2, "failed": []}
    revised = {p.pk for p in open_pots + [closed] if p.entries.filter(kind=LedgerEntry.Kind.REVISION).exists()}
    assert revised == {open_pots[0].pk, open_pots[2].pk}
