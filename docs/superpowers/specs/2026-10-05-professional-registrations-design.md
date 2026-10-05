# Practice HR: professional registration checks — design

**Date:** 2026-10-05. **Status:** for review. Backlog item 3 after spec 3
(`2026-10-04-onboarding-documents-design.md`), which it builds on: the
`checks` app and its **Professional registration** check type, the
`compliance` app's reminder schedule and morning digest, the Employee
admin's Compliance tab, the dashboard Compliance card, and the nightly job.

## What this is for

Every clinician must hold a current registration with their professional
body, and for GPs also a place on the Welsh medical performers list. Today
HR looks each one up by hand on the regulator's website and notes the date
in a spreadsheet. Success is: the registration number recorded once,
checked against the register on a schedule without anyone logging in, a
problem (lapsed, suspended, conditions, struck off, not found, wrong
person) emailed to HR and the line manager the next morning, and a
one-click check with the register's own words when HR wants to see now.

## Decisions made in conversation

| Decision | Why |
|---|---|
| The lookups read the regulators' public register search pages (scraping). | None of the four bodies offers a free, sanctioned machine interface: the GMC sells a full-register download, the NMC has a ten-PIN employer login, the GPhC and the Welsh list have web searches only. The practice accepts the terms-of-use and fragility risk. |
| Each person is checked every 7 days by default, the load spread across the nightly runs. | Weekly notices a lapse soon enough; nightly for everyone is the pattern most likely to get the practice's address blocked. |
| HR runs on-demand checks and sees everything; the person sees their own registration and its last outcome on My record; managers get the alert email only. | Keeps spec 3's line: managers see counts and alerts, never the detail of someone's checks. |
| A `registers` app that feeds the existing checks rather than a parallel compliance story. | A clear lookup records a Professional registration check, so the Compliance tab, dashboard, starter checklist and reminders work unchanged. |
| One number per person per body; the Welsh list is searched by the GMC number. | That is how the list is keyed. |
| A problem goes to the manager with the body and the register's words, unlike the lapsed-check notice. | A registration problem is something the manager must act on that day. |
| Unreadable pages are HR's concern only, and only after 14 days or when a body pauses. | A site change is not a clinical risk; a silent stall would be. |
| The fetched page is never stored, only its hash and the parsed words. | Nothing to leak; enough to tell a page changed. |

## Global constraints

Those of spec 3 (`timezone.localdate()`, services are the only writers,
pages never write on GET, no PII in logs, secrets from the environment),
and:

- **Tests make no network calls.** Every adapter's fetch is one function
  that tests replace; one test proves nothing reaches a socket. Parsers are
  tested against saved copies of real result pages kept in the repository.
- **The live register pages cannot be reached from the build sandbox.**
  Capturing the fixtures is a documented step for a person on a machine
  that can reach the sites. Until a body's fixtures exist, its adapter is
  **not verified** and runs only on demand.
- **No lookup ever raises out of the nightly job.** A failure is a logged
  class name and an `unreadable` row; the digest still goes.
- **Politeness.** One request at a time, two seconds between requests to
  the same body, a ten-second timeout, a fixed descriptive user agent
  naming the practice, no retries inside a run.

## 1. Data and bodies (`registers`)

### Models

- **RegisterBody**: `name`, `code` (`gmc`, `mpl_wales`, `nmc`, `gphc`),
  `positions` (M2M to `people.PositionTitle`: the titles that need it),
  `active`, `verified` (its parser has fixtures; set by the adapter module,
  not by hand), `paused_at` (null unless the body is paused; see §2),
  `display_order`. Seeded by migration with the four bodies and no titles;
  HR assigns titles as for check types. Adding or deleting a body is not a
  user action: new bodies are code (an adapter) plus a seed.
- **Registration**: `employee` (FK, PROTECT), `body` (FK, PROTECT),
  `number`, `next_check_on` (date), and the latest lookup denormalised for
  the pages: `last_outcome`, `last_status_text`, `last_name_on_register`,
  `last_checked_at`. Unique on (employee, body). For a GP, the `mpl_wales`
  registration carries the GMC number: entering the GMC number creates or
  updates both rows (see services).
- **Lookup**: `registration` (FK, CASCADE), `run_at`, `trigger`
  (`scheduled`, `on_demand`), `requested_by` (nullable FK to the login),
  `outcome` (`clear`, `problem`, `not_found`, `name_mismatch`,
  `unreadable`), `status_text` (the register's own words, at most 200
  characters), `name_on_register`, `page_hash` (SHA-256 of the response
  body, blank on a fetch failure), `error` (the exception class or HTTP
  status, blank on success). Append-only. Pruned with the reminder log
  later (backlog).
- **Check recording.** A `clear` or `problem` outcome also records a
  **Professional registration** check through `checks.services.checks.
  record(actor=None, …)`: `done_on` today, `expires_on` by the type's
  validity, `outcome` Clear or Not clear, `reference` the number, `note`
  the status text prefixed with the body's name. `not_found`,
  `name_mismatch` and `unreadable` record no check: they are alerts. The
  check type gains nothing; it is the seeded one.

### Number formats

Refused on the form, never sent to a register: GMC seven digits; NMC two
letters, two digits, a letter and four digits (`AB12C3456`); GPhC seven
digits. Whitespace is stripped and letters upper-cased, as for NI numbers.

## 2. Adapters

### Interface

`registers/adapters/<code>.py`, each exposing `URL(number)` (the public
page for the number, used by the pages as a link) and
`lookup(number, surname) -> Result`. `Result(outcome, status_text,
name_on_register, page_hash)`; a fetch or parse failure is a `Result` with
`outcome="unreadable"` and the error class in `status_text`. The fetch is
`registers.http.get(url)`, the one function that touches the network,
returning (status, body) and raising nothing but `FetchError(reason)`.

### What clear means

- **GMC**: the number is found, status is "Registered with a licence to
  practise", and the GP register shows the doctor. Any other status
  (provisional, registered without a licence, suspended, erased, interim
  order, conditions, undertakings, administrative erasure) is a problem.
- **Welsh medical performers list**: the GMC number is present on the
  current list and not marked suspended or conditional. Absent is
  `not_found` (which, for a GP in post, is a problem for the alert).
- **NMC**: the PIN is found with "effective registration" (or the page's
  equivalent) and no restrictions, conditions or interim order noted.
- **GPhC**: the number is found with status "Registered" and no conditions
  or interim order.

The parser keeps the register's own status words as `status_text`
verbatim, so a change of wording shows as itself rather than being lost
in a category. A page that is fetched (HTTP 200) but matches none of the
recognised shapes is `unreadable`, never `not_found`.

### Name matching

A hit whose surname does not match the employee's is `name_mismatch`, never
treated as that person. Loose match: case, accents, apostrophes, hyphens
and spaces ignored; either part of a double-barrelled surname on either
side accepted; the employee's preferred name is never used. The name the
register showed is kept on the lookup and shown to HR.

### Verification and pausing

- An adapter is **verified** when its module declares fixtures for every
  outcome it can return and the test suite exercises them. The seed and a
  startup check set `RegisterBody.verified` from the adapter module. An
  unverified body is skipped by the schedule with one log line per night
  and shows "not verified" in admin; **Check now** still works, so a body
  can be tried before its fixtures exist.
- A body whose last three lookups across all registrations were
  `unreadable` is **paused** (`paused_at` set): the schedule skips it and
  HR is told once through the digest ("The <body> page could not be read;
  checks are paused until one succeeds"). A successful on-demand lookup
  clears the pause; so does **Unpause** in admin.

## 3. Services (`registers/services/`)

- `registrations.set_number(actor, employee, body, number)`: validates the
  format, creates or updates the Registration, sets `next_check_on` to
  today (checked that night), audits on the employee as `registration:<code>`
  (before → after number). For `gmc` it also creates or updates the
  `mpl_wales` row when the employee's title needs that body.
  `registrations.clear_number(actor, employee, body)` removes the row and
  audits; lookups cascade.
- `registrations.needed(employee, today)`: the active bodies the person's
  primary title needs. `registrations.missing(employee, today)`: those with
  no number.
- `lookups.run(registration, trigger, requested_by=None)`: calls the
  adapter, writes the Lookup, updates the denormalised fields, records the
  check for clear/problem, sets `next_check_on` to today + N ± 1 day
  (N from the schedule), applies the pause rule, and returns the Lookup.
  Never raises; an exception becomes `unreadable` with its class name.
- `lookups.scheduled(today)`: every registration with `next_check_on <=
  today` whose body is active, verified and not paused, in body then pk
  order, one at a time with the two-second pause between requests to the
  same body. Returns counts per outcome for the nightly line
  (`registrations: 4 run, 3 clear, 1 problem`).
- `due.due_items(today, sched)`: the compliance contract (§5 of spec 3),
  kind `registration`:
  - A standing `problem`, `not_found` or `name_mismatch` (the latest
    lookup's outcome) for a currently employed person: to every HR admin
    and to the person's line manager, label "<Body>: <status words>",
    `due_on` the lookup date, state `overdue`, URL the Compliance tab for
    HR and My team for the manager, key
    `registration:<employee>:<body>:<lookup pk>`. Not `once`: the digest
    cadence throttles repeats.
  - A body the title needs with no number entered: to HR, label "<Body>
    number not recorded", state `missing`, `due_on` the employment start,
    URL the employee's page.
  - `unreadable` standing for 14 days, and a body pausing: to HR only,
    label "<Body>: could not be read since <date>" or "… paused", state
    `overdue`, URL the admin lookups list.
- `schedule`: the existing `ReminderSchedule` gains
  `registration_every_days` (default 7, minimum 1, maximum 90), shown on
  the Reminder settings page as **Check professional registrations every
  N days**.

## 4. Pages and admin

- **Employee page, Details tab**: one number field per body the person's
  primary title needs (`gmc` and `mpl_wales` share the one field, labelled
  "GMC number"), HR-only like NI and bank, saved through `set_number`.
  Shown only when the title needs a body.
- **Employee page, Compliance tab**: a Registrations table above the checks:
  body, number, last outcome in the register's words, name shown, checked
  on, next check, **Check now** (POST to `registers:check_now`, HR only,
  runs the lookup and redirects back with the outcome as a message), and
  **On the register** linking to the adapter's URL for the number. A row
  for a needed body with no number reads "No number recorded" with a link
  to the Details tab. A paused or unverified body says so in the row.
- **Admin**: Compliance › Register bodies (list: name, titles, active,
  verified, paused; actions **Unpause**; no delete) and Compliance ›
  Registration lookups (read-only; list: run at, person, body, outcome,
  status text, trigger; filters body, outcome, trigger; search by person).
- **Dashboard Compliance card**: "Registration problems" = registrations
  whose latest outcome is `problem`, `not_found` or `name_mismatch` for a
  currently employed person, linking to the lookups list filtered to those.
- **My record**: a Registrations card: body, number, "Registered, checked
  3 Oct" or "HR will be in touch about your <body> registration" on a
  problem, "Not checked yet" before the first lookup. No button.
- **Nightly**: `hr_nightly` gains a `registrations` step after `compliance`,
  printed as it finishes; a failure of the step is logged by class, printed
  as `registrations: failed`, and does not fail the command (the digest
  already went; the next night retries).

## 5. Errors, audit, privacy

- A number that fails the body's format is refused on the form with the
  format in words. A duplicate number across employees is allowed (the
  register decides who it is; the name check catches a slip) but shown as
  a warning on save.
- `Check now` on a paused body runs anyway and lifts the pause on success.
  On an unverified body it runs and shows the outcome with "this register's
  parser is not yet verified".
- Audit: numbers entered, changed or cleared on the employee; a Check now
  press audited as a view of the person's checks, as the tab already does.
  Lookups are not audited per run; the Lookup log is the record.
- Logs: the error class, the body code and the registration pk, never the
  number, the name or the page.
- Retention: Lookups are listed under the `checks` category of the
  retention report; pruning is backlog with the reminder log.

## 6. Testing

- **Adapters**: for each body, a fixture per outcome it can return
  (`registers/adapters/fixtures/<code>/<outcome>.html`), captured by a
  person from the live site and trimmed of anything not needed to parse;
  a parser test per fixture; the `verified` flag derived from the fixture
  set so a body without them cannot be scheduled.
- **No network**: `registers.http.get` replaced by a fixture reader in
  every test; one test patches `socket.create_connection` to raise and
  runs every adapter to prove nothing connects.
- **Services**: set_number (format, normalisation, the GMC → Welsh pair,
  audit); run (each outcome's effect on the registration, the check
  recorded only for clear/problem, next_check_on spread ±1 day, never
  raises); scheduled (only due, active, verified, unpaused; pause after
  three unreadable; unpause on success); due_items (every recipient and
  label per outcome, the missing-number item, the 14-day unreadable rule);
  the schedule setting's bounds.
- **Pages**: Check now HR-only and POST-only; the tab's rows for each
  state; My record wording; dashboard count; Details-tab field present
  only when the title needs a body; admin lists render.
- **Docs**: every bold label in the guides matches the UI.

## Documentation

- `docs/admin/compliance.md`: a Registrations section — the bodies, what
  clear means per body, the schedule, pausing and unpausing, capturing
  fixtures, the terms-of-use note (the practice reads public pages at a
  gentle rate and identifies itself; if a regulator objects, deactivate the
  body and record checks by hand).
- `docs/guides/hr-administrator.md`: "Recording someone's professional
  registration", "Checking a registration now", "When a registration check
  fails" (problem, wrong person, not found, page could not be read).
- `docs/guides/manager.md`: the alert email and what to do.
- `docs/admin/people.md`: the number fields on the Details tab.
- `docs/superpowers/backlog.md`: item 3 closes; fixture capture and the
  GMC download service (if the practice later wants it) are noted.
- `deploy/`: the user agent string is built from `SITE_URL`; no new
  environment variables.

## Not done, on purpose

Other registers (HCPC, GDC) until the practice employs those roles;
revalidation dates; the GMC download service; reading the NMC employer
confirmations service; alerting the person themselves (HR decides what
to say); any attempt to work around a regulator blocking the practice.
