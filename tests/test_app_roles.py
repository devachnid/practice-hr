"""A login's role in each app this system signs people in to (the rota):
the AppRole row, and the Apps fieldset on the Login accounts page that
writes it."""
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
