from django.core.management.base import BaseCommand
from oauth2_provider.generators import generate_client_secret
from oauth2_provider.models import Application


class Command(BaseCommand):
    help = ("Register a relying party (the rota). Prints the client id and the "
            "secret once; the secret is stored hashed and cannot be shown again.")

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)
        parser.add_argument("--redirect-uri", required=True)

    def handle(self, *args, **options):
        secret = generate_client_secret()
        app, created = Application.objects.update_or_create(
            name=options["name"],
            defaults={
                "redirect_uris": options["redirect_uri"],
                "client_type": Application.CLIENT_CONFIDENTIAL,
                "authorization_grant_type": Application.GRANT_AUTHORIZATION_CODE,
                "skip_authorization": True,
                "algorithm": "RS256",
                "client_secret": secret,
            },
        )
        self.stdout.write(f"client_id={app.client_id}")
        self.stdout.write(f"client_secret={secret}")
        self.stdout.write("Put both in the relying party's environment file now; "
                          "the secret is not shown again.")
