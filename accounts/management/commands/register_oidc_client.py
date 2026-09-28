from django.core.management.base import BaseCommand
from oauth2_provider.generators import generate_client_secret
from oauth2_provider.models import Application


class Command(BaseCommand):
    help = ("Register a relying party (the rota). Prints the client id and the "
            "secret once; the secret is stored hashed and cannot be shown again.")

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)
        parser.add_argument("--redirect-uri", required=True)
        parser.add_argument("--rotate", action="store_true",
                             help="Generate a new secret for an existing client.")

    def handle(self, *args, **options):
        app = Application.objects.filter(name=options["name"]).first()

        if app is None:
            secret = generate_client_secret()
            app = Application.objects.create(
                name=options["name"],
                redirect_uris=options["redirect_uri"],
                client_type=Application.CLIENT_CONFIDENTIAL,
                authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
                skip_authorization=True,
                algorithm="RS256",
                client_secret=secret,
            )
            self.stdout.write(f"client_id={app.client_id}")
            self.stdout.write(f"client_secret={secret}")
            self.stdout.write("Put both in the relying party's environment file now; "
                              "the secret is not shown again.")
            return

        app.redirect_uris = options["redirect_uri"]

        if not options["rotate"]:
            app.save()
            self.stdout.write(f"client_id={app.client_id}")
            self.stdout.write("Secret unchanged; pass --rotate to generate a new one.")
            return

        secret = generate_client_secret()
        app.client_secret = secret
        app.save()
        self.stdout.write(f"client_id={app.client_id}")
        self.stdout.write(f"client_secret={secret}")
        self.stdout.write("Secret rotated: update the relying party's environment "
                          "before its next sign-in.")
