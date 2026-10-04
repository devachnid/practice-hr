from datetime import date
from decimal import Decimal

from people.models import AuditEntry, EmergencyContact, PayRecord, WorkingPattern
from people.services import titles
from tests.factories import make_employee, make_employment, make_position, make_team


def test_changelists_render(admin_client):
    for url in ("/admin/people/employee/", "/admin/people/employment/", "/admin/people/team/",
                "/admin/people/contracttype/", "/admin/people/auditentry/",
                "/admin/people/positiontitle/"):
        assert admin_client.get(url).status_code == 200, url


def test_employment_change_page_shows_pay_to_admin_and_audits(admin_client, hr_admin):
    emp = make_employment()
    PayRecord.objects.create(employment=emp, from_date=date(2026, 4, 6), basis="annual", amount=25000)
    r = admin_client.get(f"/admin/people/employment/{emp.pk}/change/")
    assert r.status_code == 200 and "25000" in r.content.decode()
    assert AuditEntry.objects.filter(kind="viewed", field="pay", object_id=emp.pk).exists()


def test_employee_add_goes_through_service(admin_client):
    r = admin_client.post("/admin/people/employee/add/", {
        "first_name": "Ada", "last_name": "Lovelace", "work_email": "ada@example.org",
        "preferred_name": "", "personal_email": "", "phone": "", "address_line1": "",
        "address_line2": "", "town": "", "postcode": "", "ni_number": "",
        "emergency_contacts-TOTAL_FORMS": 0, "emergency_contacts-INITIAL_FORMS": 0,
        "employments-TOTAL_FORMS": 0, "employments-INITIAL_FORMS": 0,
    })
    assert r.status_code == 302
    assert AuditEntry.objects.filter(model="people.employee", field="created").exists()


def test_audit_log_is_read_only(admin_client):
    make_employee()
    assert admin_client.get("/admin/people/auditentry/add/").status_code == 403


def test_employee_edit_is_audited(admin_client):
    """CRITICAL 1: an edit through the employee change page must be
    diffed against the database, not against a form-mutated copy of the
    same object, or nothing is ever audited."""
    e = make_employee(first="Sam", last="Patel")
    r = admin_client.post(f"/admin/people/employee/{e.pk}/change/", {
        "first_name": "Samantha", "last_name": e.last_name, "work_email": e.work_email,
        "preferred_name": "", "personal_email": "", "phone": "", "address_line1": "",
        "address_line2": "", "town": "", "postcode": "", "ni_number": "",
        "emergency_contacts-TOTAL_FORMS": 0, "emergency_contacts-INITIAL_FORMS": 0,
        "employments-TOTAL_FORMS": 0, "employments-INITIAL_FORMS": 0,
        "_save": "Save",
    })
    assert r.status_code == 302
    entry = AuditEntry.objects.get(model="people.employee", object_id=e.pk, field="first_name")
    assert entry.before == "Sam" and entry.after == "Samantha"
    e.refresh_from_db()
    assert e.first_name == "Samantha"


def _employment_base(emp, **overrides):
    data = {
        "start_date": str(emp.start_date), "end_date": "", "leaving_reason": "",
        "continuous_service_date": str(emp.continuous_service_date),
        "positions-TOTAL_FORMS": 0, "positions-INITIAL_FORMS": 0,
        "contracts-TOTAL_FORMS": 0, "contracts-INITIAL_FORMS": 0,
        "patterns-TOTAL_FORMS": 0, "patterns-INITIAL_FORMS": 0,
        "pay_records-TOTAL_FORMS": 0, "pay_records-INITIAL_FORMS": 0,
        "_save": "Save",
    }
    data.update(overrides)
    return data


def test_existing_position_edit_is_restricted_to_to_date(admin_client, hr_admin):
    """IMPORTANT 2: an existing position row may only be ended (to_date);
    any other field change is refused with a message, and left alone."""
    emp = make_employment()
    team = make_team()
    pos = make_position(emp, title="Receptionist", team=team, start=emp.start_date)

    def position_row(**overrides):
        row = {
            "positions-0-id": pos.pk, "positions-0-employment": emp.pk,
            "positions-0-title": pos.title_id, "positions-0-team": team.pk,
            "positions-0-line_manager": "", "positions-0-primary": "on",
            "positions-0-from_date": str(pos.from_date), "positions-0-to_date": "",
        }
        row.update(overrides)
        return row

    # A title change is refused; the row is untouched.
    r = admin_client.post(f"/admin/people/employment/{emp.pk}/change/", _employment_base(
        emp, **{**position_row(**{"positions-0-title": titles.get_or_create("Manager").pk}),
                "positions-TOTAL_FORMS": 1, "positions-INITIAL_FORMS": 1}), follow=True)
    assert r.status_code == 200
    assert "only end" in r.content.decode()
    pos.refresh_from_db()
    assert pos.title.name == "Receptionist"

    # Ending it (to_date only) goes through.
    r = admin_client.post(f"/admin/people/employment/{emp.pk}/change/", _employment_base(
        emp, **{**position_row(**{"positions-0-to_date": "2026-12-31"}),
                "positions-TOTAL_FORMS": 1, "positions-INITIAL_FORMS": 1}))
    assert r.status_code == 302
    pos.refresh_from_db()
    assert pos.to_date == date(2026, 12, 31)
    assert AuditEntry.objects.filter(model="people.position", object_id=pos.pk, field="to_date").exists()


def test_employment_ended_through_admin_is_audited_with_correct_before(admin_client, hr_admin):
    """IMPORTANT 3(b): the admin's Employment change form must route an
    end through employments.end(), with the pre-change row (not the
    form-mutated one) supplying the before value."""
    emp = make_employment(start=date(2026, 1, 1))
    r = admin_client.post(f"/admin/people/employment/{emp.pk}/change/", _employment_base(
        emp, end_date="2026-06-30", leaving_reason="resigned"))
    assert r.status_code == 302
    entry = AuditEntry.objects.get(model="people.employment", object_id=emp.pk, field="end_date")
    assert entry.before == "None" and entry.after == "2026-06-30"
    emp.refresh_from_db()
    assert emp.end_date == date(2026, 6, 30)


def test_working_pattern_cannot_be_added_from_the_employment_page(admin_client, hr_admin):
    """IMPORTANT 4: the WorkingPatternInline is read-only; a pattern
    without its days is worse than no pattern at all."""
    emp = make_employment()
    r = admin_client.post(f"/admin/people/employment/{emp.pk}/change/", _employment_base(
        emp, **{"patterns-TOTAL_FORMS": 1, "patterns-INITIAL_FORMS": 0,
                "patterns-0-effective_from": str(emp.start_date)}))
    assert r.status_code == 302
    assert not WorkingPattern.objects.filter(employment=emp).exists()


def test_emergency_contact_add_is_audited(admin_client):
    """IMPORTANT 5: emergency contacts may be deleted (they are exempt
    from "rows end"), but every add, change and removal is audited."""
    e = make_employee()
    r = admin_client.post(f"/admin/people/employee/{e.pk}/change/", {
        "first_name": e.first_name, "last_name": e.last_name, "work_email": e.work_email,
        "preferred_name": "", "personal_email": "", "phone": "", "address_line1": "",
        "address_line2": "", "town": "", "postcode": "", "ni_number": "",
        "emergency_contacts-TOTAL_FORMS": 1, "emergency_contacts-INITIAL_FORMS": 0,
        "emergency_contacts-0-name": "Jo Bloggs", "emergency_contacts-0-relationship": "Partner",
        "emergency_contacts-0-phone": "0123456789", "emergency_contacts-0-priority": 1,
        "employments-TOTAL_FORMS": 0, "employments-INITIAL_FORMS": 0,
        "_save": "Save",
    })
    assert r.status_code == 302
    entry = AuditEntry.objects.get(model="people.employee", object_id=e.pk, field="emergency_contact")
    assert entry.before == "" and "Jo Bloggs" in entry.after


def test_emergency_contact_field_change_is_audited_per_field(admin_client):
    """OPEN (round 2): a change to phone or priority alone must still be
    audited, field by field — comparing whole-row str() misses it."""
    e = make_employee()
    ec = EmergencyContact.objects.create(employee=e, name="Jo Bloggs", relationship="Partner",
                                         phone="111", priority=1)
    r = admin_client.post(f"/admin/people/employee/{e.pk}/change/", {
        "first_name": e.first_name, "last_name": e.last_name, "work_email": e.work_email,
        "preferred_name": "", "personal_email": "", "phone": "", "address_line1": "",
        "address_line2": "", "town": "", "postcode": "", "ni_number": "",
        "emergency_contacts-TOTAL_FORMS": 1, "emergency_contacts-INITIAL_FORMS": 1,
        "emergency_contacts-0-id": ec.pk, "emergency_contacts-0-employee": e.pk,
        "emergency_contacts-0-name": ec.name, "emergency_contacts-0-relationship": ec.relationship,
        "emergency_contacts-0-phone": "999", "emergency_contacts-0-priority": ec.priority,
        "employments-TOTAL_FORMS": 0, "employments-INITIAL_FORMS": 0,
        "_save": "Save",
    })
    assert r.status_code == 302
    entry = AuditEntry.objects.get(model="people.employee", object_id=e.pk,
                                   field="emergency_contact.phone")
    assert entry.before == "111" and entry.after == "999"
    assert not AuditEntry.objects.filter(field="emergency_contact.name").exists()
    assert not AuditEntry.objects.filter(field="emergency_contact.priority").exists()


def test_top_level_delete_views_are_refused(admin_client, hr_admin):
    """Finding 2 (round 2): nothing in people is deleted; rows end."""
    e = make_employee()
    assert admin_client.get(f"/admin/people/employee/{e.pk}/delete/").status_code == 403


def test_pay_record_amount_edit_through_admin_is_audited(admin_client, hr_admin):
    """Finding 5 (round 2): an existing pay record's edit routes through
    pay.amend(), which diffs against the pre-change row."""
    emp = make_employment()
    pr = PayRecord.objects.create(employment=emp, from_date=date(2026, 4, 6),
                                  basis="annual", amount=Decimal("25000"))
    r = admin_client.post(f"/admin/people/employment/{emp.pk}/change/", _employment_base(
        emp, **{"pay_records-TOTAL_FORMS": 1, "pay_records-INITIAL_FORMS": 1,
                "pay_records-0-id": pr.pk, "pay_records-0-employment": emp.pk,
                "pay_records-0-from_date": str(pr.from_date), "pay_records-0-to_date": "",
                "pay_records-0-basis": "annual", "pay_records-0-amount": "27000",
                "pay_records-0-reason": ""}))
    assert r.status_code == 302
    entry = AuditEntry.objects.get(model="people.payrecord", object_id=pr.pk, field="amount")
    assert Decimal(entry.before) == Decimal("25000") and Decimal(entry.after) == Decimal("27000")
    pr.refresh_from_db()
    assert pr.amount == Decimal("27000")


# --- refused rows re-render, and adds keep their end dates (review I2, I3) ----------

from people.models import Contract, Employment  # noqa: E402
from tests.factories import make_contract, make_contract_type  # noqa: E402


def _employment_add(employee, **fields):
    data = {"employee": employee.pk, "start_date": "", "end_date": "", "leaving_reason": "",
            "continuous_service_date": "",
            "positions-TOTAL_FORMS": 0, "positions-INITIAL_FORMS": 0,
            "contracts-TOTAL_FORMS": 0, "contracts-INITIAL_FORMS": 0,
            "patterns-TOTAL_FORMS": 0, "patterns-INITIAL_FORMS": 0,
            "pay_records-TOTAL_FORMS": 0, "pay_records-INITIAL_FORMS": 0,
            "_save": "Save"}
    data.update(fields)
    return data


def test_an_added_spell_keeps_its_end_date_and_reason(admin_client):
    e = make_employee()
    r = admin_client.post("/admin/people/employment/add/", _employment_add(
        e, start_date="2020-01-06", end_date="2022-03-31", leaving_reason="resigned"))
    assert r.status_code == 302, r.content.decode()[:2000]
    emp = Employment.objects.get(employee=e)
    assert (emp.end_date, emp.leaving_reason) == (date(2022, 3, 31), "resigned")
    fields = set(AuditEntry.objects.filter(model="people.employment", object_id=emp.pk)
                 .values_list("field", flat=True))
    assert {"start_date", "end_date", "leaving_reason"} <= fields


def test_a_past_spell_can_be_added_before_a_current_one(admin_client):
    """An open-ended add would overlap every later spell; the end date is
    part of the check."""
    e = make_employee()
    make_employment(employee=e, start=date(2024, 1, 1))
    r = admin_client.post("/admin/people/employment/add/", _employment_add(
        e, start_date="2020-01-06", end_date="2022-03-31", leaving_reason="resigned"))
    assert r.status_code == 302
    assert Employment.objects.filter(employee=e).count() == 2


def test_an_overlapping_add_is_shown_on_the_form_not_a_500(admin_client):
    e = make_employee()
    make_employment(employee=e, start=date(2024, 1, 1))
    r = admin_client.post("/admin/people/employment/add/", _employment_add(e, start_date="2025-01-01"))
    assert r.status_code == 200
    html = r.content.decode()
    assert "already has an employment covering those dates" in html
    assert 'value="2025-01-01"' in html
    assert Employment.objects.filter(employee=e).count() == 1


def test_an_overlapping_spell_on_the_employee_page_is_shown_on_its_row(admin_client):
    e = make_employee()
    make_employment(employee=e, start=date(2024, 1, 1))
    r = admin_client.post(f"/admin/people/employee/{e.pk}/change/", {
        "first_name": e.first_name, "last_name": e.last_name, "work_email": e.work_email,
        "preferred_name": "", "personal_email": "", "phone": "", "address_line1": "",
        "address_line2": "", "town": "", "postcode": "", "ni_number": "",
        "emergency_contacts-TOTAL_FORMS": 0, "emergency_contacts-INITIAL_FORMS": 0,
        "employments-TOTAL_FORMS": 1, "employments-INITIAL_FORMS": 0,
        "employments-0-start_date": "2025-01-01", "employments-0-end_date": "",
        "employments-0-leaving_reason": "", "employments-0-continuous_service_date": "",
        "_save": "Save",
    })
    assert r.status_code == 200
    assert "already has an employment covering those dates" in r.content.decode()
    assert Employment.objects.filter(employee=e).count() == 1


def test_a_unit_clash_row_re_renders_and_nothing_is_saved(admin_client):
    emp = make_employment()
    make_contract(emp, make_contract_type("Reception", unit="hours"))
    gp = make_contract_type("GP sessions", unit="sessions", full_time=Decimal("9"))
    r = admin_client.post(f"/admin/people/employment/{emp.pk}/change/", _employment_base(
        emp, **{"contracts-TOTAL_FORMS": 1, "contracts-INITIAL_FORMS": 0,
                "contracts-0-contract_type": gp.pk, "contracts-0-basis": "permanent",
                "contracts-0-from_date": str(emp.start_date), "contracts-0-to_date": "",
                "contracts-0-weekly_amount": "2", "contracts-0-notes": "typed note",
                # a valid row beside it, which must not be saved without it
                "positions-TOTAL_FORMS": 1, "positions-INITIAL_FORMS": 0,
                "positions-0-title": titles.get_or_create("Receptionist").pk,
                "positions-0-team": make_team().pk,
                "positions-0-line_manager": "", "positions-0-primary": "on",
                "positions-0-from_date": str(emp.start_date), "positions-0-to_date": ""}))
    assert r.status_code == 200
    html = r.content.decode()
    assert "Concurrent contracts must share a unit" in html
    assert "typed note" in html
    assert "changed successfully" not in html
    assert not [m for m in r.context["messages"] if m.level_tag == "success"]
    assert Contract.objects.filter(employment=emp).count() == 1
    assert not emp.positions.exists(), "the rest of the page was saved without the refused row"
    assert not AuditEntry.objects.exists()


def test_viewing_an_ni_number_is_audited(admin_client, hr_admin):
    """Review I4: the NI number is restricted like pay, and each view of it
    is audited like pay."""
    e = make_employee(ni_number="AB123456C")
    r = admin_client.get(f"/admin/people/employee/{e.pk}/change/")
    assert r.status_code == 200 and "AB123456C" in r.content.decode()
    (entry,) = AuditEntry.objects.filter(kind="viewed", model="people.employee", object_id=e.pk)
    assert entry.field == "ni_number" and entry.actor == hr_admin


def test_no_ni_number_no_view_to_audit(admin_client):
    e = make_employee()
    assert admin_client.get(f"/admin/people/employee/{e.pk}/change/").status_code == 200
    assert not AuditEntry.objects.filter(kind="viewed").exists()


def test_a_login_whose_email_differs_from_the_work_email_is_warned_about(admin_client, employee_user):
    """Review minor: sign-in sends the login's email, not the work email."""
    e = make_employee(email="sam.patel@example.org")
    base = {"first_name": e.first_name, "last_name": e.last_name, "work_email": e.work_email,
            "preferred_name": "", "personal_email": "", "phone": "", "address_line1": "",
            "address_line2": "", "town": "", "postcode": "", "ni_number": "",
            "emergency_contacts-TOTAL_FORMS": 0, "emergency_contacts-INITIAL_FORMS": 0,
            "employments-TOTAL_FORMS": 0, "employments-INITIAL_FORMS": 0, "_save": "Save"}
    r = admin_client.post(f"/admin/people/employee/{e.pk}/change/",
                          {**base, "user": employee_user.pk}, follow=True)
    assert "is not the work email" in r.content.decode()
    r = admin_client.post(f"/admin/people/employee/{e.pk}/change/",
                          {**base, "user": employee_user.pk, "work_email": "SAM@example.com"},
                          follow=True)
    assert "is not the work email" not in r.content.decode()
