from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        from django.contrib.auth.signals import user_logged_in
        from django.core import checks

        from .recent_auth import on_login
        user_logged_in.connect(on_login, dispatch_uid="accounts.recent_auth")

        from hr.checks import oidc_signing_key
        checks.register(oidc_signing_key, checks.Tags.security, deploy=True)
