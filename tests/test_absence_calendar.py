from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from absence.models import Absence
from absence.services import bank_holidays, bookings, calendar
from people.models import Team
from people.services import positions
from tests.factories import absence_type, hours_employee, make_employee, make_employment, make_team

User = get_user_model()


def _team_of(n, team, boss=None):
    emps = []
    for i in range(n):
        e = hours_employee(employee=make_employee(first=f"P{i}"))
        positions.add(None, e, "Receptionist", team, boss, e.start_date)
        emps.append(e)
    return emps


def test_off_on_shows_label_not_reason(db, hr_admin):
    team = make_team()
    a, b, c = _team_of(3, team)
    bookings.request(hr_admin, a, absence_type("SICK"), date(2026, 6, 1), category="mental")
    leave = bookings.request(hr_admin, b, absence_type("AL"), date(2026, 6, 1), start_half="PM")
    bookings.approve(hr_admin, leave)
    rows = calendar.off_on(date(2026, 6, 1), team)
    labels = {r["employee"].pk: r["label"] for r in rows}
    assert labels == {a.employee.pk: "Sick", b.employee.pk: "Leave"}
    assert "mental" not in str(rows)
    assert calendar.present(team, date(2026, 6, 1)) == (1, 3)


def test_half_days_are_reported_from_costings_halves(db, hr_admin):
    team = make_team()
    a, b, _ = _team_of(3, team)
    bookings.approve(hr_admin, bookings.request(hr_admin, a, absence_type("AL"), date(2026, 6, 1),
                                                date(2026, 6, 2), start_half="PM", end_half="AM"))
    assert [r["halves"] for r in calendar.off_on(date(2026, 6, 1), team)] == [["PM"]]
    assert [r["halves"] for r in calendar.off_on(date(2026, 6, 2), team)] == [["AM"]]


def test_pending_not_on_calendar(db, hr_admin):
    team = make_team()
    (a,) = _team_of(1, team)
    bookings.request(hr_admin, a, absence_type("AL"), date(2026, 6, 1))
    assert calendar.off_on(date(2026, 6, 1), team) == []


def test_off_on_without_a_team_is_the_whole_practice(db, hr_admin):
    a, = _team_of(1, make_team("Nursing"))
    b, = _team_of(1, make_team("Reception"))
    for e in (a, b):
        bookings.approve(hr_admin, bookings.request(hr_admin, e, absence_type("AL"), date(2026, 6, 1)))
    assert len(calendar.off_on(date(2026, 6, 1))) == 2
    assert len(calendar.off_on(date(2026, 6, 1), Team.objects.get(name="Nursing"))) == 1


def test_partial_hours_do_not_reduce_present(db, hr_admin):
    from datetime import time
    team = make_team()
    a, b = _team_of(2, team)
    bookings.approve(hr_admin, bookings.request(hr_admin, a, absence_type("AL"), date(2026, 6, 1),
                                                start_time=time(9), end_time=time(11), hours=2))
    rows = calendar.off_on(date(2026, 6, 1), team)
    assert rows[0]["partial_hours"] == 2
    assert calendar.present(team, date(2026, 6, 1)) == (2, 2)


def test_automatic_bank_holidays_are_not_someone_off(db, hr_admin):
    from tests.test_absence_bank_holidays import MAY_DAY, Y0, Y1, _with_pot_handling
    team = make_team()
    a, b = _team_of(2, team)
    _with_pot_handling(a)
    bank_holidays.sync_auto_absences(a, Y0, Y1)
    assert Absence.objects.filter(employment=a, auto_bank_holiday=True, start_date=MAY_DAY,
                                  status="approved").exists()
    assert calendar.off_on(MAY_DAY, team) == []
    assert calendar.off_on(MAY_DAY) == []
    assert calendar.present(team, MAY_DAY) == (2, 2)
    assert calendar.days_for(MAY_DAY, MAY_DAY, team)[0]["off"] == []
    day = next(d for w in calendar.month(2026, 5, team) for d in w if d["day"] == MAY_DAY)
    assert day["off"] == []


def test_leavers_and_movers_are_not_counted(db, hr_admin):
    team = make_team()
    a, b = _team_of(2, team)
    positions.end(None, a.positions.first(), date(2026, 5, 31))
    assert calendar.present(team, date(2026, 5, 31)) == (2, 2)
    assert calendar.present(team, date(2026, 6, 1)) == (1, 1)


def test_days_for_is_one_row_per_day(db, hr_admin):
    team = make_team()
    a, b = _team_of(2, team)
    bookings.approve(hr_admin, bookings.request(hr_admin, a, absence_type("AL"), date(2026, 6, 2)))
    rows = calendar.days_for(date(2026, 6, 1), date(2026, 6, 3), team)
    assert [(r["day"].day, r["present"], r["headcount"], len(r["off"])) for r in rows] == [
        (1, 2, 2, 0), (2, 1, 2, 1), (3, 2, 2, 0)]
    assert calendar.days_for(date(2026, 6, 1), date(2026, 6, 1), None) == [
        {"day": date(2026, 6, 1), "off": [], "present": None, "headcount": None}]


def test_warning_if_approved(db, hr_admin):
    team = make_team(min_present=2)
    a, b, c = _team_of(3, team)
    first = bookings.request(hr_admin, a, absence_type("AL"), date(2026, 6, 1))
    bookings.approve(hr_admin, first)
    second = bookings.request(hr_admin, b, absence_type("AL"), date(2026, 6, 1))
    assert calendar.warning_if_approved(second, team) == "Approving leaves fewer than 2 of Reception present on 1 Jun 2026."
    third = bookings.request(hr_admin, c, absence_type("AL"), date(2026, 6, 2))
    assert calendar.warning_if_approved(third, team) is None


def test_no_warning_without_a_minimum_or_for_part_days(db, hr_admin):
    from datetime import time
    team = make_team()
    a, b = _team_of(2, team)
    req = bookings.request(hr_admin, a, absence_type("AL"), date(2026, 6, 1))
    assert calendar.warning_if_approved(req, team) is None
    team.min_present = 2
    team.save()
    part = bookings.request(hr_admin, b, absence_type("AL"), date(2026, 6, 2),
                            start_time=time(9), end_time=time(10), hours=1)
    assert calendar.warning_if_approved(part, team) is None
    assert calendar.warning_if_approved(req, None) is None


def test_month_grid_and_view(db, admin_client):
    weeks = calendar.month(2026, 6)
    assert weeks[0][0]["day"] == date(2026, 6, 1) and len(weeks[-1]) == 7
    assert admin_client.get("/absence/calendar/?month=2026-06").status_code == 200


def test_month_grid_puts_absences_on_their_days(db, hr_admin):
    team = make_team()
    (a,) = _team_of(1, team)
    bookings.approve(hr_admin, bookings.request(hr_admin, a, absence_type("AL"), date(2026, 6, 2), date(2026, 6, 3)))
    days = {d["day"]: d for w in calendar.month(2026, 6, team) for d in w}
    assert [len(days[date(2026, 6, n)]["off"]) for n in (1, 2, 3, 4)] == [0, 1, 1, 0]
    assert days[date(2026, 6, 1)]["in_month"] is True
    july = {d["day"]: d for w in calendar.month(2026, 7, team) for d in w}
    assert july[date(2026, 6, 29)]["in_month"] is False and july[date(2026, 6, 29)]["off"] == []


def test_view_defaults_and_ignores_bad_parameters(db, admin_client):
    for qs in ("", "?month=nonsense", "?month=2026-13", "?team=x", "?team=9999"):
        assert admin_client.get("/absence/calendar/" + qs).status_code == 200


def test_view_needs_a_login(db):
    r = Client().get(reverse("absence:calendar"))
    assert r.status_code == 302 and "login" in r["Location"]


def test_view_filters_by_team_and_links_months(db, admin_client, hr_admin):
    reception, nursing = make_team(), make_team("Nursing")
    (a,) = _team_of(1, reception)
    (b,) = _team_of(1, nursing)
    for e in (a, b):
        bookings.approve(hr_admin, bookings.request(hr_admin, e, absence_type("AL"), date(2026, 6, 1)))
    body = admin_client.get(f"/absence/calendar/?month=2026-06&team={nursing.pk}").content.decode()
    assert "P0 Patel" in body and body.count("P0 Patel") == 1
    assert "month=2026-05" in body and "month=2026-07" in body
    both = admin_client.get("/absence/calendar/?month=2026-06").content.decode()
    assert both.count("P0 Patel") == 2


def test_calendar_shows_labels_only_to_colleagues_and_type_detail_to_hr(db, hr_admin, employee_client, admin_client):
    team = make_team()
    a, b = _team_of(2, team)
    bookings.request(hr_admin, a, absence_type("SICK"), date(2026, 6, 1), category="mental")
    bookings.approve(hr_admin, bookings.request(hr_admin, b, absence_type("AL"), date(2026, 6, 1)))
    url = "/absence/calendar/?month=2026-06"
    body = employee_client.get(url).content.decode()
    assert "P0 Patel" in body and "Sick" in body and "Leave" in body
    for hidden in ("mental", "Mental health", "Sickness", "Annual leave"):
        assert hidden not in body
    hr = admin_client.get(url).content.decode()
    assert "Sickness" in hr and "Annual leave" in hr
    assert "mental" not in hr.lower() and "Mental health" not in hr


def test_nav_links_to_the_calendar(db, employee_client):
    body = employee_client.get(reverse("absence:mine")).content.decode()
    url = reverse("absence:calendar")
    desktop, tabbar = body.split('<nav class="tabbar"')
    assert f'href="{url}" class="nav-link' in desktop
    assert f'href="{url}" class="tabbar-item' not in tabbar
    sheet = tabbar.split('<div class="tabbar-sheet">')[1]
    assert f'href="{url}" class="tabbar-link"' in sheet


# --- the decision page, end to end (Task 3 tested it against a stub) ---

def _decide_setup(min_present):
    boss_user = User.objects.create_user(email="boss@example.org", password="pw")
    boss = make_employee(first="Boss", user=boss_user)
    make_employment(employee=boss, start=date(2026, 1, 1))
    team = make_team(min_present=min_present)
    a, b, c = _team_of(3, team, boss)
    client = Client()
    client.force_login(boss_user)
    return client, team, (a, b, c)


def test_decide_page_warns_when_approving_would_leave_too_few(db, hr_admin):
    client, team, (a, b, c) = _decide_setup(2)
    bookings.approve(hr_admin, bookings.request(hr_admin, a, absence_type("AL"), date(2026, 6, 1)))
    second = bookings.request(hr_admin, b, absence_type("AL"), date(2026, 6, 1))
    body = client.get(reverse("absence:decide", args=[second.pk])).content.decode()
    assert "Approving leaves fewer than 2 of Reception present on 1 Jun 2026." in body
    assert "2 of 3 present" in body
    other = bookings.request(hr_admin, c, absence_type("AL"), date(2026, 6, 2))
    assert "Approving leaves fewer" not in client.get(reverse("absence:decide", args=[other.pk])).content.decode()


def test_decide_page_shows_labels_only_never_a_category(db, hr_admin):
    client, team, (a, b, c) = _decide_setup(None)
    bookings.request(hr_admin, a, absence_type("SICK"), date(2026, 6, 1), category="mental")
    req = bookings.request(hr_admin, b, absence_type("AL"), date(2026, 6, 1))
    body = client.get(reverse("absence:decide", args=[req.pk])).content.decode()
    assert "P0 Patel (Sick)" in body and "2 of 3 present" in body
    for hidden in ("mental", "Mental health", "Sickness"):
        assert hidden not in body
