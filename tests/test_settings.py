from django.conf import settings


def test_project_apps_present():
    for app in ("accounts", "people", "axes", "oauth2_provider"):
        assert app in settings.INSTALLED_APPS


def test_user_model_and_redirects():
    assert settings.AUTH_USER_MODEL == "accounts.User"
    assert settings.LOGIN_URL == "/accounts/login/"
    assert settings.LOGIN_REDIRECT_URL == "/"


def test_no_breathe_settings_survived():
    assert not hasattr(settings, "BREATHE_API_KEY")
