from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        from django.contrib.auth.signals import user_logged_in
        from django.core import checks

        from .recent_auth import on_login
        user_logged_in.connect(on_login, dispatch_uid="accounts.recent_auth")

        from hr.checks import api_tokens, oidc_signing_key, site_url
        checks.register(oidc_signing_key, checks.Tags.security, deploy=True)
        checks.register(api_tokens, checks.Tags.security, deploy=True)
        checks.register(site_url, checks.Tags.security, deploy=True)
