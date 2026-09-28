from datetime import date

from people.models import AuditEntry, PayRecord, WorkingPattern
from tests.factories import make_employee, make_employment, make_position, make_team


def test_changelists_render(admin_client):
    for url in ("/admin/people/employee/", "/admin/people/employment/", "/admin/people/team/",
                "/admin/people/contracttype/", "/admin/people/auditentry/"):
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
            "positions-0-title": pos.title, "positions-0-team": team.pk,
            "positions-0-line_manager": "", "positions-0-primary": "on",
            "positions-0-from_date": str(pos.from_date), "positions-0-to_date": "",
        }
        row.update(overrides)
        return row

    # A title change is refused; the row is untouched.
    r = admin_client.post(f"/admin/people/employment/{emp.pk}/change/", _employment_base(
        emp, **{**position_row(**{"positions-0-title": "Manager"}),
                "positions-TOTAL_FORMS": 1, "positions-INITIAL_FORMS": 1}), follow=True)
    assert r.status_code == 200
    assert "only end" in r.content.decode()
    pos.refresh_from_db()
    assert pos.title == "Receptionist"

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
