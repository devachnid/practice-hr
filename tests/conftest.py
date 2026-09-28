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


@pytest.fixture(scope="session", autouse=True)
def _oidc_test_key():
    """The suite signs ID tokens with a throwaway key generated per run.
    Nothing here reaches the environment."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from django.conf import settings
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    settings.OAUTH2_PROVIDER["OIDC_RSA_PRIVATE_KEY"] = pem
    from oauth2_provider import settings as oauth2_settings
    oauth2_settings.oauth2_settings.OIDC_RSA_PRIVATE_KEY = pem
