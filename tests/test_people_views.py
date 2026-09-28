from datetime import date

from people.models import AuditEntry, Employee
from people.services import positions
from tests.factories import make_employee, make_employment, make_team


def test_me_shows_record_and_hides_ni(employee_client, employee_user):
    e = make_employee(user=employee_user, ni_number="AB123456C")
    make_employment(employee=e)
    r = employee_client.get("/people/me/")
    assert r.status_code == 200
    body = r.content.decode()
    assert "Sam Patel" in body and "AB123456C" not in body


def test_me_without_employee_record_is_polite(employee_client):
    r = employee_client.get("/people/me/")
    assert r.status_code == 200
    assert "no employee record" in r.content.decode().lower()


def test_me_post_updates_personal_details(employee_client, employee_user):
    e = make_employee(user=employee_user)
    r = employee_client.post("/people/me/", {"phone": "0113", "personal_email": "s@x.org",
                                             "address_line1": "", "address_line2": "",
                                             "town": "Leeds", "postcode": ""})
    assert r.status_code == 302
    assert Employee.objects.get(pk=e.pk).phone == "0113"
    entry = AuditEntry.objects.get(model="people.employee", object_id=e.pk, field="phone")
    assert (entry.before, entry.after) == ("", "0113")
    assert entry.actor == employee_user


def test_team_lists_reports_only_for_approver(employee_client, employee_user, admin_client, hr_admin):
    boss = make_employee(first="Boss", user=hr_admin)
    make_employment(employee=boss, start=date(2026, 1, 1))
    sam = make_employee(user=employee_user)
    sam_emp = make_employment(employee=sam, start=date(2026, 1, 1))
    positions.add(None, sam_emp, "Receptionist", make_team(), boss, date(2026, 1, 1))
    assert employee_client.get("/people/team/").status_code == 403
    r = admin_client.get("/people/team/")
    assert r.status_code == 200 and "Sam Patel" in r.content.decode()
