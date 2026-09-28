from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        from django.core import checks

        from hr.checks import oidc_signing_key
        checks.register(oidc_signing_key, checks.Tags.security, deploy=True)
