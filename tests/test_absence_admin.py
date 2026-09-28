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
    pot = pots.for_day(hours_employee(start=date(2026, 4, 1)), absence_type("AL"), date(2026, 6, 1))
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
