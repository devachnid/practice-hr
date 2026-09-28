"""The project's own system checks, registered in AccountsConfig.ready()."""

from django.conf import settings
from django.core import checks


def oidc_signing_key(app_configs, **kwargs):
    """With the OpenID Connect provider on, its signing key must be a PEM RSA
    private key. A key mangled on its way in — systemd's EnvironmentFile
    parser turns an unquoted \\n into "n" — otherwise switches the provider
    on and fails at the first sign-in, as an error in the rota."""
    provider = getattr(settings, "OAUTH2_PROVIDER", {})
    if not provider.get("OIDC_ENABLED"):
        return []
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    key = provider.get("OIDC_RSA_PRIVATE_KEY", "")
    try:
        parsed = load_pem_private_key(key.encode(), password=None)
    except (TypeError, ValueError):
        parsed = None
    if isinstance(parsed, RSAPrivateKey):
        return []
    return [checks.Error(
        "The OpenID Connect signing key is not a PEM RSA private key.",
        hint="Put the output of `openssl genrsa 2048` in the file OIDC_RSA_PRIVATE_KEY_FILE "
             "names (README, Deploy), unencrypted, as it is.",
        id="hr.E001",
    )]


def api_tokens(app_configs, **kwargs):
    """The read API (api/) answers 401 to everyone while HR_API_TOKENS is
    empty, so a deployment that forgot it looks fine here and the rota's
    polling fails there. Not an error: an installation may run without the
    rota."""
    if settings.DEBUG or settings.HR_API_TOKENS:
        return []
    return [checks.Warning(
        "HR_API_TOKENS is empty, so the read API refuses every request.",
        hint="Set HR_API_TOKENS in /etc/practice-hr.env to the token the rota sends "
             "(comma-separated for more than one), and restart.",
        id="hr.W001",
    )]
