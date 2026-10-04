# People

**Where:** sidebar › People › Employees / Employments / Position titles / Teams / Contract types / Audit log.
Working patterns are on the admin home page, under People.

## The mental model

**Employee is the person, created once.** Nothing dated lives on it — no
job, no pay, no pattern — because a person can leave and come back, and
history has to survive that. Everything dated hangs off **Employment**, a
row representing one spell of work. A returner gets a *new* Employment row;
the old one, and everything under it, is left exactly as it was.

**Positions, contracts and pay records only end.** None of them can be
edited once saved except to set their end date — see [Changing something](#changing-something)
below. A change is a new row, not an edit to the old one, so the record
always shows what was true on any past day, not just what is true now.

**Nothing is deleted.** There is no delete button anywhere in this section
of the admin. An Employee, Employment, Position, Position title, Contract,
Team, Contract type or Working pattern stays in the database forever; ending a spell or
role is done with its end date, never by removing the row.

## Employee

`/admin/people/employee/`

An existing person's page has two tabs: **Details** (the fields below) and
**Compliance** (see [The Compliance tab](#the-compliance-tab)). The list
has a **Compliance** filter: *Lapsed checks*, *Missing checks*, *Overdue
signatures* or *Overdue checklist items* shows only the people with one or
more. The numbers on the admin home page's **Compliance** card open this
list with that filter chosen.

### Name fields

**First name / Last name** are required. **Preferred name** is optional and,
when set, is what is shown everywhere instead of the first name — reports,
the admin list, anywhere the person's name is displayed. Leave it blank for
someone who goes by their first name.

### Work email

The person's practice email address, unique across all employees whatever
its case — "Tom.Hodges@…" and "tom.hodges@…" are the same address. **Sign-in
does not read it.** What links this record to a login is the
[User](#user) field, set by hand; the `email` the rota receives when someone
signs in through this system is their *login account's* email (see
[Login accounts](sign-in.md#login-accounts)), not this one. Keep the two the
same: saving an Employee whose linked login has a different email shows a
warning saying so, because the rota matches its own accounts by the email it
receives.

### Personal email / Phone / Date of birth / Address / Postcode

Contact and personal details. Nothing else in the app reads them; they are
for HR's own reference (the emergency contact section below is what
actually gets used in a hurry).

### NI number

**Visible to HR admins only.** Anyone without [HR admin status](sign-in.md#admin-status)
sees this employee's page with the field simply absent — not blanked, not
disabled, removed from the form entirely. Each time an HR admin opens an
Employee page that has an NI number, the audit log records the view (kind
*Viewed*, field `ni_number`), as it does for pay records. Set it once; there is nothing
that depends on its format being checked, so a typo here has no effect
beyond being wrong on a report that reads it.

### Bank details

Account name, sort code and account number, for the payroll
[Starters sheet](payroll.md#the-sheets). **Visible to HR admins only**, like the
NI number: anyone without [HR admin status](sign-in.md#admin-status) sees the
page with the three fields absent. Each time an HR admin opens an Employee page
that has a sort code or account number, the audit log records the view (kind
*Viewed*, field `bank`). The starter can enter them in self-service, or HR
can enter them here. They are checked: the sort code is stored as `NN-NN-NN`
and the account number is eight digits, and anything else is refused.

### User

Links this Employee to a **login account** — see
[Login accounts](sign-in.md#login-accounts). This link, not the work email,
is what sign-in uses: the `employee_id` a relying party receives is this
Employee's, found through it. Optional: leave it blank for
someone who has no need to sign in. Without it, `hr_nightly` cannot find an
account to disable when they leave (there is nothing to disable), and they
cannot appear as themselves anywhere the app checks who is signed in.

### Emergency contacts

An inline list on the Employee page: name, relationship, phone, and a
priority (lower is contacted first). Add, edit or remove as many as needed;
these are the one exception to "nothing is deleted" in this section, because
a contact detail that is wrong is simply wrong, not history.

### The Compliance tab

Read-only: a summary of where the person stands, with a link beside each
row to act on it. Nothing on it is saved, and opening it writes nothing.

- **Checks** — one row per check type their title needs, plus any other
  type they have a check of, with its [status](compliance.md#what-each-status-means)
  and expiry. **Open** goes to the recorded check, **Open the request** to a
  request for evidence still waiting, and **Record** to the record form with
  the person and the type filled in. Someone who has not started yet is
  shown as they will stand on their first day: what their title will need,
  and whether each check will be current then.
- **Policies** — each policy that applies to them, the version they are
  asked to sign, *Signed on* a date, *Awaiting signature* or *Overdue*, and
  the sign-by date. **Open** goes to the signature, **Open the policy** to a
  policy not yet signed.
- **Open checklist items** — every open item on their starter and leaver
  checklists, whoever owns it, with its due date (marked *overdue* once it
  has passed). **Open the checklist** goes to its page under Starters and
  leavers, where it can be closed.

See [Compliance](compliance.md) for what each part means.

## Employment

`/admin/people/employment/` — also editable inline on the Employee page.

One row per spell of work. **Positions, Contracts, Working patterns and Pay
records all hang off an Employment**, not off the Employee directly — see
[The mental model](#the-mental-model).

### Start date

The first day of the spell. Employments for one employee can never overlap;
the admin refuses to save a start date that falls inside another spell for
the same person.

A spell that is already over — someone's earlier time at the practice,
entered after the fact — is added with its end date and leaving reason
filled in on the same form, and is checked against the other spells over
those real dates.

### End date / Leaving reason

Both are set together or not at all: an end date needs a reason, and a
reason with no end date makes no sense. Setting both ends the spell from
that day on — every Position, Contract and Working pattern that has no end
date of its own is not automatically ended, so a leaver whose positions and
contracts were left open still shows them as current on a day after they
left. End those too if that matters for the report in question.

Saving an end date also **cancels the person's absences that start after
it**, requested or approved (automatic bank-holiday charges included), as if
cancelled by you: an approved one's cost goes back to its pot with a
cancellation line. The [audit log](#audit-log) entry for the end date lists
them. An absence that started on or before the last day is left for you to
shorten or cancel, and one whose leave year has already been
[closed](year-end.md#adjusting-a-balance) is left as it is and listed as
not cancelled. The audit note lists the absences that could not be
cancelled first, then those that were, and is cut with an ellipsis if it is
longer than the log allows.

### Continuous service date

**Defaults to the start date; only set it earlier.** This is what service
length is reckoned from — never the start date — so it is the field to set
when reckonable service carries over from an earlier NHS post or an earlier
spell here. Leaving it blank on a returner or a transfer understates their
service; a report that tiers on service length (annual leave entitlement,
long-service pay points) will get the tier wrong.

## Position

An inline on the Employment page. A dated job: title, team, and whether it
is the **primary** one.

### Title / Team

Title is chosen from **People › Position titles**; add a new title there
first. Renaming a title renames it on every position. Team is a link to
[Team](#team). Team drives the [team headcount
warning](#team) and nothing else in this release.

### Primary

**Exactly one position can be primary on any given day.** The admin refuses
to save a second primary position whose dates overlap an existing one. The
*primary* position's line manager is the one used for approval routing —
see [Line manager](#line-manager) — so a non-clinical secondary role (a
committee seat, a locum session elsewhere in the practice) should not be
ticked primary, or its manager becomes the person's approver instead of
their real one.

### Line manager

**Who approves this person's requests.** Optional — leave it blank for
someone at the top of a reporting line, whose requests then go to the HR
admin group instead of a named person. Two rules are enforced when saving:

- **A person cannot be their own manager.**
- **The reporting line can never loop.** Naming a manager whose own chain of
  managers eventually reaches back to this employee is refused — that would
  leave nobody able to approve either person's requests, each waiting on
  the other.

### From date / To date

The position's own dated span, independent of the employment's. **Existing
positions only end** — see [Changing something](#changing-something).

## Position title

`/admin/people/positiontitle/` — the job titles the practice uses:
Receptionist, Practice nurse, Salaried GP and so on. A position's title is
chosen from this list, so add a title here before the first position that
needs it. Check types, policies and checklist templates say who they apply
to by title, which is why a title is a row here rather than free text.

**Name** is what everyone sees; each is used once. Renaming a title renames
it on every position that has it, past and present, and everything aimed at
it follows, so rename only to correct a title, not to give someone a new
job (that is a new position: see [Changing something](#changing-something)).
**Display order** sorts the list. A title cannot be deleted.

## Team

`/admin/people/team/` — the groups positions belong to.

### Name / Display order

Free text; display order (default 100) controls listing order wherever
teams are shown. Leave gaps (100, 200, 300) so a new team can be slotted in
without renumbering the rest.

### Min present

**Optional.** Warn when a request would leave fewer than this many people
of the team present on a day. Blank means never warn for this team — the
right setting for most; set it only on a team whose absence actually causes
a problem.

## Contract type

`/admin/people/contracttype/` — configurable: adding a kind of staff is a
row here, not a code change. Eight are seeded: Partner, Salaried GP and GP
trainee (sessions, full time 9 a week); Practice nurse, HCA, Reception,
Administration and Management (hours, full time 37.5 a week).

### Name

Shown wherever a contract's type is displayed.

### Unit

**Sessions or hours.** This is the unit every contract of this type is
counted in, and it is what the [one-unit-at-a-time rule](#unit) on Contract
enforces: an employment cannot hold a sessions contract and an hours
contract at the same time.

### Full time weekly

What a full working week is, in this type's unit — 9 sessions, 37.5 hours.
This is the only input to FTE: `contracts.fte()` divides an employment's
summed contracted amount by this figure. Set it wrong and every FTE figure
for that type of staff is wrong, silently. It must be more than zero; the
admin refuses 0.

### Display order

Default 100; controls listing and dropdown order. Leave gaps.

## Contract

An inline on the Employment page. A dated contractual arrangement — a
sessional GP might hold two Contract rows at once (a permanent 6 sessions
and a fixed-term 2 sessions covering a vacancy); **the contracted amount on
any day is the sum of every contract active that day**
(`contracts.contracted_amount()`).

### Contract type / Basis

[Contract type](#contract-type) sets the unit this contract counts in.
**Basis** is Permanent or Fixed term; a fixed-term contract must have an end
date — the admin refuses to save one without.

### Weekly amount

The number of sessions or hours (whichever the contract type's unit is)
this contract is worth per week. Summed with any other contract active the
same day to get the total — see above.

### From date / To date

The contract's own dated span. Must fall inside the employment's own dates.
**Existing contracts only end** — see [Changing something](#changing-something).

### Notes

A short free-text note on the arrangement — "maternity cover for X", "phased
return, review June". Nothing depends on it: it appears on the
[payroll changes report](payroll.md) and nothing else in the app reads it,
so there is nothing to get wrong beyond being unhelpful to whoever reads it
next.

### The one-unit-at-a-time rule

**An employment cannot hold contracts in two different units at once.** A
sessions contract and an hours contract with overlapping dates on the same
employment is refused when adding or ending a contract — the message is
"Concurrent contracts must share a unit (sessions or hours)." This is what
keeps `contracted_amount()` meaningful as a single number: mixing sessions
and hours in the same sum would be adding two different things. Moving
someone from a sessional to a salaried role (or the reverse) means ending
the old contract on the day before the new one starts, not adding the new
one alongside it.

## Working pattern

`/admin/people/workingpattern/` — **not** the Employment page's Working
pattern list, which only shows what exists and links here. **A new version
is always made on this page, never on the Employment page.**

### Employment / Effective from

Which spell this version belongs to, and the date it takes effect from. The
pattern in force on any day is the version with the latest `effective_from`
on or before that day (`patterns.pattern_on()`); there can be only one
version per employment per date. Add a new version rather than editing an
old one when a pattern changes — the old version stays exactly as it was
for any day before the new one takes effect.

### Days (AM units / PM units)

One row per weekday (Monday to Sunday), each with an AM and a PM figure in
the employment's contracted unit (sessions or hours). Saving replaces the
whole set of days for that version at once — it is the version's complete
week, not an incremental edit.

### The total-differs warning

**Saving does not require the week's total to match the contracted
amount**, and it is not an error when it does not — a pattern totalling
more or fewer sessions than the contract is a legitimate temporary state
(a phased return, a pattern change mid-negotiation). But the admin warns:
"Pattern totals *X* a week; contracts total *Y*." when they differ
and a contract is active that day, so a mismatch is never silent. Treat the
warning as a prompt to check whether the pattern or the contract is the one
that is wrong, not as something to clear before saving — saving with the
warning showing is fine.

## Pay record

An inline on the Employment page, **visible only to HR admins**
(`access.can_view_restricted`) — anyone else's Employment page simply has no
Pay records section. For the payroll changes report only; nothing in the
app calculates from it.

**Opening an Employment page that has any pay records logs a "viewed" audit
entry** for the HR admin who opened it, once per page load — see [Audit
log](#audit-log). There is no equivalent log for opening a page with no pay
records: the entry only exists to record who has seen pay information.

### From date / To date / Basis / Amount / Reason

Annual salary, hourly rate or per-session rate, with a dated span and a
free-text reason (a pay review, a banding change). Existing pay records can
be amended in full — unlike Position and Contract, a Pay record's basis,
amount and dates can all be changed after saving, not only its end date,
because it is a record of what was decided, not a live contractual state
with its own start/end rules.

## Changing something

**Existing Positions and Contracts only end.** The admin refuses to save
any change to an existing row other than its `to_date` — "Existing
positions and contracts only end; add a new row for a change." To change a
title, a team, a line manager, a contract type or an amount: end the old
row with the day before the change, and add a new row starting the day of
the change. This is what keeps the history honest — a title that changed on
1 April shows as two rows, not one row that silently reads differently for
dates before and after the edit.

**A refused row stops the whole save.** When a row breaks a rule — an
overlapping spell, a second primary position, a contract in the other
unit, an edit to a row that only ends — the page comes back with the
message beside that row and everything as it was typed, and nothing on the
page is saved. Fix the row, or remove it, and save again.

Employment itself is the one row that can be amended directly (its dates
and continuous service date) rather than only ended, because it is not
dated data hanging off itself the way Positions and Contracts are.

## Audit log

`/admin/people/auditentry/` — read-only: nothing can be added, changed or
deleted here by hand. One row is written automatically for every field a
service function changes (a **Change** entry, with the before and after
values) and for every view of a restricted section (a **Viewed** entry —
opening an Employment page with pay records, see [Pay record](#pay-record),
or an Employee page with an NI number, see [NI number](#ni-number)). Filter
by kind or model, or search the actor's email, the field, before/after and
note columns.

Each row keeps the email of the login that made the change as it was at
the time, as text, so a later change to that login's email does not
rewrite the log. A login that has written to the log cannot be deleted,
not even by a superuser — deactivate it instead (see
[Deactivating](sign-in.md#deactivating)).

## Retention report

`/people/retention/` (**Retention** in the admin menu, HR admins only) lists
the people whose records are past their retention period, so HR can act on
them. **It lists and deletes nothing**: there is no automatic deletion, and
deleting is a manual decision in this release.

The period runs from the end of the person's **last employment**. Anyone with
a current or future employment (a returner) is never listed. Each row is one
person with the categories that are overdue, since when, and by how many days.
No figures or absence detail appear. The categories and their defaults:

| Category | Shown as | Default | Variable |
|---|---|---|---|
| `personal` | Personal record | 2190 days (six years) | `RETENTION_DAYS_PERSONAL` |
| `pay` | Pay records | 2190 days | `RETENTION_DAYS_PAY` |
| `health` | Health records | 2190 days | `RETENTION_DAYS_HEALTH` |
| `audit` | Audit log | 2555 days (seven years) | `RETENTION_DAYS_AUDIT` |
| `checks` | Pre-employment and other checks | 2190 days | `RETENTION_DAYS_CHECKS` |
| `files` | Stored files | 2190 days | `RETENTION_DAYS_FILES` |
| `signatures` | Policy signatures | 2190 days | `RETENTION_DAYS_SIGNATURES` |

*Checks* are the person's [recorded checks](compliance.md#checks), *files*
the documents stored against them under [Files](compliance.md#files), and
*signatures* their [policy signatures](compliance.md#what-a-signature-records).
A DBS certificate is never stored, so there is none to remove. Every
category is listed for every leaver once its period has passed, whether or
not they have anything in it.

Change one with its variable in `/etc/practice-hr.env`. The
value is a whole number of days, 1 or more; anything else stops the app
starting, with a message naming the variable.
