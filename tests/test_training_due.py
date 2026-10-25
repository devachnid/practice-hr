from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from compliance.models import ReminderSchedule
from compliance.services import digest
from people.services import employments, titles
from tests.factories import make_employee, make_employment, make_position
from training.models import Course
from training.services import due, training

pytestmark = pytest.mark.django_db
User = get_user_model()
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def fire():
    c = Course.objects.get(code="fire_safety")
    c.positions.add(titles.get_or_create("Receptionist"))
    return c


@pytest.fixture
def bls():
    c = Course.objects.get(code="basic_life_support")
    c.everyone = True
    c.save()
    return c


def _manager():
    m = make_employee(first="Mo", last="Khan", user=User.objects.create_user(email="mo@example.com", password="pw"))
    make_employment(m, start=timezone.localdate() - timedelta(days=800))
    return m


def _receptionist(user=None, manager=None):
    e = make_employee(user=user)
    emp = make_employment(e, start=timezone.localdate() - timedelta(days=400))
    make_position(emp, title="Receptionist", manager=manager)
    return e


def _items(today=None):
    return due.due_items(today or timezone.localdate(), ReminderSchedule.get())


def test_a_missing_course_goes_to_hr_and_the_person_from_the_start_date(fire, hr_admin, employee_user):
    e = _receptionist(user=employee_user)
    start = employments.current(e, timezone.localdate()).start_date
    items = _items()
    by = {i.recipient: i for i in items}
    assert set(by) == {"hr@example.com", "sam@example.com"}
    hr_item, own = by["hr@example.com"], by["sam@example.com"]
    assert hr_item.kind == "training" and hr_item.label == "Fire safety" and hr_item.state == "missing"
    assert hr_item.due_on == start and hr_item.key == f"training:{e.pk}:fire_safety:{start.isoformat()}:missing"
    assert hr_item.url.endswith(f"/training/{e.pk}/") and hr_item.once is False
    assert own.label == "Fire safety: complete the e-learning and upload your certificate"
    assert own.url.endswith("/people/me/") and own.key == hr_item.key


def test_due_soon_lapsed_and_the_manager_once_naming_the_course(fire, hr_admin, employee_user):
    today = timezone.localdate()
    m = _manager()
    e = _receptionist(user=employee_user, manager=m)
    r = training.record(hr_admin, e, fire, today - timedelta(days=350), upload=SimpleUploadedFile("c.pdf", PDF))
    items = _items()
    assert {i.recipient for i in items} == {"hr@example.com", "sam@example.com"}       # not the manager yet
    assert all(i.state == "due_soon" and i.due_on == r.expires_on for i in items)
    assert all(i.key == f"training:{e.pk}:fire_safety:{r.expires_on.isoformat()}:due_soon" for i in items)
    training.set_expiry(hr_admin, r, today - timedelta(days=1))
    items = _items()
    by = {i.recipient: i for i in items}
    assert set(by) == {"hr@example.com", "sam@example.com", "mo@example.com"}
    assert by["hr@example.com"].state == "lapsed" and by["hr@example.com"].due_on == today - timedelta(days=1)
    mgr = by["mo@example.com"]
    assert mgr.label == "Fire safety has lapsed" and mgr.once is True and mgr.url.endswith("/people/team/")
    assert mgr.key == by["hr@example.com"].key


def test_a_face_to_face_course_asks_about_the_next_session(bls, hr_admin, employee_user):
    _receptionist(user=employee_user)
    [own] = [i for i in _items() if i.recipient == "sam@example.com"]
    assert own.label == "Basic life support: ask your manager about the next session"


def test_a_pending_record_silences_the_person_and_asks_hr_to_verify(fire, hr_admin, employee_user):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    p = training.self_record(employee_user, fire, today - timedelta(days=2), upload=SimpleUploadedFile("c.pdf", PDF))
    [item] = _items()
    assert item.recipient == "hr@example.com" and item.state == "to_verify"
    assert item.label == "Fire safety: to verify" and item.key == f"training:verify:{p.pk}"
    assert item.due_on == timezone.localtime(p.recorded_at).date() and item.url.endswith(f"/training/{e.pk}/")
    assert digest._when(item) == f"uploaded {item.due_on:%-d %b %Y}"
    training.verify(hr_admin, p)
    assert _items() == []                                                 # current: nothing to say


def test_a_leaver_and_a_not_required_course_produce_nothing(fire, hr_admin, employee_user):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    assert len(_items()) == 2
    fire.positions.clear()
    assert _items() == []
    fire.positions.add(titles.get_or_create("Receptionist"))
    emp = employments.current(e, today)
    emp.end_date = today - timedelta(days=1)
    emp.save()
    assert _items() == []


def test_the_window_is_the_schedules_and_the_digest_carries_training_lines(fire, hr_admin, employee_user, configured):
    today = timezone.localdate()
    e = _receptionist(user=employee_user)
    training.record(hr_admin, e, fire, today - timedelta(days=300), upload=SimpleUploadedFile("c.pdf", PDF))
    sched = ReminderSchedule.get()
    assert due.due_items(today, sched) == []                              # 65 days out, window 60
    sched.start_days_before = 90
    sched.save()
    assert {i.state for i in due.due_items(today, sched)} == {"due_soon"}
    out = digest.run(today)
    assert out["reminders_sent"] == 2
    body = next(m for m in mail.outbox if m.to == ["sam@example.com"]).body
    assert "Fire safety: complete the e-learning and upload your certificate: due" in body


def test_training_has_its_own_retention_category(settings, admin_client, hr_admin):
    assert settings.RETENTION_DAYS["training"] == 2190
    from people.views import CATEGORY_LABELS
    assert CATEGORY_LABELS["training"] == "Training records"
