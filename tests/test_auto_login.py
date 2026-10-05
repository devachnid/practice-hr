"""Adding an employee creates their login account from the work email and
sends the invitation, unless HR unticks it or links an existing login."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core import mail
from django.core.exceptions import ValidationError

from accounts.services import logins
from people.models import AuditEntry, Employee
from tests.factories import make_employee

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture(autouse=True)
def relay(settings):
    settings.EMAIL_HOST = "smtp.example"


@pytest.fixture
def post(admin_client, django_capture_on_commit_callbacks):
    def _run(**extra):
        with django_capture_on_commit_callbacks(execute=True):
            return _post(admin_client, **extra)
    return _run


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
    return admin_client.post("/admin/people/employee/add/", data)


def _messages(r):
    """What the admin reads after the post. The invitation is sent (and
    its message added) on commit, which the test client runs after the
    response, so the messages are read from the request's own store."""
    return [str(m) for m in get_messages(r.wsgi_request)]


def test_adding_an_employee_creates_and_invites_their_login(post, hr_admin):
    r = post()
    e = Employee.objects.get(last_name="Lovelace")
    assert e.user is not None and e.user.email == "Ada@example.org"
    assert not e.user.has_usable_password() and not e.user.is_hr_admin and e.user.is_active
    assert [m.to for m in mail.outbox] == [["Ada@example.org"]]
    assert AuditEntry.objects.filter(model="people.employee", object_id=e.pk, field="user",
                                     after="Ada@example.org", actor=hr_admin).exists()
    assert "Invitation sent to Ada@example.org." in _messages(r)


def test_the_invitation_can_go_to_the_personal_email(post):
    r = post(personal_email="ada@home.example", invite_to="personal")
    e = Employee.objects.get(last_name="Lovelace")
    assert e.user.email == "Ada@example.org"                  # the login is still the work email
    assert [m.to for m in mail.outbox] == [["ada@home.example"]]
    assert "Invitation sent to ada@home.example." in _messages(r)


def test_personal_email_as_the_destination_needs_one(post):
    r = post(invite_to="personal")
    assert "Enter their personal email, or send the invitation to the work email." in r.content.decode()
    assert not Employee.objects.filter(last_name="Lovelace").exists() and not mail.outbox


def test_create_and_link_together_is_refused(post):
    other = User.objects.create_user(email="x@example.org")
    r = post(user=other.pk)
    assert "Untick Create a login account to link an existing one." in r.content.decode()
    assert not Employee.objects.filter(last_name="Lovelace").exists()


def test_an_existing_unlinked_login_with_that_email_is_linked_and_invited(post):
    existing = User.objects.create_user(email="ADA@example.org")
    post()
    e = Employee.objects.get(last_name="Lovelace")
    assert e.user == existing and User.objects.count() == 2      # hr_admin and existing: nothing new
    assert [m.to for m in mail.outbox] == [["ADA@example.org"]]


def test_a_login_already_linked_to_someone_else_is_refused(post):
    taken = User.objects.create_user(email="ada@example.org")
    make_employee(first="Other", last="Person", email="other@example.org", user=taken)
    r = post()
    assert "A login account with this email already belongs to Other Person." in r.content.decode()
    assert not Employee.objects.filter(last_name="Lovelace").exists() and not mail.outbox


def test_unticked_means_no_login_and_no_email(post):
    post(create_login=None)
    e = Employee.objects.get(last_name="Lovelace")
    assert e.user is None and not mail.outbox and User.objects.count() == 1


def test_a_failed_send_keeps_the_login_and_shows_the_link(post, settings):
    settings.EMAIL_HOST = ""
    r = post()
    e = Employee.objects.get(last_name="Lovelace")
    assert e.user is not None and not mail.outbox
    assert any("copy this link" in m for m in _messages(r))


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
    with pytest.raises(ValidationError):
        logins.create_for_employee(hr_admin, e, "work")
    e.refresh_from_db()
    assert e.user is None and User.objects.count() == 2 and not mail.outbox


# ---- review: an existing login is never taken over -------------------------------------------

def test_a_superusers_email_is_refused_to_an_hr_admin(post):
    User.objects.create_superuser(email="ada@example.org", password="pw")
    r = post(personal_email="attacker@evil.example", invite_to="personal")
    assert "A login account with this email already exists and cannot be linked here." in r.content.decode()
    assert not Employee.objects.filter(last_name="Lovelace").exists() and not mail.outbox


def test_an_existing_login_with_a_password_is_linked_and_not_emailed(post):
    existing = User.objects.create_user(email="ada@example.org", password="pw")
    r = post()
    e = Employee.objects.get(last_name="Lovelace")
    assert e.user == existing and not mail.outbox
    assert "Linked to their existing login ada@example.org; no invitation needed." in _messages(r)


def test_an_existing_logins_link_never_goes_to_the_personal_email(post):
    User.objects.create_user(email="ada@example.org")
    r = post(personal_email="ada@home.example", invite_to="personal")
    assert "A login account with this email already exists; send its invitation to the work email." in r.content.decode()
    assert not Employee.objects.filter(last_name="Lovelace").exists() and not mail.outbox


def test_an_inactive_login_is_refused(post):
    User.objects.create_user(email="ada@example.org", is_active=False)
    r = post()
    assert "That login account is inactive" in r.content.decode()
    assert not Employee.objects.filter(last_name="Lovelace").exists() and not mail.outbox


def test_the_invitation_goes_only_once_the_add_has_committed(admin_client, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks() as callbacks:
        _post(admin_client)
    assert Employee.objects.get(last_name="Lovelace").user is not None
    assert not mail.outbox and len(callbacks) == 1
    callbacks[0]()
    assert [m.to for m in mail.outbox] == [["Ada@example.org"]]


def test_a_change_post_cannot_smuggle_the_login_fields(admin_client, django_capture_on_commit_callbacks):
    e = make_employee(first="Ada", last="Lovelace", email="ada@example.org")
    with django_capture_on_commit_callbacks(execute=True):
        r = admin_client.post(f"/admin/people/employee/{e.pk}/change/", {
            "first_name": "Ada", "last_name": "Lovelace", "work_email": "ada@example.org",
            "preferred_name": "", "personal_email": "", "phone": "", "address_line1": "",
            "address_line2": "", "town": "", "postcode": "", "ni_number": "",
            "bank_account_name": "", "bank_sort_code": "", "bank_account_number": "",
            "create_login": "on", "invite_to": "personal",
            "emergency_contacts-TOTAL_FORMS": 0, "emergency_contacts-INITIAL_FORMS": 0,
            "employments-TOTAL_FORMS": 0, "employments-INITIAL_FORMS": 0, "_save": "Save"})
    assert r.status_code == 302
    e.refresh_from_db()
    assert e.user is None and not mail.outbox and User.objects.count() == 1


def test_a_failed_send_to_the_personal_email_names_it(post, settings):
    settings.EMAIL_HOST = ""
    r = post(personal_email="ada@home.example", invite_to="personal")
    assert any("send it to ada@home.example yourself" in m for m in _messages(r))


def test_a_failed_send_logs_no_address(post, settings, caplog):
    settings.EMAIL_HOST = "smtp.example"
    settings.EMAIL_BACKEND = "tests.test_auto_login.BrokenBackend"
    with caplog.at_level("ERROR", logger="accounts.mail"):
        r = post(personal_email="ada@home.example", invite_to="personal")
    assert any("copy this link" in m for m in _messages(r))
    assert "ada@home.example" not in caplog.text and "Ada@example.org" not in caplog.text


class BrokenBackend:
    def __init__(self, *args, **kwargs):
        pass

    def send_messages(self, messages):
        raise OSError("relay down")
