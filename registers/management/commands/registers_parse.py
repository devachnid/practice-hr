"""Parse a saved register page the way a lookup would, for the person
capturing fixtures: `manage.py registers_parse gmc page.html --surname Patel`.
The page goes through the same flow as a lookup (registers.adapters.base.run,
with the fetch replaced by the file), so it prints what a lookup would
record. It reads a file and prints; it writes nothing."""
from unittest import mock

from django.core.management.base import BaseCommand, CommandError

from registers import http, names
from registers.adapters import MODULES, base


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
        with mock.patch.object(http, "get", lambda url, timeout=http.TIMEOUT: (200, html)):
            result = base.run(module.url(number), module.parse, number, surname)
        name = result.name_on_register
        self.stdout.write(f"outcome: {result.outcome}")
        self.stdout.write(f"status text: {result.status_text}")
        self.stdout.write(f"name: {name}")
        matches = "yes" if name and names.surnames_match(name, surname) else "no" if name else "no name found"
        self.stdout.write(f"surname matches: {matches}")
        self.stdout.write(f"lines of text: {len(base.text_of(html))}")
