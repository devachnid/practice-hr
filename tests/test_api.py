import logging
from datetime import date

import pytest

from absence.models import Absence, AbsenceType
from absence.services import bookings
from hr.checks import api_tokens
from people.services import positions
from tests.factories import absence_type, hours_employee, make_team


@pytest.fixture
def api(client, settings):
    settings.HR_API_TOKENS = frozenset({"t0k"})
    return lambda url: client.get(url, HTTP_AUTHORIZATION="Bearer t0k")


def test_token_required(client, settings):
    settings.HR_API_TOKENS = frozenset({"t0k"})
    assert client.get("/api/v1/people").status_code == 401
    assert client.get("/api/v1/people", HTTP_AUTHORIZATION="Bearer wrong").status_code == 401


@pytest.mark.parametrize("url", ["/api/v1/people", "/api/v1/patterns?employee=1",
                                 "/api/v1/absences?from=2026-06-01&to=2026-06-30"])
def test_every_endpoint_is_behind_the_token(client, settings, url):
    settings.HR_API_TOKENS = frozenset({"t0k"})
    r = client.get(url)
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"
    assert r.json() == {"error": "unauthorised"}
    assert "no-store" in r.headers["Cache-Control"]


@pytest.mark.parametrize("header", ["Bearer ", "Bearer", "Basic t0k", "t0k", "Bearer t0k "])
def test_malformed_headers_are_refused(client, settings, header):
    settings.HR_API_TOKENS = frozenset({"t0k"})
    assert client.get("/api/v1/people", HTTP_AUTHORIZATION=header).status_code == 401


def test_no_tokens_configured_refuses_everything(client, settings):
    """An unset HR_API_TOKENS is not "any token" and not "no token needed"."""
    settings.HR_API_TOKENS = frozenset()
    assert client.get("/api/v1/people", HTTP_AUTHORIZATION="Bearer anything").status_code == 401
    assert client.get("/api/v1/people", HTTP_AUTHORIZATION="Bearer ").status_code == 401
    assert client.get("/api/v1/people").status_code == 401


def test_a_non_ascii_token_is_refused_not_an_error(client, settings):
    settings.HR_API_TOKENS = frozenset({"t0k"})
    r = client.get("/api/v1/people", HTTP_AUTHORIZATION="Bearer tök")
    assert r.status_code == 401


def test_a_session_is_not_a_token(admin_client, settings):
    settings.HR_API_TOKENS = frozenset({"t0k"})
    assert admin_client.get("/api/v1/people").status_code == 401


def test_any_configured_token_works(client, settings, db):
    settings.HR_API_TOKENS = frozenset({"one", "two"})
    assert client.get("/api/v1/people", HTTP_AUTHORIZATION="Bearer two").status_code == 200


def test_responses_are_not_stored(api, db):
    emp = hours_employee()
    for url in ("/api/v1/people", f"/api/v1/patterns?employee={emp.employee.pk}",
                "/api/v1/absences?from=2026-06-01&to=2026-06-30",
                "/api/v1/patterns", "/api/v1/absences"):
        assert "no-store" in api(url).headers["Cache-Control"], url


def test_only_get(client, settings):
    settings.HR_API_TOKENS = frozenset({"t0k"})
    for method in ("POST", "PUT", "DELETE"):
        r = client.generic(method, "/api/v1/people", HTTP_AUTHORIZATION="Bearer t0k")
        assert r.status_code == 405 and r.headers["Allow"] == "GET", method
        assert r.headers["Cache-Control"] == "no-store"
    assert client.post("/api/v1/people").status_code == 401     # the token comes first


def test_the_token_is_never_logged(api, db, caplog):
    with caplog.at_level(logging.DEBUG):
        api("/api/v1/people")
    assert "t0k" not in caplog.text


def test_a_request_line_is_logged_without_the_token(client, settings, caplog):
    settings.HR_API_TOKENS = frozenset({"t0k"})
    with caplog.at_level(logging.INFO, logger="hr"):
        client.get("/api/v1/people", HTTP_AUTHORIZATION="Bearer wr0ng")
    assert "/api/v1/people" in caplog.text and "401" in caplog.text
    assert "wr0ng" not in caplog.text and "t0k" not in caplog.text


def test_people(api, db):
    emp = hours_employee()
    positions.add(None, emp, "Receptionist", make_team(), None, emp.start_date)
    data = api("/api/v1/people").json()
    row = data["people"][0]
    assert row["id"] == emp.employee.pk and row["email"] == emp.employee.work_email
    assert row["unit"] == "hours" and row["contract_type"] == "Reception"
    assert row["employment"] == {"start": "2026-04-01", "end": None}
    assert row["positions"] == [{"title": "Receptionist", "team": "Reception"}]


def test_patterns(api, db):
    emp = hours_employee()
    data = api(f"/api/v1/patterns?employee={emp.employee.pk}").json()
    v = data["patterns"][0]
    assert v["effective_from"] == "2026-04-01" and len(v["days"]) == 7
    assert v["days"][0] == {"weekday": 0, "am": "3.75", "pm": "3.75"}


@pytest.mark.parametrize("query", ["", "?employee=", "?employee=abc", "?employee=99999"])
def test_patterns_need_a_real_employee(api, db, query):
    assert api(f"/api/v1/patterns{query}").status_code == 400


@pytest.mark.parametrize("query", ["", "?from=2026-06-01", "?to=2026-06-30", "?from=x&to=y",
                                   "?from=2026-06-30&to=2026-06-01"])
def test_absences_need_an_ordered_window(api, db, query):
    assert api(f"/api/v1/absences{query}").status_code == 400


def test_absences_overlap_window_and_hide_category(api, db, hr_admin):
    emp = hours_employee()
    long = bookings.request(hr_admin, emp, absence_type("AL"), date(2026, 5, 25), date(2026, 6, 12))
    bookings.approve(hr_admin, long)
    spanning = bookings.request(hr_admin, emp, absence_type("AL"), date(2026, 6, 24), date(2026, 7, 8))
    bookings.approve(hr_admin, spanning)
    outside = bookings.request(hr_admin, emp, absence_type("AL"), date(2026, 8, 3))
    bookings.approve(hr_admin, outside)
    bookings.request(hr_admin, emp, absence_type("SICK"), date(2026, 6, 15), category="mental")
    pending = bookings.request(hr_admin, emp, absence_type("AL"), date(2026, 6, 20))
    data = api("/api/v1/absences?from=2026-06-01&to=2026-06-30").json()["absences"]
    by_start = {a["start"]: a for a in data}
    assert "2026-05-25" in by_start                              # starts before the window
    assert "2026-06-24" in by_start                              # ends after the window
    assert "2026-08-03" not in by_start                          # wholly outside
    assert by_start["2026-06-15"]["label"] == "Sick" and "mental" not in str(data)
    assert by_start["2026-06-20"]["status"] == "requested" and pending.pk == by_start["2026-06-20"]["id"]
    assert by_start["2026-05-25"] == {"id": long.pk, "employee": emp.employee.pk, "type": "AL", "label": "Leave",
                                      "status": "approved", "start": "2026-05-25", "end": "2026-06-12",
                                      "start_half": "", "end_half": "", "partial": None}


def test_one_absence_spanning_both_edges_is_returned(api, db, hr_admin):
    emp = hours_employee()
    a = bookings.request(hr_admin, emp, absence_type("AL"), date(2026, 5, 20), date(2026, 7, 10))
    bookings.approve(hr_admin, a)
    data = api("/api/v1/absences?from=2026-06-01&to=2026-06-30").json()["absences"]
    assert [row["id"] for row in data] == [a.pk]


def test_the_window_edges_are_inclusive(api, db, hr_admin):
    emp = hours_employee()
    first = bookings.request(hr_admin, emp, absence_type("AL"), date(2026, 5, 29), date(2026, 6, 1))
    last = bookings.request(hr_admin, emp, absence_type("AL"), date(2026, 6, 30), date(2026, 7, 2))
    data = api("/api/v1/absences?from=2026-06-01&to=2026-06-30").json()["absences"]
    assert {row["id"] for row in data} == {first.pk, last.pk}


def test_automatic_bank_holidays_are_not_returned(api, db, hr_admin):
    emp = hours_employee()
    bh = absence_type("AL")
    Absence.objects.create(employment=emp, absence_type=bh, status=Absence.Status.APPROVED,
                           start_date=date(2026, 6, 8), end_date=date(2026, 6, 8), auto_bank_holiday=True)
    real = bookings.request(hr_admin, emp, absence_type("AL"), date(2026, 6, 9))
    data = api("/api/v1/absences?from=2026-06-01&to=2026-06-30").json()["absences"]
    assert [row["id"] for row in data] == [real.pk]


def test_declined_and_cancelled_are_not_returned(api, db, hr_admin):
    emp = hours_employee()
    for status in (Absence.Status.DECLINED, Absence.Status.CANCELLED):
        Absence.objects.create(employment=emp, absence_type=absence_type("AL"), status=status,
                               start_date=date(2026, 6, 9), end_date=date(2026, 6, 9))
    assert api("/api/v1/absences?from=2026-06-01&to=2026-06-30").json() == {"absences": []}


def test_a_health_sensitive_type_is_always_sick_whatever_its_label(api, db, hr_admin):
    """calendar_label is editable in the admin; a sickness label edited to
    something more revealing (or a health type given another label) must
    not reach the rota."""
    sick = absence_type("SICK")
    assert sick.health_sensitive
    AbsenceType.objects.filter(pk=sick.pk).update(calendar_label="Mental health")
    emp = hours_employee()
    bookings.request(hr_admin, emp, absence_type("SICK"), date(2026, 6, 15), category="mental")
    (row,) = api("/api/v1/absences?from=2026-06-01&to=2026-06-30").json()["absences"]
    assert row["label"] == "Sick"
    assert "Mental" not in str(row) and "mental" not in str(row)


def test_a_partial_absence_carries_its_times(api, db, hr_admin):
    from datetime import time
    emp = hours_employee()
    a = bookings.request(hr_admin, emp, absence_type("AL"), date(2026, 6, 9),
                         start_time=time(9, 0), end_time=time(11, 0), hours="2")
    (row,) = api("/api/v1/absences?from=2026-06-01&to=2026-06-30").json()["absences"]
    assert row["id"] == a.pk
    assert row["partial"] == {"start_time": "09:00", "end_time": "11:00", "hours": "2.00"}


# --- the system check ---------------------------------------------------------------------

def test_check_warns_when_no_tokens_outside_debug(settings):
    settings.DEBUG = False
    settings.HR_API_TOKENS = frozenset()
    (warning,) = api_tokens(None)
    assert warning.id == "hr.W001" and warning.level == 30


def test_check_quiet_with_a_token(settings):
    settings.DEBUG = False
    settings.HR_API_TOKENS = frozenset({"t0k"})
    assert api_tokens(None) == []


def test_check_quiet_in_debug(settings):
    settings.DEBUG = True
    settings.HR_API_TOKENS = frozenset()
    assert api_tokens(None) == []
