# Compliance

**Where:** sidebar › Compliance › Check types / Checks / Files / Policies / Signatures /
Checklist templates / Checklists / Starters and leavers / Reminder settings.
Each person's [Compliance tab](#seeing-where-everyone-stands) and the admin
home page's Compliance card bring it together.

- [Checks](#checks)
- [Professional registrations](#professional-registrations)
- [Files](#files)
- [Policies](#policies)
- [Checklists](#checklists)
- [Reminders](#reminders)
- [Seeing where everyone stands](#seeing-where-everyone-stands)
- [Retention](#retention)

## Checks

The dated checks a role needs before and during employment: right to work,
DBS, references, occupational health and the like. Which checks a person
needs follows the **title of their current primary position**; what they
have is a list of recorded checks, one row per check done.

### The mental model

**A check type says who needs it and how long it lasts.** A check is one
recorded instance of a type for one person. **Checks are append-only:** a
renewal is a new row, never an edit to the old one, and the latest one by
date done is the one that counts. There is no change or delete button on a
recorded check; a mistake is put right by recording the check again.

**Changing someone's position changes what they need, on the next read.**
Nothing is written when a position changes. A check whose type is no longer
needed for their title stays in their history, shown as *Not required*, and
nobody is chased for it.

### Check types

`/admin/checks/checktype/`

Seven are set up when the app is installed, **with no titles assigned**:
until you add the titles that need each one, nobody is required to have
anything. Open each type and move the titles across in **Positions**.

| Type | Evidence | Valid for | Person reminded too |
|---|---|---|---|
| Right to work | A file | One-off | Yes |
| DBS | A reference number | 36 months | Yes |
| References | Nothing to attach | One-off | No |
| Occupational health | A file | One-off | No |
| Hep B immunity | A file | One-off | No |
| Indemnity | A file | 12 months | No |
| Professional registration | A reference number | 12 months | No |

**Name** is what everyone sees. **Code** is how the app finds a type (the
DBS rules below key on `dbs`, the evidence category on `right_to_work`): set
when a type is added, never changed after.

**Validity months** is how long a check lasts from the date it was done,
at least one. Blank means a one-off check that never expires. The expiry is the same day
that many calendar months later, or the month's last day when that month is
shorter (a check done on 31 January with one month's validity expires on
the last day of February).

**Evidence** is what a recorded check carries: *A file* (uploaded and kept
under Files; required on a clear check), *A reference number* (required on
a clear check; no file is taken), or *Nothing to attach*.

**Remind person** sends the reminders to the person as well as to HR.

**Positions** is the titles that need this check. A person needs it while
the title of their current primary position is in this list.

**Display order** sorts the types on every page. **Active** off stops a
type being required of anyone or offered on the forms; its recorded checks
stay. A type cannot be deleted once it exists: make it inactive instead.

### Recording a check

`/admin/checks/check/add/`

**Employee** and **Check type**, then:

- **Done on** — the date of the check. It cannot be after today.
- **Outcome** — *Clear*, *Clear with notes* or *Not clear*. Only a clear
  check (with or without notes) makes a type current; a *Not clear* one
  leaves it missing.
- **Expires on** — leave it blank to have it worked out from the type's
  validity. Set it only when the certificate itself says otherwise.
- **Reference** — the certificate or registration number. Required on a
  clear check of a type whose evidence is a reference number.
- **Note** — HR only. It is never shown to the person or to their manager.
- **Evidence file** — PDF, JPEG, PNG or DOCX, for a type whose evidence is
  a file. It is stored under Files against the person, not HR only: a
  right-to-work document as *Identity*, occupational health and Hep B
  immunity evidence as *Occupational health*, anything else as
  *Certificate*. It downloads from the check's page through the audited
  download. A type whose evidence is not a file refuses one. **A clear
  check of a type whose evidence is a file needs its file**: the form
  refuses one without (*Right to work needs its evidence file.*), unless
  the person has already sent it on a request (below). Once a check is
  recorded with its evidence, the evidence is part of the record and is
  not replaced: record a new check instead.
- **DBS disclosure level** — Basic, Standard, Enhanced, or Enhanced with
  barred lists. Required on a clear DBS check.
- **On the DBS update service** — tick when the person subscribes.

**DBS certificates are not stored.** Following the DBS code of practice, a
DBS check records the certificate number, the date of issue (*Done on*),
the disclosure level and whether the update service applies. The app
refuses a file on a DBS check; do not scan the certificate into Files
either.

Opening a recorded check's page writes a *Viewed* entry to the
[audit log](people.md#audit-log).

### What each status means

Each person's checks are shown as one row per type they need, plus one per
other type they have a check of. The status comes from the latest check of
that type:

| Status | Meaning |
|---|---|
| **Current** | A clear check that has not expired and is not due soon, or a one-off clear check. |
| **Due soon** | A clear check that expires within the next 60 days. |
| **Lapsed** | The latest clear check's expiry date has passed. |
| **Missing** | Needed, and there is no check, or the latest is *Not clear*. |
| **Awaiting** | The person has been asked for evidence and HR has not yet recorded the result. |
| **Not required** | The person has checks of this type, but their title no longer needs it. Kept, not chased. |

A recorded check outranks a request still waiting: asking someone to renew
a DBS that is current leaves it *Current* until the new one is recorded.

### Asking the person for evidence

For a check the person supplies (their passport for right to work, say):

1. **Ask.** On the Checks list choose **Ask for evidence**, pick the person
   and the type. On a recorded check's page, **Ask the person for evidence**
   asks the same person for the same type again (a renewal). One request per
   person and type can be waiting at a time.
2. **They upload.** The person sees the check as *Awaiting* on My record ›
   Checks (before their first day, on Getting started), with an upload
   form when the type's evidence is a file. A renewal
   request shows the same form under the type's current status (*Due soon*,
   say), which stays as it is until you record the new check. They can
   upload once; their file is stored under Files against them. For a type
   whose evidence is not a file they are told HR will record it with them.
3. **You record the result.** Open the waiting check and choose **Record
   the result**: the same fields as recording a check, with the uploaded
   file linked at the top. You can attach a file here too, if they handed
   it over on paper.

### Who sees what

| Who | Sees |
|---|---|
| The person | My record › Checks: each type, its status, the dates and the outcome. Never the note or the reference. |
| Their line manager | My team: per report, the counts (current, due soon, lapsed, missing, and awaiting when any) and the next expiry date. Never which checks. |
| HR admins | Everything, here. |

The manager's *awaiting* number counts only the types whose status is
*Awaiting*: a first request, with no recorded check of that type to
outrank it. A renewal request on a type that is *Due soon* or *Lapsed* is
not counted as awaiting; the type stays in the due soon or lapsed number
until the new check is recorded. (A renewal on a *Current* type stays in
the current number, likewise.)

## Professional registrations

Clinicians must hold a current registration with their professional body.
Practice HR keeps each person's registration number, looks it up on the
body's public register on a schedule without anyone logging in, and tells
HR and the line manager the next morning if something is wrong. HR can
also look one up that minute with **Check now**.

### The mental model

**A register body says which titles need a registration.** There are four,
set up when the app is installed, **with no titles assigned**: the General
Medical Council (`gmc`), the All Wales medical performers list
(`mpl_wales`), the Nursing and Midwifery Council (`nmc`) and the General
Pharmaceutical Council (`gphc`). Until you add the titles that need each
one, nobody needs a registration.

**One number per person per body.** The Welsh list is searched by the GMC
number, so a title that needs both is given one number, once, and both
bodies use it.

**A lookup reads the body's public search page.** None of the four offers
a free, sanctioned machine interface, so the page is read as a person would
read it. Each person is looked up every 7 days by default, spread across the
nights (see [The schedule](#the-schedule)), and HR can look one up at any
time ([Check now](#check-now-and-on-the-register)).

**A clear or problem lookup records a *Professional registration* check**,
dated today with the number as its reference and the register's words in the
note, so the [Compliance tab](#the-compliance-tab), the card, the starter
checklist hook and the [reminders](#reminders) all see it as they see any
other check. A *not found*, *wrong name* or *unreadable* lookup records no
check: it is an alert (see below). If the check cannot be recorded for any
reason the lookup is still kept, and the error's class (never a name or a
number) is logged.

**Every lookup is logged.** Open **Compliance › Registration lookups**
(`/admin/registers/lookup/`) to see each one: when, who, which body, the
outcome, the register's own words, the name it showed, whether it was
scheduled or on demand and, for one that could not be read, why. The log
is read-only, can be filtered by body, outcome and trigger, and searched by
person. It keeps the words and a fingerprint of the page, never the page
itself.

### Register bodies

`/admin/registers/registerbody/` (sidebar › Compliance › Register bodies)

Bodies are never added or deleted here: a new body is code (a page parser)
plus a seed. What you set:

- **Positions** — the titles that need a registration with this body. Move
  each across, as for a check type. A GP's title usually needs both the GMC
  and the Welsh list.
- **Active** — tick it off to stop looking up, and stop alerting about, that
  body. Its numbers are kept. Also the way to stop altogether if a regulator
  objects (see [Terms of use](#terms-of-use)).
- **Display order** — the order the bodies are shown in.
- **Verified** — shown, not editable. The code sets it each night from the
  pages saved in `registers/adapters/fixtures/`: a body is verified when its
  folder holds a `clear.html` and a `not_found.html`. **A body that is not
  verified is looked up only on demand**, with a warning that its parser has
  not been checked against a real page. Until someone captures the pages (see
  [the fixture guide](../../registers/adapters/fixtures/README.md)), all four
  show as not verified and nothing is looked up on a schedule.
- **Paused** — shown, not editable: *No*, or *Since* a date and time. See
  [When a page cannot be read](#when-a-page-cannot-be-read).

The list shows each body's name, code, **Active**, **Verified** and
**Paused**; **Active** can be changed from the list.

### What clear means

A lookup is *clear* when the register shows the person as currently
registered with nothing noted against them, and the surname on the register
matches theirs. The register's own words are kept as the result, so a change
of wording shows as itself.

| Body | Clear | A problem |
|---|---|---|
| **GMC** | The status is "Registered with a licence to practise", the GP Register shows the doctor, and none of fitness to practise, conditions, undertakings or warnings has a value. | Provisionally registered, registered without a licence, suspended, erased, an interim order, conditions, undertakings, administrative erasure or not registered; not on the GP Register; or a restriction noted. Every doctor the practice employs is treated as a GP, so "not on the GP Register" is always a problem. |
| **Welsh medical performers list** | The GMC number is on the list, with a status of included, active or current. | Suspended, conditional or removed. A number that is not on the list is *not found*. |
| **NMC** | The PIN shows "Effective registration" (or "Registered"), with no restriction, condition of practice or sanction noted. | Lapsed, suspended, struck off, conditions of practice, a caution or interim order, a restriction, not registered or unregistered; or a restriction, condition or sanction noted. |
| **GPhC** | The number shows "Registered", with no condition, fitness to practise entry or sanction noted. | Suspended, removed, lapsed, conditions, an interim order, not registered or unregistered; or a condition, fitness to practise entry or sanction noted. |

A status is read only from the register's labelled status field, and only
whole words count: a status containing "not" or "without" is never clear.
A status the parser does not recognise is *unreadable*, never clear, so a
new wording cannot slip through as good news. A page that is not a result
at all is *unreadable* too, never *not found*: *not found* needs the
register's own no-results wording, and is looked for only when the page has
no status field.

There are five results:

- **Clear** and **Problem**, as above. A problem is the register's words
  (for example "Suspended") and goes to HR and the line manager.
- **Not found** — the register has no one with that number. Also an alert.
- **Name does not match** — the register found the number but under a
  different surname. It is never treated as that person. The match ignores
  case, accents, apostrophes, hyphens, spaces and name particles ("van",
  "de"); either part of a double-barrelled surname is accepted, on either
  side. The person's preferred name is never used. The name the register
  showed is kept on the lookup and shown on the Compliance tab.
  A hit whose name cannot be found on the page is *unreadable* rather than
  accepted.
- **Could not read the page** — see below.

### Recording a number

On the person's **Details** tab, below **NI number**, there is a number box
for each body their current title needs, visible to
[HR admins](sign-in.md#admin-status) only: **GMC number** (it covers the
Welsh list as well), **NMC PIN number** or **GPhC number**. Whitespace is
dropped and letters are put in capitals. A number that is not in the body's
format is refused and nothing is saved:

| Box | Format | Example |
|---|---|---|
| **GMC number** | Seven digits | 1234567 |
| **NMC PIN number** | Two digits, a letter, four digits and a letter | 12A3456B |
| **GPhC number** | Seven digits | 2012345 |

Saving a new or changed number checks it that night (and **Check now**
checks it at once). Emptying a box removes the number and its lookups (for the GMC number, the
Welsh list's as well). A number already recorded for someone else is accepted, with a warning
naming them: the register decides who it is and the name check catches a
slip. Every change is written to the [audit log](people.md#audit-log) as
field `registration:<code>` (for example `registration:gmc`), with the old
and new number.

A title that needs a body but has no number recorded is listed to HR as
"<Body> number not recorded", from the day their employment starts.

### Check now and On the register

On the person's [Compliance tab](#the-compliance-tab) the **Registrations**
table is first. Each row shows the body, the number, the last result in the
register's words, the name the register showed, when it was checked and the
next check. Two links end each row:

- **Check now** opens a confirmation page ("Check *name*'s *body*
  registration now?"). Nothing happens until you choose **Check now** on
  it, which looks the number up this minute and takes you back to the
  person's page with the result as a message: the register's words and the
  name for a clear or problem result (green when clear, amber otherwise),
  "the number was not found on the register", "the register shows *name*,
  not this person", or "the page could not be read" with advice to try
  later. It works on a paused body, and on a body that is not verified
  (the message then adds "This register's parser is not yet verified: read
  the result with care."). It is HR only. A **Check now** that gets a
  readable answer from the register, whatever it says about the person,
  lifts a pause. Pressing it is written to the audit log as a view of the
  person's checks.
- **On the register** opens the body's public page for that number, so you
  can read it yourself.

A row for a body the title needs with no number reads "No number recorded"
with a link to the Details tab. A body that is paused or not verified says
so after the result.

### The schedule

On **Reminder settings**, **Check professional registrations every (days)**
is how long after one lookup the next one is due. It starts at 7 and must
be between 1 and 90. The next date is that many days on, give or take one
day, so a practice's lookups spread evenly across the nights rather than
all landing together. A new or changed number is due that night.

Each night `hr_nightly` looks up every registration that is due, whose
person is employed and whose title still needs the body, and whose body is
active, verified and not paused. The lookups are polite: one at a time, two
seconds between two to the same body, a ten-second wait for a reply, no
retry within a run, and a user agent that names the practice (built from
`SITE_URL`, for example `PracticeHR/1.0 (+https://hr.example.org;
registration checks)`).

### When a page cannot be read

A page that comes back but is not a result, an error page, a reply that
times out, or a site that has changed its layout, is recorded as **Could
not read the page**, with the error's class and no more. It is not an alert
for the person: a site change is not a clinical risk.

- A registration whose latest lookups have all been unreadable for **14
  days** is listed to HR only, "<Body>: could not be read since <date>".
- A body whose last **three** lookups, across everyone, could not be read
  is **paused**: the schedule skips it, and HR is told once in the digest, in
  a section headed "The registers" ("<Body>: checks are paused (the page
  could not be read)").
- A lookup that gets a readable answer, or **Unpause**, lets it run again.

To lift a pause, open the body under **Register bodies** and choose
**Unpause**. A page asks you to confirm, and only that confirmation changes
anything. **The three unreadable lookups still count afterwards:** if the
next one is unreadable too, the body pauses again at once. So after an
Unpause, run **Check now** on one registration straight away: a readable
answer proves the page can be read again.

What to do about one: open **On the register** yourself. If it works
for you but not for Practice HR, the site has probably changed; capture
fresh pages as [the fixture guide](../../registers/adapters/fixtures/README.md)
says, so the parser can be adjusted. If the site is simply down, **Check
now** again later.

### Terms of use

The registers publish these pages for the public to search. The practice
reads them at a gentle rate and says who it is in the user agent. It has
accepted the risk that a regulator's terms do not welcome automated reading.
If a regulator objects, untick **Active** on that body and record the check
by hand ([Recording a check](#recording-a-check)) as before. Do not try to
get round a regulator that blocks the practice.

## Files

`/admin/documents/file/`

The documents kept against a person: contracts, offer letters, identity
documents, certificates, occupational health letters, correspondence and
anything else, plus each policy version's text. Evidence uploaded for a
check, and anything a starter uploads from their checklist, lands here too.

### Adding a file

Choose **+** (Add file):

- **Employee** — whose file it is. Required here: only a policy version has
  no person, and it is added by issuing the version.
- **Category** — *Contract*, *Offer letter*, *Identity*, *Certificate*,
  *Occupational health*, *Correspondence* or *Other*. (*Policy* is for policy
  versions.) Adding a file of a category can close a starter checklist item
  linked to it (`upload:<category>`; see [What a link does](#what-a-link-does)).
- **Title** — what the file is, as the person and HR see it.
- **File** — a PDF, JPEG, PNG or DOCX, at most 10 MB. **The contents must
  match the extension:** a file whose bytes are something else (a web page
  renamed `.pdf`, say) is refused with *This file is not a PDF.*, and
  nothing is stored.
- **HR only** — tick to keep it off the person's own record.

### Who can open a file

| Who | Can open |
|---|---|
| The person | Their own files that are not HR only, under **Documents** on My record. |
| Anyone with a login linked to an employee record | A policy version's file, from **Policies**. |
| Their line manager | Nothing: managers never see documents. |
| HR admins | Every file, here. |

Every download goes through the same audited route, and each writes a
*Viewed* entry (field `file`) to the [audit log](people.md#audit-log). The
files are stored under `MEDIA_ROOT/documents/` with names that say nothing
about the person or the document; the web server never serves that folder,
and the nightly backup archives it with the database.

If the file's bytes are missing from the server (a database restored
without its files, say), the download answers *not found* and the server
log notes the stored path; nothing is written to the audit log.

The list's **By employee** filter shows one person's files (beside the
filters by category and HR only).

A file is never changed or deleted here. If the wrong one was added, or a
newer version replaces it, add the right one, then open the old one and
choose **Supersede**: pick the replacement (**Replaced by**, one of the
same person's current files) and say why (**Note**). Both stay on the
record; the person's own record shows only the replacement. A file that
has been superseded cannot be chosen as a replacement, so a file is never
replaced by an older one.

## Policies

The practice's policies that staff must read and sign: information
governance, chaperoning, safeguarding and the like. A policy has
**versions**; people sign a version, and issuing a new one asks them to
sign again.

### Who must sign

`/admin/documents/policy/`

**Title** is what everyone sees, and it goes into the sentence people sign.
**Positions** is the titles that must sign it: a person must while the
title of their primary position is in the list. **Leave Positions empty for
everyone.** A starter who has not started yet counts by the position they
will start in. **Active** off stops a policy being asked of anyone; its
versions and signatures stay. A policy cannot be deleted: make it inactive
instead.

### Issuing a version

Open the policy and choose **Issue new version**:

- **Label** — what this version is called, such as *v2* or *October
  edition*. Each label is used once per policy.
- **Issued on** — the date the version takes effect. It cannot be after
  today, or before the current version's.
- **Sign within (days)** — how long people have, from the issue date. A
  starter who joins after the issue date has that many days from their
  first day.
- **File** — the policy itself, a PDF, JPEG, PNG or DOCX. It is stored
  under Files with category *Policy* and no person, and anyone whose login
  is linked to an employee record can read it, through the audited
  download.

**The newest version, by issue date, is the one people sign.** Issuing one
asks everyone the policy applies to to sign it, including those who signed
an earlier version; nobody is asked to sign an older version again. A
version is never edited or deleted: put a mistake right by issuing another.

Each person sees their policies under **Policies** in the menu, with each
one's status:

| Status | Meaning |
|---|---|
| **Signed on** *date* | They have signed the current version. |
| **Awaiting signature** | Not signed yet, and the sign-by date has not passed. |
| **Overdue** | Not signed, and the sign-by date has passed. |

### What a signature records

`/admin/documents/signature/`

A signature records the person, the version, the date and time, how they
proved it was them (*Password* or *Passkey*), the network address they
signed from, and the exact sentence they ticked:

> I confirm I have read and understood *title* (*label*).

Signatures are read-only here. Nobody, HR included, can sign for someone
else, change a signature or delete one.

### Re-authentication

Signing is the person's own act, so the sign page asks them to prove it is
them every time, not just that their browser is signed in: **their password
typed again**, or **one of their own passkeys** on a device that has one
(the browser is offered only their passkeys, never another account's). A
practice PC left signed in is not enough to sign, and neither is someone
else's passkey. A wrong password signs nothing and counts towards the
[sign-in lockout](sign-in.md#signing-in-and-lockouts) exactly as one typed at the sign-in page
does. The password is checked and forgotten: it is never stored or written
to any log.

A signature made with the password is a genuine re-authentication, so, like
typing the password on the Account page, it also opens the ten-minute
window in which the person can [add a passkey](sign-in.md#passkeys) without
being asked for their password again. Signing with a passkey does not.

## Checklists

A **starter checklist** and a **leaver checklist** list what has to happen
when someone joins or leaves, and who does each part. Each one is copied
from a **template** when the employment starts or its leaving date is set;
after that it belongs to that person and changing the template does not
change it.

### When a checklist is made

- **Starter:** when an employment is added whose start date is in the
  future or in the last 30 days. An older spell (one being entered after
  the fact) gets none.
- **Leaver:** when an employment's leaving date is set. Changing the date
  keeps the same checklist and moves its open items' due dates with the
  new date. **Clearing the leaving date closes the leaver checklist:** its
  open items become *not needed*, noted *leaving date cleared*, so nobody
  is chased for a leaving that is not happening; items already done stay
  done. Setting a leaving date again later adds a fresh set of items from
  the template to the same checklist, every one open and due by the new
  date; the old items are kept below as they were (not needed, or done),
  and none of them is reopened.

Moving an employment's start date moves its starter checklist's open items
with it. Items already closed keep their dates.

### Templates

`/admin/onboarding/checklisttemplate/`

Two are set up when the app is installed: **Default starter** and **Default
leaver**, with no titles. A template applies to the people whose **primary
position's title** is in its **Positions**; the default of its kind
(Positions left empty) applies to every title without one of its own.
**Active** off stops a template being used; checklists already made from it
stay. A template cannot be deleted: switch **Active** off instead.

The title is the one on the start date (starter) or the leaving date
(leaver). The admin saves an employment before its positions, so a starter
checklist is made with the default first and **re-made from the title's
template when the primary position is added**, as long as nobody has
closed, added or removed an item on it yet (items closed automatically do
not count). Once work on it has begun it is kept, and the gap is noted
(below). The line manager of that position takes the open line manager
items either way.

Each item has:

- **Order** — the order within the template.
- **Title** and **Instruction** — what the owner sees.
- **Owner** — who does it:

  | Owner | Who that is on a checklist |
  |---|---|
  | **HR** | Any HR admin. |
  | **Line manager** | The line manager of the person's primary position when the checklist is made (or when the position is added). |
  | **The person** | The person themselves. |

- **Due rule** and **Due days** — the due date is that many days *before
  the start date*, *after the start date*, *before the leaving date* or
  *after the leaving date*.
- **Link** — what closes the item automatically (below), or blank for an
  item someone ticks off.

The default starter items:

| Item | Owner | Due | Link |
|---|---|---|---|
| Complete your details | The person | 7 days before the start | `details` |
| Read and sign the practice policies | The person | 14 days after the start | `sign_policies` |
| Upload your right-to-work document | The person | 7 days before the start | `upload:identity` |
| References received | HR | 7 days before the start | |
| DBS check recorded | HR | On the start date | `check:dbs` |
| Occupational health clearance | HR | On the start date | `check:occupational_health` |
| Contract issued | HR | 14 days before the start | `upload:contract` |
| Induction completed | Line manager | 5 days after the start | |
| Clinical and practice systems access set up | Line manager | 1 day before the start | |
| Buddy named | Line manager | 1 day after the start | |

The default leaver items:

| Item | Owner | Due |
|---|---|---|
| Handover completed | Line manager | 5 days before the leaving date |
| Equipment returned | Line manager | On the leaving date |
| Systems access removed | Line manager | On the leaving date |
| Smartcard returned | Line manager | On the leaving date |
| Final pay and leave balance to payroll | HR | 7 days after the leaving date |
| File closed and retention date noted | HR | 14 days after the leaving date |

### What a link does

| Link | Closes when |
|---|---|
| `details` | Not by itself: the person fills in their details form, and HR marks the item done once they have checked it. |
| `upload:<category>` | A file of that category is added for the person, by anyone (`upload:identity`, `upload:contract`; the categories are those under Files, except *Policy*). |
| `sign_policies` | The person signs a policy and has nothing left to sign. |
| `check:<code>` | A clear check of that type, not already expired, is recorded for the person (`check:dbs`, `check:right_to_work`; the codes are on the check types). |
| blank | Never: the owner or HR marks it done. |

A link the app does not recognise is refused when the template is saved.
An item closed automatically shows *done automatically* and no person
against it. A `sign_policies` item closed because no policy applies to
the person yet shows *no policies to sign yet* instead, so nobody reads
it as signed; once policies are issued, the policy reminders and the
person's Policies page take over (the item is not reopened).

On HR's checklist page a linked item says what closes it and links to
where HR does it: **Add the file** opens Files › Add with the person
and the category filled in, **Record the check** opens Checks › Add with
the person and the type filled in.

**A checklist starts with what is already in place done.** When it is
made (or re-made for the title), a linked item whose condition already
holds is closed automatically straight away: `check:<code>` when the
person has a clear check of that type that has not expired (a returner's
DBS, say), `upload:<category>` when a file of that category is already
stored for them, and `sign_policies` when they have nothing to sign. A
starter with no position yet owes only the policies that apply to
everyone, so when their position is added the signing item is opened
again if their title brings policies to sign.

### Who closes what

The owner marks their own items done; **HR can mark any item done**. Only
HR can mark an item **not needed**, and must say why. HR can also add an
item to one person's checklist, or remove one. A checklist is complete once
every item is done or not needed. Every change is in the
[audit log](people.md#audit-log).

### Checklists and their gaps

`/admin/onboarding/checklist/`

Each person's checklists, read-only here, with how many items are done and
how many overdue. A checklist is never refused for a missing piece of
set-up, so it can be made with **gaps**, listed on it:

- *no position on the anchor date* — no primary position on the start (or
  leaving) date, so no title to choose a template by; it is re-checked when
  the position is added.
- *no starter (or leaver) checklist template* — no active template applies,
  so the checklist has no items. Add or switch on a default. A checklist
  with no items is never complete by itself: it stays on Starters and
  leavers until you add items to it and close them.
- *no line manager on the primary position* — the line manager items have
  no owner, and nobody but HR can close them: HR does them. The manager is
  taken only from the primary position covering the start (or leaving)
  date, when the checklist is made or that position is added; a manager
  given to someone later does not take the items over.
- *no check types for the title …* (starter checklists) — no active check
  type lists the person's title under **Positions**, so nothing will be
  asked of them or chased. Add the title to the check types it needs, if
  any.
- *the template for … was not applied* — the title's template arrived after
  work on the checklist had begun; add any missing items by hand.
- *checklist could not be built: …* — something went wrong making or
  updating the checklist (the name is the kind of error; the server log
  has the same line). The employment or position was saved all the same;
  add the items by hand, and tell whoever looks after the server.
- *the leaving date was cleared* — the leaver checklist was closed when its
  leaving date was cleared ([above](#when-a-checklist-is-made)); setting a
  date again makes it afresh.

### Pages

- **Getting started** (`/onboarding/`) — the person's own items, in the
  order they are due, each with what it needs: *Your details* opens their
  details form (contact details, address, NI number, bank details and up to
  three emergency contacts); an upload item takes the file there and then;
  the policies item opens their Policies page; a check item says HR will
  record it; an item with no link has **Done**. Saving the details form
  does not tick that item off: it shows *Sent – HR will check it*, and its
  reminders go to HR from then on (the checklist page shows when it was
  sent). Check the details on their record in the admin, then mark it done
  on the checklist page below. The form is there
  only while that item is open: once you have marked it done (or not
  needed) the person can no longer change their bank or NI details
  themselves, so any later change comes to you. After the start
  date the same items are on My record as **Your checklist** until the
  checklist is complete.
- **Before the start date** a starter who signs in sees Getting started and
  nothing else: no navigation, and every other page sends them back to it.
  They can still reach their details form, their policies (to read and
  sign), the evidence you have asked them for (a **Checks** card on
  Getting started, with its upload form) and their account (password and
  passkeys). It opens up on their
  first day. Anyone with a current employment, and any HR admin (whatever
  their own record says), is never held back.
- **To do** on My team — a line manager's open items across their starters
  and leavers, with **Done**. It is there from the moment the checklist is
  made, before the starter is one of their team.
- **Starters and leavers** (sidebar › Compliance, `/onboarding/all/`) — every
  checklist not yet complete, and every one that finished by itself (each
  item closed automatically) with a gap still listed, soonest date first, with how many items are
  done, how many are overdue and its gaps. Open one to mark any item
  **Done** (with an optional note) or **Not needed** (a reason is
  required), to **Remove** an item, or to **Add** one for this person only.

## Reminders

Every morning `hr_nightly` (see [Nightly housekeeping](sign-in.md#nightly-housekeeping))
works out what is due across checks, policies and checklists and sends
**one email per person who has something to hear about**, listing it under
the name of the person it concerns, each line with what it is, when it is
due and a link. Nobody with nothing due gets an email.

### Reminder settings

`/admin/compliance/reminderschedule/` (sidebar › Compliance › Reminder settings)

One set of four numbers for the whole practice, edited in place:

- **Start days before** (X, default 60) — the first reminder goes this many
  days before the due date. In the reminders it is also the window in which
  a check counts as *Due soon*. The pages (My record, My team, the
  Compliance tab) always use 60 days, whatever this is set to.
- **Every days before** (Y, default 30) — then again every this many days
  until the due date.
- **Every days overdue** (Z, default 7) — after the due date, again every
  this many days while it is still outstanding.
- **Check professional registrations every (days)** (default 7, from 1 to 90)
  — how often each person's registration is looked up on its register. See
  [The schedule](#the-schedule). It does not change when reminders go.

A reminder always goes **on the due date itself**, whatever Y is. With the
defaults, a DBS whose expiry date is 1 December (valid through that day)
is mentioned on 2 October, 1 November and 1 December (*due today*), then
on 2 December, the first day it is *Lapsed*, as *expired on 1 Dec*
(lapsing starts it afresh), and every 7 days after that until a new check
is recorded.

### Who is reminded of what

| What | When | Who |
|---|---|---|
| A check the person's title needs | *Due soon* (inside the window before it expires), *Lapsed*, or *Missing* (owed since their employment started). Only for someone employed today. | Every HR admin; the person too when the type has **Remind person** and they have a login that is switched on. |
| A check that has lapsed | Once, the first time it lapses. | The person's line manager, told only that *a check has lapsed*, never which one (a manager sees counts of a report's checks, not the checks). |
| A policy to sign | Inside the window before its sign-by date, then overdue. | The person, if their login is switched on; every HR admin as well once it is overdue, whether the person has a login or not. |
| A checklist item | Inside the window before its due date, then overdue, until it is done or not needed. Items of a leaver checklist stop 90 days after the leaving date. | Its owner: the person, the line manager it was given to, or every HR admin. An item whose owner has no login that is switched on, or a line manager item with no manager, goes to HR instead. |
| A registration problem: the latest lookup shows a problem, *not found* or the wrong name | The first morning after it is found, with the body and the register's words ("found 3 Oct 2026"), then again every *Every days overdue* days while the latest lookup still shows it. A fresh lookup that is clear ends it; a changed number drops it until the new number has been looked up. | Every HR admin and the person's line manager, who is told the body and the words, unlike a lapsed check, because it needs acting on that day. Only for someone employed today. |
| A registration number not recorded | For a body the person's title needs and no number is recorded: from the day their employment starts, on the same cadence as an overdue item ("not recorded"). | Every HR admin. |
| A registration page that cannot be read | A registration unreadable for 14 days, or a body that has paused. A paused body is listed under the heading "The registers", not under a person. | Every HR admin only. |

A check the person has been asked for evidence of (*Awaiting*) is still
owed: until they upload something, it is reminded of as *Missing*, owed
since their employment started, like a check nobody has asked for. Once
they have uploaded their evidence it waits on you to record the result,
and is not reminded of. The pages keep showing it as *Awaiting*. Each HR admin gets the HR lines
in one email of their own; an HR admin who is also the person, or the
manager, gets a line once.

### The sent log

Each line sent is logged against its recipient (`compliance.ReminderSent`:
address, item, date), and the log decides what goes next: a line goes
again only when the numbers above say so, counted from the last time that
recipient had it. A change to the thing itself starts it afresh: a renewed
check (new expiry), a check that moves from *Due soon* to *Lapsed*, a
policy's new version, a checklist item whose due date moved.

**Once a day.** The digest assumes it runs once a day, from `hr_nightly`:
run again the same day, it sends only what the first run did not.

**No email without a relay.** With no outgoing email configured, nothing
is sent and nothing is logged, so the first morning with a relay sends what
is due then. A send the relay refuses is listed on the admin dashboard
with the other emails that did not go (by subject only, never the
recipient), and is not logged as sent, so the next morning tries again.

### In the nightly output

`hr_nightly` prints the reminders on its **compliance:** line:
`reminders_sent` (emails that went, one per recipient), `reminders_failed`
(emails the relay refused) and `items` (lines in the emails that went). All
three are 0 with no outgoing email configured. If the step fails it prints
`compliance: failed` and the run exits with an error. See
[Nightly housekeeping](sign-in.md#nightly-housekeeping).

The registrations come after it, on a **registrations:** line printed as the
step finishes, such as `registrations: {'run': 4, 'clear': 3, 'problem': 1,
'not_found': 0, 'name_mismatch': 0, 'unreadable': 0, 'skipped': 0,
'verified': 4}`. `run` is the lookups made tonight and the next five
counts say how they came out; `skipped` is registrations that were due but
not looked up (the person is no longer employed, the title no longer needs
the body, or the body is inactive, not verified or paused); `verified` is how many of
the four bodies are verified. All are 0 until a body is verified. A failure
of this step prints `registrations: failed`, logs the error's class and
does **not** fail the run: the reminders have already gone and the next
night tries again.

## Seeing where everyone stands

### The Compliance card

The admin home page shows five numbers:

| Number | Counts |
|---|---|
| **Lapsed checks** | Checks with the status *Lapsed*, across everyone employed today. |
| **Missing checks** | Checks with the status *Missing*, across everyone employed today, and checks asked for (*Awaiting*) that the person has not answered yet. |
| **Overdue signatures** | Policies someone employed today has not signed by the sign-by date. |
| **Overdue checklist items** | Open items, on any starter or leaver checklist, past their due date, leaving out those of an employment that ended more than 90 days ago (as the reminders do). |
| **Registration problems** | Registrations of people employed today whose latest lookup is a problem, *not found* or a wrong name. One per registration: someone with two such registrations adds two. |

Each counts things, not people: someone with two lapsed checks adds two.
Choose a number to open **Employees** filtered to the people it counts (the
list's **Compliance** filter); **Registration problems** opens the people
whose registration has a standing problem, not the lookups list. A starter who has not started yet is not in
the check or signature numbers; their overdue checklist items are.

### The Compliance tab

Each person's page under **People › Employees** has a **Compliance** tab
beside **Details**: their professional registrations first (see
[Check now and On the register](#check-now-and-on-the-register)), then their
checks with each status, their policies with each
signature or sign-by date, and the open items of their checklists, each
with a link to the page that deals with it. Someone not started yet is
shown as they will stand on their first day. It is read-only. Opening it
writes one thing: when it lists any check, a *Viewed* entry (*checks*) in
the [audit log](people.md#audit-log), as opening a check does. The Checks
list itself is not audited, like any other list. See [The Compliance tab](people.md#the-compliance-tab) for
each column and link.

## Retention

Recorded checks, stored files and policy signatures each have their own
line on the [retention report](people.md#retention-report): *Pre-employment
and other checks*, *Stored files* and *Policy signatures*, six years after
the person's last employment ended by default (`RETENTION_DAYS_CHECKS`,
`RETENTION_DAYS_FILES`, `RETENTION_DAYS_SIGNATURES`). As for every category,
the report only lists: nothing is deleted automatically, and there is no
delete button for a check, a file or a signature.
