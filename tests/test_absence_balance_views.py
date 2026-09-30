from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from absence.models import Absence, LedgerEntry, Pot
from absence.services import balances, ledger, pots
from people.services import positions
from tests.factories import (absence_type, hours_employee, make_employee, make_employment,
                             make_team)

K = LedgerEntry.Kind
User = get_user_model()


def _me(employee_user, **kw):
    return hours_employee(employee=make_employee(user=employee_user), **kw)


def _manager_of(emp):
    boss_user = User.objects.create_user(email="boss@example.org", password="pw")
    boss = make_employee(first="Boss", user=boss_user)
    make_employment(employee=boss, start=emp.start_date)
    positions.add(None, emp, "Receptionist", make_team(), boss, emp.start_date)
    c = Client()
    c.force_login(boss_user)
    return c


def test_own_balances_two_years_and_ledger_link(employee_client, employee_user):
    emp = _me(employee_user)
    pot = pots.for_day(emp, absence_type("AL"), timezone.localdate())      # opened with its entitlement
    body = employee_client.get("/absence/balances/").content.decode()
    assert "210" in body and f"/absence/ledger/{pot.pk}/" in body
    assert body.count("Annual leave") >= 2                                  # this year and next
    r = employee_client.get(f"/absence/ledger/{pot.pk}/")
    assert r.status_code == 200 and "Entitlement" in r.content.decode()


def test_figures_are_quiet_links_and_the_ledger_a_plain_one(employee_client, employee_user):
    import re
    emp = _me(employee_user)
    pot = pots.for_day(emp, absence_type("AL"), timezone.localdate())
    body = employee_client.get("/absence/balances/").content.decode()
    figures = re.findall(r'<a href="([^"]+)" class="figure-link">', body)
    assert len(figures) == 7 and all(f"/absence/ledger/{pot.pk}/" in href for href in figures)
    assert f'<a href="/absence/ledger/{pot.pk}/">Ledger</a>' in body


def test_a_get_opens_no_pot_and_writes_no_line(employee_client, employee_user):
    emp = _me(employee_user)
    body = employee_client.get("/absence/balances/").content.decode()
    assert "Not opened yet" in body
    assert not Pot.objects.exists() and not LedgerEntry.objects.exists()
    pot = pots.for_day(emp, absence_type("AL"), timezone.localdate())
    before = LedgerEntry.objects.count()
    employee_client.get("/absence/balances/")
    employee_client.get(f"/absence/ledger/{pot.pk}/")
    assert LedgerEntry.objects.count() == before and Pot.objects.count() == 1


def test_the_next_year_shows_when_its_pot_is_open(employee_client, employee_user):
    emp = _me(employee_user)
    this = pots.for_day(emp, absence_type("AL"), timezone.localdate())
    nxt = pots.for_day(emp, absence_type("AL"), this.year_end + timedelta(days=1))
    body = employee_client.get("/absence/balances/").content.decode()
    assert f"/absence/ledger/{this.pk}/" in body and f"/absence/ledger/{nxt.pk}/" in body
    assert "Not opened yet" not in body


def test_other_persons_balances_need_relationship(employee_client, employee_user, admin_client):
    other = hours_employee(employee=make_employee(first="Other"))
    assert employee_client.get(f"/absence/balances/{other.employee.pk}/").status_code == 403
    assert admin_client.get(f"/absence/balances/{other.employee.pk}/").status_code == 200
    pot = pots.for_day(other, absence_type("AL"), timezone.localdate())
    assert employee_client.get(f"/absence/ledger/{pot.pk}/").status_code == 403
    assert admin_client.get(f"/absence/ledger/{pot.pk}/").status_code == 200


def test_a_manager_sees_a_reports_balances_and_ledger_but_not_a_peers(employee_user):
    emp = _me(employee_user)
    c = _manager_of(emp)
    peer = hours_employee(employee=make_employee(first="Peer"))
    pot = pots.for_day(emp, absence_type("AL"), timezone.localdate())
    peer_pot = pots.for_day(peer, absence_type("AL"), timezone.localdate())
    assert c.get(f"/absence/balances/{emp.employee.pk}/").status_code == 200
    assert c.get(f"/absence/ledger/{pot.pk}/").status_code == 200
    assert c.get(f"/absence/balances/{peer.employee.pk}/").status_code == 403
    assert c.get(f"/absence/ledger/{peer_pot.pk}/").status_code == 403


def test_a_user_with_no_employee_record_gets_an_empty_page(employee_client):
    r = employee_client.get("/absence/balances/")
    assert r.status_code == 200


def test_login_is_required(db, client):
    assert client.get("/absence/balances/").status_code == 302
    assert client.get("/absence/balances/team/").status_code == 302


def test_an_employee_is_not_shown_the_admin_text_for_a_type_with_no_policy(employee_client, employee_user):
    _me(employee_user)                                       # an AL policy only
    body = employee_client.get("/absence/balances/").content.decode()
    assert "Annual leave" in body
    assert "Add one under" not in body and "Study leave" not in body
    body = employee_client.get("/absence/mine/").content.decode()
    assert "Add one under" not in body and "No Study leave policy" not in body


def test_an_hr_admin_still_sees_the_missing_policy_note(admin_client, employee_user):
    emp = _me(employee_user)
    body = admin_client.get(f"/absence/balances/{emp.employee.pk}/").content.decode()
    assert "No Study leave policy" in body


def test_a_missing_contract_still_shows_its_message_to_the_employee(employee_client, employee_user):
    make_employment(employee=make_employee(user=employee_user))          # employed, no contract yet
    body = employee_client.get("/absence/balances/").content.decode()
    assert "has no contract" in body


def _lines(pot):
    """A past and a future booking, an adjustment, and a waiting request."""
    today = timezone.localdate()
    emp, al = pot.employment, pot.absence_type
    past = Absence.objects.create(employment=emp, absence_type=al, start_date=today - timedelta(days=20),
                                  end_date=today - timedelta(days=19), status=Absence.Status.APPROVED,
                                  cost_units=Decimal("7.50"))
    ahead = Absence.objects.create(employment=emp, absence_type=al, start_date=today + timedelta(days=20),
                                   end_date=today + timedelta(days=21), status=Absence.Status.APPROVED,
                                   cost_units=Decimal("3.75"))
    waiting = min(today + timedelta(days=30), pot.year_end)          # inside the pot's year, whatever today is
    Absence.objects.create(employment=emp, absence_type=al, start_date=waiting, end_date=waiting,
                           status=Absence.Status.REQUESTED, cost_units=Decimal("2.50"))
    ledger.write(pot, K.BOOKING, "-7.50", absence=past, note="past line")
    ledger.write(pot, K.BOOKING, "-3.75", absence=ahead, note="ahead line")
    ledger.write(pot, K.ADJUSTMENT, "1.00", note="adjustment line")


def test_every_figure_links_to_its_lines(employee_client, employee_user):
    pot = pots.for_day(_me(employee_user), absence_type("AL"), timezone.localdate())
    body = employee_client.get("/absence/balances/").content.decode()
    base = f"/absence/ledger/{pot.pk}/"
    for query in ("kind=entitlement,revision", "kind=carry_in", "kind=booking,toil_taken,cancellation&amp;period=taken",
                  "kind=booking,toil_taken,cancellation&amp;period=booked", "kind=pending", "kind=expiry",
                  "kind=adjustment,toil_earned"):
        assert f"{base}?{query}" in body, query


@pytest.mark.parametrize("query, shown, hidden", [
    ("", ["past line", "ahead line", "adjustment line", "Entitlement"], []),
    ("?kind=adjustment,toil_earned", ["adjustment line"], ["past line", "ahead line"]),
    ("?kind=entitlement,revision", ["Entitlement"], ["past line", "adjustment line"]),
    ("?kind=booking,toil_taken,cancellation&period=taken", ["past line"], ["ahead line", "adjustment line"]),
    ("?kind=booking,toil_taken,cancellation&period=booked", ["ahead line"], ["past line", "adjustment line"]),
    ("?kind=nonsense", ["past line", "ahead line", "adjustment line"], []),
])
def test_the_ledger_filters_to_the_kind_behind_a_figure(employee_client, employee_user, query, shown, hidden):
    pot = pots.for_day(_me(employee_user), absence_type("AL"), timezone.localdate())
    _lines(pot)
    body = employee_client.get(f"/absence/ledger/{pot.pk}/{query}").content.decode()
    for text in shown:
        assert text in body, text
    for text in hidden:
        assert text not in body, text


def test_a_filtered_ledger_keeps_the_true_running_balance(employee_client, employee_user):
    pot = pots.for_day(_me(employee_user), absence_type("AL"), timezone.localdate())
    _lines(pot)                                                    # 210 - 7.5 - 3.75 + 1 = 199.75
    body = employee_client.get(f"/absence/ledger/{pot.pk}/?kind=adjustment").content.decode()
    assert "199.75" in body


def test_pending_shows_the_waiting_requests_not_ledger_lines(employee_client, employee_user):
    pot = pots.for_day(_me(employee_user), absence_type("AL"), timezone.localdate())
    _lines(pot)
    body = employee_client.get(f"/absence/ledger/{pot.pk}/?kind=pending").content.decode()
    assert "<td>2.50</td>" in body and "waiting" in body.lower()
    assert "past line" not in body and "adjustment line" not in body


def test_the_team_page_lists_reports_and_links_to_their_balances(employee_user):
    emp = _me(employee_user)
    c = _manager_of(emp)
    body = c.get("/absence/balances/team/").content.decode()
    assert "Sam Patel" in body and f"/absence/balances/{emp.employee.pk}/" in body


def test_the_team_page_gives_an_hr_admin_everyone(admin_client, employee_user):
    emp = _me(employee_user)
    other = hours_employee(employee=make_employee(first="Other", last="Person"))
    body = admin_client.get("/absence/balances/team/").content.decode()
    assert f"/absence/balances/{emp.employee.pk}/" in body and f"/absence/balances/{other.employee.pk}/" in body


def test_the_team_page_is_for_approvers_and_hr_admins_only(employee_client, employee_user):
    _me(employee_user)
    assert employee_client.get("/absence/balances/team/").status_code == 403


def test_balances_is_in_both_navs(employee_client, employee_user):
    _me(employee_user)
    body = employee_client.get("/absence/mine/").content.decode()
    assert body.count('href="/absence/balances/"') == 2                 # desktop nav and the More sheet


def test_rows_return_the_next_year_without_writing(db):
    emp = hours_employee()
    today = timezone.localdate()
    assert Pot.objects.count() == 0
    row = {r["type"].code: r for r in balances.rows(emp, today, include_bh=True, with_next=True)}["AL"]
    assert row["pot"] is None and row["next_pot"] is None and not Pot.objects.exists()
    this = pots.for_day(emp, absence_type("AL"), today)
    nxt = pots.for_day(emp, absence_type("AL"), this.year_end + timedelta(days=1))
    row = {r["type"].code: r for r in balances.rows(emp, today, with_next=True)}["AL"]
    assert row["pot"] == this and row["next_pot"] == nxt
    assert row["next_summary"]["remaining"] == nxt.entries.first().units
    plain = {r["type"].code: r for r in balances.rows(emp, today)}["AL"]
    assert "next_pot" not in plain


def test_rows_leave_out_a_type_with_no_policy_unless_asked(db):
    emp = hours_employee()
    today = timezone.localdate()
    assert "STUDY" not in {r["type"].code for r in balances.rows(emp, today)}
    rows = {r["type"].code: r for r in balances.rows(emp, today, show_setup_gaps=True)}
    assert "No Study leave policy" in rows["STUDY"]["error"]


def test_after_gives_remaining_cost_and_the_balance_after(db):
    emp = hours_employee()
    today = timezone.localdate()
    al = absence_type("AL")
    assert balances.after(emp, al, today, Decimal("22.50"), today) == {"pot": None}
    assert balances.after(emp, absence_type("SICK"), today, Decimal("7.50"), today) is None
    pots.for_day(emp, al, today)
    a = balances.after(emp, al, today, Decimal("22.50"), today)
    assert (a["remaining"], a["cost"], a["after"], a["over"]) == (
        Decimal("210.00"), Decimal("22.50"), Decimal("187.50"), False)
    assert balances.after(emp, al, today, Decimal("300"), today)["over"] is True


# --- what "opens overnight" promises (I5) ---------------------------------------------

def test_the_bank_holiday_row_shows_only_where_the_pot_is_used(db):
    from absence.models import Policy
    from tests.factories import make_policy
    emp = hours_employee()
    today = timezone.localdate()
    ct = emp.contracts.first().contract_type
    make_policy(ct, "BH")                                   # a policy, but annual leave says "closed"
    assert "BH" not in {r["type"].code for r in balances.rows(emp, today, include_bh=True, show_setup_gaps=True)}
    ct.policies.filter(absence_type__code="AL").update(bank_holiday_handling=Policy.BankHolidays.PRO_RATA_POT)
    assert "BH" in {r["type"].code for r in balances.rows(emp, today, include_bh=True)}


def test_next_year_for_someone_leaving_before_it_does_not_promise_a_pot(employee_client, employee_user):
    emp = _me(employee_user)
    this = pots.for_day(emp, absence_type("AL"), timezone.localdate())
    emp.end_date = this.year_end
    emp.save()
    body = employee_client.get("/absence/balances/").content.decode()
    assert "Not opened yet" not in body and "Not employed then." in body
