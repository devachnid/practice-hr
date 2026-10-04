from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from checks.models import Check, CheckType
from checks.services import checks
from documents.models import File, Policy
from documents.services import files, policies
from onboarding.models import Checklist, ChecklistItem, ChecklistTemplate
from onboarding.services import checklists
from people.models import Team
from people.services import employments, positions, titles
from tests.factories import make_employee, make_team

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


def _starter(hr_admin, days_ahead=10, manager=None, title="Receptionist"):
    e = make_employee()
    start = timezone.localdate() + timedelta(days=days_ahead)
    emp = employments.start(hr_admin, e, start)
    team = Team.objects.first() or make_team()          # Team.name is unique: one team for every starter
    positions.add(hr_admin, emp, titles.get_or_create(title), team, manager, start)
    return emp


def test_seeded_default_templates_exist():
    kinds = {t.kind: t for t in ChecklistTemplate.objects.filter(positions=None)}
    assert set(kinds) == {"starter", "leaver"}
    starter = list(kinds["starter"].items.order_by("order"))
    assert [i.link for i in starter[:3]] == ["details", "sign_policies", "upload:identity"]
    assert {i.owner for i in starter} == {"hr", "manager", "person"}


def test_a_new_employment_gets_a_starter_checklist_with_owners_and_dates(hr_admin):
    mgr = make_employee(first="Mo", last="Khan")
    emp = _starter(hr_admin, manager=mgr)
    cl = Checklist.objects.get(employment=emp, kind="starter")
    items = list(cl.items.order_by("order"))
    assert len(items) == ChecklistTemplate.objects.get(kind="starter", positions=None).items.count()
    first = items[0]
    assert first.owner == "person" and first.owner_employee == emp.employee
    manager_item = next(i for i in items if i.owner == "manager")
    assert manager_item.owner_employee == mgr
    assert all(i.due_on is not None for i in items)
    assert checklists.gaps(cl) == []


def test_a_starter_without_a_manager_is_a_gap_not_a_failure(hr_admin):
    emp = _starter(hr_admin, manager=None)
    cl = Checklist.objects.get(employment=emp)
    assert any(i.owner == "manager" and i.owner_employee is None for i in cl.items.all())
    assert "no line manager" in " ".join(checklists.gaps(cl))


def test_a_title_template_beats_the_default_and_an_old_start_gets_none(hr_admin):
    t = ChecklistTemplate.objects.create(kind="starter", name="Nurse starter")
    t.positions.add(titles.get_or_create("Practice Nurse"))
    t.items.create(order=1, title="Hep B status", owner="hr", due_rule="after_start", due_days=7, link="check:hep_b")
    emp = _starter(hr_admin, title="Practice Nurse")
    assert Checklist.objects.get(employment=emp).template == t
    old = _starter(hr_admin, days_ahead=-60)
    assert not Checklist.objects.filter(employment=old).exists()


def test_leaving_makes_a_leaver_checklist(hr_admin):
    emp = _starter(hr_admin, days_ahead=-200)
    employments.end(hr_admin, emp, timezone.localdate() + timedelta(days=20), "resigned")
    cl = Checklist.objects.get(employment=emp, kind="leaver")
    assert cl.items.filter(due_rule="before_end").exists() or cl.items.exists()


def test_who_completes_what(hr_admin, employee_user):
    mgr_user = type(employee_user).objects.create_user(email="mo@example.com", password="pw")
    mgr = make_employee(first="Mo", last="Khan", user=mgr_user)
    emp = _starter(hr_admin, manager=mgr)
    emp.employee.user = employee_user; emp.employee.save()
    cl = Checklist.objects.get(employment=emp)
    mine = cl.items.filter(owner="person").first()
    theirs = cl.items.filter(owner="manager").first()
    hrs = cl.items.filter(owner="hr").first()
    assert checklists.may_complete(employee_user, mine) and not checklists.may_complete(employee_user, theirs)
    assert checklists.may_complete(mgr_user, theirs) and not checklists.may_complete(mgr_user, hrs)
    assert checklists.may_complete(hr_admin, hrs) and checklists.may_complete(hr_admin, theirs)
    checklists.complete(mgr_user, theirs, "done at induction")
    theirs.refresh_from_db()
    assert theirs.state == "done" and theirs.done_by == mgr_user and theirs.done_at
    with pytest.raises(PermissionDenied):
        checklists.complete(employee_user, hrs)
    with pytest.raises(ValidationError):
        checklists.not_needed(hr_admin, hrs, "")
    checklists.not_needed(hr_admin, hrs, "covered by agency")
    hrs.refresh_from_db(); assert hrs.state == "not_needed"


def test_linked_items_close_themselves(hr_admin, employee_user):
    emp = _starter(hr_admin)
    e = emp.employee; e.user = employee_user; e.save()
    cl = Checklist.objects.get(employment=emp)
    rtw = CheckType.objects.get(code="right_to_work"); rtw.positions.add(titles.get_or_create("Receptionist"))
    upload = cl.items.get(link="upload:identity")
    files.add(hr_admin, e, File.Category.IDENTITY, "Passport", SimpleUploadedFile("p.pdf", PDF, content_type="application/pdf"))
    upload.refresh_from_db(); assert upload.state == "done"
    sign = cl.items.get(link="sign_policies")
    checklists.linked_done(e, "sign_policies")          # no policies owed → closes
    sign.refresh_from_db(); assert sign.state == "done"
    dbs = cl.items.get(link="check:dbs")
    t = CheckType.objects.get(code="dbs"); t.positions.add(titles.get_or_create("Receptionist"))
    checks.record(hr_admin, e, t, timezone.localdate(), Check.Outcome.CLEAR, reference="1", dbs_level="basic")
    dbs.refresh_from_db(); assert dbs.state == "done"


def test_summary_and_completion(hr_admin):
    emp = _starter(hr_admin)
    cl = Checklist.objects.get(employment=emp)
    for item in cl.items.all():
        checklists.complete(hr_admin, item)
    cl.refresh_from_db()
    assert cl.completed_at is not None and checklists.summary(cl)["open"] == 0


# ---- beyond the brief: the edges the hooks and later tasks lean on ----------

def test_a_position_added_after_work_has_begun_keeps_the_items_and_fills_the_manager(hr_admin):
    e = make_employee()
    start = timezone.localdate() + timedelta(days=10)
    emp = employments.start(hr_admin, e, start)
    cl = Checklist.objects.get(employment=emp)
    assert "no line manager" in " ".join(checklists.gaps(cl))
    checklists.complete(hr_admin, cl.items.get(link="details"))
    t = ChecklistTemplate.objects.create(kind="starter", name="Nurse starter")
    t.positions.add(titles.get_or_create("Practice Nurse"))
    t.items.create(order=1, title="Hep B status", owner="hr", due_rule="after_start", due_days=7, link="check:hep_b")
    mgr = make_employee(first="Mo", last="Khan")
    positions.add(hr_admin, emp, titles.get_or_create("Practice Nurse"), Team.objects.first() or make_team(), mgr,
                  start)
    cl.refresh_from_db()
    assert cl.template.positions.count() == 0          # work had begun: the default stays
    assert cl.items.get(link="details").state == "done"
    assert all(i.owner_employee == mgr for i in cl.items.filter(owner="manager"))
    assert [g for g in checklists.gaps(cl)] == [
        "the template for Practice Nurse (Starter: Nurse starter) was not applied: work on this checklist had begun"]


def test_an_untouched_checklist_follows_the_title_of_the_position_added_after_the_start(hr_admin):
    t = ChecklistTemplate.objects.create(kind="starter", name="Nurse starter")
    t.positions.add(titles.get_or_create("Practice Nurse"))
    t.items.create(order=1, title="Hep B status", owner="hr", due_rule="after_start", due_days=7, link="check:hep_b")
    emp = _starter(hr_admin, title="Practice Nurse")
    cl = Checklist.objects.get(employment=emp)
    assert [i.link for i in cl.items.all()] == ["check:hep_b"]
    assert cl.items.get().due_on == emp.start_date + timedelta(days=7)


def test_a_past_spell_and_an_existing_checklist(hr_admin):
    e = make_employee()
    today = timezone.localdate()
    past = employments.start(hr_admin, e, today - timedelta(days=400), end_date=today - timedelta(days=100),
                             leaving_reason="resigned")
    assert not Checklist.objects.filter(employment=past).exists()
    assert checklists.start(hr_admin, past) is None
    emp = _starter(hr_admin, days_ahead=-20)           # inside the 30 days: still gets one
    cl = Checklist.objects.get(employment=emp)
    assert checklists.start(hr_admin, emp) == cl
    assert Checklist.objects.filter(employment=emp).count() == 1


def test_leaver_once_and_not_on_a_cleared_end_date(hr_admin):
    emp = _starter(hr_admin, days_ahead=-200)
    employments.end(hr_admin, emp, None, "")
    assert not Checklist.objects.filter(employment=emp).exists()
    end = timezone.localdate() + timedelta(days=20)
    employments.end(hr_admin, emp, end, "resigned")
    employments.end(hr_admin, emp, end + timedelta(days=1), "resigned")
    cl = Checklist.objects.get(employment=emp, kind="leaver")
    assert cl.items.get(title="Handover completed").due_on == end + timedelta(days=1) - timedelta(days=5)
    assert cl.items.get(title="Handover completed").owner_employee is None
    assert "no line manager" in " ".join(checklists.gaps(cl))


def test_linked_done_takes_a_prefix_with_keywords_and_is_a_no_op_without_items(hr_admin):
    stranger = make_employee(first="Al", last="Lee")
    checklists.linked_done(stranger, "upload:identity")     # no checklist at all: nothing, no error
    checklists.linked_done(None, "sign_policies")
    emp = _starter(hr_admin)
    cl = Checklist.objects.get(employment=emp)
    checklists.linked_done(emp.employee, "upload", category=File.Category.CONTRACT)
    checklists.linked_done(emp.employee, "check", check_code="occupational_health")
    checklists.linked_done(emp.employee, "check", check_code="nothing_links_here")
    closed = set(cl.items.filter(state="done").values_list("link", flat=True))
    assert closed == {"upload:contract", "check:occupational_health"}
    item = cl.items.get(link="upload:contract")
    assert item.done_by is None and item.done_at is not None and item.note == "done automatically"


def test_policies_owed_keep_the_signing_item_open(hr_admin, employee_user):
    emp = _starter(hr_admin, days_ahead=-5)
    e = emp.employee; e.user = employee_user; e.save()
    policy = Policy.objects.create(title="Chaperoning")
    policies.issue(hr_admin, policy, "v1", SimpleUploadedFile("c.pdf", PDF, content_type="application/pdf"),
                   timezone.localdate(), 14)
    assert policies.owed(e, timezone.localdate())
    for hook in policies.SIGNED_HOOKS:
        hook(e)
    item = ChecklistItem.objects.get(checklist__employment=emp, link="sign_policies")
    assert item.state == "open"


def test_a_failing_upload_hook_leaves_no_row_and_no_bytes(hr_admin, monkeypatch, tmp_path):
    def boom(f):
        raise RuntimeError("hook failed")
    monkeypatch.setattr(files, "ADDED_HOOKS", [boom])
    e = make_employee()
    with pytest.raises(RuntimeError):
        files.add(hr_admin, e, File.Category.IDENTITY, "Passport",
                  SimpleUploadedFile("p.pdf", PDF, content_type="application/pdf"))
    assert not File.objects.exists()
    assert not [p for p in tmp_path.rglob("*") if p.is_file()]


def test_a_file_with_no_person_closes_nothing(hr_admin):
    emp = _starter(hr_admin)
    files.add(hr_admin, None, File.Category.IDENTITY, "Template passport form",
              SimpleUploadedFile("p.pdf", PDF, content_type="application/pdf"))
    assert ChecklistItem.objects.get(checklist__employment=emp, link="upload:identity").state == "open"


def test_add_and_remove_items_are_hr_only(hr_admin, employee_user):
    mgr = make_employee(first="Mo", last="Khan")
    emp = _starter(hr_admin, days_ahead=-3, manager=mgr)
    cl = Checklist.objects.get(employment=emp)
    due = timezone.localdate() + timedelta(days=3)
    with pytest.raises(PermissionDenied):
        checklists.add_item(employee_user, cl, "Fire safety", "", "manager", due)
    item = checklists.add_item(hr_admin, cl, "Fire safety", "Walk the exits", "manager", due)
    assert item.owner_employee == mgr and item.state == "open"
    with pytest.raises(PermissionDenied):
        checklists.remove_item(employee_user, item)
    checklists.remove_item(hr_admin, item)
    assert not ChecklistItem.objects.filter(pk=item.pk).exists()
    end = timezone.localdate() + timedelta(days=30)
    employments.end(hr_admin, emp, end, "resigned")
    leaver = Checklist.objects.get(employment=emp, kind="leaver")
    late = checklists.add_item(hr_admin, leaver, "Exit interview", "", "manager", end + timedelta(days=7))
    assert late.owner_employee == mgr


def test_open_items_owned_items_and_summary(hr_admin):
    mgr = make_employee(first="Mo", last="Khan")
    emp = _starter(hr_admin, days_ahead=-10, manager=mgr)
    today = timezone.localdate()
    cl = Checklist.objects.get(employment=emp)
    mine = checklists.open_items(emp.employee, today)
    assert mine and {i.owner for i in mine} == {"person"}
    theirs = checklists.items_owned_by(mgr, today)
    assert theirs and {i.owner for i in theirs} == {"manager"}
    s = checklists.summary(cl)
    assert s["total"] == cl.items.count() and s["done"] == 0 and s["open"] == s["total"]
    overdue = [i for i in cl.items.all() if i.due_on < today]
    assert s["overdue"] == len(overdue) and s["oldest_overdue"] == min(overdue, key=lambda i: i.due_on)


def test_a_closed_item_cannot_be_closed_again(hr_admin):
    emp = _starter(hr_admin)
    item = Checklist.objects.get(employment=emp).items.first()
    checklists.complete(hr_admin, item)
    with pytest.raises(ValidationError):
        checklists.complete(hr_admin, item)
    with pytest.raises(ValidationError):
        checklists.not_needed(hr_admin, item, "covered")


def test_the_admin_pages_open_for_hr(admin_client, hr_admin):
    emp = _starter(hr_admin)
    cl = Checklist.objects.get(employment=emp)
    template = ChecklistTemplate.objects.get(kind="starter", positions=None)
    for url in ("/admin/onboarding/checklisttemplate/", f"/admin/onboarding/checklisttemplate/{template.pk}/change/",
                "/admin/onboarding/checklist/", f"/admin/onboarding/checklist/{cl.pk}/change/"):
        assert admin_client.get(url).status_code == 200, url
    page = admin_client.get("/admin/").content.decode()
    assert "Checklist templates" in page and "Checklists" in page


def test_moving_the_start_date_moves_the_open_starter_items(hr_admin):
    emp = _starter(hr_admin)
    cl = Checklist.objects.get(employment=emp)
    details = cl.items.get(link="details")
    checklists.complete(hr_admin, details)
    before = {i.pk: i.due_on for i in cl.items.all()}
    employments.amend(hr_admin, emp, start_date=emp.start_date + timedelta(days=3))
    for item in cl.items.all():
        shift = 0 if item.pk == details.pk else 3
        assert item.due_on == before[item.pk] + timedelta(days=shift), item.title


def test_a_template_item_link_must_be_one_the_app_knows():
    t = ChecklistTemplate.objects.get(kind="starter", positions=None)
    for link in ("details", "sign_policies", "upload:identity", "check:dbs", ""):
        t.items.model(template=t, title="x", owner="hr", due_rule="after_start", link=link).full_clean()
    for link in ("upload:passport", "check:nope", "sign", "upload:"):
        with pytest.raises(ValidationError):
            t.items.model(template=t, title="x", owner="hr", due_rule="after_start", link=link).full_clean()
