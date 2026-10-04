# Compliance

**Where:** sidebar › Compliance › Check types / Checks / Files / Policies / Signatures /
Checklist templates / Checklists / Starters and leavers.

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
under Files), *A reference number* (required on a clear check; no file is
taken), or *Nothing to attach*.

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
  download. A type whose evidence is not a file refuses one.
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
   Checks, with an upload form when the type's evidence is a file. A renewal
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
  done. Setting a leaving date again later makes the leaver checklist
  afresh from the template, every item open, due by the new date.

Moving an employment's start date moves its starter checklist's open items
with it. Items already closed keep their dates.

### Templates

`/admin/onboarding/checklisttemplate/`

Two are set up when the app is installed: **Default starter** and **Default
leaver**, with no titles. A template applies to the people whose **primary
position's title** is in its **Positions**; the default of its kind
(Positions left empty) applies to every title without one of its own.
**Active** off stops a template being used; checklists already made from it
stay.

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
| `check:<code>` | A clear check of that type is recorded for the person (`check:dbs`, `check:right_to_work`; the codes are on the check types). |
| blank | Never: the owner or HR marks it done. |

A link the app does not recognise is refused when the template is saved.
An item closed automatically shows *done automatically* and no person
against it.

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
  so the checklist has no items. Add or switch on a default.
- *no line manager on the primary position* — the line manager items have
  no owner, and nobody but HR can close them: HR does them. The manager is
  taken only from the primary position covering the start (or leaving)
  date, when the checklist is made or that position is added; a manager
  given to someone later does not take the items over.
- *the template for … was not applied* — the title's template arrived after
  work on the checklist had begun; add any missing items by hand.
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
  does not tick that item off: check the details on their record in the
  admin, then mark it done on the checklist page below. After the start
  date the same items are on My record as **Your checklist** until the
  checklist is complete.
- **Before the start date** a starter who signs in sees Getting started and
  nothing else: no navigation, and every other page sends them back to it.
  They can still reach their details form, their policies (to read and
  sign) and their account (password and passkeys). It opens up on their
  first day. Anyone with a current employment, and an HR admin with no
  employee record, is never held back.
- **To do** on My team — a line manager's open items across their starters
  and leavers, with **Done**. It is there from the moment the checklist is
  made, before the starter is one of their team.
- **Starters and leavers** (sidebar › Compliance, `/onboarding/all/`) — every
  checklist not yet complete, soonest date first, with how many items are
  done, how many are overdue and its gaps. Open one to mark any item
  **Done** (with an optional note) or **Not needed** (a reason is
  required), to **Remove** an item, or to **Add** one for this person only.
