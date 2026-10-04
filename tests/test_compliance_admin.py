from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from checks.models import Check, CheckType
from checks.services import checks
from documents.models import Policy
from documents.services import policies
from onboarding.models import ChecklistItem
from people.models import AuditEntry, Team
from people.services import employments, positions, titles
from tests.factories import make_employee, make_team

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


def _receptionist(hr_admin):
    e = make_employee()
    emp = employments.start(hr_admin, e, timezone.localdate() - timedelta(days=400))
    team = Team.objects.filter(name="Reception").first() or make_team()
    positions.add(hr_admin, emp, titles.get_or_create("Receptionist"), team, None, emp.start_date)
    return e


def test_employee_admin_has_a_compliance_tab(admin_client, hr_admin):
    dbs = CheckType.objects.get(code="dbs"); dbs.positions.add(titles.get_or_create("Receptionist"))
    e = _receptionist(hr_admin)
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert "Compliance" in body and "DBS" in body and "Missing" in body


def test_dashboard_card_counts(admin_client, hr_admin):
    dbs = CheckType.objects.get(code="dbs"); dbs.positions.add(titles.get_or_create("Receptionist"))
    e = _receptionist(hr_admin)
    checks.record(hr_admin, e, dbs, timezone.localdate() - timedelta(days=1200), Check.Outcome.CLEAR, reference="1", dbs_level="basic")
    body = admin_client.get("/admin/").content.decode()
    assert "Lapsed checks" in body and ">1<" in body


def test_retention_report_lists_the_new_categories(admin_client, hr_admin, settings):
    e = make_employee()
    emp = employments.start(hr_admin, e, timezone.localdate() - timedelta(days=4000))
    employments.end(hr_admin, emp, timezone.localdate() - timedelta(days=3000), "resigned")
    body = admin_client.get("/people/retention/").content.decode()
    for category in ("checks", "files", "signatures"):
        assert category in body


# --- beyond the brief's three ---------------------------------------------------

def _overdue_policy(hr_admin):
    p = Policy.objects.create(title="Information governance")
    policies.issue(hr_admin, p, "v1", SimpleUploadedFile("ig.pdf", PDF, content_type="application/pdf"),
                   timezone.localdate() - timedelta(days=30), 14)
    return p


def test_the_tab_links_a_missing_check_to_its_record_form_and_lists_policies(admin_client, hr_admin):
    dbs = CheckType.objects.get(code="dbs"); dbs.positions.add(titles.get_or_create("Receptionist"))
    e = _receptionist(hr_admin)
    p = _overdue_policy(hr_admin)
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert f"/admin/checks/check/add/?employee={e.pk}&amp;check_type={dbs.pk}" in body
    assert "Information governance" in body and "Overdue" in body
    assert f"/admin/documents/policy/{p.pk}/change/" in body


def test_the_tab_links_a_recorded_check_and_an_open_checklist_item(admin_client, hr_admin):
    dbs = CheckType.objects.get(code="dbs"); dbs.positions.add(titles.get_or_create("Receptionist"))
    e = make_employee()
    emp = employments.start(hr_admin, e, timezone.localdate() + timedelta(days=10))   # a starter
    positions.add(hr_admin, emp, titles.get_or_create("Receptionist"), make_team(), None, emp.start_date)
    c = checks.record(hr_admin, e, dbs, timezone.localdate(), Check.Outcome.CLEAR, reference="1", dbs_level="basic")
    cl = emp.checklists.get()
    item = cl.items.filter(state=ChecklistItem.State.OPEN).first()
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert f"/admin/checks/check/{c.pk}/change/" in body
    assert item.title in body and f"/onboarding/all/{cl.pk}/" in body


def test_a_starter_s_checks_are_shown_as_they_will_stand_on_day_one(admin_client, hr_admin):
    receptionist = titles.get_or_create("Receptionist")
    dbs = CheckType.objects.get(code="dbs"); dbs.positions.add(receptionist)
    rtw = CheckType.objects.get(code="right_to_work"); rtw.positions.add(receptionist)
    e = make_employee()
    emp = employments.start(hr_admin, e, timezone.localdate() + timedelta(days=10))
    positions.add(hr_admin, emp, receptionist, make_team(), None, emp.start_date)
    checks.record(hr_admin, e, dbs, timezone.localdate(), Check.Outcome.CLEAR, reference="1", dbs_level="basic")
    body = admin_client.get(f"/admin/people/employee/{e.pk}/change/").content.decode()
    assert "They start on" in body
    assert "Not required" not in body
    assert "<td>DBS</td><td>Current</td>" in body.replace(' class="pr-4"', "")
    assert "<td>Right to work</td><td>Missing</td>" in body.replace(' class="pr-4"', "")


def test_the_tab_is_not_on_the_add_page(admin_client):
    body = admin_client.get("/admin/people/employee/add/").content.decode()
    assert "compliance_summary" not in body and "Nothing is recorded" not in body
    assert admin_client.get("/admin/people/employee/add/").status_code == 200


def test_opening_the_tab_writes_nothing(admin_client, hr_admin):
    dbs = CheckType.objects.get(code="dbs"); dbs.positions.add(titles.get_or_create("Receptionist"))
    e = _receptionist(hr_admin)
    _overdue_policy(hr_admin)
    before = (AuditEntry.objects.count(), Check.objects.count(), ChecklistItem.objects.count())
    admin_client.get(f"/admin/people/employee/{e.pk}/change/")
    assert (AuditEntry.objects.count(), Check.objects.count(), ChecklistItem.objects.count()) == before


def test_each_number_links_to_the_people_it_counts(admin_client, hr_admin):
    dbs = CheckType.objects.get(code="dbs"); dbs.positions.add(titles.get_or_create("Receptionist"))
    lapsed = _receptionist(hr_admin)
    checks.record(hr_admin, lapsed, dbs, timezone.localdate() - timedelta(days=1200), Check.Outcome.CLEAR,
                  reference="1", dbs_level="basic")
    missing = make_employee(first="Alex", last="Brown")
    emp = employments.start(hr_admin, missing, timezone.localdate() - timedelta(days=400))
    positions.add(hr_admin, emp, titles.get_or_create("Receptionist"), make_team("Admin"), None, emp.start_date)
    body = admin_client.get("/admin/").content.decode()
    assert "/admin/people/employee/?compliance=lapsed_checks" in body
    assert "/admin/people/employee/?compliance=missing_checks" in body
    listed = admin_client.get("/admin/people/employee/?compliance=lapsed_checks").content.decode()
    assert f"/admin/people/employee/{lapsed.pk}/change/" in listed
    assert f"/admin/people/employee/{missing.pk}/change/" not in listed
    listed = admin_client.get("/admin/people/employee/?compliance=missing_checks").content.decode()
    assert f"/admin/people/employee/{missing.pk}/change/" in listed
    assert f"/admin/people/employee/{lapsed.pk}/change/" not in listed


def test_compliance_counts(hr_admin):
    from absence.admin_dashboard import compliance_counts
    dbs = CheckType.objects.get(code="dbs"); dbs.positions.add(titles.get_or_create("Receptionist"))
    e = _receptionist(hr_admin)
    checks.record(hr_admin, e, dbs, timezone.localdate() - timedelta(days=1200), Check.Outcome.CLEAR,
                  reference="1", dbs_level="basic")
    _receptionist(hr_admin)                                    # nothing recorded: missing
    _overdue_policy(hr_admin)                                  # applies to everyone: two overdue
    starter = make_employee(first="Jo", last="Starter")
    emp = employments.start(hr_admin, starter, timezone.localdate() + timedelta(days=30))   # nothing due yet
    cl = emp.checklists.get()
    late = cl.items.filter(state=ChecklistItem.State.OPEN).first()
    ChecklistItem.objects.filter(pk=late.pk).update(due_on=timezone.localdate() - timedelta(days=1))
    counts = compliance_counts(timezone.localdate())
    assert counts["lapsed_checks"] == 1
    assert counts["missing_checks"] == 1
    assert counts["overdue_signatures"] == 2
    assert counts["overdue_items"] == 1


def test_overdue_items_and_signatures_filter_the_employee_list(admin_client, hr_admin):
    _overdue_policy(hr_admin)
    signer = _receptionist(hr_admin)
    starter = make_employee(first="Jo", last="Starter")
    emp = employments.start(hr_admin, starter, timezone.localdate() + timedelta(days=30))   # nothing due yet
    late = emp.checklists.get().items.filter(state=ChecklistItem.State.OPEN).first()
    ChecklistItem.objects.filter(pk=late.pk).update(due_on=timezone.localdate() - timedelta(days=1))
    listed = admin_client.get("/admin/people/employee/?compliance=overdue_items").content.decode()
    assert f"/admin/people/employee/{starter.pk}/change/" in listed
    assert f"/admin/people/employee/{signer.pk}/change/" not in listed
    listed = admin_client.get("/admin/people/employee/?compliance=overdue_signatures").content.decode()
    assert f"/admin/people/employee/{signer.pk}/change/" in listed
    assert f"/admin/people/employee/{starter.pk}/change/" not in listed
