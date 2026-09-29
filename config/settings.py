import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

import sys

# Running under pytest. Django's test runner forces DEBUG=False anyway, and the
# suite must not require a real SECRET_KEY in the environment to run.
_TESTING = "pytest" in sys.modules

# DEBUG defaults OFF. It used to default ON, which meant a deployment that
# simply forgot to set the variable came up with tracebacks, the URL map on
# every 404, no HSTS, cookies without the Secure flag, and — because the
# SECRET_KEY guard below only fires when DEBUG is off — the placeholder key
# that is published in this repository. A staging deployment did exactly that.
# Forgetting a variable must fail towards safety, so development now opts in
# with DEBUG=1 rather than production opting out with DEBUG=0.
DEBUG = os.environ.get("DEBUG", "0") == "1"

if not os.environ.get("SECRET_KEY") and not _TESTING:
    from django.core.exceptions import ImproperlyConfigured

    if not DEBUG:
        raise ImproperlyConfigured(
            "SECRET_KEY env var must be set. Generate one with:\n"
            "  python -c \"from django.core.management.utils import "
            "get_random_secret_key as k; print(k())\""
        )

def _dev_secret_key():
    """A development key private to this checkout. It was a constant,
    published in this repository, so a server that ran with DEBUG=1 and no
    SECRET_KEY had a key anyone could forge session cookies with. Now it
    is random, written once to a git-ignored file beside manage.py, and
    stable across restarts, so a dev box stays signed in."""
    path = BASE_DIR / ".dev_secret_key"
    try:
        return path.read_text().strip()
    except FileNotFoundError:
        from django.core.management.utils import get_random_secret_key
        key = get_random_secret_key()
        path.touch(mode=0o600)
        path.write_text(key)
        return key


SECRET_KEY = os.environ.get("SECRET_KEY") or (
    "test-only-key-not-used-outside-pytest" if _TESTING else _dev_secret_key()
)

ALLOWED_HOSTS = [h for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h]
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o
]

INSTALLED_APPS = [
    "unfold.apps.BasicAppConfig",   # the theme; Basic, so it does not replace admin.site
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "config.apps.HrAdminConfig",  # django.contrib.admin with our site class
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "axes",
    "oauth2_provider",
    "accounts",
    "people",
    "absence",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "config.middleware.RequestLogMiddleware",
    "config.middleware.ContentSecurityPolicyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "config.middleware.PrivatePagesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "people.context_processors.roles",
                "accounts.context_processors.signed_in_recently",
            ],
            # hr/ is admin-site wiring, not an installed app (see hr/admin_site.py's
            # own docstring), so its {% load design %} tag library needs this
            # explicit registration rather than INSTALLED_APPS discovery.
            "libraries": {"design": "hr.templatetags.design"},
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        # Production keeps the database out of the code tree, in the
        # practice-hr user's state directory (deploy/gunicorn.service):
        # SQLite needs to write the directory its database is in, and the
        # app must be able to write its data without being able to write
        # its own code. Unset, the database sits beside manage.py, which is
        # what development wants.
        "NAME": os.environ.get("DB_PATH") or BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            # WAL lets readers and the single writer proceed together.
            "init_command": "PRAGMA journal_mode=WAL;",
            # SQLite's default DEFERRED transaction only takes the write lock at
            # the first write, and if another connection (another gunicorn
            # worker) got there first it fails at once with "database is
            # locked" rather than waiting out the busy timeout. IMMEDIATE
            # takes the lock at BEGIN, so writers queue instead.
            "transaction_mode": "IMMEDIATE",
        },
    }
}

AUTH_USER_MODEL = "accounts.User"
# MinimumLengthValidator alone accepts "password" and "12345678". These four
# are Django's full set: length, similarity to the user's own email, the
# 20k-common-password list, and all-numeric.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# The address the site is served at, for links in emails. Unfold's "back to
# site" link reads the same value, so the two agree.
SITE_URL = os.environ.get("SITE_URL", "/")

# The admin's chrome. Plain values and dotted paths only — unfold resolves
# the paths per request, so hr.admin_site is never imported here.
UNFOLD = {
    "SITE_TITLE": "HR",
    "SITE_HEADER": "Practice HR",
    "SITE_URL": SITE_URL,
    "SITE_SYMBOL": "badge",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "COMMAND": {"search_models": True, "show_history": False},
    "SIDEBAR": {
        "show_search": False,
        "show_all_applications": False,
        "navigation": "hr.admin_site.navigation",
    },
    "COLORS": {
        "primary": "hr.admin_theme.primary",
        "base": "hr.admin_theme.base",
        "font": {
            "subtle-light": "var(--color-base-500)",
            "subtle-dark": "var(--color-base-400)",
            "default-light": "var(--color-base-700)",
            "default-dark": "var(--color-base-300)",
            "important-light": "var(--color-base-900)",
            "important-dark": "var(--color-base-100)",
        },
    },
    "STYLES": ["hr.admin_site.style_fonts", "hr.admin_site.style_admin"],
    "DASHBOARD_CALLBACK": "absence.admin_dashboard.dashboard",
}

# A leave request still undecided after this many working days is chased, once.
CHASE_AFTER_WORKING_DAYS = int(os.environ.get("CHASE_AFTER_WORKING_DAYS", "3"))

# How long after an employment ends each category of record may be kept, in
# days: six years, and seven for the audit trail. Each is overridable by a
# RETENTION_DAYS_<CATEGORY> environment variable. The retention report only
# lists what is past its period; nothing is deleted automatically.
def _retention_days():
    from django.core.exceptions import ImproperlyConfigured

    days = {}
    for category, default in (("personal", 2190), ("pay", 2190), ("health", 2190), ("audit", 2555)):
        name = f"RETENTION_DAYS_{category.upper()}"
        raw = os.environ.get(name)
        if raw is None:
            days[category] = default
            continue
        try:
            days[category] = int(raw)
        except ValueError:
            days[category] = 0
        if days[category] < 1:
            raise ImproperlyConfigured(
                f"{name} must be a whole number of days, 1 or more; got {raw!r}.")
    return days


RETENTION_DAYS = _retention_days()

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Europe/London"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# Files the app writes (the payroll reports). Never served by Django: the
# HR-admin-only view streams them. Production points MEDIA_ROOT into the
# state directory (/var/lib/practice-hr/media), as DB_PATH does, because the
# code tree is read-only there; backup.sh archives it.
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT") or BASE_DIR / "media")
MEDIA_URL = "media/"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # The manifest storage requires a collectstatic run, which the test suite
    # has no reason to do — keyed off _TESTING as well as DEBUG so that
    # defaulting DEBUG to off does not make every test need a build step.
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        if (DEBUG or _TESTING)
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
    "accounts.backends.HrAdminBackend",
]
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours

# Addresses whose forwarded-IP header is believed. cloudflared connects over
# loopback, and the systemd unit binds gunicorn there on purpose — see
# accounts/client_ip.py for why that binding is load-bearing.
TRUSTED_PROXY_IPS = frozenset(
    h.strip() for h in os.environ.get(
        "TRUSTED_PROXY_IPS", "127.0.0.1,::1"
    ).split(",") if h.strip()
)

# Bearer tokens for the read API the rota polls (api/). From the environment
# only, comma-separated so one can be rotated in beside another. Empty means
# the API refuses every request; hr/checks.py warns about that.
HR_API_TOKENS = frozenset(t.strip() for t in os.environ.get("HR_API_TOKENS", "").split(",") if t.strip())

# Outgoing mail: invitations and password-reset links, and nothing else.
# Standard Django keys, every one from the environment. EMAIL_HOST being set
# is what "email is configured" means (accounts/mail.py): without it every
# send becomes a link for the admin to copy, the dashboard says so, and
# `check --deploy` warns. Mailjet is plain authenticated SMTP, so nothing
# here names it. EMAIL_TIMEOUT keeps a stalled relay from holding an
# admin's save past gunicorn's worker timeout.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "webmaster@localhost")

# Links are minted ahead of a start date, so a week rather than Django's
# three days. One setting covers invitations and resets alike.
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24 * 7

# Without this axes uses REMOTE_ADDR, which behind the tunnel is always
# 127.0.0.1 — one key for every user in the world. django-ipware would also do
# it, but that is a new dependency and this project does not take those.
AXES_CLIENT_IP_CALLABLE = "accounts.client_ip.client_ip"

# Each top-level entry is an independent lockout; a nested list would be one
# combined key. So this locks a username after AXES_FAILURE_LIMIT failures
# *and, separately*, an address — the second is what stops one source
# spraying many accounts, which username-only keying cannot see.
#
# How each is counted is accounts/axes_handler.py's: an address is locked by
# failures against that many *different* accounts, and a success clears only
# the signed-in person's own failures. Staff share the practice's NAT
# address, and axes' own reset — any success there clearing every counter
# for the address — kept fumbles from locking the building out, but it also
# let anyone with an account wipe a colleague's counter and keep guessing.
AXES_HANDLER = "accounts.axes_handler.HrAxesHandler"
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
# Django's login form — and the passkey login view — report a failure as
# credentials={"username": ...} whatever USERNAME_FIELD is called; axes'
# default for this setting is USERNAME_FIELD ("email"), which never matched,
# so every attempt was recorded with username=None and only the address half
# of the lockout ever locked. Name the key the form actually sends.
AXES_USERNAME_FORM_FIELD = "username"
# ...and lower-case it, so "Tom@" and "tom@" are one name with one counter,
# as they are one account to the login lookup.
AXES_USERNAME_CALLABLE = "accounts.axes_username.axes_username"
# A success clears the person's own counter — only theirs; see AXES_HANDLER.
AXES_RESET_ON_SUCCESS = True
# A lockout lasts AXES_COOLOFF_TIME from the failure that caused it. axes'
# default restarts the hour on every attempt made while locked, which let
# anyone who knew an address keep its owner locked out indefinitely, one
# request an hour. The owner can still get in meanwhile — with a passkey,
# or a password link by email; the lockout page says so.
AXES_RESET_COOL_OFF_ON_FAILURE_DURING_LOCKOUT = False
# The page or, for the passkey endpoints, the JSON a locked-out request gets.
AXES_LOCKOUT_CALLABLE = "accounts.lockout.lockout_response"

# AccessAttempt is a counter, and a success clears it — so the admin's
# "Access attempts" can read empty minutes after real failures. The failure
# log is the permanent record; axes leaves it off by default.
AXES_ENABLE_ACCESS_FAILURE_LOG = True

# axes requires a request object during authenticate(), which the test
# client's login()/force_login() don't provide — disable it under pytest.
if _TESTING:
    AXES_ENABLED = False

# Nothing in this app reads the CSRF cookie from JavaScript — base.html feeds
# htmx the token from the template context — so it can be closed to scripts.
CSRF_COOKIE_HTTPONLY = True

if not DEBUG:
    # TLS terminates at the Cloudflare tunnel, and cloudflared says so in
    # X-Forwarded-Proto (SECURE_PROXY_SSL_HEADER below), so a request that
    # arrives as http really was http and is sent to https — whatever the
    # Cloudflare zone's own "Always Use HTTPS" happens to be set to. Not
    # under pytest: CI runs the suite with DEBUG off, over the test client's
    # plain http.
    SECURE_SSL_REDIRECT = not _TESTING
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# The Content-Security-Policy (config/middleware.py) is enforced unless
# this is set, when it is only reported — the way back, without a code
# change, if the policy blocks something it should not.
CSP_REPORT_ONLY = os.environ.get("CSP_REPORT_ONLY", "0") == "1"

# Where the app's own warnings go: stderr, which systemd sends to the
# journal (`journalctl -u practice-hr`). Without this, Django sends nothing
# there when DEBUG is off — a 500, a CSRF failure or a request with a forged
# Host header left no trace for anyone looking back at an incident.
#
# One handler, on the root logger; the named loggers only set levels and
# propagate to it. (Naming "django" here also drops Django's own console
# handler, which is DEBUG-only, and mail_admins, which ADMINS leaves idle.)
# Propagation matters beyond the journal: tests read log records through
# the root logger, and a logger that stopped propagating would pass every
# "this never appears in the log" test by logging nowhere they look.
#   django.request at ERROR: 5xx responses, with tracebacks (4xx would be
#     every scanner's 404).
#   django.security: CSRF failures, disallowed hosts, suspicious operations.
#   hr.access: one line per request (config/middleware.RequestLogMiddleware),
#     with the client address from Cloudflare.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "stderr": {"class": "logging.StreamHandler", "formatter": "plain"},
    },
    "root": {"handlers": ["stderr"], "level": "WARNING"},
    "loggers": {
        "django": {"level": "WARNING"},
        "django.request": {"level": "ERROR"},
        "django.security": {"level": "INFO"},
        "hr": {"level": "INFO"},
        "accounts": {"level": "INFO"},
        "people": {"level": "INFO"},
    },
}

# OpenID Connect provider for the practice's other apps (the rota). With no
# key the provider is off and /o/ answers 404 (config/urls.py).
#
# In production the key is a PEM file of its own, named by
# OIDC_RSA_PRIVATE_KEY_FILE in /etc/practice-hr.env and readable only by
# root and the practice-hr group (README, Deploy). It used to go in the
# environment file itself, folded onto one line with \n for each newline;
# systemd's EnvironmentFile parser turns an unquoted \n into a plain "n",
# so the key arrived unparseable. A file named but unreadable stops the app
# rather than quietly switching the provider off. OIDC_RSA_PRIVATE_KEY, the
# one-line form, is still read when no file is named — for a dev box.
# hr/checks.py fails `check --deploy` on a key that is not a PEM RSA
# private key.
def _oidc_private_key():
    path = os.environ.get("OIDC_RSA_PRIVATE_KEY_FILE", "")
    if path:
        try:
            return Path(path).read_text()
        except OSError as exc:
            from django.core.exceptions import ImproperlyConfigured
            raise ImproperlyConfigured(
                f"OIDC_RSA_PRIVATE_KEY_FILE is set but {path} cannot be read "
                f"({exc.strerror or exc}).") from None
    return os.environ.get("OIDC_RSA_PRIVATE_KEY", "").replace("\\n", "\n")


OIDC_RSA_PRIVATE_KEY = _oidc_private_key()
OAUTH2_PROVIDER = {
    "OIDC_ENABLED": bool(OIDC_RSA_PRIVATE_KEY) or _TESTING,
    "OIDC_RSA_PRIVATE_KEY": OIDC_RSA_PRIVATE_KEY,
    "SCOPES": {"openid": "Sign in", "email": "Your email address"},
    "OAUTH2_VALIDATOR_CLASS": "accounts.oidc.Validator",
    "PKCE_REQUIRED": True,
    "ACCESS_TOKEN_EXPIRE_SECONDS": 600,
    "ID_TOKEN_EXPIRE_SECONDS": 600,
    # A relying party's redirect URI is https in production; http is allowed
    # only on a dev box and in the suite, for a rota on localhost.
    "ALLOWED_REDIRECT_URI_SCHEMES": ["https"] if not DEBUG and not _TESTING else ["https", "http"],
    # django-oauth-toolkit has no setting that restricts grant types server-
    # wide: the grant a client may use is its Application row's
    # authorization_grant_type, which register_oidc_client pins to
    # authorization-code, and nothing else creates clients (config/urls.py).
    # Discovery advertises only what that client can do.
    "OIDC_RESPONSE_TYPES_SUPPORTED": ["code"],
    # RFC 9700 (OAuth 2.0 Security BCP). Every gate django-oauth-toolkit 3.4
    # offers, on: no implicit or password grant even for a client registered
    # for one, no "plain" PKCE, no access token in a query string, the iss
    # parameter on every authorization response, tokens stored hashed, and
    # refresh-token replay revoking the whole family. The last four turn
    # `check --deploy`'s warnings about the covered settings into errors, so
    # an insecure value cannot pass it.
    "COMPLIANT_BCP_RFC9700_IMPLICIT_GRANT": True,
    "COMPLIANT_BCP_RFC9700_PASSWORD_GRANT": True,
    "COMPLIANT_BCP_RFC9700_PKCE_METHOD": True,
    "COMPLIANT_BCP_RFC9700_ACCESS_TOKEN_TRANSPORT": True,
    "COMPLIANT_BCP_RFC9700_AUTHZ_RESPONSE_ISS": True,
    "COMPLIANT_BCP_RFC9700_TOKEN_STORAGE": True,
    "COMPLIANT_BCP_RFC9700_REFRESH_TOKEN": True,
    "COMPLIANT_BCP_RFC9700_REDIRECT_URI_SCHEME": True,
    "COMPLIANT_BCP_RFC9700_REDIRECT_URI_MATCHING": True,
    "COMPLIANT_BCP_RFC9700_PKCE_REQUIRED": True,
    "REFRESH_TOKEN_REUSE_PROTECTION": True,
    # Signing out of the rota signs the person out here too (the rota sends
    # them to /o/logout/ after its own logout), so the next person at a
    # shared PC is not signed straight back in as them. With the rota's
    # id_token_hint there is no "are you sure" page; without one, django-
    # oauth-toolkit asks, as the OIDC spec requires.
    "OIDC_RP_INITIATED_LOGOUT_ENABLED": True,
    "OIDC_RP_INITIATED_LOGOUT_ALWAYS_PROMPT": False,
}

# A session lasts a working day at most, and ends when the browser closes.
# Consent is skipped for the rota (register_oidc_client), so a session here
# is a session there: on a shared surgery PC, a two-week session meant the
# next person to press "Sign in with the practice account" was signed
# straight in as the last one.
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 12 * 60 * 60
