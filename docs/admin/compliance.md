# Compliance

**Where:** sidebar › Compliance › Check types / Checks / Files.

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

**Validity months** is how long a check lasts from the date it was done.
Blank means a one-off check that never expires. The expiry is the same day
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
  a file. It is stored under Files (a right-to-work document as
  *Identity*, anything else as *Certificate*) and downloads from the check's
  page through the audited download. A type whose evidence is not a file
  refuses one.
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
   Checks, with an upload form when the type's evidence is a file. Their
   file is stored under Files against them. For a type whose evidence is not
   a file they are told HR will record it with them.
3. **You record the result.** Open the waiting check and choose **Record
   the result**: the same fields as recording a check, with the uploaded
   file linked at the top. You can attach a file here too, if they handed
   it over on paper.

### Who sees what

| Who | Sees |
|---|---|
| The person | My record › Checks: each type, its status, the dates and the outcome. Never the note or the reference. |
| Their line manager | My team: per report, the counts (current, due soon, lapsed, missing) and the next expiry date. Never which checks. |
| HR admins | Everything, here. |
