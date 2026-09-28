from datetime import date

from people.models import AuditEntry, PayRecord
from tests.factories import make_employee, make_employment


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
