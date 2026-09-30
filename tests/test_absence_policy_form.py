"""The policy admin form: an hours contract type's entitlement, tiers and
carry-over cap are entered in full-time days and stored as weeks (days ÷ 5);
a sessions contract type keeps its weeks fields."""
from datetime import date
from decimal import Decimal

import pytest
from django.utils.html import escape

from absence.models import Policy, PolicyTier
from tests.factories import absence_type, make_contract_type, make_policy
from tests.test_absence_admin import _policy_post

D = Decimal


def _hours_policy(**kw):
    kw.setdefault("weeks_per_year", D("4.4"))
    policy = make_policy(make_contract_type(), year_start_month=1, **kw)
    PolicyTier.objects.create(policy=policy, after_years=1, extra_weeks=D("0.2"))
    PolicyTier.objects.create(policy=policy, after_years=3, extra_weeks=D("0.6"))
    return policy


def _change(policy):
    return f"/admin/absence/policy/{policy.pk}/change/"


def _save(client, policy, **changes):
    return client.post(_change(policy), _policy_post(policy, **changes), follow=True)


def test_an_hours_policy_shows_days_not_weeks(admin_client, db):
    policy = _hours_policy()
    page = admin_client.get(_change(policy)).content.decode()
    assert 'name="days_per_year"' in page and 'value="22"' in page       # 4.4 weeks × 5
    assert 'name="weeks_per_year"' not in page
    assert "= 4.4 weeks" in page                                          # the stored figure, read-only
    assert 'name="tiers-0-days"' in page and 'value="23"' in page          # 4.4 + 0.2 weeks
    assert 'name="tiers-1-days"' in page and 'value="25"' in page          # 4.4 + 0.6 weeks
    assert 'name="tiers-0-extra_weeks"' not in page
    assert "+0.2 weeks" in page and "+0.6 weeks" in page


def test_days_are_stored_as_weeks_and_tiers_as_extra_weeks(admin_client, db):
    policy = _hours_policy()
    resp = _save(admin_client, policy, fields={"days_per_year": "24"},
                 tier_values=["26", "28"], new_tiers=[(5, "30")])
    assert resp.status_code == 200 and "pot(s) revised" in resp.content.decode()
    policy.refresh_from_db()
    assert policy.weeks_per_year == D("4.80")
    assert [(t.after_years, t.extra_weeks) for t in policy.tiers.all()] == [
        (1, D("0.40")), (3, D("0.80")), (5, D("1.20"))]


def test_the_standard_top_tier_27_days_is_one_extra_week(admin_client, db):
    policy = _hours_policy()                                        # 22 days
    _save(admin_client, policy, new_tiers=[(5, "27")])
    assert policy.tiers.get(after_years=5).extra_weeks == D("1.00")   # (27 − 22) / 5


def test_round_trip_saves_nothing_new(admin_client, db):
    policy = _hours_policy(carry_over_max_weeks=D("1"))
    resp = _save(admin_client, policy)
    assert "pot(s) revised" in resp.content.decode()
    policy.refresh_from_db()
    assert (policy.weeks_per_year, policy.carry_over_max_weeks) == (D("4.40"), D("1.00"))
    assert [t.extra_weeks for t in policy.tiers.all()] == [D("0.20"), D("0.60")]


def test_changing_the_base_days_keeps_the_tier_totals(admin_client, db):
    # the tiers are totals ("23 days after 1 year"): a lower base widens the step to them
    policy = _hours_policy()
    _save(admin_client, policy, fields={"days_per_year": "21"})
    policy.refresh_from_db()
    assert policy.weeks_per_year == D("4.20")
    assert [t.extra_weeks for t in policy.tiers.all()] == [D("0.40"), D("0.80")]   # 23 and 25 days still


def test_carry_over_cap_in_days(admin_client, db):
    policy = _hours_policy()
    page = admin_client.get(_change(policy)).content.decode()
    assert 'name="carry_over_days"' in page and 'name="carry_over_max_weeks"' not in page
    _save(admin_client, policy, fields={"carry_over_days": "5"})
    policy.refresh_from_db()
    assert policy.carry_over_max_weeks == D("1.00")
    _save(admin_client, policy, fields={"carry_over_days": ""})
    policy.refresh_from_db()
    assert policy.carry_over_max_weeks is None                   # blank: nothing carries


@pytest.mark.parametrize("fields,tiers,message", [
    ({"days_per_year": "0"}, None, "more than zero days"),
    ({"days_per_year": "-5"}, None, "more than zero days"),
    ({"days_per_year": "22.03"}, None, "multiple of 0.05"),
    ({"days_per_year": ""}, None, "This field is required"),
    ({}, ["21", "25"], "at least the 22 full-time days"),
    ({}, ["25", "23"], "fewer days than an earlier tier"),
    ({"days_per_year": "26"}, None, "at least the 26 full-time days"),   # the tiers' 23 and 25 are now below it
])
def test_invalid_days_are_refused_and_nothing_is_saved(admin_client, db, fields, tiers, message):
    policy = _hours_policy()
    resp = _save(admin_client, policy, fields=fields, tier_values=tiers)
    assert resp.status_code == 200 and message in resp.content.decode()
    policy.refresh_from_db()
    assert policy.weeks_per_year == D("4.40")
    assert [t.extra_weeks for t in policy.tiers.all()] == [D("0.20"), D("0.60")]


def test_a_sessions_policy_keeps_weeks(admin_client, db):
    policy = make_policy(make_contract_type("Salaried GP", "sessions", D("9")), weeks_per_year=D("6"))
    PolicyTier.objects.create(policy=policy, after_years=5, extra_weeks=D("1"))
    page = admin_client.get(_change(policy)).content.decode()
    assert 'name="weeks_per_year"' in page and 'name="days_per_year"' not in page
    assert 'name="carry_over_max_weeks"' in page and 'name="carry_over_days"' not in page
    assert 'name="tiers-0-extra_weeks"' in page and 'name="tiers-0-days"' not in page
    _save(admin_client, policy, fields={"weeks_per_year": "6.5"})
    policy.refresh_from_db()
    assert policy.weeks_per_year == D("6.50") and policy.tiers.get().extra_weeks == D("1.00")


def _add_post(ct, code="AL", **fields):
    data = {"contract_type": ct.pk, "absence_type": absence_type(code).pk, "effective_from": "2020-01-01",
            "effective_to": "", "days_per_year": "", "weeks_per_year": "", "leave_year_basis": "fixed",
            "year_start_month": 1, "year_start_day": 1, "carry_over_days": "", "carry_over_max_weeks": "",
            "carry_over_expires_after_days": "", "rounding": "0.25", "bank_holiday_handling": "pot",
            "accrual": "daily",
            "tiers-TOTAL_FORMS": 0, "tiers-INITIAL_FORMS": 0, "tiers-MIN_NUM_FORMS": 0,
            "tiers-MAX_NUM_FORMS": 1000}
    tiers = fields.pop("tiers", [])
    data.update(fields)
    data["tiers-TOTAL_FORMS"] = len(tiers)
    for i, (years, value, unit) in enumerate(tiers):
        data.update({f"tiers-{i}-after_years": years, f"tiers-{i}-{unit}": value})
    return data


def test_the_add_form_offers_days_and_weeks_until_the_contract_type_is_known(admin_client, db):
    page = admin_client.get("/admin/absence/policy/add/").content.decode()
    assert 'name="days_per_year"' in page and 'name="weeks_per_year"' in page
    assert 'name="carry_over_days"' in page and 'name="carry_over_max_weeks"' in page


def test_adding_an_hours_policy_in_days(admin_client, db):
    ct = make_contract_type("TUPE 2019")
    resp = admin_client.post("/admin/absence/policy/add/", _add_post(
        ct, days_per_year="25", carry_over_days="2.5", tiers=[(2, "26", "days")]), follow=True)
    assert resp.status_code == 200 and "pot(s) revised" in resp.content.decode()
    policy = Policy.objects.get(contract_type=ct)
    assert (policy.weeks_per_year, policy.carry_over_max_weeks) == (D("5.00"), D("0.50"))
    assert policy.tiers.get().extra_weeks == D("0.20")


def test_adding_an_hours_policy_needs_days(admin_client, db):
    ct = make_contract_type("TUPE 2019")
    resp = admin_client.post("/admin/absence/policy/add/", _add_post(ct, weeks_per_year="5"), follow=True)
    assert "Enter the full-time days per year" in resp.content.decode()
    assert not Policy.objects.filter(contract_type=ct).exists()


def test_adding_a_sessions_policy_in_weeks(admin_client, db):
    ct = make_contract_type("Locum GP", "sessions", D("9"))
    resp = admin_client.post("/admin/absence/policy/add/", _add_post(
        ct, weeks_per_year="6", rounding="0.5", bank_holiday_handling="closed",
        tiers=[(5, "1", "extra_weeks")]), follow=True)
    assert "pot(s) revised" in resp.content.decode()
    policy = Policy.objects.get(contract_type=ct)
    assert policy.weeks_per_year == D("6.00") and policy.tiers.get().extra_weeks == D("1.00")


def test_adding_a_sessions_policy_in_days_is_refused(admin_client, db):
    ct = make_contract_type("Locum GP", "sessions", D("9"))
    resp = admin_client.post("/admin/absence/policy/add/", _add_post(ct, days_per_year="30"), follow=True)
    assert "Days are for hours contracts" in resp.content.decode()
    assert not Policy.objects.filter(contract_type=ct).exists()


def test_policy_changelist_shows_days_for_hours(admin_client, db):
    _hours_policy()
    make_policy(make_contract_type("Salaried GP", "sessions", D("9")), weeks_per_year=D("6"),
                effective_from=date(2020, 1, 1))
    page = admin_client.get("/admin/absence/policy/").content.decode()
    assert "22 days (4.4 weeks)" in page and "6 weeks" in page


def test_the_accrual_basis_is_chosen_on_the_policy_page(admin_client, db):
    policy = _hours_policy()
    assert policy.accrual == Policy.Accrual.DAILY                 # the default: day by day, as before
    assert 'name="accrual"' in admin_client.get(_change(policy)).content.decode()
    _save(admin_client, policy, fields={"accrual": "monthly"})
    policy.refresh_from_db()
    assert policy.accrual == Policy.Accrual.MONTHLY


def _bank_holiday_policy(**kw):
    kw.setdefault("year_start_month", 1)
    return make_policy(make_contract_type(), "BH", weeks_per_year=D("0"), bank_holiday_handling="pot", **kw)


@pytest.mark.parametrize("month,line", [
    (1, "8 bank holidays in 2026, one working day each, pro rata to contracted hours"),
    (4, "10 bank holidays in 2026/27, one working day each, pro rata to contracted hours"),
])
def test_the_bank_holiday_line_counts_the_seeded_calendar(db, month, line):
    from absence import admin_forms
    policy = _bank_holiday_policy(year_start_month=month)
    assert admin_forms.bank_holiday_summary(policy, date(2026, 6, 1)) == line


def test_a_bank_holiday_policy_shows_the_calendar_line_not_weeks_days_or_handling(admin_client, db):
    from django.utils import timezone

    from absence import admin_forms
    policy = _bank_holiday_policy()
    page = admin_client.get(_change(policy)).content.decode()
    for name in ("weeks_per_year", "days_per_year", "bank_holiday_handling", "tiers-TOTAL_FORMS"):
        assert f'name="{name}"' not in page, name
    assert admin_forms.bank_holiday_summary(policy, timezone.localdate()) in page
    assert "one working day each, pro rata to contracted hours" in page
    resp = _save(admin_client, policy, fields={"rounding": "0.5"})
    assert "pot(s) revised" in resp.content.decode()
    policy.refresh_from_db()
    assert (policy.rounding, policy.weeks_per_year, policy.bank_holiday_handling) == (D("0.50"), D("0"), "pot")


def test_adding_a_bank_holiday_policy_stores_no_weeks(admin_client, db):
    ct = make_contract_type("TUPE 2019")
    resp = admin_client.post("/admin/absence/policy/add/", _add_post(ct, "BH", days_per_year="25"), follow=True)
    assert "pot(s) revised" in resp.content.decode()
    assert Policy.objects.get(contract_type=ct, absence_type__code="BH").weeks_per_year == D("0")


def test_the_changelist_shows_the_bank_holiday_line_for_a_bank_holiday_policy(admin_client, db):
    from django.utils import timezone

    from absence import admin_forms
    policy = _bank_holiday_policy()
    page = admin_client.get("/admin/absence/policy/").content.decode()
    assert admin_forms.bank_holiday_summary(policy, timezone.localdate()) in page


YEAR_LOCKED = "This type has leave pots on the current year. End this policy and add a new one from the " \
              "new year's first day instead (see the admin guide)."


@pytest.mark.parametrize("fields", [{"year_start_month": "4"}, {"year_start_day": "15"},
                                    {"leave_year_basis": "anniversary"}])
def test_a_policy_in_use_cannot_change_its_leave_year(admin_client, db, fields):
    from django.contrib.admin.models import LogEntry

    from absence.models import LedgerEntry
    from absence.services import pots
    from people.models import AuditEntry
    from tests.factories import hours_employee
    policy = _hours_policy()                                          # a 1 January year
    pot = pots.for_day(hours_employee(start=date(2026, 1, 1)), absence_type("AL"), date(2026, 6, 1))
    entries = pot.entries.count()
    resp = _save(admin_client, policy, fields={"days_per_year": "21", **fields})
    assert resp.status_code == 200 and escape(YEAR_LOCKED) in resp.content.decode()
    policy.refresh_from_db()
    assert (policy.leave_year_basis, policy.year_start_month, policy.year_start_day,
            policy.weeks_per_year) == ("fixed", 1, 1, D("4.40"))
    assert not LogEntry.objects.exists()
    assert not AuditEntry.objects.filter(model="absence.policy").exists()
    assert pot.entries.count() == entries
    assert not pot.entries.filter(kind=LedgerEntry.Kind.REVISION).exists()


def test_a_policy_in_use_can_change_anything_else(admin_client, db):
    from absence.services import pots
    from tests.factories import hours_employee
    policy = _hours_policy()
    pots.for_day(hours_employee(start=date(2026, 1, 1)), absence_type("AL"), date(2026, 6, 1))
    resp = _save(admin_client, policy, fields={"days_per_year": "21", "accrual": "monthly"})
    assert "1 pot(s) revised" in resp.content.decode()
    policy.refresh_from_db()
    assert (policy.weeks_per_year, policy.accrual) == (D("4.20"), "monthly")


def test_a_policy_without_pots_can_change_its_leave_year(admin_client, db):
    policy = _hours_policy()
    resp = _save(admin_client, policy, fields={"year_start_month": "4", "year_start_day": "15"})
    assert "0 pot(s) revised" in resp.content.decode()
    policy.refresh_from_db()
    assert (policy.year_start_month, policy.year_start_day) == (4, 15)


def test_a_bank_holiday_policy_in_use_cannot_change_its_leave_year_either(admin_client, db):
    from absence.models import Pot
    from tests.factories import hours_employee
    policy = _bank_holiday_policy()
    emp = hours_employee(start=date(2026, 1, 1))
    Pot.objects.create(employment=emp, absence_type=absence_type("BH"), year_start=date(2026, 1, 1),
                       year_end=date(2026, 12, 31), unit="hours")
    resp = _save(admin_client, policy, fields={"year_start_month": "4"})
    assert escape(YEAR_LOCKED) in resp.content.decode()
    policy.refresh_from_db()
    assert policy.year_start_month == 1


YEAR_ADD_LOCKED = "This type has leave pots under another leave year. Start a policy with a new leave year " \
                  "on that year's first day, the day after the old policy ends (see the admin guide)."


def _april_type_in_use():
    """Reception's April-year annual-leave policy (from 2020), with a pot on
    the current leave year. Returns (contract type, April policy, 1 January
    of the current leave year)."""
    from tests.factories import current_leave_year, hours_employee, make_pot
    start, _ = current_leave_year()
    emp = hours_employee(start=start)
    make_pot(emp)
    ct = emp.contracts.get().contract_type
    return ct, ct.policies.get(), date(start.year + 1, 1, 1)


def _end(client, policy, last_day):
    _save(client, policy, fields={"effective_to": last_day.isoformat()})
    policy.refresh_from_db()
    assert policy.effective_to == last_day


def _add(client, ct, effective_from, **fields):
    fields.setdefault("days_per_year", "22")
    return client.post("/admin/absence/policy/add/",
                       _add_post(ct, effective_from=effective_from.isoformat(), **fields), follow=True)


def test_the_documented_move_to_a_january_year_passes(admin_client, db):
    from datetime import timedelta
    ct, april, jan1 = _april_type_in_use()
    _end(admin_client, april, jan1 - timedelta(days=1))
    resp = _add(admin_client, ct, jan1)
    assert escape(YEAR_ADD_LOCKED) not in resp.content.decode()
    assert Policy.objects.get(contract_type=ct, effective_from=jan1).year_start_month == 1


def test_a_backdated_add_with_a_january_year_is_refused_while_the_april_policy_runs(admin_client, db):
    ct, april, jan1 = _april_type_in_use()
    resp = _add(admin_client, ct, jan1)
    assert resp.status_code == 200 and escape(YEAR_ADD_LOCKED) in resp.content.decode()
    assert list(ct.policies.all()) == [april]


def test_an_add_starting_mid_year_after_the_old_one_ended_is_refused(admin_client, db):
    from datetime import timedelta
    ct, april, jan1 = _april_type_in_use()
    july1 = jan1.replace(year=jan1.year - 1, month=7)
    _end(admin_client, april, july1 - timedelta(days=1))
    resp = _add(admin_client, ct, july1)                                  # a January year from 1 July
    assert escape(YEAR_ADD_LOCKED) in resp.content.decode()
    assert list(ct.policies.all()) == [april]


def test_an_add_with_the_same_leave_year_may_be_backdated(admin_client, db):
    ct, april, jan1 = _april_type_in_use()
    resp = _add(admin_client, ct, jan1, year_start_month=4, days_per_year="25")
    assert escape(YEAR_ADD_LOCKED) not in resp.content.decode()
    assert ct.policies.get(effective_from=jan1).weeks_per_year == D("5")


@pytest.mark.parametrize("old,new", [({}, {"leave_year_basis": "anniversary"}),
                                     ({"leave_year_basis": "anniversary"}, {})])
def test_a_change_to_or_from_an_anniversary_year_with_pots_is_refused(admin_client, db, old, new):
    from datetime import timedelta
    ct, april, jan1 = _april_type_in_use()
    Policy.objects.filter(pk=april.pk).update(effective_to=jan1 - timedelta(days=1), **old)
    resp = _add(admin_client, ct, jan1, **new)                         # January year, or anniversary
    assert escape(YEAR_ADD_LOCKED) in resp.content.decode()
    assert ct.policies.count() == 1


def test_moving_a_january_policy_back_into_the_april_year_is_refused(admin_client, db):
    from datetime import timedelta
    ct, april, jan1 = _april_type_in_use()
    Policy.objects.filter(pk=april.pk).update(effective_to=jan1 - timedelta(days=1))
    january = make_policy(ct, effective_from=jan1, year_start_month=1)
    resp = _save(admin_client, january, fields={"effective_from": (jan1 - timedelta(days=31)).isoformat()})
    assert escape(YEAR_ADD_LOCKED) in resp.content.decode()
    january.refresh_from_db()
    assert january.effective_from == jan1


def test_a_type_with_no_pots_takes_any_new_leave_year(admin_client, db):
    from tests.factories import current_leave_year
    ct = make_contract_type()
    april = make_policy(ct)
    jan1 = date(current_leave_year()[0].year + 1, 1, 1)
    resp = _add(admin_client, ct, jan1)
    assert escape(YEAR_ADD_LOCKED) not in resp.content.decode()
    assert ct.policies.exclude(pk=april.pk).get().year_start_month == 1


def test_a_superseded_open_ended_april_policy_does_not_block_a_january_add(admin_client, db):
    # the type moved to January a year ago without ending its 2020 April policy: the
    # January one governs from then on, so a new January policy is compared with it
    ct, april, jan1 = _april_type_in_use()
    january = make_policy(ct, effective_from=jan1.replace(year=jan1.year - 1), year_start_month=1)
    resp = _add(admin_client, ct, jan1, days_per_year="25")
    assert escape(YEAR_ADD_LOCKED) not in resp.content.decode()
    assert set(ct.policies.exclude(pk__in=(april.pk, january.pk)).values_list("effective_from", flat=True)) == {jan1}


def test_moving_the_only_policy_s_effective_from_is_not_refused_against_itself(admin_client, db):
    ct, april, jan1 = _april_type_in_use()
    # saved from 1 Jan 2020, so on 31 May 2020 the policy in force is this one itself
    resp = _save(admin_client, april, fields={"effective_from": "2020-06-01"})
    assert escape(YEAR_ADD_LOCKED) not in resp.content.decode()
    april.refresh_from_db()
    assert april.effective_from == date(2020, 6, 1)
