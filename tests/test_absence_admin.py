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
    """The admin change form's POST for `policy`, its tiers as inline rows.
    An hours policy's form takes days, not weeks (absence.admin_forms): its
    entitlement, carry-over cap and tiers are posted as full-time days, and
    `tier_values` and `new_tiers` values are days for it, weeks otherwise."""
    from django.forms.models import model_to_dict
    days = policy.contract_type.unit == "hours" and policy.absence_type.code != "BH"
    data = {k: ("" if v is None else v) for k, v in model_to_dict(policy).items() if k != "id"}
    if days:
        data["days_per_year"] = data.pop("weeks_per_year") * 5
        carry = data.pop("carry_over_max_weeks")
        data["carry_over_days"] = "" if carry == "" else carry * 5
    data.update(changes.pop("fields", {}))
    tiers = list(policy.tiers.all())
    values = changes.pop("tier_values", None) or [
        (policy.weeks_per_year + t.extra_weeks) * 5 if days else t.extra_weeks for t in tiers]
    new_tiers = changes.pop("new_tiers", [])
    name = "days" if days else "extra_weeks"
    data.update({"tiers-TOTAL_FORMS": len(tiers) + len(new_tiers), "tiers-INITIAL_FORMS": len(tiers),
                 "tiers-MIN_NUM_FORMS": 0, "tiers-MAX_NUM_FORMS": 1000})
    for i, (t, value) in enumerate(zip(tiers, values)):
        data.update({f"tiers-{i}-id": t.pk, f"tiers-{i}-policy": policy.pk,
                     f"tiers-{i}-after_years": t.after_years, f"tiers-{i}-{name}": value})
    for i, (years, value) in enumerate(new_tiers, start=len(tiers)):
        data.update({f"tiers-{i}-policy": policy.pk, f"tiers-{i}-after_years": years,
                     f"tiers-{i}-{name}": value})
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
                             _policy_post(policy, fields={"days_per_year": "30"},     # 6 weeks
                                          new_tiers=[(5, "35")]),                 # +1 week
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
            "rounding": "0.25", "bank_holiday_handling": "pot", "accrual": "daily",
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


def _family_absence(employee_user):
    from datetime import date

    from absence.services import bookings
    from tests.factories import absence_type, hours_employee
    return bookings.request(employee_user, hours_employee(), absence_type("MAT"), date(2026, 7, 1),
                            date(2027, 3, 31), expected_start=date(2026, 7, 1))


def test_family_dates_are_edited_in_admin_through_the_service(admin_client, hr_admin, employee_user):
    from datetime import date

    from people.models import AuditEntry
    a = _family_absence(employee_user)
    url = f"/admin/absence/absence/{a.pk}/change/"
    page = admin_client.get(url).content.decode()
    assert 'name="actual_start"' in page and 'name="start_date"' not in page and 'name="status"' not in page
    resp = admin_client.post(url, {"expected_start": "2026-07-01", "actual_start": "2026-07-06",
                                   "expected_return": "2027-04-05", "status": "cancelled"})
    assert resp.status_code == 302
    a.refresh_from_db()
    assert (a.actual_start, a.expected_return, a.status) == (date(2026, 7, 6), date(2027, 4, 5), "requested")
    assert AuditEntry.objects.filter(model="absence.absence", object_id=a.pk, actor=hr_admin,
                                     field="actual_start", after="2026-07-06").exists()


def test_family_dates_out_of_order_show_a_message_and_save_nothing(admin_client, employee_user):
    a = _family_absence(employee_user)
    url = f"/admin/absence/absence/{a.pk}/change/"
    resp = admin_client.post(url, {"expected_start": "2026-07-01", "actual_start": "2026-07-06",
                                   "expected_return": "2026-07-02"}, follow=True)
    body = resp.content.decode()
    assert resp.status_code == 200 and "after the actual start" in body and "changed successfully" not in body
    a.refresh_from_db()
    assert a.actual_start is None and a.expected_return is None
    from django.contrib.admin.models import LogEntry
    assert not LogEntry.objects.filter(object_id=str(a.pk)).exists()


def test_other_absences_stay_read_only_in_admin(admin_client, employee_user):
    from datetime import date

    from absence.services import bookings
    from tests.factories import absence_type, hours_employee
    leave = bookings.request(employee_user, hours_employee(), absence_type("AL"), date(2026, 6, 1))
    url = f"/admin/absence/absence/{leave.pk}/change/"
    assert 'name="expected_return"' not in admin_client.get(url).content.decode()
    assert admin_client.post(url, {"expected_return": "2026-06-02"}).status_code == 403


def test_an_absence_shows_its_cancel_reason_read_only(admin_client, hr_admin, db):
    from datetime import timedelta

    from absence.services import bookings
    from tests.factories import absence_type, current_leave_year, hours_employee
    start, _ = current_leave_year()
    monday = start + timedelta(days=70)
    monday -= timedelta(days=monday.weekday())
    leave = bookings.request(hr_admin, hours_employee(start=start), absence_type("AL"), monday)
    bookings.cancel(hr_admin, leave, reason="booked in error")
    page = admin_client.get(f"/admin/absence/absence/{leave.pk}/change/").content.decode()
    assert "Cancel reason" in page and "booked in error" in page and 'name="cancel_reason"' not in page


# --- "Cancel absence" on an absence's page ---------------------------------------------------

def _auto_row(employee=None):
    from datetime import timedelta

    from absence.models import Absence
    from tests.factories import absence_type, current_leave_year, hours_employee
    start, _ = current_leave_year()
    emp = hours_employee(start=start, **({"employee": employee} if employee else {}))
    day = start + timedelta(days=14)
    return Absence.objects.create(employment=emp, absence_type=absence_type("BH"), start_date=day, end_date=day,
                                  status=Absence.Status.APPROVED, auto_bank_holiday=True)


def test_an_hr_admin_cancels_another_persons_automatic_row_from_its_page(admin_client, hr_admin, db):
    auto = _auto_row()
    change, cancel = f"/admin/absence/absence/{auto.pk}/change/", f"/admin/absence/absence/{auto.pk}/cancel/"
    body = admin_client.get(change).content.decode()
    assert cancel in body and "Cancel absence" in body
    confirm = admin_client.get(cancel)
    assert confirm.status_code == 200 and 'method="post"' in confirm.content.decode()
    auto.refresh_from_db()
    assert auto.status == "approved"                                    # a GET writes nothing
    r = admin_client.post(cancel)
    assert r.status_code == 302 and r["Location"] == change
    auto.refresh_from_db()
    assert (auto.status, auto.cancel_reason, auto.cancelled_by) == ("cancelled", "", hr_admin)
    assert cancel not in admin_client.get(change).content.decode()      # no longer live
    assert admin_client.post(cancel).status_code == 403


def test_the_cancel_action_shows_the_services_refusal(admin_client, hr_admin, db):
    from datetime import timedelta

    from absence.services import bookings, pots, year_end
    from tests.factories import absence_type, current_leave_year, hours_employee
    start, _ = current_leave_year()
    emp = hours_employee(start=start)
    monday = start + timedelta(days=70)
    monday -= timedelta(days=monday.weekday())
    leave = bookings.approve(hr_admin, bookings.request(hr_admin, emp, absence_type("AL"), monday))
    year_end.close(pots.for_day(emp, absence_type("AL"), monday))
    r = admin_client.post(f"/admin/absence/absence/{leave.pk}/cancel/", follow=True)
    assert r.status_code == 200 and "is closed" in r.content.decode()
    leave.refresh_from_db()
    assert leave.status == "approved"


def test_an_hr_admin_does_not_cancel_their_own_absence_from_its_page(admin_client, hr_admin, db):
    from tests.factories import make_employee
    auto = _auto_row(make_employee(first="Hana", user=hr_admin))
    body = admin_client.get(f"/admin/absence/absence/{auto.pk}/change/").content.decode()
    assert f"/admin/absence/absence/{auto.pk}/cancel/" not in body
    assert admin_client.post(f"/admin/absence/absence/{auto.pk}/cancel/").status_code == 403
    auto.refresh_from_db()
    assert auto.status == "approved"


def test_a_manager_does_not_cancel_from_the_admin(db):
    from django.contrib.auth import get_user_model
    from django.test import Client

    from tests.factories import make_employee, make_position
    manager = get_user_model().objects.create_user(email="manager@example.org", password="pw", is_staff=True)
    auto = _auto_row()
    make_position(auto.employment, manager=make_employee(first="Mo", user=manager))
    c = Client()
    c.force_login(manager)
    r = c.post(f"/admin/absence/absence/{auto.pk}/cancel/")
    assert r.status_code == 302 and r["Location"].startswith("/admin/login/")     # not an admin at all
    auto.refresh_from_db()
    assert auto.status == "approved"


def test_cancelling_an_ordinary_absence_here_emails_the_approver_and_an_automatic_row_does_not(
        admin_client, hr_admin, configured, db):
    from datetime import timedelta

    from django.core import mail

    from absence.services import bookings
    from tests.factories import absence_type, current_leave_year, hours_employee
    start, _ = current_leave_year()
    monday = start + timedelta(days=70)
    monday -= timedelta(days=monday.weekday())
    leave = bookings.request(hr_admin, hours_employee(start=start), absence_type("AL"), monday)
    mail.outbox.clear()
    assert admin_client.post(f"/admin/absence/absence/{leave.pk}/cancel/").status_code == 302
    assert len(mail.outbox) == 1 and "cancelled" in mail.outbox[0].subject
    auto = _auto_row()
    assert admin_client.post(f"/admin/absence/absence/{auto.pk}/cancel/").status_code == 302
    assert len(mail.outbox) == 1


def test_the_cancel_page_of_a_health_sensitive_absence_is_audited_as_viewed(admin_client, hr_admin, db):
    from datetime import timedelta

    from absence.services import bookings
    from people.models import AuditEntry
    from tests.factories import absence_type, current_leave_year, hours_employee
    start, _ = current_leave_year()
    sick = bookings.request(hr_admin, hours_employee(start=start), absence_type("SICK"),
                            start + timedelta(days=70), category="illness")
    viewed = AuditEntry.objects.filter(kind=AuditEntry.Kind.VIEWED, model="absence.absence", object_id=sick.pk)
    assert admin_client.get(f"/admin/absence/absence/{sick.pk}/cancel/").status_code == 200
    assert [(v.actor, v.field) for v in viewed] == [(hr_admin, "health")]
    auto = _auto_row()
    admin_client.get(f"/admin/absence/absence/{auto.pk}/cancel/")
    assert not AuditEntry.objects.filter(kind=AuditEntry.Kind.VIEWED, object_id=auto.pk).exists()


def _opted_out(admin_client):
    """A real automatic row (the sync's), cancelled by HR on its admin page."""
    from absence.models import Absence
    from absence.services import bank_holidays
    from tests.test_absence_bank_holidays import _this_year_with_a_holiday
    emp, start, end, day = _this_year_with_a_holiday()
    bank_holidays.sync_auto_absences(emp, start, end)
    auto = Absence.objects.get(employment=emp, auto_bank_holiday=True, start_date=day)
    assert admin_client.post(f"/admin/absence/absence/{auto.pk}/cancel/").status_code == 302
    auto.refresh_from_db()
    return auto


def test_an_hr_admin_charges_an_opted_out_day_again_from_its_page(admin_client, hr_admin, db):
    from absence.models import Absence
    from absence.services import bank_holidays
    from people.models import AuditEntry
    auto = _opted_out(admin_client)
    change, again = f"/admin/absence/absence/{auto.pk}/change/", f"/admin/absence/absence/{auto.pk}/charge-again/"
    body = admin_client.get(change).content.decode()
    assert again in body and "Charge again" in body
    confirm = admin_client.get(again)
    assert confirm.status_code == 200 and 'method="post"' in confirm.content.decode()
    auto.refresh_from_db()
    assert auto.cancel_reason == ""                                     # a GET writes nothing
    assert not AuditEntry.objects.filter(kind=AuditEntry.Kind.VIEWED, object_id=auto.pk).exists()
    r = admin_client.post(again)
    assert r.status_code == 302 and r["Location"] == change
    auto.refresh_from_db()
    assert auto.cancel_reason == bank_holidays.NOT_IMPLIED
    back = Absence.objects.get(employment=auto.employment, start_date=auto.start_date, status="approved")
    assert back.auto_bank_holiday and back.decided_by == hr_admin
    assert again not in admin_client.get(change).content.decode()       # no longer an opt-out
    assert admin_client.post(again).status_code == 403


def test_charge_again_is_only_for_an_opt_out_and_an_hr_admin(admin_client, hr_admin, db):
    from django.contrib.auth import get_user_model
    from django.test import Client

    from absence.models import Absence
    from absence.services import bank_holidays, bookings
    from tests.factories import make_employee
    live = _auto_row()
    by_sync = _auto_row()
    bookings.cancel(hr_admin, by_sync, reason=bank_holidays.NOT_IMPLIED)
    own = _auto_row(make_employee(first="Hana", user=hr_admin))
    bookings.cancel(get_user_model().objects.create_user(email="hr2@example.org", password="pw",
                                                         is_hr_admin=True), own)
    for row in (live, by_sync, own):
        page = admin_client.get(f"/admin/absence/absence/{row.pk}/change/").content.decode()
        assert "/charge-again/" not in page
        assert admin_client.post(f"/admin/absence/absence/{row.pk}/charge-again/").status_code == 403
    opted_out = _auto_row()
    bookings.cancel(hr_admin, opted_out)
    manager = get_user_model().objects.create_user(email="manager@example.org", password="pw", is_staff=True)
    c = Client()
    c.force_login(manager)
    r = c.post(f"/admin/absence/absence/{opted_out.pk}/charge-again/")
    assert r.status_code == 302 and r["Location"].startswith("/admin/login/")     # not an admin at all
    assert Absence.objects.get(pk=opted_out.pk).cancel_reason == ""


# --- "Adjust balance" on the pot's page (I7) ------------------------------------------------

def _open_pot():
    from datetime import date

    from absence.services import pots
    from tests.factories import absence_type, hours_employee
    return pots.for_day(hours_employee(start=date(2025, 4, 1)), absence_type("AL"), date(2026, 6, 1))


def test_the_pot_page_offers_adjust_balance_to_an_hr_admin(admin_client, db):
    pot = _open_pot()
    body = admin_client.get(f"/admin/absence/pot/{pot.pk}/change/").content.decode()
    assert f"/admin/absence/pot/{pot.pk}/adjust/" in body and "Adjust balance" in body
    r = admin_client.get(f"/admin/absence/pot/{pot.pk}/adjust/")
    assert r.status_code == 200 and 'name="units"' in r.content.decode() and 'name="note"' in r.content.decode()


def test_the_adjust_form_writes_one_line_as_the_admin_and_shows_the_new_balance(admin_client, hr_admin, db):
    from decimal import Decimal

    from absence.models import LedgerEntry
    from absence.services import ledger
    pot = _open_pot()
    count, before = pot.entries.count(), ledger.balance(pot)
    r = admin_client.post(f"/admin/absence/pot/{pot.pk}/adjust/", {"units": "-3.75", "note": "bought back"},
                          follow=True)
    assert r.status_code == 200 and pot.entries.count() == count + 1
    line = pot.entries.latest("id")
    assert (line.kind, line.units, line.actor, line.note) == (
        LedgerEntry.Kind.ADJUSTMENT, Decimal("-3.75"), hr_admin, "bought back")
    assert f"New balance: {before - Decimal('3.75'):.2f}" in r.content.decode()


def test_the_adjust_form_refuses_zero_units(admin_client, db):
    pot = _open_pot()
    count = pot.entries.count()
    r = admin_client.post(f"/admin/absence/pot/{pot.pk}/adjust/", {"units": "0", "note": "nothing"})
    assert r.status_code == 200 and "other than zero" in r.content.decode()
    assert pot.entries.count() == count


def test_the_adjust_form_refuses_a_closed_pot(admin_client, db):
    from absence.services import year_end
    pot = _open_pot()
    year_end.close(pot)
    count = pot.entries.count()
    r = admin_client.post(f"/admin/absence/pot/{pot.pk}/adjust/", {"units": "5", "note": "restore"})
    assert r.status_code == 200 and "closed" in r.content.decode() and pot.entries.count() == count


def test_the_adjust_form_is_for_hr_admins_only(db):
    from django.contrib.auth import get_user_model
    from django.test import Client
    pot = _open_pot()
    staff = get_user_model().objects.create_user(email="staff@example.org", password="pw", is_staff=True)
    c = Client()
    c.force_login(staff)
    assert c.post(f"/admin/absence/pot/{pot.pk}/adjust/", {"units": "5", "note": "x"}).status_code in (302, 403)
    assert pot.entries.filter(kind="adjustment").count() == 0


def _policy_data(ct, code):
    from tests.factories import absence_type
    return {"contract_type": ct.pk, "absence_type": absence_type(code).pk, "effective_from": "2020-01-01",
            "effective_to": "", "weeks_per_year": "0", "days_per_year": "", "carry_over_days": "",
            "leave_year_basis": "fixed", "year_start_month": 4, "year_start_day": 1,
            "carry_over_max_weeks": "", "carry_over_expires_after_days": "", "rounding": "0.25",
            "bank_holiday_handling": "closed", "accrual": "daily",
            "tiers-TOTAL_FORMS": 0, "tiers-INITIAL_FORMS": 0, "tiers-MIN_NUM_FORMS": 0,
            "tiers-MAX_NUM_FORMS": 1000}


def test_the_policy_admin_refuses_a_policy_for_toil(admin_client, db):
    from absence.models import Policy
    from tests.factories import make_contract_type
    ct = make_contract_type()
    resp = admin_client.post("/admin/absence/policy/add/", _policy_data(ct, "TOIL"))
    assert resp.status_code == 200
    assert "TOIL is earned, not accrued; it needs no policy — set its expiry on the absence type." in \
        resp.content.decode()
    assert not Policy.objects.exists()


def test_the_absence_type_admin_sets_accrues_and_the_earned_expiry(admin_client, db):
    from absence.models import AbsenceType
    from tests.factories import absence_type
    toil = absence_type("TOIL")
    page = admin_client.get(f"/admin/absence/absencetype/{toil.pk}/change/").content.decode()
    assert 'name="accrues"' in page and 'name="earned_expires_after_days"' in page
    data = {"name": "TOIL", "paid": "on", "uses_pot": "on", "needs_approval": "on", "calendar_label": "Leave",
            "display_order": 40, "active": "on", "earned_expires_after_days": 180}
    assert admin_client.post(f"/admin/absence/absencetype/{toil.pk}/change/", data).status_code == 302
    assert AbsenceType.objects.get(pk=toil.pk).earned_expires_after_days == 180
    resp = admin_client.post(f"/admin/absence/absencetype/{toil.pk}/change/", {**data, "accrues": "on"})
    assert resp.status_code == 200 and "Only for a type that does not accrue" in resp.content.decode()
    assert AbsenceType.objects.get(pk=toil.pk).accrues is False
