import pytest
from django.core.exceptions import ValidationError

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


def test_audit_rows_are_immutable(hr_admin):
    e = make_employee()
    row = audit.viewed(hr_admin, e, "pay")
    row.field = "health"
    with pytest.raises(ValidationError):
        row.save()
    with pytest.raises(ValidationError):
        row.delete()


# --- who did it survives (review I5) ----------------------------------------------

def test_the_actors_email_is_kept_as_text(hr_admin):
    e = make_employee()
    (row,) = audit.record(hr_admin, e, {"phone": ("", "0113")})
    assert row.actor_email == "hr@example.com"
    assert audit.viewed(hr_admin, e, "pay").actor_email == "hr@example.com"
    hr_admin.email = "renamed@example.com"
    hr_admin.save()
    assert AuditEntry.objects.get(pk=row.pk).actor_email == "hr@example.com"


def test_a_login_with_audit_rows_cannot_be_deleted(hr_admin):
    from django.db.models import ProtectedError
    audit.record(hr_admin, make_employee(), {"phone": ("", "0113")})
    with pytest.raises(ProtectedError):
        hr_admin.delete()
    assert AuditEntry.objects.get().actor == hr_admin


def test_not_even_a_superuser_through_the_admin(superuser_client, hr_admin):
    audit.record(hr_admin, make_employee(), {"phone": ("", "0113")})
    r = superuser_client.post(f"/admin/accounts/user/{hr_admin.pk}/delete/", {"post": "yes"})
    assert r.status_code == 200          # Django's "cannot delete: protected" page
    assert type(hr_admin).objects.filter(pk=hr_admin.pk).exists()


def test_the_audit_list_shows_the_actors_email(admin_client, hr_admin):
    audit.record(hr_admin, make_employee(), {"phone": ("", "0113")})
    assert "hr@example.com" in admin_client.get("/admin/people/auditentry/").content.decode()


def test_the_migration_backfills_existing_rows(hr_admin):
    import importlib

    from django.apps import apps as global_apps
    (row,) = audit.record(hr_admin, make_employee(), {"phone": ("", "0113")})
    AuditEntry.objects.filter(pk=row.pk).update(actor_email="")
    importlib.import_module("people.migrations.0009_auditentry_actor_email").backfill(global_apps, None)
    assert AuditEntry.objects.get(pk=row.pk).actor_email == "hr@example.com"


# --- who may delete a login (the rota's fa07084) -----------------------------------

def test_an_hr_admin_cannot_delete_a_login(admin_client, employee_user):
    """Deactivating does everything deleting is for and keeps the history."""
    User = type(employee_user)
    assert admin_client.get(f"/admin/accounts/user/{employee_user.pk}/delete/").status_code == 403
    admin_client.post("/admin/accounts/user/", {
        "action": "delete_selected", "_selected_action": [employee_user.pk], "post": "yes"})
    assert User.objects.filter(pk=employee_user.pk).exists()
    assert "delete_selected" not in admin_client.get("/admin/accounts/user/").content.decode()


def test_a_superuser_still_can(superuser_client, employee_user):
    r = superuser_client.post(f"/admin/accounts/user/{employee_user.pk}/delete/", {"post": "yes"})
    assert r.status_code == 302
    assert not type(employee_user).objects.filter(pk=employee_user.pk).exists()
