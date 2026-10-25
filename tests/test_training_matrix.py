import csv
import io
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from people.services import titles
from tests.factories import make_employee, make_employment, make_position, make_team
from training.models import Course
from training.services import matrix, training

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def courses():
    fire = Course.objects.get(code="fire_safety")
    fire.positions.add(titles.get_or_create("Receptionist"))
    bls = Course.objects.get(code="basic_life_support")
    bls.everyone = True
    bls.save()
    return fire, bls


def _people(hr_admin):
    """Two receptionists in Reception, a nurse in Nursing, and a leaver."""
    today = timezone.localdate()
    reception, nursing = make_team(name="Reception"), make_team(name="Nursing")
    out = {}
    for first, last, title, team in (("Sam", "Patel", "Receptionist", reception),
                                     ("Ann", "Brown", "Receptionist", reception),
                                     ("Nia", "Evans", "Practice Nurse", nursing)):
        e = make_employee(first=first, last=last)
        make_position(make_employment(e, start=today - timedelta(days=400)), title=title, team=team)
        out[first] = e
    leaver = make_employee(first="Old", last="Hand")
    make_position(make_employment(leaver, start=today - timedelta(days=900), end_date=today - timedelta(days=1)),
                  title="Receptionist", team=reception)
    return out, reception, nursing


def test_the_matrix_has_people_down_and_needed_or_held_courses_across(courses, hr_admin):
    fire, bls = courses
    people, reception, nursing = _people(hr_admin)
    today = timezone.localdate()
    training.record(hr_admin, people["Nia"], fire, today - timedelta(days=5), upload=SimpleUploadedFile("c.pdf", PDF))
    m = matrix.build(today)
    assert [e.employee.name for e in m.rows] == ["Ann Brown", "Nia Evans", "Sam Patel"]        # no leaver
    assert [c.code for c in m.courses] == ["basic_life_support", "fire_safety"]
    nia = next(e for e in m.rows if e.employee == people["Nia"])
    assert nia.cells[fire.pk].status == "not_required" and nia.cells[bls.pk].status == "missing"
    sam = next(e for e in m.rows if e.employee == people["Sam"])
    assert sam.cells[fire.pk].status == "missing" and bls.pk in sam.cells


def test_filters_by_course_team_and_name(courses, hr_admin):
    fire, bls = courses
    people, reception, nursing = _people(hr_admin)
    today = timezone.localdate()
    m = matrix.build(today, team=nursing)
    assert [e.employee.first_name for e in m.rows] == ["Nia"]
    m = matrix.build(today, course=fire)
    assert [c.code for c in m.courses] == ["fire_safety"]
    assert [e.employee.first_name for e in m.rows] == ["Ann", "Nia", "Sam"]
    assert m.rows[1].cells == {}                                        # Nia neither needs nor has it: an empty cell
    m = matrix.build(today, query="pat")
    assert [e.employee.first_name for e in m.rows] == ["Sam"]
    m = matrix.build(today, query="nobody")
    assert m.rows == [] and m.courses == []
    assert matrix.build(today, query="nobody", course=fire).courses == [fire]


def test_problems_only_and_to_verify(courses, hr_admin):
    fire, bls = courses
    people, reception, nursing = _people(hr_admin)
    today = timezone.localdate()
    from django.contrib.auth import get_user_model
    user = get_user_model().objects.create_user(email="ann@example.com", password="pw")
    people["Ann"].user = user
    people["Ann"].save()
    for e in people.values():
        training.record(hr_admin, e, bls, today - timedelta(days=5))
    training.record(hr_admin, people["Sam"], fire, today - timedelta(days=5), upload=SimpleUploadedFile("c.pdf", PDF))
    pending = training.self_record(user, fire, today, upload=SimpleUploadedFile("c.pdf", PDF))
    dee = make_employee(first="Dee", last="Young")                            # 12 months, done 350 days ago: due soon
    make_position(make_employment(dee, start=today - timedelta(days=400)), title="Practice Nurse", team=nursing)
    training.record(hr_admin, dee, bls, today - timedelta(days=350))
    assert matrix.build(today).rows[-1].cells[bls.pk].status == "due_soon"
    m = matrix.build(today, show="problems")
    assert [e.employee.first_name for e in m.rows] == ["Ann"]                 # Sam and Nia have nothing wrong, Dee is only due soon
    assert [c.code for c in m.courses] == ["fire_safety"]
    assert m.rows[0].cells[fire.pk].status == "awaiting_verification" and m.rows[0].cells[fire.pk].pending == pending
    m = matrix.build(today, show="to_verify")
    assert [e.employee.first_name for e in m.rows] == ["Ann"]
    training.verify(hr_admin, pending)
    assert matrix.build(today, show="problems").rows == [] and matrix.build(today, show="to_verify").rows == []


def test_the_csv_does_not_let_a_cell_run_as_a_formula(courses, hr_admin):
    fire, bls = courses
    e = make_employee(first="Sam", last="Patel", preferred_name="=SUM(1)")
    today = timezone.localdate()
    make_position(make_employment(e, start=today - timedelta(days=400)), title="Practice Nurse", team=make_team(name="Reception"))
    rows = list(csv.reader(io.StringIO(matrix.to_csv(matrix.build(today)))))
    assert rows[1][0].startswith("'=") and rows[1][0] == "'" + e.name
    bls.name = "+Basic life support"
    bls.save()
    rows = list(csv.reader(io.StringIO(matrix.to_csv(matrix.build(today)))))
    assert rows[0][1] == "'+Basic life support"


def test_the_query_count_does_not_grow_with_the_practice(courses, hr_admin, django_assert_max_num_queries):
    people, reception, nursing = _people(hr_admin)
    today = timezone.localdate()
    for i in range(12):
        e = make_employee(first=f"P{i}", last="Many")
        make_position(make_employment(e, start=today - timedelta(days=100)), title="Receptionist", team=reception)
    with django_assert_max_num_queries(8):
        m = matrix.build(today)
    assert len(m.rows) == 15


def test_the_csv_quotes_names_and_carries_no_note(courses, hr_admin):
    fire, bls = courses
    people, reception, nursing = _people(hr_admin)
    today = timezone.localdate()
    fire.name = "Fire safety, awareness"
    fire.save()
    r = training.record(hr_admin, people["Sam"], fire, today - timedelta(days=5), note="HR ONLY NOTE",
                        upload=SimpleUploadedFile("c.pdf", PDF))
    text = matrix.to_csv(matrix.build(today))
    assert "HR ONLY NOTE" not in text
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0] == ["Person", "Basic life support", "Fire safety, awareness"]
    sam = next(row for row in rows if row[0] == "Sam Patel")
    assert sam[1] == "Missing" and sam[2] == f"Current, {r.expires_on:%d %b %Y}"
    nia = next(row for row in rows if row[0] == "Nia Evans")
    assert nia[2] == ""                                                 # neither needs nor has it: an empty cell
    assert matrix.filename(today) == f"training-matrix-{today.isoformat()}.csv"
    assert matrix.filename(today, course=fire, team=reception, query="Sam P", show="problems") == \
        f"training-matrix-fire_safety-reception-sam-p-problems-{today.isoformat()}.csv"
