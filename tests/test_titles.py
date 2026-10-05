import pytest
from django.db import IntegrityError

from people.models import Position, PositionTitle
from people.services import titles
from tests.factories import make_employment, make_position

pytestmark = pytest.mark.django_db


def test_a_title_is_a_row_and_a_position_points_at_it():
    pos = make_position(make_employment(), title="Practice Nurse")
    assert isinstance(pos.title, PositionTitle)
    assert pos.title.name == "Practice Nurse"
    assert PositionTitle.objects.filter(name="Practice Nurse").count() == 1


def test_get_or_create_is_case_sensitive_and_unique():
    t1 = titles.get_or_create("Receptionist")
    t2 = titles.get_or_create("Receptionist")
    assert t1.pk == t2.pk
    with pytest.raises(IntegrityError):
        PositionTitle.objects.create(name="Receptionist")


def test_renaming_a_title_moves_every_position_with_it():
    pos = make_position(make_employment(), title="Receptionist")
    title = pos.title
    title.name = "Patient Services Advisor"
    title.save()
    pos.refresh_from_db()
    assert pos.title.name == "Patient Services Advisor"
    assert Position.objects.filter(title=title).count() == 1


def test_the_api_still_sends_the_title_as_text(client, settings):
    settings.HR_API_TOKENS = ["t"]
    pos = make_position(make_employment(), title="Receptionist")
    r = client.get("/api/v1/people", HTTP_AUTHORIZATION="Bearer t")
    assert r.status_code == 200
    assert r.json()["people"][0]["positions"][0]["title"] == "Receptionist"
    assert pos.title.name == "Receptionist"


@pytest.mark.django_db(transaction=True)
def test_the_migration_turns_title_text_into_rows_and_back():
    from datetime import date

    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    def migrate(targets):
        executor = MigrationExecutor(connection)
        executor.migrate(targets)
        return executor.loader.project_state(targets).apps

    before = [("people", "0012_employee_work_email_help_text_rota_api")]
    leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
    try:
        old = migrate(before)
        Employee, Employment = old.get_model("people", "Employee"), old.get_model("people", "Employment")
        Team, OldPosition = old.get_model("people", "Team"), old.get_model("people", "Position")
        team = Team.objects.create(name="Reception")
        emp = Employment.objects.create(
            employee=Employee.objects.create(
                first_name="Sam", last_name="Patel", work_email="sam.patel@example.org"),
            start_date=date(2026, 4, 6), continuous_service_date=date(2026, 4, 6))
        for name in ("Receptionist", "Practice Nurse", "Receptionist"):
            OldPosition.objects.create(employment=emp, title=name, team=team, primary=False,
                                       from_date=date(2026, 4, 6))

        new = migrate([("people", "0013_positiontitle")])
        Title, NewPosition = new.get_model("people", "PositionTitle"), new.get_model("people", "Position")
        assert list(Title.objects.order_by("name").values_list("name", "display_order")) == [
            ("Practice Nurse", 100), ("Receptionist", 100)]
        assert sorted(NewPosition.objects.values_list("title__name", flat=True)) == [
            "Practice Nurse", "Receptionist", "Receptionist"]

        old = migrate(before)
        assert sorted(old.get_model("people", "Position").objects.values_list("title", flat=True)) == [
            "Practice Nurse", "Receptionist", "Receptionist"]
    finally:
        migrate(leaves)
