def test_changelists_render(admin_client, db):
    for url in ("/admin/absence/absencetype/", "/admin/absence/policy/", "/admin/absence/bankholiday/",
                "/admin/absence/closedday/", "/admin/absence/pot/", "/admin/absence/absence/"):
        assert admin_client.get(url).status_code == 200, url


def test_pot_and_absence_are_read_only(admin_client, db):
    assert admin_client.get("/admin/absence/pot/add/").status_code == 403
    assert admin_client.get("/admin/absence/absence/add/").status_code == 403


def test_pot_recalculate_action_writes_a_revision_through_the_service(admin_client, hr_admin, db):
    from datetime import date

    from absence.models import LedgerEntry
    from absence.services import ledger, pots
    from tests.factories import absence_type, hours_employee
    pot = pots.for_day(hours_employee(start=date(2026, 4, 1)), absence_type("AL"), date(2026, 6, 1),
                       sync=False)     # opened bare, as the nightly opens pots, for the action to fill
    assert not pot.entries.exists()
    resp = admin_client.post("/admin/absence/pot/", {
        "action": "recalculate", "_selected_action": [pot.pk]}, follow=True)
    assert resp.status_code == 200
    entry = pot.entries.get()
    assert entry.kind == LedgerEntry.Kind.ENTITLEMENT and entry.actor == hr_admin
    assert ledger.balance(pot) == entry.units


def test_pot_change_page_shows_ledger_read_only(admin_client, db):
    from datetime import date

    from absence.services import ledger, pots
    from tests.factories import absence_type, hours_employee
    pot = pots.for_day(hours_employee(start=date(2026, 4, 1)), absence_type("AL"), date(2026, 6, 1))
    ledger.sync_entitlement(pot)
    resp = admin_client.get(f"/admin/absence/pot/{pot.pk}/change/")
    assert resp.status_code == 200
    assert b"entries-0-units" not in resp.content  # no editable ledger fields
    assert admin_client.post(f"/admin/absence/pot/{pot.pk}/change/", {}).status_code == 403


def test_absence_group_in_navigation(admin_client, db):
    assert b"/admin/absence/pot/" in admin_client.get("/admin/").content


def test_recalculate_reports_a_pot_with_no_policy_and_revises_the_rest(admin_client, db):
    from datetime import date

    from absence.services import pots
    from tests.factories import (absence_type, hours_employee, make_contract, make_contract_type,
                                 make_employment, make_pattern, make_policy)
    al = absence_type("AL")
    good = pots.for_day(hours_employee(start=date(2026, 4, 1)), al, date(2026, 6, 1), sync=False)
    other = make_contract_type("Other")
    emp = make_employment(start=date(2026, 4, 1))
    make_contract(emp, other)
    make_policy(other)
    make_pattern(emp)
    bad = pots.for_day(emp, al, date(2026, 6, 1), sync=False)
    other.policies.all().delete()
    resp = admin_client.post("/admin/absence/pot/", {
        "action": "recalculate", "_selected_action": [good.pk, bad.pk]}, follow=True)
    assert resp.status_code == 200
    assert good.entries.count() == 1 and not bad.entries.exists()
    text = resp.content.decode()
    assert "No Annual leave policy for Other" in text and "1 pot(s) revised." in text


def _policy_post(policy, **changes):
    """The admin change form's POST for `policy`, its tiers as inline rows."""
    from django.forms.models import model_to_dict
    data = {k: ("" if v is None else v) for k, v in model_to_dict(policy).items() if k != "id"}
    data.update(changes.pop("fields", {}))
    tiers = list(policy.tiers.all())
    new_tiers = changes.pop("new_tiers", [])
    data.update({"tiers-TOTAL_FORMS": len(tiers) + len(new_tiers), "tiers-INITIAL_FORMS": len(tiers),
                 "tiers-MIN_NUM_FORMS": 0, "tiers-MAX_NUM_FORMS": 1000})
    for i, t in enumerate(tiers):
        data.update({f"tiers-{i}-id": t.pk, f"tiers-{i}-policy": policy.pk,
                     f"tiers-{i}-after_years": t.after_years, f"tiers-{i}-extra_weeks": t.extra_weeks})
    for i, (years, weeks) in enumerate(new_tiers, start=len(tiers)):
        data.update({f"tiers-{i}-policy": policy.pk, f"tiers-{i}-after_years": years,
                     f"tiers-{i}-extra_weeks": weeks})
    return data


def test_policy_save_in_admin_revises_affected_pots_once_as_the_admin(admin_client, hr_admin, db):
    from decimal import Decimal

    from absence.models import LedgerEntry
    from absence.services import pots
    from people.models import AuditEntry
    from tests.factories import (absence_type, current_leave_year, hours_employee, make_contract,
                                 make_contract_type, make_employment, make_pattern, make_policy)
    start, _ = current_leave_year()
    al = absence_type("AL")
    a = hours_employee(start=start, continuous_service_date=start.replace(year=start.year - 11))
    b = hours_employee(start=start)
    pa, pb = pots.for_day(a, al, start), pots.for_day(b, al, start)       # 210.00 each
    other = make_contract_type("Other")
    c = make_employment(start=start)
    make_contract(c, other)
    make_policy(other)
    make_pattern(c)
    pc = pots.for_day(c, al, start)
    policy = a.contracts.first().contract_type.policies.get()
    resp = admin_client.post(f"/admin/absence/policy/{policy.pk}/change/",
                             _policy_post(policy, fields={"weeks_per_year": "6"}, new_tiers=[(5, "1")]),
                             follow=True)
    assert resp.status_code == 200 and "2 pot(s) revised" in resp.content.decode()
    ra, rb = (p.entries.get(kind=LedgerEntry.Kind.REVISION) for p in (pa, pb))   # one each, not per row saved
    assert ra.units == Decimal("7.0") * Decimal("37.5") - Decimal("210") and ra.actor == hr_admin
    assert rb.units == Decimal("0.4") * Decimal("37.5") and rb.actor == hr_admin
    assert not pc.entries.filter(kind=LedgerEntry.Kind.REVISION).exists()
    audit = AuditEntry.objects.filter(model="absence.policy", object_id=policy.pk, actor=hr_admin)
    assert audit.filter(field="weeks_per_year", before="5.60", after="6.00").exists()
    assert audit.filter(field="tiers", after="+1.00 weeks after 5 years").exists()


def test_ending_the_only_policy_in_admin_shows_an_error_not_a_500(admin_client, db):
    from datetime import timedelta

    from absence.services import ledger, pots
    from tests.factories import absence_type, current_leave_year, hours_employee
    start, _ = current_leave_year()
    emp = hours_employee(start=start)
    pot = pots.for_day(emp, absence_type("AL"), start)
    before = ledger.balance(pot)
    policy = emp.contracts.first().contract_type.policies.get()
    ended = (start + timedelta(days=30)).isoformat()
    resp = admin_client.post(f"/admin/absence/policy/{policy.pk}/change/",
                             _policy_post(policy, fields={"effective_to": ended}), follow=True)
    assert resp.status_code == 200
    assert "No Annual leave policy for Reception" in resp.content.decode()
    assert ledger.balance(pot) == before
    policy.refresh_from_db()
    assert policy.effective_to.isoformat() == ended            # the edit itself stands


def test_saving_a_policy_or_tier_outside_the_admin_writes_no_ledger_line(db):
    from datetime import timedelta
    from decimal import Decimal

    from absence.models import LedgerEntry, PolicyTier
    from absence.services import pots
    from tests.factories import absence_type, current_leave_year, hours_employee
    start, _ = current_leave_year()
    emp = hours_employee(start=start, continuous_service_date=start - timedelta(days=4000))
    pot = pots.for_day(emp, absence_type("AL"), start)
    policy = emp.contracts.first().contract_type.policies.get()
    policy.weeks_per_year = Decimal("6")
    policy.save()
    PolicyTier.objects.create(policy=policy, after_years=5, extra_weeks=Decimal("1"))
    assert not pot.entries.filter(kind=LedgerEntry.Kind.REVISION).exists()   # the nightly picks it up


def test_adding_a_policy_in_admin_audits_it_and_syncs_nothing_it_cannot_reach(admin_client, hr_admin, db):
    from absence.models import Policy
    from people.models import AuditEntry
    from tests.factories import absence_type, make_contract_type
    ct = make_contract_type()
    data = {"contract_type": ct.pk, "absence_type": absence_type("BH").pk, "effective_from": "2020-01-01",
            "effective_to": "", "weeks_per_year": "0", "leave_year_basis": "fixed", "year_start_month": 4,
            "year_start_day": 1, "carry_over_max_weeks": "", "carry_over_expires_after_days": "",
            "rounding": "0.25", "bank_holiday_handling": "pot", "toil_expires_after_days": "",
            "tiers-TOTAL_FORMS": 0, "tiers-INITIAL_FORMS": 0, "tiers-MIN_NUM_FORMS": 0,
            "tiers-MAX_NUM_FORMS": 1000}
    resp = admin_client.post("/admin/absence/policy/add/", data, follow=True)
    assert resp.status_code == 200 and "0 pot(s) revised" in resp.content.decode()
    policy = Policy.objects.get(contract_type=ct, absence_type__code="BH")
    assert AuditEntry.objects.filter(model="absence.policy", object_id=policy.pk, actor=hr_admin,
                                     field="weeks_per_year", before="", after="0.00").exists()


def test_viewing_sickness_is_audited_and_leave_is_not(admin_client, hr_admin, db):
    from datetime import date

    from absence.services import bookings
    from people.models import AuditEntry
    from tests.factories import absence_type, hours_employee
    emp = hours_employee()
    sick = bookings.request(hr_admin, emp, absence_type("SICK"), date(2026, 6, 1), category="illness")
    leave = bookings.request(hr_admin, emp, absence_type("AL"), date(2026, 6, 8))
    viewed = AuditEntry.objects.filter(kind=AuditEntry.Kind.VIEWED, model="absence.absence")
    assert admin_client.get(f"/admin/absence/absence/{sick.pk}/change/").status_code == 200
    assert viewed.count() == 1
    row = viewed.get()
    assert (row.object_id, row.actor, row.field) == (sick.pk, hr_admin, "health")
    assert admin_client.get(f"/admin/absence/absence/{leave.pk}/change/").status_code == 200
    assert viewed.count() == 1


def test_absence_type_code_is_read_only_once_saved(admin_client, db):
    from absence.models import AbsenceType
    from tests.factories import absence_type
    al = absence_type("AL")
    page = admin_client.get(f"/admin/absence/absencetype/{al.pk}/change/").content.decode()
    assert 'name="code"' not in page and 'name="name"' in page
    add = admin_client.get("/admin/absence/absencetype/add/").content.decode()
    assert 'name="code"' in add
    data = {"name": "Annual leave", "code": "HOLS", "paid": "on", "uses_pot": "on", "needs_approval": "on",
            "calendar_label": "Leave", "display_order": 10, "active": "on"}
    assert admin_client.post(f"/admin/absence/absencetype/{al.pk}/change/", data).status_code == 302
    assert AbsenceType.objects.get(pk=al.pk).code == "AL"
