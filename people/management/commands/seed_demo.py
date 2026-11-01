"""Seed the shared fictional practice (19 people) for a STAGING box.

    manage.py seed_demo --email-base tom@example.org --yes-this-is-staging

Every staff email is plus-addressed from the base (tom+morgan.ellis@example.org),
so anything the app ever sent them would land in one inbox. The same cast is
seeded into the rota and Shift Central; names, teams, titles and contract kinds
must stay identical across the three.

Everything goes through the service layer with an actor, so it is audited as
the real admin flows are. It sends nothing: the invitation is the admin's
separate step in the People admin, and is never called here. The whole run is
one transaction, and a second run with the same base creates nothing.
docs/admin/people.md has the admin-facing description.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone

from absence.models import Absence, AbsenceType, Policy, PolicyTier, Pot
from absence.services import balances, bookings, pots
from accounts.models import AppRole, User
from accounts.services import logins
from people.models import ContractType, Employee, Position, Team, WorkingPattern
from people.services import contracts, employees, employments, patterns, positions

SHIFT_CENTRAL = "shift-central"

# NEVER SEND EMAIL. The services below never mail (the views and the admin do),
# and accounts.services.logins.create_for_employee makes the login without
# inviting; people.admin sends the invitation and is not called. As a second
# line, the whole run is wrapped in override_settings with the dummy backend
# (it discards every message, locmem included, so mail.outbox stays empty) and
# no EMAIL_HOST (so accounts.mail treats the box as having no relay).
NO_MAIL = {"EMAIL_BACKEND": "django.core.mail.backends.dummy.EmailBackend", "EMAIL_HOST": ""}

D = Decimal
HOURS, SESSIONS = "hours", "sessions"

# Team name -> display_order, set only when the team is created here.
TEAMS = {"GPs": 10, "Reception": 20, "Admin/Secretarial": 30, "Nursing": 40,
         "Pharmacy": 50, "Management": 60, "Cleaning": 70}

# Contract types made only when missing (the first eight are seeded by the app).
CONTRACT_TYPES = {
    "Partner": (SESSIONS, "9"), "Salaried GP": (SESSIONS, "9"),
    "Practice nurse": (HOURS, "37.5"), "HCA": (HOURS, "37.5"), "Reception": (HOURS, "37.5"),
    "Administration": (HOURS, "37.5"), "Management": (HOURS, "37.5"),
    "Pharmacy": (HOURS, "37.5"), "Cleaning": (HOURS, "37.5"),
}


def _hours(weekdays, per_day=D("7.5")):
    """Whole working days, split AM/PM evenly: 7.5 hours is 3.75 and 3.75."""
    half = per_day / 2
    return {d: (half, half) for d in weekdays}


def _sessions(*days):
    """(weekday, am, pm) rows, one session per half day worked."""
    return {d: (D(am), D(pm)) for d, am, pm in days}


@dataclass(frozen=True)
class Person:
    key: str
    first: str
    last: str
    team: str
    title: str
    ctype: str
    amount: str
    start: date
    manager: str | None
    pattern: dict


# Managers come before the people who report to them: the order matters.
CAST = [
    Person("morgan", "Morgan", "Ellis", "Management", "Practice Manager", "Management", "37.5",
           date(2015, 4, 1), None, _hours(range(5))),
    Person("jo", "Jo", "Whitaker", "Management", "Assistant Practice Manager", "Management", "37.5",
           date(2017, 5, 15), "morgan", _hours(range(5))),
    Person("dev", "Dev", "Anand", "Management", "Assistant Practice Manager", "Management", "37.5",
           date(2019, 2, 4), "morgan", _hours(range(5))),

    Person("rosa", "Rosa", "Delgado", "Reception", "Reception Manager", "Reception", "37.5",
           date(2016, 6, 1), "morgan", _hours(range(5))),
    Person("sophie", "Sophie", "Brennan", "Reception", "Receptionist", "Reception", "37.5",
           date(2018, 10, 1), "rosa", _hours(range(5))),
    Person("liam", "Liam", "Doyle", "Reception", "Receptionist", "Reception", "30",
           date(2021, 3, 8), "rosa", _hours((0, 1, 2, 3))),
    Person("aisha", "Aisha", "Rahman", "Reception", "Receptionist", "Reception", "22.5",
           date(2023, 1, 16), "rosa", _hours((0, 2, 4))),
    Person("tomasz", "Tomasz", "Kowal", "Reception", "Receptionist", "Reception", "15",
           date(2025, 9, 1), "rosa", _hours((1, 3))),

    Person("priya", "Priya", "Nair", "GPs", "GP Partner", "Partner", "8",
           date(2015, 9, 7), "morgan", _sessions((0, 1, 1), (1, 1, 1), (2, 1, 1), (3, 1, 1))),
    Person("callum", "Callum", "Ross", "GPs", "Salaried GP", "Salaried GP", "6",
           date(2019, 8, 5), "priya", _sessions((0, 1, 1), (1, 1, 1), (3, 1, 1))),
    Person("helen", "Helen", "Okafor", "GPs", "Salaried GP", "Salaried GP", "5",
           date(2022, 4, 4), "priya", _sessions((1, 1, 1), (2, 1, 1), (4, 1, 0))),

    Person("fiona", "Fiona", "Marsh", "Nursing", "Lead Nurse", "Practice nurse", "37.5",
           date(2016, 1, 11), "morgan", _hours(range(5))),
    Person("grace", "Grace", "Tanaka", "Nursing", "Practice Nurse", "Practice nurse", "30",
           date(2020, 6, 1), "fiona", _hours((0, 1, 2, 3))),
    Person("owen", "Owen", "Pryce", "Nursing", "Healthcare Assistant", "HCA", "22.5",
           date(2024, 2, 12), "fiona", _hours((1, 2, 4))),

    Person("elena", "Elena", "Fischer", "Admin/Secretarial", "Secretary", "Administration", "37.5",
           date(2017, 11, 6), "jo", _hours(range(5))),
    Person("marcus", "Marcus", "Bell", "Admin/Secretarial", "Medical Secretary", "Administration", "30",
           date(2023, 9, 4), "jo", _hours((0, 1, 2, 3))),

    Person("hamid", "Hamid", "Qureshi", "Pharmacy", "Head Pharmacist", "Pharmacy", "37.5",
           date(2021, 10, 4), "morgan", _hours(range(5))),
    Person("ines", "Ines", "Costa", "Pharmacy", "Pharmacy Technician", "Pharmacy", "30",
           date(2026, 3, 2), "hamid", _hours((0, 1, 2, 3))),

    Person("doreen", "Doreen", "Hughes", "Cleaning", "Cleaner", "Cleaning", "15",
           date(2018, 3, 5), "jo", _hours((0, 2, 4), per_day=D("5"))),
]

# Who is an admin of Shift Central (every team's manager there).
MANAGERS = ("morgan", "jo", "dev", "rosa")


def parse_base(base):
    """(local, domain) of the base, or a CommandError saying what is wrong."""
    if not base or base.count("@") != 1 or "+" in base:
        raise CommandError(f"--email-base must be local@domain with exactly one @ and no +, not {base!r}.")
    local, domain = base.split("@")
    if not local or not domain or any(c.isspace() for c in base):
        raise CommandError(f"--email-base must be local@domain, not {base!r}.")
    try:
        validate_email(f"{local}+x@{domain}")
    except ValidationError:
        raise CommandError(f"--email-base {base!r} does not make a valid email address.") from None
    return local, domain


def address(person, local, domain):
    return f"{local}+{person.first.lower()}.{person.last.lower()}@{domain}"


class Command(BaseCommand):
    help = ("Seed the shared fictional demo practice (19 people) on a STAGING box. Sends no email. "
            "Needs --email-base and --yes-this-is-staging; refuses if the database holds any employee "
            "outside the cast. Safe to run again.")

    def add_arguments(self, parser):
        parser.add_argument("--email-base", help="local@domain; staff are local+first.last@domain.")
        parser.add_argument("--yes-this-is-staging", action="store_true",
                            help="Required: this writes fictional people into the database.")

    def handle(self, *args, **options):
        if not options["email_base"] or not options["yes_this_is_staging"]:
            raise CommandError(
                "seed_demo writes a fictional practice into the database and must never run on "
                "production. Give --email-base local@domain and --yes-this-is-staging to confirm "
                "this is a staging box. Nothing was changed.")
        local, domain = parse_base(options["email_base"])
        emails = {p.key: address(p, local, domain) for p in CAST}
        today = timezone.localdate()
        if any(p.start > today for p in CAST):
            raise CommandError("The box's clock is before the cast's start dates; check the date.")
        foreign = Employee.objects.exclude(work_email__in=list(emails.values())).count()
        if foreign:
            raise CommandError(
                f"The database already holds {foreign} employee(s) who are not part of the demo cast. "
                "seed_demo only runs on an empty database or one it seeded. Nothing was changed.")

        with override_settings(**NO_MAIL), transaction.atomic():
            counts = self.seed(emails, local, domain, today)
        for line in counts:
            self.stdout.write(line)

    # -- the work --------------------------------------------------------------------

    def seed(self, emails, local, domain, today):
        actor = self._actor(local, domain)
        teams = {name: self._team(name, order) for name, order in TEAMS.items()}
        ctypes = {name: self._contract_type(name, unit, full) for name, (unit, full) in CONTRACT_TYPES.items()}
        for p in CAST:
            self._check_unit(ctypes[p.ctype], p)
        made_policies = sum(self._ensure_policies(ct) for ct in ctypes.values())

        people = {}
        new = {"employees": 0, "logins": 0, "employments": 0, "positions": 0, "contracts": 0, "patterns": 0}
        for p in CAST:
            employee = Employee.objects.filter(work_email__iexact=emails[p.key]).first()
            if employee is None:
                employee = employees.create(actor, first_name=p.first, last_name=p.last,
                                            work_email=emails[p.key])
                new["employees"] += 1
            if employee.user_id is None:
                logins.create_for_employee(actor, employee)         # the login only; never an invitation
                new["logins"] += 1
            people[p.key] = employee

            employment = employee.employments.first()
            if employment is None:
                employment = employments.start(actor, employee, p.start)
                new["employments"] += 1
            if not Position.objects.filter(employment=employment).exists():
                manager = people[p.manager] if p.manager else None
                positions.add(actor, employment, p.title, teams[p.team], manager, p.start)
                new["positions"] += 1
            if not employment.contracts.exists():
                contracts.add(actor, employment, ctypes[p.ctype], D(p.amount), p.start)
                new["contracts"] += 1
            if not WorkingPattern.objects.filter(employment=employment).exists():
                _, warning = patterns.set_pattern(actor, employment, p.start, p.pattern)
                if warning:
                    raise CommandError(f"{p.first} {p.last}: {warning}")
                new["patterns"] += 1

        pots_before = Pot.objects.count()
        for p in CAST:
            self._open_pots(people[p.key].employments.first(), actor, today)
        opened = Pot.objects.count() - pots_before
        absences = self._sample_absences(actor, people, today)
        grant = self._grant_shift_central_admin(people)

        lines = [f"Demo practice: {Employee.objects.count()} people, emails {local}+first.last@{domain}.",
                 "Created " + ", ".join(f"{n} {what}" for what, n in new.items()) +
                 f", {made_policies} policies, {opened} leave pots, {absences} sample absences.",
                 "No email was sent and no invitation was issued; send invitations from the People admin.",
                 grant]
        return lines

    def _actor(self, local, domain):
        """Whoever the audit log names: a login that cannot sign in (inactive, no password)
        and is linked to no employee."""
        email = f"{local}+seed.demo@{domain}"
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User.objects.create_user(email=email, is_active=False)
        return user

    def _team(self, name, order):
        """An existing team is used as it is, display order and all."""
        team, _ = Team.objects.get_or_create(name=name, defaults={"display_order": order})
        return team

    def _contract_type(self, name, unit, full):
        ct, _ = ContractType.objects.get_or_create(
            name=name, defaults={"unit": unit, "full_time_weekly": D(full),
                                 "display_order": 100})
        return ct

    def _check_unit(self, ct, person):
        """A GP must be on a sessions contract (it is how Shift Central recognises one), everyone else
        on hours. An existing contract type of the wrong unit is real data and is never altered."""
        want = SESSIONS if person.ctype in ("Partner", "Salaried GP") else HOURS
        if ct.unit != want:
            raise CommandError(f"Contract type {ct.name!r} already exists with unit {ct.unit!r}, but "
                               f"{person.first} {person.last} needs {want!r}. Nothing was changed.")

    def _ensure_policies(self, ct):
        """What the app does for the seeded types, for a type that has none: an annual-leave policy
        (the practice's standard for hours, five weeks and a day for sessions) and, where that
        charges bank holidays as a pot, the bank-holiday policy that goes with it. A policy that
        exists is left alone. Returns how many were created."""
        al_type = AbsenceType.objects.get(code="AL")
        bh_type = AbsenceType.objects.get(code="BH")
        made = 0
        al = Policy.objects.filter(contract_type=ct, absence_type=al_type).order_by("effective_from").first()
        if al is None:
            if ct.unit == HOURS:
                values = dict(weeks_per_year=D("4.4"), year_start_month=1, year_start_day=1, rounding=D("0.25"),
                              accrual=Policy.Accrual.MONTHLY, bank_holiday_handling=Policy.BankHolidays.PRO_RATA_POT)
            else:
                values = dict(weeks_per_year=D("5.6"), year_start_month=4, year_start_day=1, rounding=D("0.5"),
                              bank_holiday_handling=Policy.BankHolidays.CLOSED_NOT_CHARGED)
            al = Policy(contract_type=ct, absence_type=al_type, effective_from=date(2020, 1, 1),
                        leave_year_basis=Policy.Basis.FIXED, **values)
            al.full_clean()
            al.save()
            if ct.unit == HOURS:
                PolicyTier.objects.bulk_create(PolicyTier(policy=al, after_years=y, extra_weeks=D(w))
                                               for y, w in ((1, "0.2"), (3, "0.6"), (5, "1.0")))
            made += 1
        if (al.bank_holiday_handling == Policy.BankHolidays.PRO_RATA_POT
                and not Policy.objects.filter(contract_type=ct, absence_type=bh_type).exists()):
            bh = Policy(contract_type=ct, absence_type=bh_type, effective_from=al.effective_from,
                        weeks_per_year=D("0"), leave_year_basis=al.leave_year_basis,
                        year_start_month=al.year_start_month, year_start_day=al.year_start_day,
                        rounding=al.rounding, bank_holiday_handling=Policy.BankHolidays.PRO_RATA_POT)
            bh.full_clean()
            bh.save()
            made += 1
        return made

    def _open_pots(self, employment, actor, today):
        """This leave year's and next year's annual-leave pot (and the bank-holiday pot where the
        policy charges one), as the nightly job opens them for a new starter, so the person's leave
        screen works at once."""
        for code in ("AL", "BH"):
            absence_type = AbsenceType.objects.get(code=code)
            day = today
            if code == "BH" and not balances.bank_holiday_pot_used(employment, day):
                continue
            for _ in range(2):
                try:
                    pot = pots.for_day(employment, absence_type, day, actor=actor)    # opens it if missing
                except ValidationError as e:
                    raise CommandError(f"{employment.employee}: {'; '.join(e.messages)}") from e
                day = pot.year_end + timedelta(days=1)

    # -- sample absences -------------------------------------------------------------

    def _sample_absences(self, actor, people, today):
        """Two booked weeks of annual leave in the next two months and one sick day last month,
        recorded through bookings.record (approved at once, no email). A person who already has any
        absence of the type is left as they are, so a later run adds none."""
        made = 0
        for key, offset in (("sophie", 14), ("callum", 28)):
            employment = people[key].employments.first()
            if self._has_absence(employment, "AL"):
                continue
            monday = today + timedelta(days=offset)
            monday += timedelta(days=(7 - monday.weekday()) % 7)
            for _ in range(4):                          # a week straddling the year end moves on
                try:
                    bookings.record(actor, employment, AbsenceType.objects.get(code="AL"),
                                    monday, monday + timedelta(days=4), comment="Demo booking")
                except ValidationError:
                    monday += timedelta(days=7)
                else:
                    made += 1
                    break
        employment = people["liam"].employments.first()
        if not self._has_absence(employment, "SICK"):
            last_month = today.replace(day=1) - timedelta(days=1)
            day = last_month.replace(day=14)
            while patterns.units_on(employment, day, "AM") <= 0:
                day += timedelta(days=1)
            bookings.record(actor, employment, AbsenceType.objects.get(code="SICK"), day, day,
                            comment="Demo sickness")
            made += 1
        return made

    def _has_absence(self, employment, code):
        return Absence.objects.filter(employment=employment, absence_type__code=code,
                                      auto_bank_holiday=False).exists()

    # -- Shift Central ---------------------------------------------------------------

    def _grant_shift_central_admin(self, people):
        """An AppRole needs a registered OIDC client to point at, so the "Admin of shift-central"
        tick can only exist after `register_oidc_client --name shift-central` has run. When that
        client is there the four managers are made its admins (the same row the Login accounts page
        writes); when it is not, nothing is granted and the line printed says so."""
        from oauth2_provider.models import Application
        apps = list(Application.objects.filter(name=SHIFT_CENTRAL, user__isnull=True)[:2])
        if len(apps) != 1:
            why = "is not registered" if not apps else "is registered more than once"
            return (f"Shift Central admin grant: skipped, the {SHIFT_CENTRAL} client {why}. Register it "
                    f"(register_oidc_client --name {SHIFT_CENTRAL} ...) and run seed_demo again.")
        for key in MANAGERS:
            AppRole.objects.update_or_create(user=people[key].user, application=apps[0],
                                             defaults={"is_admin": True})
        return (f"Shift Central admin grant: done, {len(MANAGERS)} managers are admins of {SHIFT_CENTRAL} "
                f"({', '.join(people[k].name for k in MANAGERS)}).")
