"""Move the rota's logins here, once, so everyone signs in to the rota
through this system without choosing a new password. The file is what the
rota's export_logins writes; it holds password hashes, so it is deleted
once this has run (docs/admin/sign-in.md)."""

import json
import re
from datetime import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX, identify_hasher
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction
from oauth2_provider.models import Application

from accounts.models import AppRole
from people.models import Employee
from people.services import employees

FLAGS = ("is_active", "is_rota_admin", "is_superuser")
KEYS = {"email", "password", *FLAGS}
COUNTS = ("created", "passwords_set", "password_kept", "linked", "admins")
# What a Django hash starts with: its algorithm's name, then "$".
HASH_PREFIX = re.compile(r"[a-z0-9_]+\$")


def _read(path):
    """The file's logins, or a CommandError saying what is wrong with it.
    Nothing here repeats a password field's value."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        raise CommandError(f"Cannot read {path}: {e.strerror}.") from None
    except (ValueError, UnicodeDecodeError) as e:
        raise CommandError(f"{path} is not JSON: {e}.") from None

    def refuse(what):
        raise CommandError(f"{path} is not a login export from the rota: {what}.")

    if not isinstance(data, dict) or set(data) != {"exported_at", "logins"}:
        refuse('expected an object with "exported_at" and "logins" and nothing else')
    try:
        datetime.fromisoformat(data["exported_at"])
    except (TypeError, ValueError):
        refuse('"exported_at" is not an ISO date and time')
    if not isinstance(data["logins"], list):
        refuse('"logins" is not a list')
    seen = set()
    for n, login in enumerate(data["logins"], 1):
        if not isinstance(login, dict) or set(login) != KEYS:
            refuse(f"login {n} is not an object with exactly {', '.join(sorted(KEYS))}")
        try:
            validate_email(login["email"])
        except (TypeError, ValidationError):
            refuse(f"login {n}'s email is not an email address")
        if login["email"].casefold() in seen:
            refuse(f"duplicate email in file: {login['email']}")
        seen.add(login["email"].casefold())
        if any(not isinstance(login[flag], bool) for flag in FLAGS):
            refuse(f"login {n}'s {', '.join(FLAGS)} are not all true or false")
        password = login["password"]
        if not isinstance(password, str):
            refuse(f"login {n}'s password is not text")
        if not password.startswith(UNUSABLE_PASSWORD_PREFIX):
            try:
                identify_hasher(password)
            except ValueError:
                # Neither message repeats the value: it may be a password.
                if HASH_PREFIX.match(password):
                    refuse(f"login {n}'s password ({login['email']}) is not a hash this "
                           "system can check (its algorithm is not one of PASSWORD_HASHERS)")
                refuse(f"login {n}'s password ({login['email']}) is not a password hash")
    return data["logins"]


def _client(name):
    # Only the ownerless clients register_oidc_client makes, as everywhere.
    matches = list(Application.objects.filter(name=name, user__isnull=True)[:2])
    if not matches:
        raise CommandError(f"No registered client is named {name!r}. Register it with "
                           "register_oidc_client first, or name it with --app.")
    if len(matches) > 1:
        raise CommandError(f"More than one client is named {name!r}. Remove the extra one "
                           "in the admin (OAuth2 Provider › Applications) and run this again.")
    return matches[0]


class Command(BaseCommand):
    help = ("Import the rota's logins from the file its export_logins wrote: create or match "
            "each login, set its password where it has none here, link its employee, and set "
            "its admin role in the app. Prints counts; never a password or a hash.")

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="The rota's export_logins file.")
        parser.add_argument("--app", default="rota",
                            help="The registered client the admin flags are for (default: rota).")
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would happen, and write nothing.")

    def handle(self, *args, **options):
        logins = _read(options["file"])
        app = _client(options["app"])
        self.counts = dict.fromkeys(COUNTS, 0)
        self.unmatched, self.linked_elsewhere = [], []
        with transaction.atomic():
            for login in logins:
                self._import(login, app)
            if options["dry_run"]:
                transaction.set_rollback(True)

        for name in COUNTS:
            self.stdout.write(f"{name}: {self.counts[name]}")
        for heading, emails in (("No matching employee", self.unmatched),
                                ("Employee already linked to another login", self.linked_elsewhere)):
            if emails:
                self.stdout.write(f"{heading}:")
                for email in emails:
                    self.stdout.write(f"  {email}")
        if options["dry_run"]:
            self.stdout.write("Dry run: nothing was written.")

    def _import(self, login, app):
        email = login["email"]
        User = get_user_model()
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            # No password argument: the account starts with none usable.
            user = User.objects.create_user(email, is_active=login["is_active"])
            self.counts["created"] += 1

        if user.has_usable_password():
            # Someone chose it here; the rota's never replaces it.
            self.counts["password_kept"] += 1
        elif not login["password"].startswith(UNUSABLE_PASSWORD_PREFIX):
            # The hash as the rota stored it: both systems use Django's
            # hashers, so the same password checks here.
            user.password = login["password"]
            user.save(update_fields=["password"])
            self.counts["passwords_set"] += 1

        if not Employee.objects.filter(user=user).exists():
            employee = Employee.objects.filter(work_email__iexact=email).first()
            if employee is None:
                self.unmatched.append(email)
            elif employee.user_id is not None:
                self.linked_elsewhere.append(email)
            else:
                try:
                    employees.update(None, employee, user=user)
                except ValidationError as e:
                    raise CommandError(f"Cannot link {email} to their employee record: "
                                       f"{'; '.join(e.messages)}") from None
                self.counts["linked"] += 1

        # is_superuser in the file is not read: superusers here are made
        # with createsuperuser.
        AppRole.objects.update_or_create(user=user, application=app,
                                         defaults={"is_admin": login["is_rota_admin"]})
        if login["is_rota_admin"]:
            self.counts["admins"] += 1
