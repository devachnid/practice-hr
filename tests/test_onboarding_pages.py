from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone

from documents.models import File
from onboarding.models import Checklist, ChecklistItem
from onboarding.services import checklists
from people.models import AuditEntry, EmergencyContact, Team
from people.services import access, employees, employments, positions, titles
from tests.factories import make_employee, make_team

pytestmark = pytest.mark.django_db
User = get_user_model()
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


def _starter(hr_admin, user, days_ahead=10, manager=None):
    e = make_employee(user=user)
    start = timezone.localdate() + timedelta(days=days_ahead)
    emp = employments.start(hr_admin, e, start)
    positions.add(hr_admin, emp, titles.get_or_create("Receptionist"), make_team(), manager, start)
    return emp


def test_a_pre_start_starter_is_sent_to_getting_started_from_every_page(hr_admin, employee_user, employee_client):
    _starter(hr_admin, employee_user)
    for path in ("/people/me/", "/absence/mine/", "/absence/calendar/", "/"):
        r = employee_client.get(path)
        assert r.status_code == 302 and r["Location"].startswith("/onboarding/")
    assert employee_client.get("/onboarding/").status_code == 200
    assert employee_client.get("/accounts/account/").status_code == 200


def test_on_the_start_date_the_normal_pages_open(hr_admin, employee_user, employee_client):
    _starter(hr_admin, employee_user, days_ahead=0)
    assert employee_client.get("/people/me/").status_code == 200
    assert employee_client.get("/onboarding/").status_code == 200    # still reachable until complete


def test_getting_started_lists_my_items_in_due_order_with_their_forms(hr_admin, employee_user, employee_client):
    _starter(hr_admin, employee_user)
    body = employee_client.get("/onboarding/").content.decode()
    assert "Complete your details" in body and "Upload your right-to-work document" in body
    assert body.index("Complete your details") < body.index("Read and sign the practice policies")
    assert "/onboarding/details/" in body and "/documents/policies/" in body


def test_details_form_writes_through_the_service_and_closes_the_item(hr_admin, employee_user, employee_client):
    emp = _starter(hr_admin, employee_user)
    r = employee_client.post("/onboarding/details/", {
        "preferred_name": "Sam", "personal_email": "sam@home.example", "phone": "07700 900000",
        "address_line1": "1 High St", "town": "Town", "postcode": "AB1 2CD", "ni_number": "QQ123456C",
        "bank_account_name": "S Patel", "bank_sort_code": "12-34-56", "bank_account_number": "12345678",
        "contacts-TOTAL_FORMS": "1", "contacts-INITIAL_FORMS": "0", "contacts-MIN_NUM_FORMS": "0", "contacts-MAX_NUM_FORMS": "3",
        "contacts-0-name": "Jo Patel", "contacts-0-relationship": "Partner", "contacts-0-phone": "07700 900001",
    })
    assert r.status_code == 302
    e = emp.employee; e.refresh_from_db()
    assert e.bank_sort_code == "12-34-56" and EmergencyContact.objects.filter(employee=e).count() == 1
    assert AuditEntry.objects.filter(object_id=e.pk, field="bank_sort_code").exists()
    item = ChecklistItem.objects.get(checklist__employment=emp, link="details")
    assert item.state == "open"           # HR verifies; see next test
    assert employee_client.get("/onboarding/details/").status_code == 200   # can return to it


def test_hr_marks_details_verified_which_closes_the_item(hr_admin, employee_user, admin_client):
    emp = _starter(hr_admin, employee_user)
    item = ChecklistItem.objects.get(checklist__employment=emp, link="details")
    r = admin_client.post(f"/onboarding/item/{item.pk}/done/", {"note": "verified against passport"})
    assert r.status_code == 302
    item.refresh_from_db(); assert item.state == "done"


def test_manager_to_do_card_and_done(hr_admin, employee_user, client):
    mgr_user = type(employee_user).objects.create_user(email="mo@example.com", password="pw")
    mgr = make_employee(first="Mo", last="Khan", user=mgr_user)
    employments.start(hr_admin, mgr, timezone.localdate() - timedelta(days=400))
    emp = _starter(hr_admin, employee_user, manager=mgr)
    client.force_login(mgr_user)
    body = client.get("/people/team/").content.decode()
    assert "Induction completed" in body and emp.employee.name in body
    item = ChecklistItem.objects.get(checklist__employment=emp, title="Induction completed")
    assert client.post(f"/onboarding/item/{item.pk}/done/", {}).status_code == 302
    item.refresh_from_db(); assert item.state == "done"
    hr_item = ChecklistItem.objects.filter(checklist__employment=emp, owner="hr").first()
    assert client.post(f"/onboarding/item/{hr_item.pk}/done/", {}).status_code == 403


def test_hr_list_and_detail(hr_admin, employee_user, admin_client, employee_client):
    emp = _starter(hr_admin, employee_user, manager=None)
    body = admin_client.get("/onboarding/all/").content.decode()
    assert emp.employee.name in body and "no line manager" in body
    cl = Checklist.objects.get(employment=emp)
    body = admin_client.get(f"/onboarding/all/{cl.pk}/").content.decode()
    assert "Contract issued" in body and "Not needed" in body
    assert employee_client.get("/onboarding/all/").status_code == 403
    r = admin_client.post(f"/onboarding/all/{cl.pk}/add/", {"title": "Uniform ordered", "instruction": "", "owner": "hr",
                                                             "due_on": timezone.localdate().isoformat()})
    assert r.status_code == 302 and cl.items.filter(title="Uniform ordered").exists()


# ---- beyond the brief: every role on every page ------------------------------------------


@pytest.fixture
def cast(hr_admin, employee_user):
    """A pre-start starter (employee_user) with a line manager, a colleague
    employed already with no link to them, and a client for each, plus HR
    and an anonymous visitor."""
    mgr_user = User.objects.create_user(email="mo@example.com", password="pw")
    mgr = make_employee(first="Mo", last="Khan", user=mgr_user)
    employments.start(hr_admin, mgr, timezone.localdate() - timedelta(days=400))
    other_user = User.objects.create_user(email="ola@example.com", password="pw")
    other = make_employee(first="Ola", last="Ade", user=other_user)
    employments.start(hr_admin, other, timezone.localdate() - timedelta(days=400))
    emp = _starter(hr_admin, employee_user, manager=mgr)
    cl = Checklist.objects.get(employment=emp)

    def client_for(user):
        c = Client()
        if user is not None:
            c.force_login(user)
        return c

    return {"emp": emp, "checklist": cl, "manager": mgr,
            "clients": {"own": client_for(employee_user), "other": client_for(other_user),
                        "manager": client_for(mgr_user), "hr": client_for(hr_admin), "anonymous": client_for(None)}}


def _is_login(r):
    return r.status_code == 302 and r["Location"].startswith("/accounts/login/")


@pytest.mark.parametrize("who,expected", [("own", 200), ("other", 200), ("manager", 200), ("hr", 200),
                                          ("anonymous", "login")])
def test_getting_started_shows_each_person_only_their_own_items(cast, who, expected):
    r = cast["clients"][who].get("/onboarding/")
    if expected == "login":
        assert _is_login(r)
        return
    assert r.status_code == 200
    body = r.content.decode()
    assert ("Upload your right-to-work document" in body) is (who == "own")
    assert "Induction completed" not in body and "Contract issued" not in body


@pytest.mark.parametrize("who,expected", [("own", 200), ("other", 200), ("manager", 200), ("hr", 200),
                                          ("anonymous", "login")])
def test_the_details_page_is_always_your_own(cast, who, expected):
    employees.update(None, cast["emp"].employee, bank_account_number="12345678")
    r = cast["clients"][who].get("/onboarding/details/")
    if expected == "login":
        assert _is_login(r)
        return
    assert r.status_code == 200
    assert ("12345678" in r.content.decode()) is (who == "own")


def test_hr_with_no_employee_record_is_told_so_on_the_details_page(admin_client):
    body = admin_client.get("/onboarding/details/").content.decode()
    assert "no employee record" in body
    assert admin_client.post("/onboarding/details/", {"preferred_name": "X"}).status_code == 200


@pytest.mark.parametrize("who,expected", [("own", 403), ("other", 403), ("manager", 403), ("hr", 302),
                                          ("anonymous", "login")])
def test_who_may_close_an_hr_item(cast, who, expected):
    item = cast["checklist"].items.get(title="References received")
    r = cast["clients"][who].post(f"/onboarding/item/{item.pk}/done/", {})
    item.refresh_from_db()
    if expected == "login":
        assert _is_login(r) and item.state == "open"
    else:
        assert r.status_code == expected
        assert item.state == ("done" if expected == 302 else "open")


@pytest.mark.parametrize("who,expected", [("own", 403), ("other", 403), ("manager", 302), ("hr", 302),
                                          ("anonymous", "login")])
def test_who_may_close_a_manager_item(cast, who, expected):
    item = cast["checklist"].items.get(title="Buddy named")
    r = cast["clients"][who].post(f"/onboarding/item/{item.pk}/done/", {})
    item.refresh_from_db()
    if expected == "login":
        assert _is_login(r) and item.state == "open"
    else:
        assert r.status_code == expected
        assert item.state == ("done" if expected == 302 else "open")


@pytest.mark.parametrize("who,expected", [("own", 302), ("other", 403), ("manager", 403), ("hr", 302),
                                          ("anonymous", "login")])
def test_who_may_close_a_persons_own_unlinked_item(cast, hr_admin, who, expected):
    item = checklists.add_item(hr_admin, cast["checklist"], "Bring your smartcard", "", "person",
                               timezone.localdate())
    r = cast["clients"][who].post(f"/onboarding/item/{item.pk}/done/", {})
    item.refresh_from_db()
    if expected == "login":
        assert _is_login(r) and item.state == "open"
    else:
        assert r.status_code == expected
        assert item.state == ("done" if expected == 302 else "open")


def test_the_person_cannot_close_their_own_details_item_only_hr_can(cast):
    """The details item is HR's to close after checking; any linked item
    closes itself or by HR, never by its owner's Done."""
    for link in ("details", "upload:identity"):
        item = cast["checklist"].items.get(link=link)
        assert cast["clients"]["own"].post(f"/onboarding/item/{item.pk}/done/", {}).status_code == 403
        item.refresh_from_db()
        assert item.state == "open"


def test_getting_started_has_no_done_button_for_linked_items(cast):
    body = cast["clients"]["own"].get("/onboarding/").content.decode()
    for link in ("details", "upload:identity"):
        item = cast["checklist"].items.get(link=link)
        assert f"/onboarding/item/{item.pk}/done/" not in body


def test_closing_an_item_twice_says_so(cast):
    item = cast["checklist"].items.get(title="References received")
    hr = cast["clients"]["hr"]
    hr.post(f"/onboarding/item/{item.pk}/done/", {})
    r = hr.post(f"/onboarding/item/{item.pk}/done/", {}, follow=True)
    assert "Already closed." in r.content.decode()


@pytest.mark.parametrize("url", ["/onboarding/item/{item}/done/", "/onboarding/item/{item}/not-needed/",
                                 "/onboarding/item/{item}/remove/", "/onboarding/item/{item}/upload/",
                                 "/onboarding/all/{cl}/add/"])
def test_the_write_views_refuse_a_get(cast, url):
    item = cast["checklist"].items.get(title="References received")
    r = cast["clients"]["hr"].get(url.format(item=item.pk, cl=cast["checklist"].pk))
    assert r.status_code == 405
    item.refresh_from_db()
    assert item.state == "open"


@pytest.mark.parametrize("who,expected", [("own", 403), ("other", 403), ("manager", 403), ("hr", 302),
                                          ("anonymous", "login")])
def test_only_hr_marks_an_item_not_needed(cast, who, expected):
    item = cast["checklist"].items.get(title="References received")
    r = cast["clients"][who].post(f"/onboarding/item/{item.pk}/not-needed/", {"note": "returner"})
    item.refresh_from_db()
    if expected == "login":
        assert _is_login(r)
    else:
        assert r.status_code == expected
    assert item.state == ("not_needed" if expected == 302 else "open")


def test_not_needed_without_a_reason_is_refused_with_a_message(cast):
    item = cast["checklist"].items.get(title="References received")
    r = cast["clients"]["hr"].post(f"/onboarding/item/{item.pk}/not-needed/", {"note": " "}, follow=True)
    assert "Say why it is not needed." in r.content.decode()
    item.refresh_from_db()
    assert item.state == "open"


@pytest.mark.parametrize("who,expected", [("own", 403), ("other", 403), ("manager", 403), ("hr", 302),
                                          ("anonymous", "login")])
def test_only_hr_adds_and_removes_items(cast, who, expected):
    cl = cast["checklist"]
    client = cast["clients"][who]
    r = client.post(f"/onboarding/all/{cl.pk}/add/", {"title": "Uniform ordered", "owner": "hr",
                                                      "due_on": timezone.localdate().isoformat()})
    assert _is_login(r) if expected == "login" else r.status_code == expected
    assert cl.items.filter(title="Uniform ordered").exists() is (expected == 302)
    item = cl.items.get(title="References received")
    r = client.post(f"/onboarding/item/{item.pk}/remove/", {})
    assert _is_login(r) if expected == "login" else r.status_code == expected
    assert cl.items.filter(pk=item.pk).exists() is (expected != 302)


def test_adding_an_item_with_an_unknown_link_or_owner_is_refused_with_a_message(cast):
    cl = cast["checklist"]
    r = cast["clients"]["hr"].post(f"/onboarding/all/{cl.pk}/add/", {
        "title": "Odd", "owner": "hr", "due_on": timezone.localdate().isoformat(), "link": "upload:nonsense"},
        follow=True)
    assert r.status_code == 200 and not cl.items.filter(title="Odd").exists()
    assert "upload:" in r.content.decode()
    r = cast["clients"]["hr"].post(f"/onboarding/all/{cl.pk}/add/", {
        "title": "Odd", "owner": "boss", "due_on": timezone.localdate().isoformat()}, follow=True)
    assert not cl.items.filter(title="Odd").exists()


@pytest.mark.parametrize("who,expected", [("own", 403), ("other", 403), ("manager", 403), ("hr", 200),
                                          ("anonymous", "login")])
def test_the_hr_pages_are_hr_only(cast, who, expected):
    for url in ("/onboarding/all/", f"/onboarding/all/{cast['checklist'].pk}/"):
        r = cast["clients"][who].get(url)
        assert _is_login(r) if expected == "login" else r.status_code == expected


def test_the_hr_list_shows_progress_and_leaves_out_completed_checklists(cast, hr_admin):
    body = cast["clients"]["hr"].get("/onboarding/all/").content.decode()
    assert cast["emp"].employee.name in body
    for item in cast["checklist"].items.filter(state="open"):
        checklists.not_needed(hr_admin, item, "test")
    body = cast["clients"]["hr"].get("/onboarding/all/").content.decode()
    assert cast["emp"].employee.name not in body


def test_the_hr_detail_shows_every_owner_and_the_people(cast):
    body = cast["clients"]["hr"].get(f"/onboarding/all/{cast['checklist'].pk}/").content.decode()
    for title in ("Complete your details", "References received", "Induction completed"):
        assert title in body
    assert cast["manager"].name in body


@pytest.mark.parametrize("who,expected", [("own", 302), ("other", 403), ("manager", 403), ("hr", 302),
                                          ("anonymous", "login")])
def test_an_upload_from_getting_started_files_it_and_closes_the_item(cast, who, expected):
    item = cast["checklist"].items.get(link="upload:identity")
    r = cast["clients"][who].post(f"/onboarding/item/{item.pk}/upload/",
                                  {"file": SimpleUploadedFile("passport.pdf", PDF)})
    item.refresh_from_db()
    if expected == "login":
        assert _is_login(r)
    else:
        assert r.status_code == expected
    stored = File.objects.filter(employee=cast["emp"].employee, category="identity")
    assert stored.exists() is (expected == 302)
    assert item.state == ("done" if expected == 302 else "open")


def test_an_upload_that_is_not_a_document_is_refused_with_a_message(cast):
    item = cast["checklist"].items.get(link="upload:identity")
    r = cast["clients"]["own"].post(f"/onboarding/item/{item.pk}/upload/",
                                    {"file": SimpleUploadedFile("passport.pdf", b"not a pdf")}, follow=True)
    assert r.status_code == 200 and not File.objects.filter(employee=cast["emp"].employee).exists()
    item.refresh_from_db()
    assert item.state == "open"
    r = cast["clients"]["own"].post(f"/onboarding/item/{item.pk}/upload/", {}, follow=True)
    assert "Choose a file" in r.content.decode()


def test_an_item_without_an_upload_link_takes_no_upload(cast):
    item = cast["checklist"].items.get(link="details")
    r = cast["clients"]["own"].post(f"/onboarding/item/{item.pk}/upload/",
                                    {"file": SimpleUploadedFile("passport.pdf", PDF)})
    assert r.status_code == 404
    assert not File.objects.exists()


# ---- the pre-start gate ---------------------------------------------------------------


def test_the_gate_lets_through_documents_accounts_and_static(cast):
    own = cast["clients"]["own"]
    assert own.get("/documents/policies/").status_code == 200
    assert own.get("/accounts/account/").status_code == 200
    assert own.get("/onboarding/details/").status_code == 200
    for path in ("/people/team/", "/checks/1/upload/", "/absence/request/", "/admin/"):
        r = own.get(path)
        assert r.status_code == 302 and r["Location"] == "/onboarding/", path


def test_a_pre_start_starter_sees_no_navigation(cast):
    body = cast["clients"]["own"].get("/onboarding/").content.decode()
    for href in ("/people/me/", "/absence/mine/", "/absence/calendar/", "/absence/balances/"):
        assert f'href="{href}"' not in body, href
    assert "Log out" in body
    body = cast["clients"]["other"].get("/onboarding/").content.decode()
    assert 'href="/people/me/"' in body


def test_who_is_pre_start(cast, hr_admin, employee_user):
    today = timezone.localdate()
    assert access.is_pre_start(employee_user, today)
    assert not access.is_pre_start(employee_user, cast["emp"].start_date)
    assert not access.is_pre_start(hr_admin, today)                    # no employee record
    assert not access.is_pre_start(cast["manager"].user, today)        # employed now
    from django.contrib.auth.models import AnonymousUser
    assert not access.is_pre_start(AnonymousUser(), today)


def test_a_returner_between_spells_is_pre_start(hr_admin, employee_user, employee_client):
    e = make_employee(user=employee_user)
    today = timezone.localdate()
    employments.start(hr_admin, e, today - timedelta(days=800), end_date=today - timedelta(days=400),
                      leaving_reason="resigned")
    employments.start(hr_admin, e, today + timedelta(days=5))
    assert employee_client.get("/people/me/").status_code == 302


def test_a_leaver_with_nothing_ahead_is_not_gated(hr_admin, employee_user, employee_client):
    e = make_employee(user=employee_user)
    today = timezone.localdate()
    employments.start(hr_admin, e, today - timedelta(days=800), end_date=today - timedelta(days=400),
                      leaving_reason="resigned")
    assert employee_client.get("/people/me/").status_code == 200


# ---- the cards on My record and My team ----------------------------------------------------


def test_my_record_shows_your_checklist_once_started(hr_admin, employee_user, employee_client):
    _starter(hr_admin, employee_user, days_ahead=0)
    body = employee_client.get("/people/me/").content.decode()
    assert "Your checklist" in body and "Upload your right-to-work document" in body
    assert "References received" not in body


def test_my_record_has_no_checklist_card_without_one(employee_user, employee_client):
    e = make_employee(user=employee_user)
    employments.start(None, e, timezone.localdate() - timedelta(days=400))
    assert "Your checklist" not in employee_client.get("/people/me/").content.decode()


def test_the_to_do_card_lists_only_my_items(cast, hr_admin):
    other_mgr = make_employee(first="Pat", last="Lee")
    e = make_employee(first="Ana", last="Bell")
    start = timezone.localdate() + timedelta(days=3)
    emp = employments.start(hr_admin, e, start)
    positions.add(hr_admin, emp, titles.get_or_create("Receptionist"), Team.objects.first(), other_mgr, start)
    body = cast["clients"]["manager"].get("/people/team/").content.decode()
    assert cast["emp"].employee.name in body and "Ana Bell" not in body


def test_a_manager_with_items_but_no_reports_yet_sees_my_team_in_the_nav(cast):
    body = cast["clients"]["manager"].get("/people/me/").content.decode()
    assert 'href="/people/team/"' in body
    body = cast["clients"]["other"].get("/people/me/").content.decode()
    assert 'href="/people/team/"' not in body
    assert cast["clients"]["other"].get("/people/team/").status_code == 403


def test_the_admin_sidebar_links_starters_and_leavers(admin_client):
    body = admin_client.get("/admin/").content.decode()
    assert "Starters and leavers" in body and 'href="/onboarding/all/"' in body


# ---- emergency contacts --------------------------------------------------------------


def test_emergency_contacts_are_replaced_and_audited(hr_admin):
    e = make_employee()
    employees.set_emergency_contacts(hr_admin, e, [{"name": "Jo Patel", "relationship": "Partner",
                                                    "phone": "07700 900001"}])
    employees.set_emergency_contacts(hr_admin, e, [{"name": "Al Patel", "relationship": "Parent",
                                                    "phone": "07700 900002"},
                                                   {"name": "Jo Patel", "relationship": "Partner",
                                                    "phone": "07700 900001"}])
    rows = list(EmergencyContact.objects.filter(employee=e).values_list("name", "priority"))
    assert rows == [("Al Patel", 1), ("Jo Patel", 2)]
    entries = AuditEntry.objects.filter(object_id=e.pk, field="emergency_contacts").order_by("pk")
    assert entries.count() == 2
    assert "Jo Patel" in entries.last().before and "Al Patel" in entries.last().after


def test_unchanged_emergency_contacts_write_no_audit(hr_admin):
    e = make_employee()
    rows = [{"name": "Jo Patel", "relationship": "Partner", "phone": "07700 900001"}]
    employees.set_emergency_contacts(hr_admin, e, rows)
    employees.set_emergency_contacts(hr_admin, e, rows)
    assert AuditEntry.objects.filter(object_id=e.pk, field="emergency_contacts").count() == 1


def test_an_emergency_contact_needs_a_name_and_phone(hr_admin):
    from django.core.exceptions import ValidationError
    e = make_employee()
    with pytest.raises(ValidationError):
        employees.set_emergency_contacts(hr_admin, e, [{"name": "Jo", "relationship": "", "phone": ""}])
    assert not EmergencyContact.objects.filter(employee=e).exists()


def test_the_details_form_keeps_contacts_and_refuses_a_half_row(hr_admin, employee_user, employee_client):
    emp = _starter(hr_admin, employee_user)
    employees.set_emergency_contacts(hr_admin, emp.employee, [{"name": "Jo Patel", "relationship": "Partner",
                                                               "phone": "07700 900001"}])
    body = employee_client.get("/onboarding/details/").content.decode()
    assert "Jo Patel" in body
    r = employee_client.post("/onboarding/details/", {
        "contacts-TOTAL_FORMS": "1", "contacts-INITIAL_FORMS": "0", "contacts-MIN_NUM_FORMS": "0",
        "contacts-MAX_NUM_FORMS": "3", "contacts-0-name": "Al Patel"})
    assert r.status_code == 200
    assert list(EmergencyContact.objects.filter(employee=emp.employee).values_list("name", flat=True)) == ["Jo Patel"]
    r = employee_client.post("/onboarding/details/", {
        "bank_sort_code": "123456",
        "contacts-TOTAL_FORMS": "0", "contacts-INITIAL_FORMS": "0", "contacts-MIN_NUM_FORMS": "0",
        "contacts-MAX_NUM_FORMS": "3"})
    assert r.status_code == 200
    emp.employee.refresh_from_db()
    assert emp.employee.bank_sort_code == ""
