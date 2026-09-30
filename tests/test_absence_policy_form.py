"""The policy admin form: an hours contract type's entitlement, tiers and
carry-over cap are entered in full-time days and stored as weeks (days ÷ 5);
a sessions contract type keeps its weeks fields."""
from datetime import date
from decimal import Decimal

import pytest

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
            "toil_expires_after_days": "", "accrual": "daily",
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
