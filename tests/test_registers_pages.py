from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from people.models import AuditEntry, Team
from people.services import employments, positions, titles
from registers import adapters
from registers.adapters import Result
from registers.models import Lookup, RegisterBody, Registration
from registers.services import lookups, registrations
from tests.factories import make_employee

pytestmark = pytest.mark.django_db
User = get_user_model()
CLEAR = Result("clear", "Registered with a licence to practise", "Priya Patel", "a" * 64)


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr(lookups, "sleep", lambda seconds: None)


@pytest.fixture
def gp_bodies():
    gmc, mpl = RegisterBody.objects.get(code="gmc"), RegisterBody.objects.get(code="mpl_wales")
    title = titles.get_or_create("Salaried GP")
    gmc.positions.add(title)
    mpl.positions.add(title)
    for b in (gmc, mpl):
        b.verified = True
        b.save()
    return gmc, mpl


def _gp(hr_admin, user=None):
    e = make_employee(first="Priya", last="Patel", user=user)
    emp = employments.start(hr_admin, e, timezone.localdate() - timedelta(days=400))
    team = Team.objects.get_or_create(name="Reception")[0]        # two GPs share the one team
    positions.add(hr_admin, emp, titles.get_or_create("Salaried GP"), team, None, emp.start_date)
    return e


def _change_post(e, **extra):
    data = {"first_name": "Priya", "last_name": "Patel", "work_email": e.work_email, "preferred_name": "",
            "personal_email": "", "phone": "", "address_line1": "", "address_line2": "", "town": "",
            "postcode": "", "ni_number": "", "bank_account_name": "", "bank_sort_code": "",
            "bank_account_number": "", "emergency_contacts-TOTAL_FORMS": 0, "emergency_contacts-INITIAL_FORMS": 0,
            "employments-TOTAL_FORMS": 0, "employments-INITIAL_FORMS": 0, "_save": "Save"}
    data.update(extra)
    return data


# ---- the Details tab ---------------------------------------------------------------------------

def test_the_details_tab_has_one_number_field_per_needed_body_and_saves_through_the_service(admin_client, hr_admin,
                                                                                             gp_bodies):
    gmc, mpl = gp_bodies
    e = _gp(hr_admin)
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert 'name="registration_gmc"' in body and "GMC number" in body
    assert 'name="registration_mpl_wales"' not in body        # shares the GMC number
    r = admin_client.post(f"/admin/people/employee/{e.pk}/change/", _change_post(e, registration_gmc="1234567"))
    assert r.status_code == 302
    assert Registration.objects.get(employee=e, body=gmc).number == "1234567"
    assert Registration.objects.get(employee=e, body=mpl).number == "1234567"
    assert AuditEntry.objects.filter(model="people.employee", object_id=e.pk, field="registration:gmc").exists()
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert 'value="1234567"' in body


def test_a_bad_number_is_a_form_error_and_blank_clears_it(admin_client, hr_admin, gp_bodies):
    gmc, _ = gp_bodies
    e = _gp(hr_admin)
    r = admin_client.post(f"/admin/people/employee/{e.pk}/change/", _change_post(e, registration_gmc="12"))
    assert r.status_code == 200 and "A GMC number is seven digits." in r.content.decode()
    assert not Registration.objects.filter(employee=e).exists()
    registrations.set_number(hr_admin, e, gmc, "1234567")
    r = admin_client.post(f"/admin/people/employee/{e.pk}/change/", _change_post(e, registration_gmc=""))
    assert r.status_code == 302 and not Registration.objects.filter(employee=e).exists()


def test_no_field_for_a_title_that_needs_no_body_and_none_on_the_add_page(admin_client, hr_admin, gp_bodies):
    e = make_employee()
    employments.start(hr_admin, e, timezone.localdate() - timedelta(days=10))
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert "registration_" not in body
    assert "registration_" not in admin_client.get("/admin/people/employee/add/").content.decode()


def test_a_shared_number_across_two_people_is_a_warning_not_a_refusal(admin_client, hr_admin, gp_bodies):
    gmc, _ = gp_bodies
    other = _gp(hr_admin)
    registrations.set_number(hr_admin, other, gmc, "1234567")
    e = _gp(hr_admin)
    r = admin_client.post(f"/admin/people/employee/{e.pk}/change/", _change_post(e, registration_gmc="1234567"),
                          follow=True)
    assert Registration.objects.get(employee=e, body=gmc).number == "1234567"
    assert "is also recorded for Priya Patel" in r.content.decode()


# ---- the Compliance tab -------------------------------------------------------------------------

def test_the_compliance_tab_lists_registrations_with_check_now_and_the_register_link(admin_client, hr_admin,
                                                                                    gp_bodies, monkeypatch):
    gmc, mpl = gp_bodies
    e = _gp(hr_admin)
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert "Registrations" in body and "No number recorded" in body
    registrations.set_number(hr_admin, e, gmc, "1234567")
    monkeypatch.setattr(adapters, "lookup", lambda *a: CLEAR)
    lookups.run(Registration.objects.get(employee=e, body=gmc), "scheduled")
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert "Registered with a licence to practise" in body and "Priya Patel" in body
    assert "Not checked yet" in body                       # the Welsh row
    reg = Registration.objects.get(employee=e, body=gmc)
    assert f'href="/registers/{reg.pk}/check/"' in body and "Check now" in body
    assert f'href="{adapters.url("gmc", "1234567")}"' in body and "On the register" in body


def test_the_tab_says_when_a_body_is_paused_or_not_verified(admin_client, hr_admin, gp_bodies):
    gmc, _ = gp_bodies
    e = _gp(hr_admin)
    registrations.set_number(hr_admin, e, gmc, "1234567")
    gmc.verified = False
    gmc.save()
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert "not verified" in body
    gmc.verified, gmc.paused_at = True, timezone.now()
    gmc.save()
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert "paused" in body and "not verified" not in body


# ---- Check now ---------------------------------------------------------------------------------

def test_check_now_confirms_on_get_runs_on_post_and_is_hrs_only(admin_client, hr_admin, gp_bodies, monkeypatch):
    gmc, _ = gp_bodies
    e = _gp(hr_admin)
    reg = registrations.set_number(hr_admin, e, gmc, "1234567")
    monkeypatch.setattr(adapters, "lookup", lambda *a: CLEAR)
    r = admin_client.get(f"/registers/{reg.pk}/check/")
    assert r.status_code == 200 and "Check Priya Patel" in r.content.decode() and Lookup.objects.count() == 0
    r = admin_client.post(f"/registers/{reg.pk}/check/", follow=True)
    assert r.redirect_chain[0][0].endswith(f"/admin/people/employee/{e.pk}/change/")
    assert "GMC: Registered with a licence to practise (Priya Patel)" in r.content.decode()
    lk = Lookup.objects.get()
    assert lk.trigger == "on_demand" and lk.requested_by == hr_admin
    assert AuditEntry.objects.filter(kind="viewed", field="checks", object_id=e.pk).exists()
    c = Client()
    c.force_login(User.objects.create_user(email="x@example.com", password="pw"))
    assert c.get(f"/registers/{reg.pk}/check/").status_code == 403
    assert c.post(f"/registers/{reg.pk}/check/").status_code == 403 and Lookup.objects.count() == 1
    anon = Client().post(f"/registers/{reg.pk}/check/")
    assert anon.status_code == 302 and anon["Location"].startswith("/accounts/login/")


def test_check_now_on_an_unverified_body_says_so_and_runs(admin_client, hr_admin, gp_bodies, monkeypatch):
    gmc, _ = gp_bodies
    gmc.verified = False
    gmc.save()
    e = _gp(hr_admin)
    reg = registrations.set_number(hr_admin, e, gmc, "1234567")
    monkeypatch.setattr(adapters, "lookup", lambda *a: Result("unreadable", "HTTP 503", "", "e" * 64))
    r = admin_client.post(f"/registers/{reg.pk}/check/", follow=True)
    body = r.content.decode()
    assert "could not be read" in body and "not yet verified" in body and Lookup.objects.count() == 1
