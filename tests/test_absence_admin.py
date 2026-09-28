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
