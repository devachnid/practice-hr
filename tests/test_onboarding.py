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
from people.models import AuditEntry, Team
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
    CheckType.objects.get(code="dbs").positions.add(titles.get_or_create("Receptionist"))
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
    for item in cl.items.filter(state="open"):         # sign_policies is done at build: nothing to sign
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
    CheckType.objects.get(code="hep_b").positions.add(titles.get_or_create("Practice Nurse"))
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


def test_leaver_once_and_its_dates_follow_the_leaving_date(hr_admin):
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


def test_clearing_the_leaving_date_closes_the_leaver_checklist(hr_admin, employee_user):
    emp = _starter(hr_admin, days_ahead=-200)
    end = timezone.localdate() + timedelta(days=20)
    employments.end(hr_admin, emp, end, "resigned")
    cl = Checklist.objects.get(employment=emp, kind="leaver")
    handover = cl.items.get(title="Handover completed")
    checklists.complete(hr_admin, handover)
    employments.end(hr_admin, emp, None, "")
    cl.refresh_from_db()
    assert cl.completed_at is not None
    assert cl.items.get(pk=handover.pk).state == "done"
    rest = cl.items.exclude(pk=handover.pk)
    assert rest.exists() and all(i.state == "not_needed" and i.note == "leaving date cleared" and i.done_by is None
                                 for i in rest)
    assert AuditEntry.objects.filter(model="onboarding.checklistitem", object_id__in=[i.pk for i in rest],
                                     after="not_needed").count() == rest.count()
    assert checklists.open_items(emp.employee, timezone.localdate()) == []


def test_set_clear_set_again_makes_a_fresh_leaver_checklist(hr_admin):
    emp = _starter(hr_admin, days_ahead=-200)
    first = timezone.localdate() + timedelta(days=20)
    employments.end(hr_admin, emp, first, "resigned")
    cl = Checklist.objects.get(employment=emp, kind="leaver")
    checklists.complete(hr_admin, cl.items.get(title="Handover completed"))
    employments.end(hr_admin, emp, None, "")
    second = timezone.localdate() + timedelta(days=60)
    employments.end(hr_admin, emp, second, "resigned")
    cl = Checklist.objects.get(employment=emp, kind="leaver")
    template = ChecklistTemplate.objects.get(kind="leaver", positions=None)
    n = template.items.count()
    # final review M2: the old items are kept as they were, a fresh set follows
    assert cl.completed_at is None and cl.items.count() == 2 * n
    fresh = cl.items.filter(state="open")
    assert fresh.count() == n
    assert fresh.get(title="Handover completed").due_on == second - timedelta(days=5)
    old = cl.items.exclude(state="open")
    assert old.filter(state="done").count() == 1
    assert old.filter(state="not_needed", note="leaving date cleared").count() == n - 1
    assert "cleared" not in " ".join(checklists.gaps(cl))


def test_a_cleared_leaver_checklist_with_nothing_open_is_still_made_afresh(hr_admin):
    emp = _starter(hr_admin, days_ahead=-200)
    employments.end(hr_admin, emp, timezone.localdate() + timedelta(days=20), "resigned")
    cl = Checklist.objects.get(employment=emp, kind="leaver")
    for item in cl.items.all():
        checklists.complete(hr_admin, item)
    employments.end(hr_admin, emp, None, "")
    employments.end(hr_admin, emp, timezone.localdate() + timedelta(days=40), "resigned")
    cl.refresh_from_db()
    n = ChecklistTemplate.objects.get(kind="leaver", positions=None).items.count()
    assert cl.completed_at is None and cl.items.filter(state="open").count() == n
    assert cl.items.filter(state="done").count() == n           # kept, not reopened


def test_a_returner_starts_with_what_is_already_in_place_done(hr_admin):
    e = make_employee()
    today = timezone.localdate()
    dbs = CheckType.objects.get(code="dbs")
    checks.record(hr_admin, e, dbs, today - timedelta(days=30), Check.Outcome.CLEAR, reference="1", dbs_level="basic")
    files.add(hr_admin, e, File.Category.IDENTITY, "Passport",
              SimpleUploadedFile("p.pdf", PDF, content_type="application/pdf"))
    oh = CheckType.objects.get(code="occupational_health")
    checks.record(hr_admin, e, oh, today - timedelta(days=30), Check.Outcome.NOT_CLEAR)
    emp = employments.start(hr_admin, e, today + timedelta(days=10))
    cl = Checklist.objects.get(employment=emp)
    done = {i.link: i for i in cl.items.filter(state="done")}
    assert set(done) == {"check:dbs", "upload:identity", "sign_policies"}
    assert all(i.note == "done automatically" and i.done_by is None for i in done.values())
    assert cl.items.get(link="check:occupational_health").state == "open"   # not clear: still to do
    assert cl.items.get(link="upload:contract").state == "open"


def test_a_lapsed_check_does_not_count_at_build(hr_admin):
    e = make_employee()
    today = timezone.localdate()
    dbs = CheckType.objects.get(code="dbs")
    checks.record(hr_admin, e, dbs, today - timedelta(days=400), Check.Outcome.CLEAR, reference="1",
                  dbs_level="basic", expires_on=today - timedelta(days=1))
    emp = employments.start(hr_admin, e, today + timedelta(days=10))
    assert ChecklistItem.objects.get(checklist__employment=emp, link="check:dbs").state == "open"


def test_sign_policies_is_done_at_build_only_when_nothing_is_owed(hr_admin):
    emp = _starter(hr_admin)
    assert ChecklistItem.objects.get(checklist__employment=emp, link="sign_policies").state == "done"
    policy = Policy.objects.create(title="Chaperoning")
    policies.issue(hr_admin, policy, "v1", SimpleUploadedFile("c.pdf", PDF, content_type="application/pdf"),
                   timezone.localdate(), 14)
    later = _starter(hr_admin)
    assert ChecklistItem.objects.get(checklist__employment=later, link="sign_policies").state == "open"


def test_a_title_template_rebuild_starts_with_what_is_already_in_place_done(hr_admin):
    t = ChecklistTemplate.objects.create(kind="starter", name="Nurse starter")
    t.positions.add(titles.get_or_create("Practice Nurse"))
    t.items.create(order=1, title="Hep B status", owner="hr", due_rule="after_start", due_days=7, link="check:hep_b")
    e = make_employee()
    today = timezone.localdate()
    checks.record(hr_admin, e, CheckType.objects.get(code="hep_b"), today, Check.Outcome.CLEAR,
                  upload=SimpleUploadedFile("hep-b.pdf", PDF))
    start = today + timedelta(days=10)
    emp = employments.start(hr_admin, e, start)
    positions.add(hr_admin, emp, titles.get_or_create("Practice Nurse"), make_team(), None, start)
    cl = Checklist.objects.get(employment=emp)
    assert cl.template == t and cl.items.get().state == "done"
    assert cl.completed_at is not None


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
    assert closed == {"upload:contract", "check:occupational_health", "sign_policies"}  # the last at build
    item = cl.items.get(link="upload:contract")
    assert item.done_by is None and item.done_at is not None and item.note == "done automatically"


def test_policies_owed_keep_the_signing_item_open(hr_admin, employee_user):
    policy = Policy.objects.create(title="Chaperoning")
    policies.issue(hr_admin, policy, "v1", SimpleUploadedFile("c.pdf", PDF, content_type="application/pdf"),
                   timezone.localdate(), 14)
    emp = _starter(hr_admin, days_ahead=-5)
    e = emp.employee; e.user = employee_user; e.save()
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
    linked = checklists.add_item(hr_admin, leaver, "Leaving letter", "", "hr", end, link="upload:correspondence")
    assert linked.link == "upload:correspondence"
    with pytest.raises(ValidationError):
        checklists.add_item(hr_admin, leaver, "Leaving letter", "", "hr", end, link="upload:letter")


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
    assert s["total"] == cl.items.count() and s["done"] == 1 and s["open"] == s["total"] - 1   # sign_policies
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
    before = {i.pk: (i.due_on, i.state) for i in cl.items.all()}
    employments.amend(hr_admin, emp, start_date=emp.start_date + timedelta(days=3))
    for item in cl.items.all():
        due, state = before[item.pk]
        shift = 3 if state == "open" else 0
        assert item.due_on == due + timedelta(days=shift), item.title


def test_a_template_item_link_must_be_one_the_app_knows():
    t = ChecklistTemplate.objects.get(kind="starter", positions=None)
    for link in ("details", "sign_policies", "upload:identity", "check:dbs", ""):
        t.items.model(template=t, title="x", owner="hr", due_rule="after_start", link=link).full_clean()
    for link in ("upload:passport", "check:nope", "sign", "upload:"):
        with pytest.raises(ValidationError):
            t.items.model(template=t, title="x", owner="hr", due_rule="after_start", link=link).full_clean()


def test_a_title_that_owes_policies_reopens_signing_done_before_the_position(hr_admin):
    policy = Policy.objects.create(title="Reception procedures")
    policy.positions.add(titles.get_or_create("Receptionist"))
    policies.issue(hr_admin, policy, "v1", SimpleUploadedFile("r.pdf", PDF, content_type="application/pdf"),
                   timezone.localdate(), 14)
    e = make_employee()
    start = timezone.localdate() + timedelta(days=10)
    emp = employments.start(hr_admin, e, start)
    item = ChecklistItem.objects.get(checklist__employment=emp, link="sign_policies")
    assert item.state == "done"                     # no title yet: nothing owed
    checklists.complete(hr_admin, ChecklistItem.objects.get(checklist__employment=emp, link="details"))
    positions.add(hr_admin, emp, titles.get_or_create("Receptionist"), make_team(), None, start)
    item.refresh_from_db()
    assert item.state == "open" and item.done_at is None and item.note == ""


# ---- final review I4/I5: empty and gapped checklists ----------------------------------------

def test_a_checklist_with_no_items_is_never_complete_by_itself(hr_admin):
    ChecklistTemplate.objects.filter(kind="starter").update(active=False)
    emp = _starter(hr_admin)
    cl = Checklist.objects.get(employment=emp)
    assert cl.items.count() == 0 and cl.completed_at is None
    assert "no starter checklist template" in " ".join(checklists.gaps(cl))
    assert cl in checklists.for_hr()


def test_a_checklist_closed_automatically_with_a_gap_stays_on_hrs_list(hr_admin):
    t = ChecklistTemplate.objects.create(kind="starter", name="Nurse starter")
    t.positions.add(titles.get_or_create("Practice Nurse"))
    t.items.create(order=1, title="Contract", owner="hr", due_rule="before_start", due_days=1,
                   link="upload:contract")
    emp = _starter(hr_admin, title="Practice Nurse")            # no manager: a gap
    cl = Checklist.objects.get(employment=emp)
    files.add(hr_admin, emp.employee, File.Category.CONTRACT, "Contract", SimpleUploadedFile("c.pdf", PDF))
    cl.refresh_from_db()
    assert cl.completed_at is not None and checklists.gaps(cl)
    assert cl in checklists.for_hr()                            # nobody finished it by hand
    other = _starter(hr_admin, title="Practice Nurse")
    ocl = Checklist.objects.get(employment=other)
    checklists.complete(hr_admin, ocl.items.get())
    ocl.refresh_from_db()
    assert ocl.completed_at is not None and checklists.gaps(ocl)
    assert ocl not in checklists.for_hr()                       # HR finished it


def test_a_starter_whose_title_needs_no_check_types_has_that_gap(hr_admin):
    emp = _starter(hr_admin, title="Practice Nurse")
    cl = Checklist.objects.get(employment=emp)
    assert "no check types for the title Practice Nurse" in " ".join(checklists.gaps(cl))
    dbs = CheckType.objects.get(code="dbs")
    dbs.positions.add(titles.get_or_create("Receptionist"))
    cl = Checklist.objects.get(employment=_starter(hr_admin, title="Receptionist"))
    assert "no check types" not in " ".join(checklists.gaps(cl))
    dbs.active = False
    dbs.save()
    cl = Checklist.objects.get(employment=_starter(hr_admin, title="Receptionist"))
    assert "no check types for the title Receptionist" in " ".join(checklists.gaps(cl))   # active ones only


def test_a_leaver_checklist_has_no_check_types_gap(hr_admin):
    emp = _starter(hr_admin, days_ahead=-5)
    employments.end(hr_admin, emp, timezone.localdate() + timedelta(days=30), "resigned")
    cl = Checklist.objects.get(employment=emp, kind="leaver")
    assert "no check types" not in " ".join(checklists.gaps(cl))


def test_a_checklist_template_cannot_be_deleted(admin_client):
    t = ChecklistTemplate.objects.filter(kind="starter").first()
    assert admin_client.get(f"/admin/onboarding/checklisttemplate/{t.pk}/delete/").status_code == 403
    assert ChecklistTemplate.objects.filter(pk=t.pk).exists()


# ---- final review M4: a checklist error never stops the employment save ---------------------

def test_a_failing_checklist_build_is_a_gap_and_a_log_line_not_a_failed_save(hr_admin, monkeypatch, caplog):
    def boom(*a, **kw):
        raise RuntimeError("Sam Patel's template is broken")
    monkeypatch.setattr(checklists, "_build", boom)
    e = make_employee()
    emp = employments.start(hr_admin, e, timezone.localdate() + timedelta(days=10))
    assert emp.pk is not None
    cl = Checklist.objects.get(employment=emp, kind="starter")
    assert checklists.gaps(cl) == ["checklist could not be built: RuntimeError"] and cl.items.count() == 0
    assert "RuntimeError" in caplog.text and "Sam Patel" not in caplog.text and "broken" not in caplog.text
    assert cl in checklists.for_hr()
    assert AuditEntry.objects.filter(model="onboarding.checklist", object_id=cl.pk, field="created",
                                     after="starter checklist, 0 items").exists()


def test_a_failing_position_hook_still_saves_the_position(hr_admin, monkeypatch):
    emp = employments.start(hr_admin, make_employee(), timezone.localdate() + timedelta(days=10))

    def boom(*a, **kw):
        raise ValueError("no")
    monkeypatch.setattr(checklists, "_resolve", boom)
    pos = positions.add(hr_admin, emp, titles.get_or_create("Receptionist"), make_team(), None, emp.start_date)
    assert pos.pk is not None
    cl = Checklist.objects.get(employment=emp, kind="starter")
    assert "checklist could not be built: ValueError" in checklists.gaps(cl)


def test_a_failing_leaver_step_still_saves_the_leaving_date(hr_admin, monkeypatch):
    emp = _starter(hr_admin, days_ahead=-5)
    monkeypatch.setattr(checklists, "_build", lambda *a, **kw: 1 / 0)
    end = timezone.localdate() + timedelta(days=30)
    employments.end(hr_admin, emp, end, "resigned")
    emp.refresh_from_db()
    assert emp.end_date == end
    cl = Checklist.objects.get(employment=emp, kind="leaver")
    assert checklists.gaps(cl) == ["checklist could not be built: ZeroDivisionError"]


# ---- final review M6: a recorded check closes its item only if clear and in date ------------

def test_a_check_recorded_already_expired_does_not_close_its_item(hr_admin):
    emp = _starter(hr_admin)
    item = Checklist.objects.get(employment=emp).items.get(link="check:dbs")
    dbs = CheckType.objects.get(code="dbs")
    today = timezone.localdate()
    checks.record(hr_admin, emp.employee, dbs, today - timedelta(days=400), Check.Outcome.CLEAR, reference="1",
                  dbs_level="basic", expires_on=today - timedelta(days=1))
    item.refresh_from_db()
    assert item.state == "open"
    checks.record(hr_admin, emp.employee, dbs, today, Check.Outcome.CLEAR, reference="2", dbs_level="basic")
    item.refresh_from_db()
    assert item.state == "done" and item.note == "done automatically"


# ---- final review, round 2 -----------------------------------------------------------------

def test_a_reset_leaving_date_with_no_leaver_template_stays_on_hrs_list(hr_admin):
    emp = _starter(hr_admin, days_ahead=-200)
    employments.end(hr_admin, emp, timezone.localdate() + timedelta(days=20), "resigned")
    employments.end(hr_admin, emp, None, "")
    ChecklistTemplate.objects.filter(kind="leaver").update(active=False)
    employments.end(hr_admin, emp, timezone.localdate() + timedelta(days=40), "resigned")
    cl = Checklist.objects.get(employment=emp, kind="leaver")
    assert cl.completed_at is None and not cl.items.filter(state="open").exists()
    assert "no leaver checklist template" in " ".join(checklists.gaps(cl))
    assert cl in checklists.for_hr()


def test_sent_details_count_as_work_begun_so_a_title_template_does_not_rebuild(hr_admin):
    e = make_employee()
    start = timezone.localdate() + timedelta(days=10)
    emp = employments.start(hr_admin, e, start)
    cl = Checklist.objects.get(employment=emp)
    assert checklists.details_submitted(hr_admin, e) == 1
    sent = cl.items.get(link="details")
    t = ChecklistTemplate.objects.create(kind="starter", name="Nurse starter")
    t.positions.add(titles.get_or_create("Practice Nurse"))
    t.items.create(order=1, title="Hep B status", owner="hr", due_rule="after_start", due_days=7, link="check:hep_b")
    positions.add(hr_admin, emp, titles.get_or_create("Practice Nurse"), Team.objects.first() or make_team(), None,
                  start)
    cl.refresh_from_db()
    kept = cl.items.get(link="details")
    assert kept.pk == sent.pk and kept.submitted_at == sent.submitted_at and kept.state == "open"
    assert cl.template != t and "was not applied" in " ".join(checklists.gaps(cl))
