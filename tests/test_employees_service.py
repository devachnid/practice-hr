from people.models import AuditEntry
from people.services import employees
from tests.factories import make_employee


def test_create_audits_creation(hr_admin):
    e = employees.create(hr_admin, first_name="Ada", last_name="Lovelace", work_email="ada@example.org")
    assert e.pk
    row = AuditEntry.objects.get(model="people.employee", object_id=e.pk)
    assert row.field == "created" and row.after == "Ada Lovelace"


def test_update_audits_only_changed_fields(hr_admin):
    e = make_employee()
    employees.update(hr_admin, e, phone="0113", town="")
    rows = AuditEntry.objects.filter(model="people.employee", object_id=e.pk, kind="change")
    assert [r.field for r in rows] == ["phone"]
    e.refresh_from_db()
    assert e.phone == "0113"


def test_update_refuses_unknown_field(hr_admin):
    e = make_employee()
    import pytest
    with pytest.raises(ValueError):
        employees.update(hr_admin, e, salary=1)
