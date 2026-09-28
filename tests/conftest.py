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


@pytest.fixture(autouse=True)
def no_seeded_policies(request):
    """The absence migration seeds an AL policy per contract type. Tests build their own,
    so those rows (and their tiers, by cascade) are cleared before each test that uses the
    database, unless it is marked `seeded_policies`. Tests that never touch the database
    (test_settings, test_deploy) are left alone: the `db` fixture is only pulled in when
    the test already asks for it, directly or through the `django_db` marker."""
    if request.node.get_closest_marker("seeded_policies"):
        return
    if "db" in request.fixturenames or request.node.get_closest_marker("django_db"):
        request.getfixturevalue("db")
        from absence.models import Policy
        Policy.objects.all().delete()
