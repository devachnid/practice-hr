"""Parse a saved register page the way a lookup would, for the person
capturing fixtures: `manage.py registers_parse gmc page.html --surname Patel`.
The page goes through the same flow as a lookup (registers.adapters.base.run,
with the fetch replaced by the file, and the HTTP status from a `<stem>.status`
sidecar when registers_fetch saved one), so it prints what a lookup would
record. It reads a file and prints; it writes nothing."""
from pathlib import Path
from unittest import mock

from django.core.management.base import BaseCommand, CommandError

from registers import http, names
from registers.adapters import MODULES, base, not_found_statuses


class Command(BaseCommand):
    help = "Parse a saved register page (HTML) with a body's adapter and print what a lookup would record."

    def add_arguments(self, parser):
        parser.add_argument("code", choices=sorted(MODULES))
        parser.add_argument("path")
        parser.add_argument("--surname", required=True,
                            help="The surname on the person's record, as a lookup matches it.")
        parser.add_argument("--number", default="", help="The number, for the Welsh list's row match.")

    def handle(self, *args, **options):
        module = MODULES[options["code"]]
        try:
            with open(options["path"], encoding="utf-8", errors="replace") as page:
                html = page.read()
        except OSError as exc:
            raise CommandError(f"cannot read the page: {exc.__class__.__name__}") from None
        number, surname = options["number"] or "", options["surname"]
        status = _status_beside(Path(options["path"]))
        with mock.patch.object(http, "get", lambda url, timeout=http.TIMEOUT: (status, html)):
            result = base.run(module.url(number), module.parse, number, surname, not_found_statuses(options["code"]))
        name = result.name_on_register
        self.stdout.write(f"HTTP status: {status}")
        self.stdout.write(f"outcome: {result.outcome}")
        self.stdout.write(f"status text: {result.status_text}")
        self.stdout.write(f"name: {name}")
        matches = "yes" if name and names.surnames_match(name, surname) else "no" if name else "no name found"
        self.stdout.write(f"surname matches: {matches}")
        self.stdout.write(f"lines of text: {len(base.text_of(html))}")


def _status_beside(page):
    """The HTTP status registers_fetch saved beside the page, else 200."""
    sidecar = page.with_suffix(".status")
    try:
        return int(sidecar.read_text().strip()) if sidecar.exists() else 200
    except (OSError, ValueError):
        return 200
