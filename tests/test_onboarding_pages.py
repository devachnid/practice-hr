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


DETAILS_POST = {"preferred_name": "Sam", "bank_sort_code": "12-34-56", "bank_account_number": "12345678",
                "contacts-TOTAL_FORMS": "0", "contacts-INITIAL_FORMS": "0", "contacts-MIN_NUM_FORMS": "0",
                "contacts-MAX_NUM_FORMS": "3"}


@pytest.mark.parametrize("who,expected", [("own", 200), ("other", 404), ("manager", 404), ("hr", 404),
                                          ("anonymous", "login")])
def test_the_details_page_is_only_for_a_person_with_an_open_details_item(cast, who, expected):
    """HR here has no employee record; the other employee and the manager
    have no details item of their own."""
    client = cast["clients"][who]
    r = client.get("/onboarding/details/")
    if expected == "login":
        assert _is_login(r) and _is_login(client.post("/onboarding/details/", DETAILS_POST))
        return
    assert r.status_code == expected
    r = client.post("/onboarding/details/", DETAILS_POST)
    assert r.status_code == (302 if who == "own" else 404)
    e = cast["emp"].employee
    e.refresh_from_db()
    assert (e.bank_account_number == "12345678") is (who == "own")


def test_the_details_page_closes_once_hr_has_checked_them(cast, hr_admin):
    item = cast["checklist"].items.get(link="details")
    checklists.complete(hr_admin, item, "checked")
    own = cast["clients"]["own"]
    assert own.get("/onboarding/details/").status_code == 404
    assert own.post("/onboarding/details/", DETAILS_POST).status_code == 404
    e = cast["emp"].employee
    e.refresh_from_db()
    assert e.bank_account_number == ""
    assert "/onboarding/details/" not in own.get("/onboarding/").content.decode()


def test_a_bad_ni_number_is_refused_on_the_form_and_by_the_service(cast, hr_admin):
    from django.core.exceptions import ValidationError
    r = cast["clients"]["own"].post("/onboarding/details/", {**DETAILS_POST, "ni_number": "QQ12345C"})
    assert r.status_code == 200 and "two letters, six digits" in r.content.decode()
    e = cast["emp"].employee
    e.refresh_from_db()
    assert e.ni_number == "" and e.bank_account_number == ""
    for bad in ("qq123456c", "QQ123456E", "Q1123456C"):
        with pytest.raises(ValidationError):
            employees.update(hr_admin, e, ni_number=bad)
    employees.update(hr_admin, e, ni_number="QQ123456C")
    employees.update(hr_admin, e, ni_number="")


# ---- an employee-own column apart from pre-start: a starter whose first day has come ----------


@pytest.fixture
def started(hr_admin, cast):
    """A second starter, whose start date is today: past the gate, their
    checklist still open."""
    user = User.objects.create_user(email="kit@example.com", password="pw")
    e = make_employee(first="Kit", last="Moss", user=user)
    today = timezone.localdate()
    emp = employments.start(hr_admin, e, today)
    positions.add(hr_admin, emp, titles.get_or_create("Receptionist"), Team.objects.first(), cast["manager"], today)
    c = Client()
    c.force_login(user)
    assert not access.is_pre_start(user, today)
    return {"emp": emp, "checklist": Checklist.objects.get(employment=emp), "client": c}


def test_a_started_starter_closes_their_own_unlinked_item_but_no_one_elses(started, cast, hr_admin):
    mine = checklists.add_item(hr_admin, started["checklist"], "Bring your smartcard", "", "person",
                               timezone.localdate())
    theirs = checklists.add_item(hr_admin, cast["checklist"], "Bring your badge", "", "person",
                                 timezone.localdate())
    c = started["client"]
    assert c.post(f"/onboarding/item/{mine.pk}/done/", {"next": "me"})["Location"] == "/people/me/"
    assert c.post(f"/onboarding/item/{theirs.pk}/done/", {}).status_code == 403
    details = started["checklist"].items.get(link="details")
    assert c.post(f"/onboarding/item/{details.pk}/done/", {}).status_code == 403
    mine.refresh_from_db(); theirs.refresh_from_db(); details.refresh_from_db()
    assert (mine.state, theirs.state, details.state) == ("done", "open", "open")


def test_a_started_starter_uploads_to_their_own_item_but_no_one_elses(started, cast):
    c = started["client"]
    mine = started["checklist"].items.get(link="upload:identity")
    theirs = cast["checklist"].items.get(link="upload:identity")
    assert c.post(f"/onboarding/item/{mine.pk}/upload/", {"file": SimpleUploadedFile("p.pdf", PDF)}).status_code == 302
    assert c.post(f"/onboarding/item/{theirs.pk}/upload/",
                  {"file": SimpleUploadedFile("p.pdf", PDF)}).status_code == 403
    mine.refresh_from_db(); theirs.refresh_from_db()
    assert (mine.state, theirs.state) == ("done", "open")
    assert not File.objects.filter(employee=cast["emp"].employee).exists()


def test_a_started_starter_fills_in_their_details(started, cast):
    c = started["client"]
    assert c.get("/onboarding/details/").status_code == 200
    assert c.post("/onboarding/details/", DETAILS_POST).status_code == 302
    e = started["emp"].employee
    e.refresh_from_db()
    assert e.bank_account_number == "12345678"
    other = cast["emp"].employee
    other.refresh_from_db()
    assert other.bank_account_number == ""


def test_my_record_links_a_started_starter_to_their_details(started):
    body = started["client"].get("/people/me/").content.decode()
    assert "Your checklist" in body and "/onboarding/details/" in body


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


def test_an_upload_to_a_closed_item_is_refused_but_hr_may(cast, hr_admin):
    item = cast["checklist"].items.get(link="upload:identity")
    checklists.not_needed(hr_admin, item, "seen the original")
    r = cast["clients"]["own"].post(f"/onboarding/item/{item.pk}/upload/",
                                    {"file": SimpleUploadedFile("passport.pdf", PDF)}, follow=True)
    assert "already closed" in r.content.decode()
    assert not File.objects.exists()
    r = cast["clients"]["hr"].post(f"/onboarding/item/{item.pk}/upload/",
                                   {"file": SimpleUploadedFile("passport.pdf", PDF)})
    assert r.status_code == 302 and File.objects.filter(employee=cast["emp"].employee).count() == 1


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
    assert own.get("/checks/1/upload/").status_code == 405     # let through (final review I1); POST only
    for path in ("/people/team/", "/absence/request/", "/admin/"):
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


# ---- final review I1: evidence asked of a starter before their first day -----------------


def _asked_rtw(hr_admin, employee):
    from checks.models import CheckType
    from checks.services import checks
    return checks.ask(hr_admin, employee, CheckType.objects.get(code="right_to_work"))


def test_a_pre_start_starter_sees_and_answers_a_request_for_evidence_on_getting_started(cast, hr_admin):
    asked = _asked_rtw(hr_admin, cast["emp"].employee)
    own = cast["clients"]["own"]
    body = own.get("/onboarding/").content.decode()
    assert f'action="/checks/{asked.pk}/upload/"' in body and "Upload your right to work evidence" in body
    r = own.post(f"/checks/{asked.pk}/upload/", {"file": SimpleUploadedFile("passport.pdf", PDF)})
    assert r.status_code == 302 and r["Location"] == "/onboarding/"
    asked.refresh_from_db()
    assert asked.evidence is not None and asked.evidence.employee == cast["emp"].employee
    body = own.get("/onboarding/").content.decode()
    assert "Sent. HR will record it." in body and f'action="/checks/{asked.pk}/upload/"' not in body


def test_an_anonymous_upload_to_a_check_goes_to_sign_in(cast, hr_admin):
    asked = _asked_rtw(hr_admin, cast["emp"].employee)
    r = cast["clients"]["anonymous"].post(f"/checks/{asked.pk}/upload/",
                                          {"file": SimpleUploadedFile("passport.pdf", PDF)})
    assert _is_login(r)
    asked.refresh_from_db()
    assert asked.evidence is None


def test_hr_is_told_where_the_person_sees_a_request(cast, admin_client):
    from checks.models import CheckType
    rtw = CheckType.objects.get(code="right_to_work")
    r = admin_client.post("/admin/checks/check/ask/", {"employee": cast["emp"].employee.pk, "check_type": rtw.pk},
                          follow=True)
    body = r.content.decode()
    assert "They see it on Getting started." in body and "They see it on My record" not in body
    r = admin_client.post("/admin/checks/check/ask/", {"employee": cast["manager"].pk, "check_type": rtw.pk},
                          follow=True)
    assert "They see it on My record." in r.content.decode()


# ---- final review I2: a details item, once sent, is HR's to check -------------------------


def _due_for_details(today):
    from compliance.models import ReminderSchedule
    from onboarding.services import due
    return [d for d in due.due_items(today, ReminderSchedule.get()) if d.label == "Complete your details"]


def test_sending_the_details_form_marks_the_item_sent_and_says_so(cast):
    own = cast["clients"]["own"]
    item = cast["checklist"].items.get(link="details")
    assert item.submitted_at is None
    assert own.post("/onboarding/details/", DETAILS_POST).status_code == 302
    item.refresh_from_db()
    assert item.submitted_at is not None and item.state == "open"
    assert AuditEntry.objects.filter(model="onboarding.checklistitem", object_id=item.pk,
                                     field="submitted_at").exists()
    body = own.get("/onboarding/").content.decode()
    assert "Sent – HR will check it" in body and "/onboarding/details/" in body


def test_a_details_item_is_chased_of_the_person_until_sent_then_of_hr(cast):
    today = timezone.localdate()
    item = cast["checklist"].items.get(link="details")
    ChecklistItem.objects.filter(pk=item.pk).update(due_on=today)
    (before,) = _due_for_details(today)
    assert before.recipient == "sam@example.com" and before.url.endswith("/onboarding/")
    assert cast["clients"]["own"].post("/onboarding/details/", DETAILS_POST).status_code == 302
    (after,) = _due_for_details(today)
    assert after.recipient == "hr@example.com" and after.url.endswith(f"/onboarding/all/{cast['checklist'].pk}/")


def test_an_hr_admin_with_a_future_employment_is_never_pre_start(hr_admin, client):
    """Final review M8: HR is never gated, whatever their own record says."""
    e = make_employee(first="Hana", last="Reed", user=hr_admin)
    employments.start(hr_admin, e, timezone.localdate() + timedelta(days=10))
    assert access.employee_is_pre_start(e, timezone.localdate())
    assert not access.is_pre_start(hr_admin, timezone.localdate())
    client.force_login(hr_admin)
    assert client.get("/people/me/").status_code == 200


def test_a_starter_with_no_template_is_on_starters_and_leavers_with_its_gap(hr_admin, admin_client):
    """Final review I4: an empty checklist is never complete by itself."""
    from onboarding.models import ChecklistTemplate
    ChecklistTemplate.objects.filter(kind="starter").update(active=False)
    other = User.objects.create_user(email="nia@example.com", password="pw")
    emp = _starter(hr_admin, other)
    body = admin_client.get("/onboarding/all/").content.decode()
    assert emp.employee.name in body and "no starter checklist template" in body
