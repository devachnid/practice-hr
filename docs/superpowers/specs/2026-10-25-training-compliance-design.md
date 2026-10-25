# Practice HR: training compliance — design

**Date:** 2026-10-25. **Status:** for review. Spec 4 of the set in
`2026-09-27-practice-hr-foundation-and-absence-design.md`, and backlog item
3 after the professional registration checks (merged as #22). It builds on
spec 3 (`2026-10-04-onboarding-documents-design.md`): the `checks` app's
shape, the `documents` app's files, `people.PositionTitle`, the
`compliance` package's due-items contract, reminder schedule and morning
digest, the Employee admin's Compliance tab, the dashboard Compliance card
and the nightly job.

## What this is for

Every member of staff must hold current training in a set of subjects that
depends on their role: basic life support, safeguarding, fire safety,
information governance and the like, most of it annual or three-yearly.
Today the record is a spreadsheet and a folder of certificates, and a CQC
inspector asks to see the matrix. About seven in ten completions are
e-learning with a PDF certificate; the rest are face-to-face sessions run
for a group on one day.

Success is: each person uploads their own certificate and HR verifies it
rather than types it; a manager records a group session once for everyone
who attended; nobody's training lapses silently; and the training matrix,
filtered by course, team or person, is on screen or downloaded in under a
minute when an inspector asks.

## Decisions made in conversation

| Decision | Why |
|---|---|
| A new `training` app, built on the shared pieces, not an extension of `checks` and not a generic requirements engine. | Training's rules differ from checks' (managers see everything, staff record their own, group sessions, verification, a matrix). A kind flag on checks would put a filter on every checks query and the word "check" on every training page. Spec 3 rejected the generic engine, and nothing has changed. |
| The two helpers both apps need, expiry arithmetic and the status rule, move from `checks` into the shared `compliance` package. | Moved, not copied: one place to fix. |
| Staff record their own completions, with the certificate; HR or the line manager verifies. Managers record for their reports too. | HR's work becomes checking rather than typing. Managers run the group sessions. |
| A line manager sees everything about their reports' training, certificates included. | Training is not health or identity material. Chasing and recording need the detail. |
| A course is required by position title, or of everyone by a switch. | The switch stops the common omission of a new title from a practice-wide course. |
| A group session needs no file; an attendance sheet may be attached and is shared by every record from that session. | A sheet does not always exist; the record of who ran it and when is the evidence. |
| The matrix page, filtered by course, team, person and status, with a CSV download. | What an inspector asks for. CSV opens in Excel and needs no library. |
| Reminders always go to the person as well as HR. | The person does the course. There is no case for an HR-only training reminder. |
| Nothing is edited or deleted. A pending record HR turns down is rejected with a note and stays in history. | The append-only line from spec 3. |

## Global constraints

Those of spec 3 (`timezone.localdate()`, services are the only writers,
pages never write on GET, no PII or secrets in the repository or logs, no
network in tests, tests never expire with the calendar, every behaviour an
HR admin meets documented in `docs/admin/` and in the plain-language guides
where staff meet it), and:

- **Files never leave the application unchecked.** Certificates and
  attendance sheets are `documents.File` rows; every download goes through
  `documents.files.open`, which applies the access rules and writes the
  audit "viewed" row.
- **Append-only.** Training records and sessions are never edited or
  deleted; `expires_on` is the one field HR may change after the fact, as
  on a check. Mistakes are put right by recording again or rejecting.
- **A manager acts only for their own reports.** Every write a manager
  makes is checked against their direct reports on the day, including each
  attendee of a session.

## 1. Models (`training`)

### `Course`

- `name` (char 60, unique), `code` (slug 40, unique), `display_order`
  (default 100), `active` (default True).
- `validity_months` (nullable, 1 or more; blank means a one-off that never
  renews).
- `everyone` (bool, default False): required of every currently employed
  person. When false, `positions` (M2M `people.PositionTitle`, blank) names
  the titles that need it. A course with neither is optional: recorded when
  someone has done it, required of nobody.
- `delivery`: `online` or `face_to_face`. A label: it sets the default on
  the record form, decides whether a self-recorded completion must carry a
  certificate (online: yes; face-to-face: no), and chooses the reminder
  wording. Nothing else hangs on it.

Seeded by the first migration with no titles and `everyone` false, as the
check types were, so nothing is owed until HR sets it up. A starting list,
not a rule; HR renames, deactivates or adds:

| Course | Delivery | Valid for |
|---|---|---|
| Basic life support | Face to face | 12 months |
| Fire safety | Online | 12 months |
| Information governance | Online | 12 months |
| Infection prevention and control | Online | 12 months |
| Safeguarding children | Online | 36 months |
| Safeguarding adults | Online | 36 months |
| Equality and diversity | Online | 36 months |
| Health and safety | Online | 36 months |
| Conflict resolution | Online | 36 months |
| Chaperone | Online | One-off |

### `TrainingRecord`

Append-only. The latest by `done_on` among verified, unrejected records is
the one that counts.

- `employee` (PROTECT), `course` (PROTECT), `done_on`, `expires_on`
  (nullable; defaulted from validity, editable by HR), `note` (text, blank;
  seen by HR and the line manager, never the person).
- `certificate` (FK `documents.File`, nullable, PROTECT): the person's
  file, category Certificate, never HR-only, so it also appears in My
  record › Documents.
- `session` (FK `TrainingSession`, nullable, PROTECT): the group session
  this record came from.
- `recorded_by` (user, SET_NULL), `recorded_at`.
- `verified_by` (user, nullable, SET_NULL), `verified_at` (nullable). Set
  at creation when HR or a manager records; null while a self-recorded
  entry waits.
- `rejected_at` (nullable), `rejected_note` (char 200, blank): set by
  `reject`. A rejected record counts for nothing and stays in history.

Ordering `-done_on, -id`. Indexes on (`employee`, `course`).

### `TrainingSession`

- `course` (PROTECT), `held_on`, `trainer` (char 120, blank: an outside
  provider or a colleague's name), `note` (text, blank).
- `attendance_sheet` (FK `documents.File`, nullable, PROTECT): a file with
  no employee, category Certificate, `hr_only` false.
- `recorded_by`, `recorded_at`.

Recording a session makes one verified `TrainingRecord` per attendee,
each pointing at the session, so every person's history reads normally.
A person left off is added by recording the session again with just them.

## 2. Shared helpers (`compliance/validity.py`)

Two functions move out of `checks/services/checks.py`, with their tests:

- `expires_from(done_on, validity_months)`: `done_on` plus the months,
  clipped to the month's end; `None` when the validity is blank.
- `status(latest_expires_on, has_latest, required, today, window_days)`:
  `not_required`, `missing`, `current`, `due_soon` (expiry within the
  window), `lapsed`. Checks' two extra cases (`awaiting`, an unclear
  outcome) stay in the checks service around the call.

Checks imports both from the new module. No behaviour changes; the checks
tests still pass unchanged apart from the import.

## 3. Services (`training/services/`)

### Reading (`training/services/training.py`)

- `required_for(employee, today)`: active courses with `everyone`, plus
  active courses whose `positions` include the title of the current
  primary position. No current employment: nothing.
- `state(employee, today, window_days)`: one `Row` per required course and
  per other course the person has any record of, ordered by
  `display_order, name`: `course`, `latest` (the counting record or None),
  `pending` (the newest unverified, unrejected record or None), `rejected`
  (the newest rejected record newer than `latest`, or None), `status`,
  `expires_on`. Status from the shared rule, then: a pending record on a
  `missing` or `lapsed` row makes it `awaiting_verification`. Labels:
  Current, Due soon, Lapsed, Missing, Not required, Awaiting verification.
- `summary(employee, today, window_days)`: counts per status and the next
  expiry, for the team card.
- `matrix(today, course=None, team=None, employee=None, only_problems=False)`:
  people (currently employed, matching the filters, ordered by surname)
  down, courses (active, needed or held by at least one of them) across,
  each cell a `Row` or None. Built from one query for the people, one for
  the records, one for the courses; never a query per cell.
- `to_verify(today)`: the pending records across the practice, for the
  dashboard count and the matrix's status filter.

### Writing

- `record(actor, employee, course, done_on, upload=None, expires_on=None,
  note="")`: HR, or the person's line manager on the day
  (`access.may_record_training_for`). Validates `done_on <= today`, the
  course is active, the file if given (through `documents.files.add`).
  Verified at creation. Audits `training.recorded`.
- `self_record(actor, course, done_on, upload=None)`: the person, for
  themselves. A pre-start starter may. The file is required when the
  course is online, optional for face to face. Creates an unverified
  record. No email: it reaches HR through the next digest's "to verify"
  lines and the dashboard count. Audits `training.self_recorded`.
- `verify(actor, record)`: HR or the person's line manager, on an
  unverified, unrejected record. Sets `verified_by`, `verified_at`.
  Audits.
- `reject(actor, record, note)`: the same people; the note is required.
  Sets `rejected_at`, `rejected_note`. Emails the person (through the
  existing email helpers) with the course, the note and the link to My
  record to record again. Audits.
- `record_session(actor, course, held_on, attendees, trainer="", note="",
  upload=None)`: HR for anyone; a manager only when every attendee is a
  direct report on `held_on`, else `PermissionDenied` for the whole call.
  Validates `held_on <= today`, at least one attendee, the course active.
  In one transaction: the sheet (if any) through `files.add` with no
  employee, the session, one verified record per attendee with
  `done_on = held_on`. Audits once per attendee.
- `set_expiry(actor, record, expires_on)`: HR only; the one edit.
  Audits.

Nothing else writes. There is no delete.

### Access (`people/services/access.py`)

- `can_view_training(user, employee)`: HR, the person, their current line
  manager.
- `may_record_training_for(user, employee, day)`: HR, or the line manager
  of the person on `day`. Never yourself.
- `may_verify(user, record)`: the same rule as recording, for the record's
  employee today.
- `can_view_file` gains two cases: a file that is a training certificate is
  visible to the person's current line manager; a file that is an
  attendance sheet is visible to HR and to any manager with a direct report
  on that session. Both found by the reverse relation from `File`.

A pre-start starter is treated as the employee for their own training and
may self-record; nothing is required of them before their start date
because `required_for` finds no current employment.

## 4. Pages and admin

### My record › Training (everyone; Getting started for a pre-start starter)

The person's rows from `state`: course, status, date done, expiry, a link
to the certificate (audited download), and **Record** opening a form on the
page: date done, certificate file, submit to `training:self_record`
(POST only). A pending row shows *Awaiting verification* and the upload
date; a rejected row shows the note and the Record button again. Required
courses first, then extra ones the person has done. The HR note is never
shown here.

### My team › Training (line managers)

One card per report with `summary` counts and the next expiry, linking to
**their training page** at `training:person` (`/training/<employee>/`): the
same table with the note column, a **Record for this person** form (POST
`training:record`), and **Verify** / **Reject** on pending rows (`Verify`
POSTs; `Reject` opens a confirm page asking for the note, then POSTs).
Above the cards, **Record a session** (`training:session`): course, date,
trainer, attendance sheet, tick boxes for the manager's reports on that
date. A manager who is nobody's manager sees no training card.

### Admin › Compliance

- **Courses**: list and edit, with `positions` as a filter widget, the
  `everyone` switch and `delivery`.
- **Training records**: changelist filtered by course, employee, status
  (current, due soon, lapsed, awaiting verification, rejected); the add
  page is the record form and calls `record`; afterwards `expires_on` is
  the only editable field (`set_expiry`). Detail actions **Verify** and
  **Reject** (confirm on GET, act on POST, as the registers' Unpause).
- **Training sessions**: changelist and an **Add** page that is the
  record-a-session form with everyone currently employed available.
- **Training matrix** (`/admin/training/matrix/`): the grid from `matrix`.
  Cells coloured by status with the expiry date; a pending cell reads
  *To verify* and links to the record. Filters: team, course, person
  (name search), and *problems only* (people with something lapsed,
  missing or to verify). **Download** gives the filtered grid as CSV:
  `training-matrix-<filter>-<yyyy-mm-dd>.csv`, one row per person, one
  column per course, a cell "Status, dd Mon yyyy". All GETs; the page
  writes nothing.

### Admin home and the Compliance tab

The Compliance card gains **Training lapsed or missing** and **Training to
verify**, each linking to the matrix with the matching filter. The
Employee admin's Compliance tab gains a Training table under Registrations
with the person's rows from `state`.

## 5. Reminders, dashboard, retention

### Due items (`training/services/due.py`)

Added to the digest's `SOURCES`. For each currently employed person and
each required course with status `due_soon`, `lapsed` or `missing`:

- a `DueItem` to every HR admin and one to the person (always), kind
  `training`, keyed `training:<employee>:<course>:<due>:<status>`, so the
  existing sent log applies the X/Y/Z cadence unchanged; `missing` is owed
  from the employment start date, as with checks;
- the line manager gets one line, `once`, the first time a course lapses,
  naming the course (managers see training detail);
- a course with a pending record produces no line to the person and one
  line to HR with state `to_verify`, keyed `training:verify:<record>`, so
  it repeats on the overdue cadence until someone acts.

The person's wording follows `delivery`: "Complete the e-learning and
upload your certificate" or "Ask your manager about the next session". The
digest template gets a **Training** heading beside Checks and Policies.

### Dashboard

`compliance_counts` adds the two training counts.

### Retention

`RETENTION_DAYS_TRAINING` joins the categories (default six years). The
retention report lists a leaver's training records and sessions once past
the period; certificates are already covered by `files`. Nothing is
deleted by the system.

## 6. Errors, audit, privacy

- A manager acting outside their team gets `PermissionDenied` before any
  write; a session with one outsider writes nothing.
- A self-recorded online course without a file is a `ValidationError`
  shown on the page; a bad file is refused by `files.add` as today.
- Audit rows: `training.recorded`, `training.self_recorded`,
  `training.verified`, `training.rejected`, `training.session_recorded`
  (one per attendee), `training.expiry_changed`, and `file.viewed` on
  every download.
- The HR note never reaches the person's page, the digest or the CSV.
- Emails name the course and the note; never the certificate.

## 7. Testing

No network, no calendar dependence (every test passes a `today`),
services as the only writers.

- `compliance/validity.py`: the moved tests pass unchanged; month-end
  clipping; the status table.
- `required_for`: everyone, titles, both, no employment, inactive course.
- `state`: every status, including pending on missing and on lapsed,
  rejected newer than the latest, extra courses, ordering.
- `record`, `self_record`, `verify`, `reject`, `record_session`,
  `set_expiry`: who may, validation, the file rules by delivery, the
  session's single transaction (one outsider, nothing written), audits.
- `matrix`: each filter alone and together, problems only, query count
  bounded, CSV content and filename.
- `due_items`: keys, recipients, manager once, pending suppresses the
  person and adds the HR line, missing from start date, wording by
  delivery.
- Pages: each role on GET and POST; a manager refused on another team's
  person and session; a pre-start starter's self-record; downloads
  audited; the admin actions confirm on GET and act on POST.
- Access: certificate visible to the line manager, sheet visible to HR
  and a manager with a report on the session, nobody else.
- Docs tests: the new sections exist in the admin doc and the guides.

## Documentation

In the same PR: `docs/admin/compliance.md` gains a Training section
(mental model, courses and the everyone switch, recording, verifying,
sessions, the matrix and download, reminders); `docs/admin/people.md` the
Compliance tab's Training table; `docs/guides/hr-administrator.md` the
going-live steps (assign titles, switch on everyone courses, invite staff
to upload what they hold); `docs/guides/manager.md` the team training
page, verifying and sessions; the staff guide the My record card and
recording your own; `README.md` the app list; the backlog closes item 3 and
records what is parked.

## Not done, on purpose

- Course levels and equivalence (safeguarding level 3 satisfying level 2):
  separate courses for now.
- Importing an e-learning platform's completion export.
- A certificate pack download or a per-course certificate bundle.
- Bookings, waiting lists or a training calendar.
- Editing or deleting a record.
