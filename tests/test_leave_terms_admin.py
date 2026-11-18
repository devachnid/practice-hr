"""Leave terms in the admin: the usual terms on a contract type, a
contract's own on its own page, and the line on the employment page."""
from datetime import timedelta
from decimal import Decimal as D

import pytest

from people.models import AuditEntry, Contract, ContractType, Employment
from people.services import leave_terms
from tests.factories import make_contract, make_contract_type, make_employment

pytestmark = pytest.mark.django_db
STEPS = "leave_steps"


def _steps(*rows, initial=0, prefix=STEPS):
    """The inline's POST fields. Each row is (id, after_years, total, delete)."""
    data = {f"{prefix}-TOTAL_FORMS": len(rows), f"{prefix}-INITIAL_FORMS": initial}
    for i, (pk, years, total, delete) in enumerate(rows):
        data.update({f"{prefix}-{i}-id": pk, f"{prefix}-{i}-after_years": years, f"{prefix}-{i}-total": total})
        if delete:
            data[f"{prefix}-{i}-DELETE"] = "on"
    return data


def _type_post(ct, base, *rows, initial=0):
    return {"name": ct.name, "unit": ct.unit, "full_time_weekly": str(ct.full_time_weekly),
            "display_order": ct.display_order, "leave_base": base, "_save": "Save", **_steps(*rows, initial=initial)}


def test_the_type_page_saves_usual_terms_through_the_service(admin_client, hr_admin):
    ct = make_contract_type()
    url = f"/admin/people/contracttype/{ct.pk}/change/"
    assert "Usual annual leave a year" in admin_client.get(url).content.decode()
    r = admin_client.post(url, _type_post(ct, "22", ("", 5, "25", False), ("", 1, "23", False)))
    assert r.status_code == 302, r.content.decode()[:3000]
    ct.refresh_from_db()
    assert ct.leave_base == D("22") and [(s.after_years, s.total) for s in ct.leave_steps.all()] == [(1, D("23")), (5, D("25"))]
    audited = AuditEntry.objects.filter(model="people.contracttype", object_id=ct.pk)
    assert {a.field for a in audited} == {"leave_base", "leave_steps"} and {a.actor for a in audited} == {hr_admin}


def test_a_step_can_be_removed_and_the_terms_cleared(admin_client, hr_admin):
    ct = make_contract_type()
    leave_terms.set_type_terms(hr_admin, ct, D("22"), [(1, D("23")), (5, D("25"))])
    one, five = ct.leave_steps.all()
    url = f"/admin/people/contracttype/{ct.pk}/change/"
    r = admin_client.post(url, _type_post(ct, "22", (one.pk, 1, "23.00", False), (five.pk, 5, "25.00", True), initial=2))
    assert r.status_code == 302, r.content.decode()[:3000]
    assert [(s.after_years, s.total) for s in ct.leave_steps.all()] == [(1, D("23"))]
    one = ct.leave_steps.get()
    r = admin_client.post(url, _type_post(ct, "", (one.pk, 1, "23.00", True), initial=1))
    assert r.status_code == 302
    ct.refresh_from_db()
    assert ct.leave_base is None and not ct.leave_steps.exists()


@pytest.mark.parametrize("base,rows,says", [
    ("22", [("", 1, "22", False)], "more than the figure before it"),
    ("", [("", 1, "23", False)], "need the figure they step up from"),
    ("0", [], "More than 0"),
])
def test_bad_usual_terms_re_render_and_save_nothing(admin_client, base, rows, says):
    ct = make_contract_type()
    r = admin_client.post(f"/admin/people/contracttype/{ct.pk}/change/", _type_post(ct, base, *rows))
    assert r.status_code == 200 and says in r.content.decode()
    ct.refresh_from_db()
    assert ct.leave_base is None and not ct.leave_steps.exists() and not AuditEntry.objects.exists()


def test_the_other_fields_of_a_type_still_save(admin_client):
    ct = make_contract_type("Cleaning")
    data = _type_post(ct, "")
    data["display_order"] = 45
    assert admin_client.post(f"/admin/people/contracttype/{ct.pk}/change/", data).status_code == 302
    ct.refresh_from_db()
    assert ct.display_order == 45 and ct.leave_base is None


def test_the_employment_page_shows_each_contracts_terms_with_a_link(admin_client, hr_admin):
    emp = make_employment()
    ct = make_contract_type()
    leave_terms.set_type_terms(hr_admin, ct, D("22"), [(1, D("23"))])
    c = make_contract(emp, ct)
    body = admin_client.get(f"/admin/people/employment/{emp.pk}/change/").content.decode()
    assert "Usual for Reception: 22 days; 23 after 1 year" in body
    assert f'href="/admin/people/contract/{c.pk}/change/"' in body
    assert ">Change leave terms</a>" in body


def _contract_post(mode, base, *rows, initial=0):
    return {"leave_terms": mode, "leave_base": base, "_save": "Save", **_steps(*rows, initial=initial)}


def test_the_contract_page_sets_own_terms_and_returns_to_the_employment(admin_client, hr_admin):
    c = make_contract(make_employment())
    url = f"/admin/people/contract/{c.pk}/change/"
    body = admin_client.get(url).content.decode()
    assert "Own terms" in body and 'name="weekly_amount"' not in body          # the rest of the contract is read-only
    r = admin_client.post(url, _contract_post("own", "27", ("", 10, "30", False)))
    assert r.status_code == 302 and r["Location"] == f"/admin/people/employment/{c.employment_id}/change/"
    c.refresh_from_db()
    assert (c.leave_terms, c.leave_base) == ("own", D("27")) and [(s.after_years, s.total) for s in c.leave_steps.all()] == [(10, D("30"))]
    assert {a.actor for a in AuditEntry.objects.filter(model="people.contract", object_id=c.pk)} == {hr_admin}


def test_choosing_another_option_drops_the_contracts_own_figure(admin_client, hr_admin):
    c = make_contract(make_employment())
    leave_terms.set_contract_terms(hr_admin, c, "own", D("27"), [(10, D("30"))])
    step = c.leave_steps.get()
    r = admin_client.post(f"/admin/people/contract/{c.pk}/change/",
                          _contract_post("none", "27.00", (step.pk, 10, "30.00", False), initial=1))
    assert r.status_code == 302, r.content.decode()[:3000]
    c.refresh_from_db()
    assert (c.leave_terms, c.leave_base, c.leave_steps.count()) == ("none", None, 0)


def test_own_terms_without_a_figure_re_render(admin_client):
    c = make_contract(make_employment())
    r = admin_client.post(f"/admin/people/contract/{c.pk}/change/", _contract_post("own", ""))
    assert r.status_code == 200 and "Own terms need a figure" in r.content.decode()
    c.refresh_from_db()
    assert c.leave_terms == "usual"


def test_a_contract_cannot_be_added_deleted_or_otherwise_edited_from_its_page(admin_client):
    c = make_contract(make_employment(), amount=D("30"))
    assert admin_client.get("/admin/people/contract/add/").status_code == 403
    assert admin_client.post(f"/admin/people/contract/{c.pk}/delete/", {"post": "yes"}).status_code == 403
    data = _contract_post("usual", "")
    data.update({"weekly_amount": "10", "from_date": "2020-01-01"})
    assert admin_client.post(f"/admin/people/contract/{c.pk}/change/", data).status_code == 302
    c.refresh_from_db()
    assert c.weekly_amount == D("30") and Contract.objects.count() == 1


def test_the_contract_page_is_not_on_the_admin_index_and_is_for_hr_admins(admin_client, employee_client):
    c = make_contract(make_employment())
    assert 'href="/admin/people/contract/"' not in admin_client.get("/admin/").content.decode()
    assert employee_client.get(f"/admin/people/contract/{c.pk}/change/").status_code in (302, 403)


def test_a_third_decimal_place_is_refused_not_saved(admin_client):
    ct = make_contract_type()
    r = admin_client.post(f"/admin/people/contracttype/{ct.pk}/change/", _type_post(ct, "22.005"))
    assert r.status_code == 200 and "decimal places" in r.content.decode()
    ct.refresh_from_db()
    assert ct.leave_base is None and not AuditEntry.objects.exists()


def test_a_contract_that_starts_before_its_employment_still_saves_its_terms(admin_client):
    emp = make_employment()
    c = make_contract(emp)
    Employment.objects.filter(pk=emp.pk).update(start_date=c.from_date + timedelta(days=30))
    r = admin_client.post(f"/admin/people/contract/{c.pk}/change/", _contract_post("own", "27"))
    assert r.status_code == 302, r.content.decode()[:3000]
    c.refresh_from_db()
    assert (c.leave_terms, c.leave_base) == ("own", D("27"))


def test_the_base_label_names_the_unit_and_one_request_does_not_change_the_next(admin_client):
    hours = make_contract_type("Reception")
    sessions = make_contract_type("Salaried GP", unit="sessions", full_time=D("8"))
    type_url = "/admin/people/contracttype/{}/change/"
    for ct, word in ((hours, "days"), (sessions, "weeks"), (hours, "days")):
        assert f"Usual annual leave a year ({word})" in admin_client.get(type_url.format(ct.pk)).content.decode()
    add = admin_client.get("/admin/people/contracttype/add/").content.decode()
    assert "Usual annual leave a year" in add and "Usual annual leave a year (" not in add
    ch, cs = make_contract(make_employment(), hours), make_contract(make_employment(), sessions, amount=D("8"))
    for c, word in ((ch, "days"), (cs, "weeks"), (ch, "days")):
        assert f"Annual leave a year ({word})" in admin_client.get(f"/admin/people/contract/{c.pk}/change/").content.decode()


def test_the_unit_cannot_change_under_a_usual_figure(admin_client, hr_admin):
    ct = make_contract_type()
    leave_terms.set_type_terms(hr_admin, ct, D("22"))
    data = {**_type_post(ct, "22"), "unit": "sessions"}
    r = admin_client.post(f"/admin/people/contracttype/{ct.pk}/change/", data)
    assert r.status_code == 200 and leave_terms.UNIT_CHANGE.replace("'", "&#x27;") in r.content.decode()
    ct.refresh_from_db()
    assert ct.unit == "hours"


def test_the_unit_cannot_change_under_a_contract_on_own_terms(admin_client, hr_admin):
    ct = make_contract_type()
    leave_terms.set_contract_terms(hr_admin, make_contract(make_employment(), ct), "own", D("27"))
    r = admin_client.post(f"/admin/people/contracttype/{ct.pk}/change/", {**_type_post(ct, ""), "unit": "sessions"})
    assert r.status_code == 200 and "before changing the unit" in r.content.decode()
    ct.refresh_from_db()
    assert ct.unit == "hours"


def test_the_unit_can_change_when_no_terms_depend_on_it(admin_client):
    ct = make_contract_type()
    make_contract(make_employment(), ct)
    r = admin_client.post(f"/admin/people/contracttype/{ct.pk}/change/", {**_type_post(ct, ""), "unit": "sessions"})
    assert r.status_code == 302, r.content.decode()[:3000]
    ct.refresh_from_db()
    assert ct.unit == "sessions"


def test_the_type_add_page_saves_a_usual_figure_and_a_step_audited_to_the_admin(admin_client, hr_admin):
    data = {"name": "Locum", "unit": "hours", "full_time_weekly": "37.5", "display_order": 100,
            "leave_base": "22", "_save": "Save", **_steps(("", 5, "25", False))}
    r = admin_client.post("/admin/people/contracttype/add/", data)
    assert r.status_code == 302, r.content.decode()[:3000]
    ct = ContractType.objects.get(name="Locum")
    assert ct.leave_base == D("22") and [(s.after_years, s.total) for s in ct.leave_steps.all()] == [(5, D("25"))]
    audited = AuditEntry.objects.filter(model="people.contracttype", object_id=ct.pk)
    assert {a.field for a in audited} == {"leave_base", "leave_steps"} and {a.actor for a in audited} == {hr_admin}
