import pytest
from django.contrib.auth import get_user_model
from django.test import Client

User = get_user_model()


@pytest.fixture
def hr_admin(db):
    return User.objects.create_user(email="hr@example.com", password="pw", is_hr_admin=True)


@pytest.fixture
def employee_user(db):
    return User.objects.create_user(email="sam@example.com", password="pw")


@pytest.fixture
def admin_client(hr_admin):
    c = Client()
    c.force_login(hr_admin)
    return c


@pytest.fixture
def employee_client(employee_user):
    c = Client()
    c.force_login(employee_user)
    return c


@pytest.fixture
def superuser_client(db):
    u = User.objects.create_superuser(email="root@example.com", password="pw")
    c = Client()
    c.force_login(u)
    return c


@pytest.fixture
def configured(settings):
    settings.EMAIL_HOST = "smtp.example"
    settings.DEFAULT_FROM_EMAIL = "Practice HR <hr@example.org>"
