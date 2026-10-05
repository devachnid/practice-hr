"""Adding an employee creates their login account from the work email and
sends the invitation, unless HR unticks it or links an existing login."""

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import RequestFactory

from accounts.services import logins
from people.models import AuditEntry, Employee
from tests.factories import make_employee

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture(autouse=True)
def relay(settings):
    settings.EMAIL_HOST = "smtp.example"


def _post(admin_client, **extra):
    data = {
        "first_name": "Ada", "last_name": "Lovelace", "work_email": "Ada@Example.org",
        "preferred_name": "", "personal_email": "", "phone": "", "address_line1": "",
        "address_line2": "", "town": "", "postcode": "", "ni_number": "",
        "bank_account_name": "", "bank_sort_code": "", "bank_account_number": "",
        "create_login": "on", "invite_to": "work",
        "emergency_contacts-TOTAL_FORMS": 0, "emergency_contacts-INITIAL_FORMS": 0,
        "employments-TOTAL_FORMS": 0, "employments-INITIAL_FORMS": 0,
    }
    data.update(extra)
    if data.get("create_login") is None:
        data.pop("create_login")
    return admin_client.post("/admin/people/employee/add/", data, follow=True)


def test_adding_an_employee_creates_and_invites_their_login(admin_client, hr_admin):
    r = _post(admin_client)
    e = Employee.objects.get(last_name="Lovelace")
    assert e.user is not None and e.user.email == "Ada@example.org"
    assert not e.user.has_usable_password() and not e.user.is_hr_admin and e.user.is_active
    assert [m.to for m in mail.outbox] == [["Ada@example.org"]]
    assert AuditEntry.objects.filter(model="people.employee", object_id=e.pk, field="user",
                                     after="Ada@example.org", actor=hr_admin).exists()
    assert "Invitation sent to Ada@example.org" in r.content.decode()


def test_the_invitation_can_go_to_the_personal_email(admin_client):
    r = _post(admin_client, personal_email="ada@home.example", invite_to="personal")
    e = Employee.objects.get(last_name="Lovelace")
    assert e.user.email == "Ada@example.org"                  # the login is still the work email
    assert [m.to for m in mail.outbox] == [["ada@home.example"]]
    assert "Invitation sent to ada@home.example" in r.content.decode()


def test_personal_email_as_the_destination_needs_one(admin_client):
    r = _post(admin_client, invite_to="personal")
    assert "Enter their personal email, or send the invitation to the work email." in r.content.decode()
    assert not Employee.objects.filter(last_name="Lovelace").exists() and not mail.outbox


def test_create_and_link_together_is_refused(admin_client):
    other = User.objects.create_user(email="x@example.org")
    r = _post(admin_client, user=other.pk)
    assert "Untick Create a login account to link an existing one." in r.content.decode()
    assert not Employee.objects.filter(last_name="Lovelace").exists()


def test_an_existing_unlinked_login_with_that_email_is_linked_and_invited(admin_client):
    existing = User.objects.create_user(email="ADA@example.org")
    _post(admin_client)
    e = Employee.objects.get(last_name="Lovelace")
    assert e.user == existing and User.objects.count() == 2      # hr_admin and existing: nothing new
    assert [m.to for m in mail.outbox] == [["ADA@example.org"]]


def test_a_login_already_linked_to_someone_else_is_refused(admin_client):
    taken = User.objects.create_user(email="ada@example.org")
    make_employee(first="Other", last="Person", email="other@example.org", user=taken)
    r = _post(admin_client)
    assert "A login account with this email already belongs to Other Person." in r.content.decode()
    assert not Employee.objects.filter(last_name="Lovelace").exists() and not mail.outbox


def test_unticked_means_no_login_and_no_email(admin_client):
    _post(admin_client, create_login=None)
    e = Employee.objects.get(last_name="Lovelace")
    assert e.user is None and not mail.outbox and User.objects.count() == 1


def test_a_failed_send_keeps_the_login_and_shows_the_link(admin_client, settings):
    settings.EMAIL_HOST = ""
    r = _post(admin_client)
    e = Employee.objects.get(last_name="Lovelace")
    assert e.user is not None and not mail.outbox
    assert "copy this link" in r.content.decode()


def test_the_change_page_has_no_login_fields(admin_client):
    e = make_employee()
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert 'name="create_login"' not in body and 'name="invite_to"' not in body
    body = admin_client.get("/admin/people/employee/add/").content.decode()
    assert 'name="create_login"' in body and 'name="invite_to"' in body


def test_the_service_refuses_a_login_linked_elsewhere_and_writes_nothing(hr_admin):
    taken = User.objects.create_user(email="ada@example.org")
    make_employee(first="Other", last="Person", email="other@example.org", user=taken)
    e = make_employee(first="Ada", last="Lovelace", email="ada@example.org")
    request = RequestFactory().get("/admin/people/employee/add/")
    request.user = hr_admin
    with pytest.raises(ValidationError):
        logins.create_for_employee(hr_admin, e, request, "work")
    e.refresh_from_db()
    assert e.user is None and User.objects.count() == 2 and not mail.outbox
