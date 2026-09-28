from people.models import AuditEntry
from people.services import audit
from tests.factories import make_employee


def test_record_writes_one_row_per_field(hr_admin):
    e = make_employee()
    rows = audit.record(hr_admin, e, {"phone": ("", "0113"), "town": ("", "Leeds")}, note="edit")
    assert len(rows) == 2
    row = AuditEntry.objects.get(field="phone")
    assert row.kind == AuditEntry.Kind.CHANGE
    assert (row.model, row.object_id, row.before, row.after, row.note) == ("people.employee", e.pk, "", "0113", "edit")
    assert row.actor == hr_admin


def test_record_skips_unchanged_fields(hr_admin):
    e = make_employee()
    assert audit.record(hr_admin, e, {"phone": ("x", "x")}) == []


def test_viewed_writes_a_viewed_row(hr_admin):
    e = make_employee()
    row = audit.viewed(hr_admin, e, "pay")
    assert row.kind == AuditEntry.Kind.VIEWED and row.field == "pay"
