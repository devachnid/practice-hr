from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from oauth2_provider.generators import generate_client_secret
from oauth2_provider.models import Application

# What every relying party of this system is: a confidential client (it keeps
# a secret on its server) using the authorization-code flow, its ID tokens
# signed RS256, consent skipped because it is a practice app the practice
# runs. Reasserted on every run, so a row edited by hand comes back to it.
FIXED = {
    "client_type": Application.CLIENT_CONFIDENTIAL,
    "authorization_grant_type": Application.GRANT_AUTHORIZATION_CODE,
    "algorithm": Application.RS256_ALGORITHM,
    "skip_authorization": True,
}


def _default_post_logout(redirect_uri):
    parts = urlsplit(redirect_uri)
    return f"{parts.scheme}://{parts.netloc}/accounts/login/"


class Command(BaseCommand):
    help = ("Register a relying party (the rota). Prints the client id and the "
            "secret once; the secret is stored hashed and cannot be shown again.")

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)
        parser.add_argument("--redirect-uri", required=True)
        parser.add_argument(
            "--post-logout-redirect-uri",
            help="Where the relying party's sign-out lands after signing out here too. "
                 "Defaults to the redirect URI's origin plus /accounts/login/.")
        parser.add_argument("--rotate", action="store_true",
                            help="Generate a new secret for an existing client.")

    def handle(self, *args, **options):
        # Only clients with no owner: the ones this command made. A client
        # registered through django-oauth-toolkit's own views would belong
        # to the person who registered it, and must never be taken over here.
        matches = list(Application.objects.filter(name=options["name"], user__isnull=True)[:2])
        if len(matches) > 1:
            raise CommandError(
                f"More than one client is named {options['name']!r}. Remove the extra one "
                "in the admin (OAuth2 Provider › Applications) and run this again.")
        app = matches[0] if matches else None
        post_logout = (options.get("post_logout_redirect_uri")
                       or _default_post_logout(options["redirect_uri"]))

        if app is None:
            secret = generate_client_secret()
            app = Application(name=options["name"], redirect_uris=options["redirect_uri"],
                              post_logout_redirect_uris=post_logout, client_secret=secret,
                              **FIXED)
            self._save(app)
            self.stdout.write(f"client_id={app.client_id}")
            self.stdout.write(f"client_secret={secret}")
            self.stdout.write("Put both in the relying party's environment file now; "
                              "the secret is not shown again.")
            return

        app.redirect_uris = options["redirect_uri"]
        app.post_logout_redirect_uris = post_logout
        for field, value in FIXED.items():
            setattr(app, field, value)

        if not options["rotate"]:
            self._save(app)
            self.stdout.write(f"client_id={app.client_id}")
            self.stdout.write("Secret unchanged; pass --rotate to generate a new one.")
            return

        secret = generate_client_secret()
        app.client_secret = secret
        self._save(app)
        self.stdout.write(f"client_id={app.client_id}")
        self.stdout.write(f"client_secret={secret}")
        self.stdout.write("Secret rotated: update the relying party's environment "
                          "before its next sign-in.")

    def _save(self, app):
        """Application.clean() checks the redirect URIs against
        ALLOWED_REDIRECT_URI_SCHEMES (https only in production), among other
        things; save() alone would store an http one without a word."""
        try:
            app.full_clean()
        except ValidationError as e:
            raise CommandError("; ".join(e.messages)) from e
        app.save()
