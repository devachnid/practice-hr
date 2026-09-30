# Practice HR

HR software for a GP practice: people, contracts, working patterns, absence
and leave, and the sign-in for the practice's apps. Replaces BreatheHR.

The design specs live in `docs/superpowers/specs/`, one per piece of work in
the order it was built. The first is the foundation and absence system. The
rota (`devachnid/rota`) reads people, patterns and absences from here.

## Develop

    source .venv/bin/activate
    DEBUG=1 python manage.py migrate
    DEBUG=1 python manage.py runserver
    pytest

`DEBUG=1` is what lets `manage.py` start on a box with no `SECRET_KEY` in
the environment. It then uses a key of this checkout's own, generated once
into the git-ignored `.dev_secret_key`. With debug off, the settings refuse
to run without a real key (see Deploy). The suite needs neither — it detects pytest and never
reaches a mail relay. With no `EMAIL_HOST` set, a dev box behaves as
production does without a relay: an admin is shown each invitation or
password link on screen instead of it being sent. With no OIDC signing key
set, the OIDC provider is off and `/o/` answers 404
— nothing else about the app changes.

CI (`.github/workflows/tests.yml`) runs `ruff check .` (pyflakes only — see
`ruff.toml`), `makemigrations --check`, the suite, and `collectstatic` +
`check --deploy` against a throwaway environment; the required ruleset
needs it green. Locally: `pip install ruff==0.16.6 && ruff check .`.

## Admin guide

Every admin setting is documented in [docs/admin/](docs/admin/README.md) —
one page per area, each field explained with what depends on it and what
goes wrong if it is set wrong. The sequence below gets a new practice
running; that guide is the reference for what the settings actually mean.

## First-time setup

1. `deploy/manage createsuperuser` on the server (`DEBUG=1 python
   manage.py createsuperuser` on a dev box).
2. Sign in and open **Admin**. Eight [contract types](docs/admin/people.md#contract-type)
   are seeded already (Partner, Salaried GP, GP trainee, Practice nurse,
   HCA, Reception, Administration, Management); add or edit them to match
   the practice, then create [teams](docs/admin/people.md#team).
3. Create everyone's records under **People › Employees › Add**, and each
   employee's first [Employment](docs/admin/people.md#employment) with its
   [Position](docs/admin/people.md#position),
   [Contract](docs/admin/people.md#contract) and
   [Working pattern](docs/admin/people.md#working-pattern).
4. Create everyone's login accounts under **Login accounts › Add** — an
   email and whether they are an admin, nothing else. Each person receives
   an invitation, chooses their own password from its link, and can then
   add a passkey. The superuser's from step 1 is the only password an admin
   ever types. See [Login accounts](docs/admin/sign-in.md#login-accounts).
5. Set up [absence and leave](docs/admin/absence.md): check each contract
   type's annual-leave [policy](docs/admin/absence.md#policies) (the seeded
   ones carry nothing over until you set a
   [carry cap](docs/admin/absence.md#carry-over-max-weeks-carry_over_max_weeks)),
   add a policy for study leave if you use it (TOIL needs none: it is
   [earned by claims](docs/admin/absence.md#accrues)), and set each
   person's line manager, who approves their leave and TOIL claims. If you enter balances by
   hand, run the [year end](docs/admin/year-end.md#running-it-by-hand) first.
6. If the rota (or another relying party) is signing in against this
   system, register it — see [Registering a relying
   party](docs/admin/sign-in.md#registering-a-relying-party); that needs
   `OIDC_RSA_PRIVATE_KEY_FILE` set first (below).

## Deploy (Cloudflare tunnel)

The app runs as its own `practice-hr` user, never as root, in two places:

| Where | Owner | What |
|---|---|---|
| `/srv/practice-hr` | root, read-only to the app | the code, its `.venv` and `staticfiles/` |
| `/var/lib/practice-hr` | `practice-hr`, closed to everyone else | the database and its nightly backups |
| `/etc/practice-hr.env` | root, mode 600 | the settings and secrets |

So a bug that let a request run code reaches the app's own data and
nothing else: not the app's own code, not a Cloudflare credential, not the
rest of the container. Every unit in `deploy/` also runs in a systemd
sandbox; `deploy/gunicorn.service` explains each part.

    useradd --system --home-dir /var/lib/practice-hr --no-create-home --shell /usr/sbin/nologin practice-hr
    install -d -o practice-hr -g practice-hr -m 700 /var/lib/practice-hr
    git clone https://github.com/devachnid/practice-hr /srv/practice-hr
    cd /srv/practice-hr
    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    chown -R root:root /srv/practice-hr
    chmod -R u=rwX,go=rX /srv/practice-hr

Create the secrets file — root-only, never in the unit file. The subshell
keeps `umask 077` from leaking into later commands, where it would make
files the app has to read unreadable:

    (
    umask 077
    .venv/bin/python -c 'from django.core.management.utils import get_random_secret_key as k; print("SECRET_KEY=" + k())' > /etc/practice-hr.env
    cat >> /etc/practice-hr.env <<'EOF'
    DEBUG=0
    DB_PATH=/var/lib/practice-hr/db.sqlite3
    MEDIA_ROOT=/var/lib/practice-hr/media
    ALLOWED_HOSTS=hr.example.org
    CSRF_TRUSTED_ORIGINS=https://hr.example.org
    SITE_URL=https://hr.example.org
    EOF
    )

**Environment variables** (`/etc/practice-hr.env`, all read in
`config/settings.py`):

| Variable | Meaning |
|---|---|
| `SECRET_KEY` | Django's signing key. Required with `DEBUG` off. |
| `DEBUG` | `0` in production (the default); `1` only for development. |
| `DB_PATH` | Where the SQLite database lives. Unset, it sits beside `manage.py`, which is what development wants; production points it at `/var/lib/practice-hr/db.sqlite3`, out of the read-only code tree, because SQLite needs to write the directory its database is in. |
| `MEDIA_ROOT` | Where the app writes files: the payroll changes reports, in `payroll/` beneath it. Unset, it is `media/` beside `manage.py`, which is what development wants (git-ignored); production points it at `/var/lib/practice-hr/media`, because the code tree is read-only. Django never serves it; the payroll page streams a report to an HR admin. The nightly backup archives it. |
| `ALLOWED_HOSTS` | Comma-separated hostnames the app answers for. |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated `https://` origins allowed to POST. |
| `SITE_URL` | The address the site is served at, `https://hr.example.org`. The links in emails (a request waiting for a decision) are built from it; unset they are relative and unusable, and `check --deploy` warns (`hr.W002`). |
| `HR_API_TOKENS` | Comma-separated bearer tokens the rota's read API accepts (`openssl rand -hex 32` makes one). Unset, the API refuses everything and `check --deploy` warns (`hr.W001`). See [the read API](docs/admin/api.md). |
| `CHASE_AFTER_WORKING_DAYS` | A leave request undecided after this many working days (weekends, England and Wales bank holidays and closed days excluded) is shown on the admin dashboard and the HR admins are emailed once. Default `3`. |
| `RETENTION_DAYS_PERSONAL`, `RETENTION_DAYS_PAY`, `RETENTION_DAYS_HEALTH`, `RETENTION_DAYS_AUDIT` | Days after an employment ends that the [retention report](docs/admin/people.md#retention-report) starts listing that kind of record. Defaults 2190, 2190, 2190 and 2555 (six years, seven for the audit log). It only lists; nothing is deleted. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` | The outgoing mail relay. `EMAIL_HOST` blank means unset: invitations and password links are shown on screen instead of sent. |
| `DEFAULT_FROM_EMAIL` | The From address on every email the app sends. |
| `CSP_REPORT_ONLY` | `1` sends the Content-Security-Policy as report-only, blocking nothing — the way back if it blocks something after a deploy. Unset (the default), it is enforced. |
| `TRUSTED_PROXY_IPS` | Comma-separated addresses whose forwarded-IP header is believed for login rate-limiting. Defaults to loopback, which is right behind a Cloudflare tunnel; never set it to a wildcard. |
| `OIDC_RSA_PRIVATE_KEY_FILE` | The file holding the key that signs OpenID Connect tokens for relying parties like the rota. Unset switches the provider off. See below and [the OIDC provider](docs/admin/sign-in.md#the-openid-connect-provider). |
| `OIDC_RSA_PRIVATE_KEY` | The same key inline, one line with `\n` for each newline — for a dev box only. Ignored when `OIDC_RSA_PRIVATE_KEY_FILE` is set. |

The OIDC signing key lives in a file of its own, not in the environment
file: systemd's environment-file parser turns an unquoted `\n` into a plain
`n`, so a PEM key folded onto one line arrives broken. Generate it into a
directory only root and the app's group can read — the app reads the file
itself, as the `practice-hr` user:

    install -d -o root -g practice-hr -m 750 /etc/practice-hr
    (umask 027; openssl genrsa -out /etc/practice-hr/oidc.pem 2048)
    chgrp practice-hr /etc/practice-hr/oidc.pem
    echo OIDC_RSA_PRIVATE_KEY_FILE=/etc/practice-hr/oidc.pem >> /etc/practice-hr.env

Leave it unset on a box with no relying party yet — the app runs exactly
the same either way, `/o/` just answers 404. A named file the app cannot
read stops it starting, and `deploy/manage check --deploy` fails
(`hr.E001`) on a key that is not a PEM RSA private key.

Then:

    deploy/manage collectstatic --noinput
    deploy/manage migrate
    cp deploy/gunicorn.service /etc/systemd/system/practice-hr.service
    cp deploy/hr-backup.* deploy/hr-clearsessions.* deploy/hr-nightly.* /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable --now practice-hr hr-backup.timer hr-clearsessions.timer hr-nightly.timer

**Run every `manage.py` command through `deploy/manage`**, as root:
`deploy/manage createsuperuser`, `deploy/manage check --deploy` and so on.
It runs the command as the `practice-hr` user with the settings from
`/etc/practice-hr.env`, exactly as the services do. Plain `python manage.py`
as root is the one way to break this layout: the database is in WAL mode,
so a root process that opens it can leave `db.sqlite3-wal`/`-shm` files
owned by root, which the app then cannot open. Sourcing the settings into a
shell (`. /etc/practice-hr.env`) also fails on a secret key holding `(` or
`$`, which Django's generated keys do.

Once `OIDC_RSA_PRIVATE_KEY_FILE` is set and the service restarted, register each
relying party:

    deploy/manage register_oidc_client --name rota --redirect-uri https://rota.example.org/oidc/callback/

See [Registering a relying party](docs/admin/sign-in.md#registering-a-relying-party)
for `--rotate` and what the command prints.

Point the Cloudflare tunnel ingress at `http://127.0.0.1:8322` — gunicorn
binds to loopback only, on purpose; see `deploy/gunicorn.service`.

Backups land in `/var/lib/practice-hr/backups/`, kept 30 days, readable
only by the `practice-hr` user: a SQLite copy every night
(`hr-backup.timer`), and a `media/` archive alongside it once a `media/`
directory exists in the state directory (`MEDIA_ROOT` above: the payroll
reports; until it exists the backup skips it rather than failing). Expired sessions are
cleared nightly too (`hr-clearsessions.timer`), and `hr-nightly.timer`
runs `manage.py hr_nightly`, which disables the login of anyone whose
employment has ended, closes each leave year that has ended, opens this
year's and next year's leave pots, charges bank holidays and chases waiting leave requests
— see [Nightly housekeeping](docs/admin/sign-in.md#nightly-housekeeping) and
[Year end](docs/admin/year-end.md). `deploy/manage absence_year_end` runs
the year-end part by hand, and `deploy/manage payroll_report --period
2026-06` builds a month's [payroll report](docs/admin/payroll.md).

`systemd-analyze security practice-hr` scores the sandbox.

**Logs** go to the journal: `journalctl -u practice-hr`. There is one line
per request (`hr.access`: the client's address from Cloudflare,
`user=<id>` or `anon`, method, path, status, time), with no query strings,
and with a password link's token replaced by `<redacted>`. Also logged:
server errors with tracebacks, CSRF failures and disallowed hosts
(`django.security`), and lockouts (`axes`).

**A Content-Security-Policy** is on every page the app renders (not the
admin, whose theme needs `eval`; `config/middleware.py`). No script runs on
those pages except the app's own files: no inline script, no event-handler
attributes and no `eval`. So a future escaping bug shows as text, not as
script running in a colleague's session. Styles may be inline.

The header also carries a fresh nonce on each response. The app itself uses
none: it's there for **Cloudflare**, which injects its own bot-detection
script and stamps it with the nonce it finds in the header. `form-action`
is `'self'` plus each registered relying party's origin: browsers hold the
redirect that follows a form post to it, and signing in to the rota ends
with one.

After a deploy, open the site with the browser's console showing. A
"Refused to…" line means the policy blocked something. To turn blocking off
without a code change, set `CSP_REPORT_ONLY=1` in `/etc/practice-hr.env`
and restart; the browser then only reports what it would have blocked.

**HTTPS.** With `DEBUG` off the app sends any plain-http request to https
itself (`SECURE_SSL_REDIRECT`), trusting cloudflared's `X-Forwarded-Proto`
— one more reason gunicorn binds to loopback only.

### Redeploying

    cd /srv/practice-hr
    git pull
    .venv/bin/pip install -r requirements.txt
    deploy/manage migrate
    deploy/manage collectstatic --noinput
    deploy/manage check --deploy
    systemctl restart practice-hr

A pull that changes a file in `deploy/` needs that unit copied into
`/etc/systemd/system/` again, then `systemctl daemon-reload`. The `.service`
files are the ones that change.
