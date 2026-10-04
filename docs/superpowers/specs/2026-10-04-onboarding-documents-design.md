# Practice HR: onboarding, offboarding and documents — design

**Date:** 2026-10-04. **Status:** for review. Spec 3 of the set in
`2026-09-27-practice-hr-foundation-and-absence-design.md` ("The set, and where
this spec sits"). Builds on that spec's people model, roles, audit, nightly
job, email and retention report, all of which exist and are in use.

## What this is for

The practice's starter and leaver process, the dated checks every employee
must hold, and each person's documents are paper files and spreadsheets
today. Nothing is imported: records start fresh here. Success is HR running
a starter or leaver from one checklist without a separate spreadsheet,
managers seeing what is outstanding for their people, policies signed with
proof, and nothing lapsing silently.

## Decisions made in conversation

| Decision | Why |
|---|---|
| Start fresh; no import of existing checks or documents. | They are paper and assorted spreadsheets. |
| Starters do their own part before day one, with a login issued before they start. | HR verifies rather than types. A pre-start login is acceptable. |
| Checks are admin-defined types, required by **position title**. | The list (right to work, DBS, references, occupational health, Hep B, indemnity, professional registration) is right today and will change. |
| Managers see no documents, ever. | The file holds health and identity material. |
| Policies apply by position title; a new version must be signed again by everyone it applies to. | Compliance, not convenience. |
| Signing asks for the person's password (or passkey) in the same form. | A signature should prove presence, not just a session. |
| Checklist items have an owner: HR, the manager, or the person. No fourth owner. | Matches who does the work. |
| Reminder cadence is a practice setting: start X days before due, every Y days until due, every Z days overdue. Default 60, 30, 7. | HR tunes it without a code change. |
| The person is reminded as well as HR only for check types flagged for it (DBS and right to work by default). | Other checks are HR's business. |
| Three focused apps sharing one "what is due" contract and one morning digest, not a generic requirement engine. | Each reads like the thing it is; the digest is what spec 4 plugs into. |

## Global constraints

Everything in the foundation spec's global constraints applies: services are
the only writers; `timezone.localdate()`; pages never write on GET; no
network in tests; no PII or secrets in the repository; tests never expire
with the calendar; every behaviour an HR admin meets is documented in
`docs/admin/` and, where staff meet it, in the plain-language guides.

In addition:

- **Files never leave the application unchecked.** Every download goes
  through a view that applies the access rules and writes an audit "viewed"
  row. Nothing under `MEDIA_ROOT` is served by the web server directly.
- **Nothing is deleted automatically.** Files, checks, signatures and
  checklists are append-only or soft-superseded; the retention report lists
  what is due for deletion and a person does it.
- **No model identifier, no plaintext credential, no file content in logs.**

## 1. Architecture, storage, access

Three new apps in `practice-hr`: `checks`, `documents`, `onboarding`. Each
has models, services (the only writers), views, templates, admin, tests and
its page of `docs/admin/`. A small shared module, `compliance` (a Python
package, not a Django app), holds the due-items contract and the digest.

**Files.** Under `MEDIA_ROOT/<app>/<yyyy>/<opaque id>.<ext>`. The row keeps
the original filename, content type, size, SHA-256, uploader and time.
Accepted: PDF, JPEG, PNG, DOCX; 10 MB cap; the content is sniffed, so a
file whose bytes do not match its extension is refused. The existing backup
timer already copies `MEDIA_ROOT`.

**Access rules**, in `people/services/access.py`, extending what exists:

| Who | Checks | Files | Policies | Checklists |
|---|---|---|---|---|
| Employee | own: dates, status, outcome; not HR's note | own, except files marked HR-only | the versions that apply to them; sign | own items |
| Line manager | a per-report summary: counts and next due date, no detail | nothing | nothing | the items they own, for their reports |
| HR admin | all, write | all, write; every view audited | all, write | all, write |
| Pre-start starter | as employee, through **Getting started** only | as employee | as employee | own items |

A pre-start starter is a login linked to an employee whose only employment
has a `start_date` after today. Until that date, every page but **Getting
started** and the account page redirects there; from the start date the
normal pages open. The login is created the usual way (invitation email).

**Sensitive material.**
- DBS: the check records the certificate number, issue date, disclosure
  level (basic, standard, enhanced, enhanced with barred lists) and whether
  the update service applies. No certificate image is stored, following the
  DBS code of practice.
- Right to work: the evidence file is stored (a retained copy is required).
- Bank details: `Employee` gains `bank_account_name`, `bank_sort_code`,
  `bank_account_number`, HR-only, viewed-audited like `ni_number`, shown on
  the payroll changes report's new-starter rows.

**Retention.** `RETENTION_DAYS_*` gains categories `checks`, `files` and
`signatures`; the retention report lists a leaver's rows in each once the
period passes. Nothing is deleted by the system.

## 2. Checks

### Models (`checks`)

- `CheckType`: `name` (unique), `code` (slug, unique), `validity_months`
  (nullable; blank means one-off), `evidence` (`none`, `file`, `reference`),
  `remind_person` (bool, default False), `positions` (M2M to a new
  `people.PositionTitle` — see below), `display_order`, `active`. Seeded:
  Right to work (file, remind person), DBS (reference, 36 months, remind
  person), References (none, one-off), Occupational health (file, one-off),
  Hep B immunity (file, one-off), Indemnity (file, 12 months),
  Professional registration (reference, 12 months).
- `Check`: `employee`, `check_type`, `done_on`, `expires_on` (nullable;
  defaulted from validity, editable), `outcome` (`clear`, `clear_with_notes`,
  `not_clear`), `reference` (char 60), `note` (text, HR-only), `evidence`
  (FK `documents.File`, nullable), `recorded_by`, `recorded_at`, `awaiting`
  (bool: created by HR to ask the person for evidence; cleared when HR
  completes it). DBS extras as fields: `dbs_level`, `dbs_update_service`.
  Append-only: a renewal is a new row; `done_on` is the ordering key.

**Position titles.** Today `Position.title` is free text. This spec adds
`people.PositionTitle` (`name` unique, `display_order`) and makes
`Position.title` a FK to it, with a data migration that creates one row per
distinct existing title. Check types, policies and checklist templates all
target `PositionTitle`. The admin offers the titles as a list; HR adds a new
title in **People › Position titles**.

### Services (`checks/services/`)

- `required_for(employee, today)`: the active check types required by any
  current primary position's title.
- `state(employee, today)`: one row per required type (and per extra type
  that has a check): the latest check, and a status from `current`,
  `due_soon` (inside the reminder window from §5), `lapsed` (expired),
  `missing` (required, no clear check), `not_required` (has rows, type no
  longer required), `awaiting` (asked of the person).
- `record(actor, employee, check_type, done_on, outcome, **fields)`: HR
  records a check; validates `done_on <= today`, outcome, DBS fields when
  the type is DBS, evidence when the type needs it; closes any linked
  checklist item (§4); audits.
- `ask(actor, employee, check_type)`: HR creates an `awaiting` row the
  person can upload evidence against from My record; `complete(actor,
  check, ...)` turns it into a recorded check.
- `upload_evidence(actor, check, file)`: the person, on their own awaiting
  check; HR, on any.

A position change re-evaluates `required_for` on the next read; nothing is
written. A check whose type is no longer required stays in history and is
not chased.

### Pages

- My record › **Checks**: each required type with its status, dates and
  outcome; an awaiting check shows the upload form.
- My team › per report: counts (current, due soon, lapsed, missing) and the
  next expiry date. No names of checks beyond the counts.
- Admin › Compliance › Checks: changelist filtered by type, status,
  employee; the add page is the record form; evidence download audited.

## 3. Documents and policies

### Models (`documents`)

- `File`: `employee` (nullable: policy versions have none), `category`
  (`contract`, `offer`, `identity`, `certificate`, `occupational_health`,
  `correspondence`, `policy`, `other`), `title`, `path` (opaque), `original_name`,
  `content_type`, `size`, `sha256`, `uploaded_by`, `uploaded_at`, `hr_only`
  (bool), `superseded_by` (self FK, nullable), `superseded_note`.
- `Policy`: `title`, `positions` (M2M `PositionTitle`; empty means
  everyone), `active`.
- `PolicyVersion`: `policy`, `label` (e.g. "v3, Oct 2026"), `file`,
  `issued_on`, `sign_within_days`, `issued_by`. The latest by `issued_on` is
  current.
- `Signature`: `employee`, `version`, `signed_at`, `method` (`password`,
  `passkey`), `confirmation_text` (the exact sentence shown), `ip_address`.
  Unique on (employee, version). Immutable.

### Services (`documents/services/`)

- `files.add(actor, employee, category, title, upload, hr_only=False)`:
  validates type, size and sniffed content; writes the file and row;
  audits. `files.supersede(actor, file, note)`.
- `files.open(actor, file)`: the access check and the audit "viewed" row;
  returns the response. Every download view calls it.
- `policies.issue(actor, policy, label, upload, issued_on, sign_within_days)`:
  a new version; every person it applies to now owes a signature.
- `policies.owed(employee, today)`: the current versions that apply to the
  employee and lack their signature, each with its due date
  (`issued_on + sign_within_days`, or the start date plus the period for a
  starter) and state (`awaiting`, `overdue`).
- `policies.sign(actor, version, credential)`: re-authenticates `actor`
  with the password or passkey assertion given (reusing the account app's
  checks; a wrong password counts towards the lockout as today); writes the
  `Signature`; closes any linked checklist item; audits. Fails closed.
- `policies.state(employee, today)`: per applicable policy: signed (version,
  when), awaiting, overdue.

### Pages

- **Policies** (nav, everyone): the policies that apply to you, each with
  signed/awaiting/overdue, a link to read the current version, and **Sign**
  which opens the sign page: the document, the confirmation sentence
  ("I confirm I have read and understood <title> <label>."), the password
  field or a passkey button, **Sign**.
- My record › **Documents**: own files (not HR-only ones), by category.
- Admin › Compliance › Policies (versions inline; **Issue new version**
  action), Files (per-employee, with upload), Signatures (read-only).

## 4. Checklists, starters and leavers

### Models (`onboarding`)

- `ChecklistTemplate`: `kind` (`starter`, `leaver`), `name`, `positions`
  (M2M `PositionTitle`; empty means the default for the kind), `active`.
- `TemplateItem`: `template`, `order`, `title`, `instruction` (text),
  `owner` (`hr`, `manager`, `person`), `due_rule` (`before_start`,
  `after_start`, `before_end`, `after_end`), `due_days`, `link` (`none`,
  `details`, `upload:<category>`, `sign_policies`, `check:<check type code>`).
- `Checklist`: `employment`, `kind`, `template` (nullable FK, informational),
  `created_at`, `created_by`, `completed_at` (nullable).
- `ChecklistItem`: `checklist`, `order`, `title`, `instruction`, `owner`,
  `owner_employee` (nullable: the manager resolved at creation; HR items
  have none), `due_on`, `link`, `state` (`open`, `done`, `not_needed`),
  `done_by`, `done_at`, `note`.

Seeded templates: a default starter list (details collected; policies
signed; right to work evidence; references; DBS; occupational health;
contract issued; induction; systems access; buddy named) and a default
leaver list (handover; equipment returned; systems access removed;
smartcard returned; final pay; file closed), each item with an owner and a
due rule, for HR to edit.

### Services (`onboarding/services/`)

- `start(actor, employment)`: called by `people.services.employments` when
  an employment is created with a future or recent start date: picks the
  starter template matching the primary position's title (else the default),
  copies its items, resolves owners (manager from the primary position's
  line manager; HR as a group; the person), computes `due_on` from
  `start_date`; audits. Reports, not fails, when no template exists or the
  position has no manager: the checklist is created with those items
  flagged and the Starters and leavers page shows the gap.
- `leave(actor, employment)`: the same for the leaver template when
  `end_date` is set (from `employments.end`).
- `complete(actor, item, note="")`: the owner, or HR for anyone; records
  who and when. `not_needed(actor, item, note)`: HR only, note required.
  `add_item(actor, checklist, ...)`, `remove_item(actor, item)`: HR, on one
  person's checklist.
- Linked items close themselves: `details` when the self-service form is
  submitted and HR marks it verified; `upload:<category>` when a file of
  that category is added for the person; `sign_policies` when
  `policies.owed` is empty; `check:<code>` when a clear check of that type
  is recorded. Each of those services calls `onboarding.services.linked_done`
  after its own write.
- `open_items(employee, today)`, `items_owned_by(employee, today)`,
  `summary(employment)` for the pages.

### Self-service details

The `details` item opens one form: preferred name, personal email, phone,
address, emergency contacts, NI number, bank details. Submitting writes
through `people.services.employees.update` and the emergency-contact
service, so each change is audited. The person may return to it until HR
marks the item verified; afterwards contact details stay editable on My
record as now, and the rest is HR's.

### Pages

- **Getting started** (pre-start, the only page): the person's items in due
  order, each opening its form, upload or sign page inline; a progress
  line.
- My record › **Your checklist** (from the start date until complete).
- My team › **To do** card: the manager's open items across reports, with
  person, item, due date, and a **Done** control (POST).
- HR › **Starters and leavers**: every open checklist with the person,
  kind, start or end date, completion fraction, oldest overdue item and its
  owner; opening one shows every item with owner and state and lets HR act
  on any. Gaps (no template, no manager, no check types for the title) are
  listed at the top.

## 5. Reminders and the digest

### The contract

`compliance/due.py` defines `DueItem(employee, recipient, kind, label,
due_on, state, url)` with `state` in `due_soon`, `due_today`, `overdue`,
`lapsed`, `missing`, and each app exposes `due_items(today, schedule)`
returning a list of them:

- `checks`: for each required type per employee: `due_soon` within the
  schedule window before `expires_on`; `lapsed` after it; `missing` when no
  clear check exists and the employment has started. Recipients: the HR
  admins; the person too when `remind_person`; the line manager once when
  a check lapses.
- `documents`: an owed policy signature past its due date is `overdue`,
  within the window `due_soon`. Recipient: the person; HR once overdue.
- `onboarding`: an open item is `due_soon` within the window, `due_today`,
  then `overdue`. Recipient: the owner (the manager, the person, or the HR
  admins).

### The schedule

`compliance.ReminderSchedule`, a single row edited at **Admin › Compliance
› Reminder settings**: `start_days_before` (X, default 60), `every_days_before`
(Y, default 30), `every_days_overdue` (Z, default 7). The window is
"within X days of due". A reminder for an item is sent on the first day it
is due soon, then every Y days while still before the due date, on the due
date, then every Z days while overdue or lapsed. The "sent" log
(`compliance.ReminderSent`: recipient, item key, sent_on) decides what is
due to go today; an item whose state or due date changes starts its cadence
again.

### The digest

The nightly job, after year end and the chase, calls `compliance.digest.run(today)`:
collects every app's `due_items`, filters by the schedule and the sent log,
groups by recipient, and sends one email per recipient: sections per
person, lines per item with its state, due date and link. HR admins as a
group get one email each. Sends use the existing `absence.services.notify`
delivery (templates in `templates/email/compliance_*.txt`) and the
`EmailFailure` log. Nothing is sent to a recipient with no items. The
nightly result gains `reminders_sent` and `reminders_failed`.

## 6. Admin, navigation, dashboard

- Admin sidebar group **Compliance**: Check types, Checks, Policies, Files,
  Signatures, Checklist templates, Checklists, Reminder settings. **People**
  gains Position titles.
- Each Employee admin page gains a **Compliance** tab (read-only summary
  with links): checks by status, policies by status, open checklist items.
- Dashboard card **Compliance**: lapsed checks, missing checks, overdue
  signatures, overdue checklist items, each linking to the filtered list.
- Nav: **Policies** for everyone (desktop and the phone More sheet); the
  manager's To do card lives on My team; HR's Starters and leavers under
  the admin group and linked from the dashboard card.

## 7. Errors, audit, retention

- Uploads: refused with a plain message for type, size or mismatched
  content; nothing is written on refusal.
- Signing fails closed: a failed re-authentication writes no signature and
  shows the login form's own error text; the lockout counts it.
- Checklist creation never fails an employment save: gaps are recorded on
  the checklist and surfaced on the Starters and leavers page.
- Audit: every write goes through a service that records an `AuditEntry`;
  every file view and every HR view of a person's checks or bank details
  records a "viewed" entry.
- Retention: the three new categories on the report; the file rows and
  their bytes are listed together so deletion by hand removes both.

## 8. Testing

As the foundation spec: pytest-django, factories, no network, no literal
calendar years, services the only writers, pages never write on GET. In
particular: access rules per role for every new page and every download
(employee own, other employee, manager, HR, pre-start, anonymous); the
pre-start redirect; append-only checks and the status table; policy
re-sign on a new version and the signature's immutability and
re-authentication (right password, wrong password counts, passkey);
checklist creation from templates including the gap cases; linked items
closing from each source; the self-service form writing through the
employee service with audit rows; the schedule arithmetic and the once-only
sent log across a run of days; the digest's grouping and recipients; the
retention categories; migrations including the position-title data
migration on existing rows.

## Documentation

`docs/admin/compliance.md` (check types, policies, templates, reminder
settings, the digest, retention), updates to `people.md` (position titles,
bank details), `nightly` keys in the existing nightly doc, and plain-language
sections in `docs/guides/hr-administrator.md` (set up a starter, record a
check, issue a policy, work the leaver list) and `docs/guides/manager.md`
(your To do items, what you can see of a report's checks). A short
employee-facing section is added to the manager guide's "your own" part
until an employee guide exists.

## Not done, on purpose

- Automated register lookups (backlog item 3; the professional
  registration check type exists so the date is recorded now).
- Training records, courses and the role-to-course matrix (spec 4), which
  will add a fourth `due_items` source.
- E-signature services, drawn signatures, OCR of uploads, exit interviews
  as a structured form, document templating (generating a contract from a
  template), automatic deletion under retention, per-check-type reminder
  cadences (the practice-wide schedule is enough until shown otherwise).
