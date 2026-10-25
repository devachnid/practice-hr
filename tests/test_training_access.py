from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from documents.models import File
from documents.services import files
from people.services import access
from tests.factories import make_employee, make_employment, make_position
from training.models import Course, TrainingRecord, TrainingSession

pytestmark = pytest.mark.django_db
User = get_user_model()
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


def _user(email):
    return User.objects.create_user(email=email, password="pw")


def _cast():
    """A person with a login, their manager (with a login), and a bystander (with a login)."""
    person = make_employee(user=_user("sam@example.com"))
    manager = make_employee(first="Mo", last="Khan", user=_user("mo@example.com"))
    other = make_employee(first="Jo", last="Bloggs", user=_user("jo@example.com"))
    today = timezone.localdate()
    make_position(make_employment(person, start=today - timedelta(days=400)), manager=manager)
    make_employment(manager, start=today - timedelta(days=800))
    make_employment(other, start=today - timedelta(days=800))
    return person, manager, other


def test_can_view_training_is_hr_the_person_and_their_manager(hr_admin):
    person, manager, other = _cast()
    assert access.can_view_training(hr_admin, person)
    assert access.can_view_training(person.user, person)
    assert access.can_view_training(manager.user, person)
    assert not access.can_view_training(other.user, person)
    assert not access.can_view_training(person.user, manager)


def test_may_record_training_for_is_hr_or_the_manager_never_yourself(hr_admin):
    person, manager, other = _cast()
    today = timezone.localdate()
    assert access.may_record_training_for(hr_admin, person, today)
    assert access.may_record_training_for(manager.user, person, today)
    assert not access.may_record_training_for(other.user, person, today)
    assert not access.may_record_training_for(person.user, person, today)        # that is self_record
    assert not access.may_record_training_for(manager.user, manager, today)
    # HR records their own training, as HR records their own checks today
    me = make_employee(first="Pat", last="Rees", user=hr_admin)
    make_employment(me, start=today - timedelta(days=10))
    assert access.may_record_training_for(hr_admin, me, today)
    # the manager of record on another day
    assert not access.may_record_training_for(manager.user, person, today - timedelta(days=500))


def test_may_verify_follows_may_record_for_the_records_person(hr_admin):
    person, manager, other = _cast()
    r = TrainingRecord.objects.create(employee=person, course=Course.objects.get(code="fire_safety"),
                                      done_on=timezone.localdate(), recorded_by=person.user)
    assert access.may_verify(hr_admin, r) and access.may_verify(manager.user, r)
    assert not access.may_verify(other.user, r) and not access.may_verify(person.user, r)


def test_a_certificate_opens_for_the_manager_a_contract_does_not(hr_admin):
    person, manager, other = _cast()
    cert = files.add(hr_admin, person, File.Category.CERTIFICATE, "Fire safety certificate",
                     SimpleUploadedFile("c.pdf", PDF))
    TrainingRecord.objects.create(employee=person, course=Course.objects.get(code="fire_safety"),
                                  done_on=timezone.localdate(), certificate=cert, recorded_by=hr_admin,
                                  verified_by=hr_admin, verified_at=timezone.now())
    plain = files.add(hr_admin, person, File.Category.CERTIFICATE, "Some other certificate",
                      SimpleUploadedFile("d.pdf", PDF))
    assert access.can_view_file(manager.user, cert)
    assert not access.can_view_file(manager.user, plain)          # a certificate not on a training record
    assert not access.can_view_file(other.user, cert)
    assert access.can_view_file(person.user, cert) and access.can_view_file(hr_admin, cert)


def test_an_attendance_sheet_opens_for_hr_and_a_manager_with_a_report_on_it(hr_admin):
    person, manager, other = _cast()
    sheet = files.add(hr_admin, None, File.Category.CERTIFICATE, "BLS attendance sheet",
                      SimpleUploadedFile("s.pdf", PDF))
    session = TrainingSession.objects.create(course=Course.objects.get(code="basic_life_support"),
                                             held_on=timezone.localdate(), attendance_sheet=sheet,
                                             recorded_by=hr_admin)
    assert access.can_view_file(hr_admin, sheet)
    assert not access.can_view_file(manager.user, sheet)            # nobody of theirs on it yet
    TrainingRecord.objects.create(employee=person, course=session.course, done_on=session.held_on,
                                  session=session, recorded_by=hr_admin, verified_by=hr_admin,
                                  verified_at=timezone.now())
    assert access.can_view_file(manager.user, sheet)
    assert not access.can_view_file(other.user, sheet)
    assert not access.can_view_file(person.user, sheet)             # the sheet is not the person's file
