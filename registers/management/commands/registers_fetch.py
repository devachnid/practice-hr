"""Save a register's reply exactly as a lookup fetches it, for the person
capturing fixtures: `manage.py registers_fetch gmc 1234567 clear.html`
(`clear.json` for the Welsh list, whose reply is JSON). It checks the
number's format, fetches the reply through registers.adapters.fetch (the
body's own search where it has one, else its page; the app's own user
agent, timeout and size cap) and writes the reply to the file named, making the file's folder if it is not
there yet (the fixtures folders are not in the repository until a page is
saved in them), when the reply is a 200 or a status the body uses to say
"not on the register" (the GMC's 404): that reply is saved with a
`<stem>.status` sidecar holding the status, which the parse command and
the fixture tests read. Any other error reply never overwrites a page
already saved. It prints the HTTP status and the size only: never the
page, the name or the number."""
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from registers import adapters, http, numbers


class Command(BaseCommand):
    help = "Fetch a body's register page for a number, as a lookup would, and save it to a file."

    def add_arguments(self, parser):
        parser.add_argument("code", choices=sorted(adapters.MODULES))
        parser.add_argument("number")
        parser.add_argument("path", help="The file to write the reply to, such as clear.html (clear.json for the "
                                         "Welsh list).")

    def handle(self, *args, **options):
        code, number = options["code"], numbers.normalise(options["number"])
        try:
            numbers.check(code, number)
        except ValidationError as exc:
            raise CommandError(exc.messages[0]) from None
        try:
            status, body = adapters.fetch(code, number)
        except http.FetchError as exc:
            raise CommandError(f"could not fetch the page: {exc}") from None
        data = body.encode("utf-8")
        not_found = status in adapters.not_found_statuses(code)
        if status != 200 and not not_found:
            self.stdout.write(f"HTTP {status}, {len(data)} bytes; nothing written")
            return
        path = Path(options["path"])
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            if not_found:
                path.with_suffix(".status").write_text(f"{status}\n")
        except OSError as exc:
            # the path is the one typed on the command line: nothing from the page
            raise CommandError(f"cannot write {path}: {exc.strerror or exc.__class__.__name__}") from None
        if not_found:
            self.stdout.write(f"HTTP {status}, {len(data)} bytes; this register's not-found reply, saved with "
                              f"{path.with_suffix('.status').name}")
        else:
            self.stdout.write(f"HTTP {status}, {len(data)} bytes")
