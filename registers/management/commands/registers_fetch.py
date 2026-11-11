"""Save a register page exactly as a lookup fetches it, for the person
capturing fixtures: `manage.py registers_fetch gmc 1234567 clear.html`.
It checks the number's format, fetches the body's page for it through
registers.http.get (the app's own user agent, timeout and size cap) and
writes the reply to the file named, making the file's folder if it is not
there yet (the fixtures folders are not in the repository until a page is
saved in them), only when the reply is a 200: an error reply never
overwrites a page already saved. It prints the HTTP status and the size
only: never the page, the name or the number."""
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from registers import adapters, http, numbers


class Command(BaseCommand):
    help = "Fetch a body's register page for a number, as a lookup would, and save it to a file."

    def add_arguments(self, parser):
        parser.add_argument("code", choices=sorted(adapters.MODULES))
        parser.add_argument("number")
        parser.add_argument("path", help="The file to write the page to, such as clear.html.")

    def handle(self, *args, **options):
        code, number = options["code"], numbers.normalise(options["number"])
        try:
            numbers.check(code, number)
        except ValidationError as exc:
            raise CommandError(exc.messages[0]) from None
        try:
            status, body = http.get(adapters.url(code, number))
        except http.FetchError as exc:
            raise CommandError(f"could not fetch the page: {exc}") from None
        data = body.encode("utf-8")
        if status != 200:
            self.stdout.write(f"HTTP {status}, {len(data)} bytes; nothing written")
            return
        path = Path(options["path"])
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except OSError as exc:
            # the path is the one typed on the command line: nothing from the page
            raise CommandError(f"cannot write {path}: {exc.strerror or exc.__class__.__name__}") from None
        self.stdout.write(f"HTTP {status}, {len(data)} bytes")
