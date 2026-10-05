"""Parse a saved register page the way a lookup would, for the person
capturing fixtures: `manage.py registers_parse gmc page.html --surname Patel`.
It reads a file and prints; it writes nothing."""
from django.core.management.base import BaseCommand, CommandError

from registers import names
from registers.adapters import MODULES, base


class Command(BaseCommand):
    help = "Parse a saved register page (HTML) with a body's adapter and print what a lookup would record."

    def add_arguments(self, parser):
        parser.add_argument("code", choices=sorted(MODULES))
        parser.add_argument("path")
        parser.add_argument("--surname", default="", help="The person's surname, to show whether it would match.")
        parser.add_argument("--number", default="", help="The number, for the Welsh list's row match.")

    def handle(self, *args, **options):
        module = MODULES[options["code"]]
        try:
            with open(options["path"], encoding="utf-8", errors="replace") as page:
                html = page.read()
        except OSError as exc:
            raise CommandError(f"cannot read the page: {exc.__class__.__name__}") from None
        lines = base.text_of(html)
        outcome, status, name = module.parse(lines, options["number"] or "")
        self.stdout.write(f"outcome: {outcome}")
        self.stdout.write(f"status text: {status}")
        self.stdout.write(f"name: {name}")
        if options["surname"]:
            self.stdout.write(f"surname matches: {'yes' if names.surnames_match(name, options['surname']) else 'no'}")
        self.stdout.write(f"lines of text: {len(lines)}")
