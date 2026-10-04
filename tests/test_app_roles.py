"""A login's role in each app this system signs people in to (the rota):
the AppRole row, and the Apps fieldset on the Login accounts page that
writes it."""
import re

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from oauth2_provider.models import Application

from accounts.models import AppRole

User = get_user_model()


def _client(name="rota", **kw):
    return Application.objects.create(
        name=name, redirect_uris=f"https://{name}.example/cb/",
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE, **kw)


def test_a_role_reads_as_who_on_what(employee_user):
    rota = _client()
    role = AppRole.objects.create(user=employee_user, application=rota, is_admin=True)
    assert str(role) == "sam@example.com on rota: admin"
    role.is_admin = False
    assert str(role) == "sam@example.com on rota: user"


def test_one_role_per_login_per_app(employee_user):
    rota = _client()
    AppRole.objects.create(user=employee_user, application=rota)
    with pytest.raises(IntegrityError):
        AppRole.objects.create(user=employee_user, application=rota, is_admin=True)


def test_the_roles_go_with_the_login_and_with_the_app(employee_user, hr_admin):
    rota, other = _client(), _client("other")
    AppRole.objects.create(user=employee_user, application=rota)
    AppRole.objects.create(user=hr_admin, application=other)
    employee_user.delete()
    other.delete()
    assert not AppRole.objects.exists()


# --- the Apps fieldset on the Login accounts page ----------------------------------

HELP = ("Whether this login is an admin of that app. Access to the app itself needs "
        "only an active login here.")


def _url(user):
    return f"/admin/accounts/user/{user.pk}/change/"


def _apps_heading(body):
    """Where the Apps fieldset's heading is on the page, or -1."""
    m = re.search(r">\s*Apps\s*</h2>", body)
    return m.start() if m else -1


def _ticked(client, user, app):
    """What the page's box for `app` shows, read from the rendered form."""
    return client.get(_url(user)).context["adminform"].form[f"app_admin_{app.pk}"].value()


def _save(client, user, *ticked):
    data = {"email": user.email, "is_active": "on", "_save": "Save",
            "passkeys-TOTAL_FORMS": 0, "passkeys-INITIAL_FORMS": 0,
            "passkeys-MIN_NUM_FORMS": 0, "passkeys-MAX_NUM_FORMS": 1000}
    if user.is_hr_admin:
        data["is_hr_admin"] = "on"
    data.update({f"app_admin_{app.pk}": "on" for app in ticked})
    r = client.post(_url(user), data)
    assert r.status_code == 302, r.content.decode()[:2000]


def test_with_no_registered_client_there_is_no_apps_fieldset(admin_client, employee_user):
    _client("theirs", user=employee_user)  # owned by someone: not one of ours
    body = admin_client.get(_url(employee_user)).content.decode()
    assert _apps_heading(body) == -1 and "Admin of" not in body and "app_admin_" not in body


def test_each_registered_client_has_its_own_box_after_hr_admin(admin_client, employee_user):
    _client("rota")
    _client("other")
    _client("theirs", user=employee_user)
    body = admin_client.get(_url(employee_user)).content.decode()
    assert "Admin of other" in body and "Admin of rota" in body and "Admin of theirs" not in body
    assert body.index("HR admin") < _apps_heading(body) < body.index("Admin of other") \
        < body.index("Admin of rota")
    assert HELP in body


def test_the_add_page_has_no_apps_fieldset(admin_client):
    _client("rota")
    body = admin_client.get("/admin/accounts/user/add/").content.decode()
    assert "Admin of rota" not in body and _apps_heading(body) == -1


def test_an_unticked_box_with_no_role_makes_no_row(admin_client, employee_user):
    _client("rota")
    _save(admin_client, employee_user)
    assert not AppRole.objects.exists()


def test_ticking_makes_them_an_admin_and_unticking_keeps_the_row_as_a_user(admin_client, employee_user):
    rota, other = _client("rota"), _client("other")
    assert _ticked(admin_client, employee_user, rota) is False
    _save(admin_client, employee_user, rota)
    assert AppRole.objects.get(user=employee_user, application=rota).is_admin
    assert not AppRole.objects.filter(application=other).exists()
    assert _ticked(admin_client, employee_user, rota) is True
    _save(admin_client, employee_user)
    assert not AppRole.objects.get(user=employee_user, application=rota).is_admin
    assert _ticked(admin_client, employee_user, rota) is False
    assert AppRole.objects.count() == 1


def test_an_existing_user_role_is_ticked_to_admin(admin_client, employee_user):
    rota = _client()
    AppRole.objects.create(user=employee_user, application=rota, is_admin=False)
    _save(admin_client, employee_user, rota)
    assert AppRole.objects.get(user=employee_user, application=rota).is_admin
    assert AppRole.objects.count() == 1


def test_a_superuser_can_set_it_too_and_an_hr_admin_never_reaches_a_superusers(
        superuser_client, admin_client, employee_user):
    rota = _client()
    root = User.objects.get(email="root@example.com")
    _save(superuser_client, employee_user, rota)
    assert AppRole.objects.get(user=employee_user).is_admin
    assert admin_client.get(_url(root)).status_code == 403
    r = admin_client.post(_url(root), {"email": root.email, f"app_admin_{rota.pk}": "on"})
    assert r.status_code == 403
    assert not AppRole.objects.filter(user=root).exists()


def test_the_list_shows_who_is_an_admin_of_what(admin_client, employee_user, hr_admin):
    rota = _client()
    AppRole.objects.create(user=employee_user, application=rota, is_admin=True)
    AppRole.objects.create(user=hr_admin, application=rota, is_admin=False)
    nobody = User.objects.create_user(email="new@example.com")
    r = admin_client.get("/admin/accounts/user/")
    cl = r.context["cl"]
    apps = {u.email: cl.model_admin.apps(u) for u in cl.result_list}
    assert apps == {"sam@example.com": "rota (admin)", "hr@example.com": "rota", nobody.email: ""}
    assert "rota (admin)" in r.content.decode()


def test_the_form_builds_when_django_passes_no_field_list(rf, hr_admin, employee_user):
    """Django's own _get_form_for_get_fields passes fields=None."""
    from django.contrib import admin as django_admin
    _client()
    request = rf.get("/")
    request.user = hr_admin
    model_admin = django_admin.site._registry[User]
    form = model_admin.get_form(request, employee_user, fields=None)
    assert form._meta.fields and not any(f.startswith("app_admin_") for f in form._meta.fields)
