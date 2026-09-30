from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from absence.models import Absence, LedgerEntry, Pot
from people.models import AuditEntry
from absence.services import balances, bookings, ledger, pots
from tests.factories import absence_type, hours_employee, make_pattern

D = Decimal
MON, WED = date(2026, 6, 1), date(2026, 6, 3)


def test_request_then_approve_writes_booking(db, hr_admin, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    assert a.status == Absence.Status.REQUESTED and a.cost_units == D("22.50")
    pot = pots.for_day(emp, absence_type("AL"), MON)
    assert not pot.entries.filter(kind=LedgerEntry.Kind.BOOKING).exists()
    bookings.approve(hr_admin, a, "fine")
    a.refresh_from_db()
    assert a.status == Absence.Status.APPROVED and a.decided_by == hr_admin
    line = pot.entries.get(kind=LedgerEntry.Kind.BOOKING)
    assert line.units == D("-22.50") and line.absence == a


def test_decline_writes_nothing(db, hr_admin, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("AL"), MON)
    bookings.decline(hr_admin, a, "short staffed")
    assert Absence.objects.get(pk=a.pk).status == Absence.Status.DECLINED
    assert LedgerEntry.objects.count() == 0


def test_cancel_restores_exactly(db, hr_admin, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    bookings.approve(hr_admin, a)
    pot = pots.for_day(emp, absence_type("AL"), MON)
    before = ledger.balance(pot)
    bookings.cancel(employee_user, a)
    assert ledger.balance(pot) == before + D("22.50")
    assert Absence.objects.get(pk=a.pk).status == Absence.Status.CANCELLED


def test_overlap_refused(db, employee_user):
    emp = hours_employee()
    bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    with pytest.raises(ValidationError):
        bookings.request(employee_user, emp, absence_type("AL"), WED)


def test_partial_only_for_hours_unit(db, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("DEP"), MON,
                         start_time=time(9, 0), end_time=time(10, 30), hours=D("1.5"))
    assert a.status == Absence.Status.APPROVED and a.cost_units == D("1.50")
    from tests.factories import make_contract, make_contract_type, make_employee, make_employment
    gp = make_employment(employee=make_employee(first="Gee"))
    make_contract(gp, make_contract_type("Salaried GP", "sessions", D("9")), amount=D("8"))
    make_pattern(gp, {d: (D("1"), D("1")) for d in range(4)})
    with pytest.raises(ValidationError):
        bookings.request(employee_user, gp, absence_type("DEP"), MON,
                         start_time=time(9, 0), end_time=time(10, 30), hours=D("1.5"))


def test_crossing_leave_year_refused(db, employee_user):
    emp = hours_employee()
    with pytest.raises(ValidationError) as e:
        bookings.request(employee_user, emp, absence_type("AL"), date(2027, 3, 29), date(2027, 4, 2))
    assert "two leave years" in str(e.value)


def test_sickness_needs_no_approval_and_no_pot(db, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("SICK"), MON, WED, category="illness")
    assert a.status == Absence.Status.APPROVED and a.self_certified
    assert LedgerEntry.objects.count() == 0


def test_sickness_over_seven_days_not_self_certified(db, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("SICK"), MON, date(2026, 6, 10), category="illness")
    assert not a.self_certified


def test_negative_balance_allowed_but_reported(db, hr_admin, employee_user):
    emp = hours_employee(amount=D("7.5"))          # 42 hours a year
    make_pattern(emp, {0: (D("3.75"), D("3.75"))}, effective_from=date(2026, 4, 2))
    pot = pots.for_day(emp, absence_type("AL"), MON)
    ledger.sync_entitlement(pot)
    for week in range(7):
        a = bookings.request(employee_user, emp, absence_type("AL"), MON + timedelta(weeks=week))
        bookings.approve(hr_admin, a)
    s = balances.summary(pot, date(2026, 6, 20))
    assert s["remaining"] == D("-10.50")
    assert s["taken"] == D("22.50") and s["booked"] == D("30.00")


def test_summary_keys(db, employee_user):
    emp = hours_employee()
    pot = pots.for_day(emp, absence_type("AL"), MON)
    ledger.sync_entitlement(pot)
    bookings.request(employee_user, emp, absence_type("AL"), MON)
    s = balances.summary(pot, MON)
    assert s == {"entitlement": D("210.00"), "carried_in": D("0"), "taken": D("0"), "booked": D("0"),
                 "pending": D("7.50"), "expired": D("0"), "adjustments": D("0"), "remaining": D("210.00")}


def _approved_mon_to_wed(hr_admin, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    bookings.approve(hr_admin, a)
    return emp, a


def test_recost_writes_one_adjustment_for_the_difference(db, hr_admin, employee_user):
    emp, a = _approved_mon_to_wed(hr_admin, employee_user)
    pot = pots.for_day(emp, absence_type("AL"), MON)
    make_pattern(emp, {0: (D("3.75"), D("3.75"))}, effective_from=date(2026, 4, 2))   # Mon only
    line = bookings.recost(hr_admin, a, "pattern changed")
    assert line.kind == LedgerEntry.Kind.ADJUSTMENT and line.units == D("15.00")   # 22.50 - 7.50
    assert pot.entries.filter(kind=LedgerEntry.Kind.ADJUSTMENT).count() == 1
    assert a.cost_units == D("7.50") and Absence.objects.get(pk=a.pk).cost_units == D("7.50")
    assert AuditEntry.objects.filter(object_id=a.pk, field="cost_units", before="22.50", after="7.50").exists()


def test_recost_with_no_change_writes_nothing(db, hr_admin, employee_user):
    emp, a = _approved_mon_to_wed(hr_admin, employee_user)
    count = LedgerEntry.objects.count()
    assert bookings.recost(hr_admin, a, "checked") is None
    assert LedgerEntry.objects.count() == count
    assert not LedgerEntry.objects.filter(kind=LedgerEntry.Kind.ADJUSTMENT).exists()


def test_cancel_after_recost_restores_starting_balance(db, hr_admin, employee_user):
    emp = hours_employee()
    pot = pots.for_day(emp, absence_type("AL"), MON)
    ledger.sync_entitlement(pot)
    start = ledger.balance(pot)
    a = bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    bookings.approve(hr_admin, a)
    make_pattern(emp, {0: (D("3.75"), D("3.75"))}, effective_from=date(2026, 4, 2))
    bookings.recost(hr_admin, a, "pattern changed")
    bookings.cancel(employee_user, a)
    assert ledger.balance(pot) == start


def test_recost_refused_unless_approved_and_pot_backed(db, hr_admin, employee_user):
    emp = hours_employee()
    requested = bookings.request(employee_user, emp, absence_type("AL"), MON)
    with pytest.raises(ValidationError):
        bookings.recost(hr_admin, requested, "no")
    sick = bookings.request(employee_user, emp, absence_type("SICK"), date(2026, 6, 8), category="illness")
    assert sick.status == Absence.Status.APPROVED
    with pytest.raises(ValidationError):
        bookings.recost(hr_admin, sick, "no")


def test_stale_second_approve_is_refused(db, hr_admin, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    stale = Absence.objects.get(pk=a.pk)
    bookings.approve(hr_admin, a)
    assert stale.status == Absence.Status.REQUESTED
    with pytest.raises(ValidationError):
        bookings.approve(hr_admin, stale)
    assert LedgerEntry.objects.filter(kind=LedgerEntry.Kind.BOOKING).count() == 1


def test_approve_refuses_a_second_ordinary_booking_over_the_same_days(db, hr_admin, employee_user):
    emp = hours_employee()
    first = bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    bookings.approve(hr_admin, first)
    # a row written before the first existed (say, from an import) and approved afterwards
    second = Absence.objects.create(employment=emp, absence_type=absence_type("AL"), start_date=WED,
                                    end_date=WED, cost_units=D("7.50"))
    with pytest.raises(ValidationError) as e:
        bookings.approve(hr_admin, second)
    assert "overlaps" in str(e.value)
    assert Absence.objects.get(pk=second.pk).status == Absence.Status.REQUESTED


def test_ordinary_bookings_and_automatic_bank_holidays_do_not_clash(db, employee_user):
    emp = hours_employee()
    auto = Absence.objects.create(employment=emp, absence_type=absence_type("BH"), start_date=MON,
                                  end_date=MON, status=Absence.Status.APPROVED, auto_bank_holiday=True)
    assert not bookings.overlaps(emp, MON, WED)
    assert bookings.overlaps(emp, MON, MON, auto=True)
    assert not bookings.overlaps(emp, MON, MON, auto=True, exclude_pk=auto.pk)
    bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    assert bookings.overlaps(emp, WED, WED)
    assert not bookings.overlaps(emp, WED, WED, auto=True)


def test_a_leavers_future_leave_is_cancelled_on_the_pot_it_was_booked_to(db, hr_admin):
    from people.services import contracts, employments
    emp = hours_employee()
    leave = bookings.approve(hr_admin, bookings.request(hr_admin, emp, absence_type("AL"),
                                                        date(2026, 12, 14), date(2026, 12, 16)))
    booking = leave.ledger_entries.get(kind=LedgerEntry.Kind.BOOKING)
    contracts.end(hr_admin, emp.contracts.get(), date(2026, 11, 30))
    # ending the employment cancels it (bookings.cancel): no contract on 14 Dec any more must not matter
    employments.end(hr_admin, emp, date(2026, 11, 30), "resigned")
    line = leave.ledger_entries.get(kind=LedgerEntry.Kind.CANCELLATION)
    assert line.pot == booking.pot and line.units == D("22.50")
    assert Absence.objects.get(pk=leave.pk).status == Absence.Status.CANCELLED


def test_recost_and_cancel_stay_on_the_booked_pot_after_the_leave_year_changes(db, hr_admin):
    emp = hours_employee(start=date(2025, 10, 1))
    leave = bookings.approve(hr_admin, bookings.request(hr_admin, emp, absence_type("AL"), MON, WED))
    booked_pot = leave.ledger_entries.get().pot
    assert booked_pot.year_start == date(2026, 4, 1)
    # the policy moves to anniversary years: today's resolution of 1 June is the 2025/26 pot
    emp.contracts.first().contract_type.policies.update(leave_year_basis="anniversary")
    make_pattern(emp, {0: (D("3.75"), D("3.75"))}, effective_from=date(2026, 5, 1))   # Mon only
    pots_before = set(Pot.objects.values_list("pk", flat=True))
    line = bookings.recost(hr_admin, leave, "pattern changed")
    assert line.pot == booked_pot and line.units == D("15.00")
    bookings.cancel(hr_admin, leave)
    cancellation = leave.ledger_entries.get(kind=LedgerEntry.Kind.CANCELLATION)
    assert cancellation.pot == booked_pot and cancellation.units == D("7.50")
    assert set(Pot.objects.values_list("pk", flat=True)) == pots_before   # nothing re-resolved


def test_a_first_booking_on_a_fresh_pot_shows_a_positive_balance(db, hr_admin, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    bookings.approve(hr_admin, a)
    pot = pots.for_day(emp, absence_type("AL"), MON)
    assert ledger.balance(pot) == D("187.50")               # 210 accrued, 22.50 booked
    assert balances.summary(pot, MON)["entitlement"] == D("210.00")


@pytest.mark.parametrize("handling,charged_to", [("pot", "BH"), ("annual", "AL")])
def test_opening_the_annual_pot_charges_the_years_bank_holidays_once(db, hr_admin, employee_user,
                                                                     handling, charged_to):
    from absence.models import Policy
    from tests.factories import make_policy
    emp = hours_employee()
    ct = emp.contracts.first().contract_type
    ct.policies.filter(absence_type__code="AL").update(bank_holiday_handling=handling)
    if handling == Policy.BankHolidays.PRO_RATA_POT:
        make_policy(ct, "BH", bank_holiday_handling="pot")
    bookings.approve(hr_admin, bookings.request(employee_user, emp, absence_type("AL"), MON, WED))
    autos = Absence.objects.filter(employment=emp, auto_bank_holiday=True, status="approved")
    assert autos.count() == 10
    assert {a.ledger_entries.get().pot.absence_type.code for a in autos} == {charged_to}
    al = pots.for_day(emp, absence_type("AL"), MON)
    if handling == Policy.BankHolidays.PRO_RATA_POT:
        bh = pots.for_day(emp, absence_type("BH"), MON)
        assert ledger.balance(bh) == D("0.00")              # 75 accrued on opening, 75 charged
        assert ledger.balance(al) == D("187.50")
    else:
        assert ledger.balance(al) == D("112.50")            # 210 - 75 bank holidays - 22.50


def test_preview_costs_without_writing(db, employee_user):
    emp = hours_employee()
    a = bookings.preview(emp, absence_type("AL"), MON, WED)
    assert a.pk is None and a.cost_units == D("22.50")
    assert not Absence.objects.exists() and not Pot.objects.exists()
    bookings.request(employee_user, emp, absence_type("AL"), MON, WED)
    with pytest.raises(ValidationError, match="already an absence"):
        bookings.preview(emp, absence_type("AL"), WED)


def test_request_stores_expected_family_dates(db, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("MAT"), date(2026, 7, 1), date(2027, 3, 31),
                         expected_start=date(2026, 7, 1), expected_return=date(2027, 4, 1))
    a.refresh_from_db()
    assert (a.expected_start, a.expected_return) == (date(2026, 7, 1), date(2027, 4, 1))
    with pytest.raises(ValidationError, match="Only family leave"):
        bookings.request(employee_user, emp, absence_type("AL"), MON, expected_return=WED)
    with pytest.raises(ValidationError, match="after the expected start"):
        bookings.request(employee_user, emp, absence_type("PAT"), date(2027, 6, 1),
                         expected_start=date(2027, 6, 1), expected_return=date(2027, 5, 1))


def test_set_family_dates_audits_each_change(db, hr_admin, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("MAT"), date(2026, 7, 1), date(2027, 3, 31),
                         expected_start=date(2026, 7, 1))
    out = bookings.set_family_dates(hr_admin, a, expected_start=date(2026, 7, 1), actual_start=date(2026, 7, 6),
                                    expected_return=date(2027, 4, 5))
    assert out is a and a.actual_start == date(2026, 7, 6)
    a.refresh_from_db()
    assert (a.expected_start, a.actual_start, a.expected_return) == (
        date(2026, 7, 1), date(2026, 7, 6), date(2027, 4, 5))
    rows = AuditEntry.objects.filter(model="absence.absence", object_id=a.pk, actor=hr_admin)
    assert {(r.field, r.before, r.after) for r in rows} == {
        ("actual_start", "", "2026-07-06"), ("expected_return", "", "2027-04-05")}


def test_set_family_dates_refuses_a_return_before_the_start_or_another_type(db, hr_admin, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("MAT"), date(2026, 7, 1), date(2027, 3, 31))
    with pytest.raises(ValidationError, match="after the actual start"):
        bookings.set_family_dates(hr_admin, a, actual_start=date(2026, 7, 6), expected_return=date(2026, 7, 1))
    a.refresh_from_db()
    assert a.actual_start is None
    leave = bookings.request(employee_user, emp, absence_type("AL"), MON)
    with pytest.raises(ValidationError, match="Only family leave"):
        bookings.set_family_dates(hr_admin, leave, actual_start=MON)


def test_add_kit_day_within_live_family_leave_once(db, employee_user):
    emp = hours_employee()
    a = bookings.request(employee_user, emp, absence_type("MAT"), date(2026, 7, 1), date(2027, 3, 31))
    bookings.add_kit_day(employee_user, a, date(2026, 9, 15))
    bookings.add_kit_day(employee_user, a, date(2026, 9, 15))
    assert a.kit_days.count() == 1
    assert AuditEntry.objects.filter(model="absence.absence", object_id=a.pk, field="kit_day",
                                     after="2026-09-15").count() == 1
    with pytest.raises(ValidationError, match="within the leave"):
        bookings.add_kit_day(employee_user, a, date(2027, 4, 1))
    leave = bookings.request(employee_user, emp, absence_type("AL"), MON)
    with pytest.raises(ValidationError, match="family leave"):
        bookings.add_kit_day(employee_user, leave, MON)
    bookings.cancel(employee_user, a)
    with pytest.raises(ValidationError, match="requested or approved"):
        bookings.add_kit_day(employee_user, a, date(2026, 9, 16))


def test_ending_an_employment_cancels_the_live_absences_after_the_leaving_date(db, hr_admin, employee_user):
    from people.models import AuditEntry
    from people.services import employments
    emp = hours_employee()
    al = absence_type("AL")
    before = bookings.approve(hr_admin, bookings.request(employee_user, emp, al, date(2026, 11, 23)))
    spanning = bookings.approve(hr_admin, bookings.request(employee_user, emp, al, date(2026, 11, 30),
                                                           date(2026, 12, 2)))
    after = bookings.approve(hr_admin, bookings.request(employee_user, emp, al, date(2026, 12, 14),
                                                        date(2026, 12, 16)))
    waiting = bookings.request(employee_user, emp, al, date(2027, 1, 11))
    booked_pot = after.ledger_entries.get().pot
    employments.end(hr_admin, emp, date(2026, 12, 1), "resigned")
    status = dict(Absence.objects.values_list("pk", "status"))
    assert status[after.pk] == status[waiting.pk] == Absence.Status.CANCELLED
    assert status[before.pk] == status[spanning.pk] == Absence.Status.APPROVED     # started by then: untouched
    line = after.ledger_entries.get(kind=LedgerEntry.Kind.CANCELLATION)
    assert line.pot == booked_pot and line.units == D("22.50") and line.actor == hr_admin
    assert not waiting.ledger_entries.exists()
    note = AuditEntry.objects.get(model="people.employment", object_id=emp.pk, field="end_date").note
    assert note.startswith("cancelled 2 absence(s) after the leaving date") and "14 Dec" in note


def test_ending_an_employment_leaves_an_absence_on_a_closed_pot_and_says_so(db, hr_admin, employee_user):
    from people.models import AuditEntry
    from people.services import employments
    from absence.services import year_end
    emp = hours_employee(start=date(2025, 4, 1))
    late = bookings.approve(hr_admin, bookings.request(employee_user, emp, absence_type("AL"), date(2027, 3, 15)))
    year_end.close(late.ledger_entries.get().pot)
    employments.end(hr_admin, emp, date(2027, 3, 1), "resigned")              # recorded late
    assert Absence.objects.get(pk=late.pk).status == Absence.Status.APPROVED
    note = AuditEntry.objects.get(model="people.employment", object_id=emp.pk, field="end_date").note
    assert "not cancelled" in note and "closed" in note


def _weekdays(start, n):
    """n consecutive weekdays from `start` on (a weekend start moves to Monday)."""
    days, day = [], start
    while len(days) < n:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def _leaver_with_absences(hr_admin, employee_user, cancellable, uncancellable_year_end=False):
    """A leaver whose spell ended on 1 March of the current leave year's first
    calendar year, with `cancellable` approved single days in the current leave
    year and, if asked, one approved day in the closed previous year."""
    from absence.services import year_end
    from people.services import employments
    from tests.factories import current_leave_year
    ly_start, _ = current_leave_year()
    emp = hours_employee(start=date(ly_start.year - 2, 4, 1))
    al = absence_type("AL")
    if uncancellable_year_end:
        late = bookings.approve(hr_admin, bookings.request(employee_user, emp, al,
                                                           _weekdays(date(ly_start.year, 3, 10), 1)[0]))
        year_end.close(late.ledger_entries.get().pot)
    for day in _weekdays(ly_start + timedelta(days=14), cancellable):
        bookings.approve(hr_admin, bookings.request(employee_user, emp, al, day))
    employments.end(hr_admin, emp, date(ly_start.year, 3, 1), "resigned")      # recorded late
    return emp


def _end_note(emp):
    from people.models import AuditEntry
    return AuditEntry.objects.get(model="people.employment", object_id=emp.pk, field="end_date").note


def test_the_leaver_note_lists_what_was_not_cancelled_first_even_when_it_is_long(db, hr_admin, employee_user):
    emp = _leaver_with_absences(hr_admin, employee_user, cancellable=10, uncancellable_year_end=True)
    note = _end_note(emp)
    assert note.startswith("not cancelled:") and "closed" in note
    assert len(note) <= 200
    assert Absence.objects.filter(employment=emp, status=Absence.Status.CANCELLED).count() == 10


def test_a_leaver_note_that_overflows_ends_with_an_ellipsis(db, hr_admin, employee_user):
    emp = _leaver_with_absences(hr_admin, employee_user, cancellable=12)
    note = _end_note(emp)
    assert len(note) == 200 and note.endswith("…")
    assert note.startswith("cancelled 12 absence(s) after the leaving date: ")


def test_a_leaver_note_with_nothing_left_over_is_just_the_cancelled_part(db, hr_admin, employee_user):
    emp = _leaver_with_absences(hr_admin, employee_user, cancellable=2)
    note = _end_note(emp)
    assert note.startswith("cancelled 2 absence(s) after the leaving date: ")
    assert "not cancelled" not in note and not note.endswith("…")


def test_record_with_no_comment_says_who_recorded_it(db, hr_admin):
    from tests.factories import make_employee
    make_employee(first="Jo", last="Bloggs", user=hr_admin)
    emp = hours_employee()
    a = bookings.record(hr_admin, emp, absence_type("AL"), MON)
    assert a.status == Absence.Status.APPROVED and a.decision_comment == "Recorded by Jo Bloggs"


def test_record_keeps_a_comment_it_is_given(db, hr_admin):
    from tests.factories import make_employee
    make_employee(first="Jo", last="Bloggs", user=hr_admin)
    a = bookings.record(hr_admin, hours_employee(), absence_type("AL"), MON, comment="Agreed in person")
    assert a.decision_comment == "Agreed in person"


def test_record_by_an_actor_with_no_employee_falls_back_to_their_email(db, hr_admin):
    a = bookings.record(hr_admin, hours_employee(), absence_type("AL"), MON)
    assert a.decision_comment == "Recorded by hr@example.com"
