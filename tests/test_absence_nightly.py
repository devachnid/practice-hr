from datetime import date
from decimal import Decimal

from absence.services import nightly, pots
from tests.factories import (absence_type, hours_employee, make_contract, make_contract_type,
                             make_employment, make_pattern, make_policy)


def test_nightly_syncs_open_pots_and_bank_holidays(db):
    emp = hours_employee(start=date(2026, 4, 1))
    pot = pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))     # opened with 210.00
    emp.contracts.update(weekly_amount=Decimal("18.75"))              # behind the signals' back
    result = nightly.run(date(2026, 6, 1))
    assert result["pots_opened"] == 1                                  # next year's, at the new amount
    # this year's revision, and next year's opening entitlement (counted with the revisions)
    assert result["pots_synced"] == 2 and result["revisions"] == 2
    assert pot.entries.get(kind="revision").units == Decimal("-105.00")
    assert nightly.run(date(2026, 6, 1))["revisions"] == 0


def test_command_includes_absence(db, capsys):
    from django.core.management import call_command
    call_command("hr_nightly")
    assert "absence:" in capsys.readouterr().out


def test_a_pot_with_no_policy_is_reported_and_the_rest_still_sync(db):
    good = hours_employee(start=date(2026, 4, 1))
    other = make_contract_type("Other")
    bad = make_employment(start=date(2026, 4, 1))
    make_contract(bad, other)
    make_policy(other)
    make_pattern(bad)
    al = absence_type("AL")
    pots.for_day(good, al, date(2026, 6, 1))
    bad_pot = pots.for_day(bad, al, date(2026, 6, 1))
    other.policies.all().delete()   # the policy ends: no policy covers the pot's year
    result = nightly.run(date(2026, 6, 1))
    assert result["pots_synced"] == 2 and result["revisions"] == 1    # good's two years: next year's entitlement
    # the open pot cannot sync, and next year's cannot open
    assert len(result["failed"]) == 2 and str(bad_pot) in result["failed"][1]
    assert "No Annual leave policy for Other on 01 Apr 2027" in result["failed"][0]


def test_bank_holiday_keys_count_created_then_nothing(db):
    from absence.models import Policy
    emp = hours_employee()
    ct = emp.contracts.first().contract_type
    ct.policies.filter(absence_type__code="AL").update(bank_holiday_handling=Policy.BankHolidays.PRO_RATA_POT)
    make_policy(ct, "BH", bank_holiday_handling="pot")
    first = nightly.run(date(2026, 6, 1))                            # opens the pots itself
    assert first["bank_holiday_created"] == 10 + 6 and first["failed"] == []    # this year's and next
    second = nightly.run(date(2026, 6, 1))
    assert second["bank_holiday_created"] == 0 and second["bank_holiday_removed"] == 0
    assert second["bank_holiday_recosted"] == 0


def test_missing_bank_holiday_policy_is_reported_in_failed(db):
    from absence.models import Policy
    emp = hours_employee()
    pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    emp.contracts.first().contract_type.policies.filter(absence_type__code="AL").update(
        bank_holiday_handling=Policy.BankHolidays.PRO_RATA_POT)
    result = nightly.run(date(2026, 6, 1))
    assert any("No Bank holiday policy for Reception" in f for f in result["failed"])
    assert result["bank_holiday_created"] == 0


def test_nightly_removes_automatic_bank_holidays_after_the_leaving_date(db, hr_admin):
    from absence.models import Absence, LedgerEntry, Policy
    from absence.services import bank_holidays
    from people.services import contracts
    emp = hours_employee(start=date(2026, 4, 1))
    ct = emp.contracts.first().contract_type
    ct.policies.filter(absence_type__code="AL").update(bank_holiday_handling=Policy.BankHolidays.PRO_RATA_POT)
    make_policy(ct, "BH", bank_holiday_handling="pot")
    pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    bank_holidays.sync_auto_absences(emp, date(2026, 4, 1), date(2027, 3, 31))
    contracts.end(hr_admin, emp.contracts.get(), date(2026, 11, 30))
    # employments.end cancels them itself (test_absence_bookings); the nightly is the
    # safety net for a leaving date written some other way
    type(emp).objects.filter(pk=emp.pk).update(end_date=date(2026, 11, 30), leaving_reason="resigned")
    result = nightly.run(date(2026, 10, 1))
    # 25 and 28 Dec, 1 Jan, and Easter 2027 fall after the leaving date
    assert result["bank_holiday_removed"] == 5 and result["failed"] == []
    live = Absence.objects.filter(employment=emp, auto_bank_holiday=True, status="approved")
    assert live.count() == 5 and max(a.start_date for a in live) <= date(2026, 11, 30)
    cancellations = LedgerEntry.objects.filter(kind=LedgerEntry.Kind.CANCELLATION)
    assert cancellations.count() == 5 and {c.pot.absence_type.code for c in cancellations} == {"BH"}


def _pot_handling(emp):
    from absence.models import Policy
    ct = emp.contracts.first().contract_type
    ct.policies.filter(absence_type__code="AL").update(bank_holiday_handling=Policy.BankHolidays.PRO_RATA_POT)
    make_policy(ct, "BH", bank_holiday_handling="pot")


def test_a_new_starter_gets_entitlement_and_bank_holidays_from_one_run(db):
    from absence.models import Absence, LedgerEntry
    from absence.services import ledger
    emp = hours_employee(start=date(2026, 4, 1))       # never booked: no pot yet
    _pot_handling(emp)
    result = nightly.run(date(2026, 6, 1))
    assert result["pots_opened"] == 4 and result["failed"] == []      # AL and BH, this year and next
    assert result["bank_holiday_created"] == 10 + 6
    al = pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    bh = pots.for_day(emp, absence_type("BH"), date(2026, 6, 1))
    assert al.entries.get(kind=LedgerEntry.Kind.ENTITLEMENT).units == Decimal("210.00")
    assert bh.entries.get(kind=LedgerEntry.Kind.ENTITLEMENT).units == Decimal("75.00")
    assert Absence.objects.filter(employment=emp, auto_bank_holiday=True, status="approved",
                                  start_date__lte=date(2027, 3, 31)).count() == 10
    assert ledger.balance(bh) == Decimal("0.00")        # 75 accrued, ten 7.5-hour days charged
    again = nightly.run(date(2026, 6, 1))
    assert (again["pots_opened"], again["revisions"], again["bank_holiday_created"]) == (0, 0, 0)


def test_bootstrap_reports_an_employment_with_no_policy(db):
    other = make_contract_type("Other")
    emp = make_employment(start=date(2026, 4, 1))
    make_contract(emp, other)
    make_pattern(emp)
    result = nightly.run(date(2026, 6, 1))
    assert result["pots_opened"] == 0
    assert len(result["failed"]) == 1 and "No Annual leave policy for Other" in result["failed"][0]
    assert str(emp) in result["failed"][0]


def test_bootstrap_skips_employments_not_active_today(db):
    hours_employee(start=date(2026, 7, 1))              # starts next month
    assert nightly.run(date(2026, 6, 1))["pots_opened"] == 0


# --- next year's pots, and the other pot-backed types (I5) ------------------------------

def test_a_nightly_in_february_opens_next_years_annual_pot_with_its_bank_holidays(db):
    from absence.models import Absence, LedgerEntry, Policy
    emp = hours_employee(start=date(2026, 4, 1))
    Policy.objects.update(bank_holiday_handling=Policy.BankHolidays.INCLUDED_IN_ANNUAL)
    result = nightly.run(date(2027, 2, 15))
    assert result["pots_opened"] == 2 and result["failed"] == []
    nxt = pots.lookup(emp, absence_type("AL"), date(2027, 4, 1))
    assert (nxt.year_start, nxt.year_end) == (date(2027, 4, 1), date(2028, 3, 31))
    assert nxt.entries.get(kind=LedgerEntry.Kind.ENTITLEMENT).units == Decimal("210.00")
    charged = Absence.objects.filter(employment=emp, auto_bank_holiday=True, start_date__gte=date(2027, 4, 1))
    assert [a.start_date for a in charged.order_by("start_date")] == [
        date(2027, 5, 3), date(2027, 5, 31), date(2027, 8, 30), date(2027, 12, 27), date(2027, 12, 28),
        date(2028, 1, 3)]
    assert nxt.entries.filter(kind=LedgerEntry.Kind.BOOKING).count() == 6
    assert nightly.run(date(2027, 2, 15))["pots_opened"] == 0


def test_a_study_policy_gets_a_study_pot_and_a_type_without_one_gets_none(db):
    from absence.models import LedgerEntry, Pot
    emp = hours_employee(start=date(2026, 4, 1))
    make_policy(emp.contracts.first().contract_type, "STUDY", weeks_per_year=Decimal("1"))
    result = nightly.run(date(2026, 6, 1))
    assert result["failed"] == []                                     # nothing reported for TOIL
    study = Pot.objects.filter(employment=emp, absence_type__code="STUDY").order_by("year_start")
    assert [p.year_start for p in study] == [date(2026, 4, 1), date(2027, 4, 1)]
    assert all(p.entries.get(kind=LedgerEntry.Kind.ENTITLEMENT).units == Decimal("37.50") for p in study)
    assert not Pot.objects.filter(employment=emp, absence_type__code="TOIL").exists()   # earned: opens when earned


def test_next_year_is_not_opened_for_someone_leaving_before_it(db, hr_admin):
    from absence.models import Pot
    from people.services import contracts, employments
    emp = hours_employee(start=date(2026, 4, 1))
    contracts.end(hr_admin, emp.contracts.get(), date(2027, 1, 31))
    employments.end(hr_admin, emp, date(2027, 1, 31), "resigned")
    result = nightly.run(date(2026, 6, 1))
    assert result["pots_opened"] == 1 and result["failed"] == []
    assert list(Pot.objects.filter(employment=emp).values_list("year_start", flat=True)) == [date(2026, 4, 1)]


def test_a_missing_annual_policy_for_next_year_is_reported(db):
    other = make_contract_type("Other")
    emp = make_employment(start=date(2026, 4, 1))
    make_contract(emp, other)
    make_policy(other, effective_to=date(2027, 3, 31))
    make_pattern(emp)
    result = nightly.run(date(2026, 6, 1))
    assert result["pots_opened"] == 1
    assert result["failed"] == [f"{emp}: No Annual leave policy for Other on 01 Apr 2027. "
                                "Add one under Absence › Policies."]


def test_ending_the_employment_cancels_its_automatic_bank_holidays_at_once(db, hr_admin):
    from absence.models import Absence
    from absence.services import bank_holidays
    from people.services import contracts, employments
    emp = hours_employee(start=date(2026, 4, 1))
    _pot_handling(emp)
    pots.for_day(emp, absence_type("AL"), date(2026, 6, 1))
    bank_holidays.sync_auto_absences(emp, date(2026, 4, 1), date(2027, 3, 31))
    contracts.end(hr_admin, emp.contracts.get(), date(2026, 11, 30))
    employments.end(hr_admin, emp, date(2026, 11, 30), "resigned")
    live = Absence.objects.filter(employment=emp, auto_bank_holiday=True, status="approved")
    assert live.count() == 5 and max(a.start_date for a in live) <= date(2026, 11, 30)
    assert nightly.run(date(2026, 10, 1))["bank_holiday_removed"] == 0


def test_nightly_counts_automatic_bank_holidays_kept_cancelled(db, hr_admin):
    from datetime import timedelta

    from django.utils import timezone

    from absence.models import Absence, BankHoliday
    from absence.services import bookings
    today = timezone.localdate()
    day = today + timedelta(days=30)
    day += timedelta(days=(2 - day.weekday()) % 7)                   # a Wednesday they work
    BankHoliday.objects.get_or_create(date=day, nation="EW", defaults={"name": "Test holiday"})
    emp = hours_employee(start=today - timedelta(days=30))
    _pot_handling(emp)
    assert nightly.run(today)["failed"] == []
    bookings.cancel(hr_admin, Absence.objects.get(employment=emp, auto_bank_holiday=True, start_date=day))
    result = nightly.run(today)
    assert (result["bank_holiday_kept_cancelled"], result["bank_holiday_created"]) == (1, 0)

