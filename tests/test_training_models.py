from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from training.models import Course, TrainingRecord, TrainingSession

pytestmark = pytest.mark.django_db


def test_seeded_courses_exist_with_the_spec_defaults_and_nothing_required():
    by = {c.code: c for c in Course.objects.all()}
    assert set(by) == {"basic_life_support", "fire_safety", "information_governance", "infection_control",
                       "safeguarding_children", "safeguarding_adults", "equality_diversity", "health_safety",
                       "conflict_resolution", "chaperone"}
    assert by["basic_life_support"].delivery == "face_to_face" and by["basic_life_support"].validity_months == 12
    assert by["fire_safety"].delivery == "online" and by["fire_safety"].validity_months == 12
    assert by["safeguarding_children"].validity_months == 36
    assert by["chaperone"].validity_months is None
    assert all(not c.everyone and not c.positions.exists() and c.active for c in by.values())
    assert [c.code for c in Course.objects.all()][:2] == ["basic_life_support", "fire_safety"]   # display order


def test_validity_months_cannot_be_zero():
    c = Course(name="X", code="x", validity_months=0)
    with pytest.raises(ValidationError):
        c.full_clean()


def test_a_record_is_pending_then_counts_or_is_rejected(hr_admin):
    from tests.factories import make_employee
    e = make_employee()
    course = Course.objects.get(code="fire_safety")
    r = TrainingRecord.objects.create(employee=e, course=course, done_on=timezone.localdate(), recorded_by=hr_admin)
    assert r.pending and not r.counts and not r.rejected
    r.verified_by, r.verified_at = hr_admin, timezone.now()
    assert r.counts and not r.pending
    r.rejected_at = timezone.now()
    assert r.rejected and not r.counts and not r.pending
    assert str(r) == f"Fire safety for {e}"


def test_a_session_orders_newest_first_and_names_itself(hr_admin):
    course = Course.objects.get(code="basic_life_support")
    today = timezone.localdate()
    old = TrainingSession.objects.create(course=course, held_on=today - timedelta(days=30), recorded_by=hr_admin)
    new = TrainingSession.objects.create(course=course, held_on=today, trainer="Resus UK", recorded_by=hr_admin)
    assert list(TrainingSession.objects.all()) == [new, old]
    assert str(new) == f"Basic life support on {today:%d %b %Y}"


def test_the_app_is_an_hr_app_with_its_courses_in_the_compliance_sidebar(admin_client):
    from django.test import RequestFactory

    from accounts.backends import HR_APPS
    from hr.admin_site import navigation
    assert "training" in HR_APPS
    request = RequestFactory().get("/admin/")
    request.user = type("U", (), {"is_active": True, "is_hr_admin": True, "is_superuser": False})()
    group = next(g for g in navigation(request) if g["title"] == "Compliance")
    titles = [i["title"] for i in group["items"]]
    assert titles[:5] == ["Check types", "Checks", "Register bodies", "Registration lookups", "Files"]
    assert titles.index("Signatures") + 1 == titles.index("Courses")
    assert "Training records" in titles and "Training sessions" in titles
    assert admin_client.get("/admin/training/course/").status_code == 200


def test_courses_are_made_inactive_never_deleted(admin_client):
    c = Course.objects.get(code="chaperone")
    assert admin_client.get(f"/admin/training/course/{c.pk}/delete/").status_code == 403
    body = admin_client.get(f"/admin/training/course/{c.pk}/change/").content.decode()
    assert 'name="everyone"' in body and 'name="code"' not in body      # code is read-only once added
