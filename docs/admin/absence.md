# Absence and leave

Everything about time off: what employees see and do at `/absence/`, and the
settings an HR admin maintains under **Absence** in the admin menu (absence
types, policies, bank holidays, closed days, and the read-only pots and
absences). The year-end job that closes each leave year has [its own
page](year-end.md); the monthly file for the payroll bureau is on the
[Payroll page](payroll.md).

## The mental model

**A pot is one person's allowance of one type for one leave year.** It has no
balance field. Its balance is the sum of its *ledger lines* (entitlement,
carried in, booked, cancelled, expired, adjusted…), which are only ever
added, never edited or deleted. Every figure anyone sees can be traced to
lines.

**Policies are data.** How much leave a contract type earns, when the leave
year starts, what carries over and how bank holidays are charged are rows
under **Absence › Policies**, not code. Nothing in the code tests a type's
name, apart from four codes the services look up (`AL`, `BH`, `SICK`,
`TOIL`) and the family-leave codes.

**The nightly job does the housekeeping.** Pots are opened, entitlements
recalculated, bank holidays charged, the year closed and waiting requests
chased by `hr_nightly` (01:30) — see [Nightly housekeeping](sign-in.md#nightly-housekeeping)
and [the year-end page](year-end.md). Each night it opens, for everyone
employed, **this leave year's and next year's pot** of every allowance-backed
type they have a policy for (annual leave always; the bank-holiday pot where
annual leave's policy says "pot"; TOIL, study leave or your own types once
their contract type has a policy), so the request and decide pages can show
next year's balance. Until it has run, such a pot shows "Not opened yet: it
opens overnight." A year beyond next opens when leave in it is approved.

## Absence types

`/admin/absence/absencetype/`. Thirteen are seeded: Annual leave (`AL`), Bank
holiday (`BH`), Study leave, TOIL, Sickness, Maternity, Paternity, Shared
parental and Adoption leave, Compassionate, Dependants, Unpaid and Other.
Add your own; the flags decide what it does.

### Name / Code

The name is what people pick. The **code** is set when the type is added and
can never be changed after (the field is read-only on an existing type): the
services look up `AL`, `BH`, `SICK` and `TOIL` by code, and the four
family-leave types (`MAT`, `PAT`, `SPL`, `ADOPT`) are identified by theirs.
Do not reuse or retire those codes.

### Paid

Whether the time off is paid. Read by the [payroll report](payroll.md): a
payroll-reportable type that is not paid, and is not sickness or family
leave, goes on the Unpaid sheet.

### Uses pot

**The type draws on an allowance.** Ticked, every contract type needs a
[policy](#policies) for it, the request page shows the balance before and
after, and approving writes a booking line to the pot. Unticked, a request
is costed and recorded but nothing is deducted. *If you tick it on a type
with no policy,* requests fail with a message naming the missing policy
(and the nightly reports it) rather than silently costing nothing. Study
leave and TOIL are seeded pot-backed **without** a policy: add one before
anyone books them. Once a contract type has one, the nightly opens a pot of
that type for everyone on it; without one, nobody on that contract type has
that allowance and nothing is reported.

### Needs approval

Ticked: a request waits for the person's approver. Unticked: it is written
**approved** the moment it is submitted (Sickness and Dependants leave are
seeded this way). Bank holiday is also unticked: it is only ever created
automatically.

### Self certified

A label on the type ("the employee records it themselves"). The workflow
does not read it. What makes Sickness need no approval is *Needs approval*
being unticked. Separately, every sickness absence of seven calendar days
or fewer (first to last day inclusive) is stamped self-certified when
recorded, and the payroll Sickness sheet says so.

### Calendar label

What colleagues see for this type on the [calendar](#the-calendar): Leave,
Sick, Away. Keep it generic; it is shown to everyone.

### Payroll reportable

Only types with this ticked reach the [payroll report](payroll.md), and
which sheet follows the other flags. A type you add yourself does nothing
for payroll until you tick it.

### Health sensitive

Sickness-like types. The kind of sickness (asked in broad terms on the
request) and the dates are restricted to HR admins and the line manager;
opening such an absence in the admin is written to the
[audit log](people.md#audit-log). The calendar shows the type's calendar
label to colleagues, the [read API](api.md) always says "Sick", and
payroll reports dates only, never the kind.

### Display order / Active

Order in the list, and whether people can pick it. Deactivating hides a type
from new requests without touching history.

## Policies

`/admin/absence/policy/` — one per contract type and pot-backed absence type,
valid between **Effective from** and **Effective to** (blank: open-ended).
A day's policy is the newest one in force that day for the contract type the
person has that day. If none covers a day the person needs, the error says
"No Annual leave policy for … Add one under Absence › Policies", and the
nightly lists it. A gap between one policy ending and the next starting is
that same error.

Saving a policy immediately recalculates the entitlement of every open pot it
can change, as you, and reports "N pot(s) revised". Changes therefore reach
existing people at once.

Eight annual-leave policies are seeded (one per seeded contract type, from
1 Jan 2020): 5.6 weeks, leave year from 1 April, rounding 0.25 (hours) or 0.5
(sessions), bank holidays as a pot for hours contracts and closed for
sessions contracts, **no carry-over** (see below), and a bank-holiday
policy for each hours type.

### Weeks per year (`weeks_per_year`)

The entitlement in weeks, multiplied by the contracted weekly amount (37.5
hours, 9 sessions…). It is earned day by day across the leave year for the
days the person is employed with a contract, so starters and leavers are
pro-rated and a contract change mid-year changes the rate from that day.
*Too low or too high* simply gives everyone the wrong allowance, and it
revises every open pot at once. The bank-holiday pot ignores this figure
(its policy is seeded at 0): its weeks come from the calendar.

### Leave year basis (`leave_year_basis`)

**Fixed date:** the year starts on **Year start month / day** (default 1
April). **Anniversary of start:** the year starts on the anniversary of the
*employment's start date* (not the continuous service date). Decide it once: pots already open keep the dates they were opened with, so
changing the basis on a policy in use can leave them out of step with the
new boundaries. A leave request that runs across the end of the leave year is refused ("book
the two leave years separately").

### Carry over max weeks (`carry_over_max_weeks`)

The most that carries into the next year, in weeks times the contracted
amount on the new year's first day, rounded. **Blank means nothing carries**:
all unused leave expires at year end. Negative balances always carry in
full. See [Year end](year-end.md).

### Carry over expires after days (`carry_over_expires_after_days`)

How long carried-in leave may be *booked* for, counted from the start of
the new year. Leave carried in and still unbooked after that many days
expires. Blank means it never expires. Setting a cap but no expiry lets
carried leave sit forever.

### Rounding (`rounding`)

The step that entitlements and costs are rounded to, half up: 0.25 for
hours, 0.5 for sessions. A step that does not suit the unit (0.5 hours,
say) makes every cost and entitlement a multiple of it.

### Bank holiday handling (`bank_holiday_handling`)

How England and Wales bank holidays are charged, applied on the annual
leave policy:

- **Practice closed, not charged:** nobody is charged; the day is simply
  not leave. The right choice where the practice closes and allowances are
  in sessions.
- **Pro-rated bank holiday pot:** each person has a separate Bank holiday
  pot, sized as the year's bank holidays divided by five, as weeks, times
  their weekly amount. Each bank holiday that falls on a day they work is
  charged to it automatically at that day's pattern.
- **Included in annual leave:** each is charged to the Annual leave pot
  instead.

The charge is an automatic, approved absence row per bank holiday, created
when the pot opens and kept in step nightly (removed if the pattern or policy
no longer implies it; re-costed from today if the pattern changes). *The
pot option needs a Bank holiday policy for the same contract type* to give
the pot its leave year and rounding; without one the nightly reports the gap
instead of charging nothing.

### TOIL expires after days (`toil_expires_after_days`)

On a TOIL policy: how long earned TOIL may be used, counted from the day it
was earned. Blank means never. See [Year end](year-end.md#toil).

### Tiers

The inline on a policy adds weeks for service: **After years** and **Extra
weeks**. The extra is the *total* extra at that point, not added on top of
earlier tiers (a 5-year tier of 1 and a 10-year tier of 2 give one extra
week at 6 years, two at 11). Service is counted from the employment's
continuous service date, and the entitlement steps up from the day a tier
is reached.

## Bank holidays and closed days

`/admin/absence/bankholiday/` holds the England and Wales calendar, seeded
for 2026 to 2028. Add each later year's dates before that year starts: a
year with none charges nothing and gives the bank-holiday pot no
entitlement. Only `EW` entries count. `/admin/absence/closedday/`
holds practice closures that are not bank holidays. **Closed days are never
charged.** Bank holidays are charged only by the automation above: an
ordinary booking skips them, so a Monday-to-Friday week off across a bank
holiday costs four days and the automatic row costs the fifth. Both are
skipped when counting working days for [chasing](#waiting-requests).

## How a request is costed

Cost is the working pattern in force on each day, in the person's unit,
day by day: every whole day counts its AM and PM units from the
[working pattern](people.md#working-pattern); weekends and non-working days
cost nothing; bank holidays and closed days are skipped. The total is
rounded to the policy's rounding step (0.25 if the type has no policy). A
first day marked *afternoon only* loses the morning; a last day marked
*morning only* loses the afternoon. For people in hours, a *part of a day*
gives start and end times and the hours: it costs the hours given, at most
the pattern's hours for the halves the times touch. Part days are one day
and only for hours contracts.

## Requesting leave

Employees use **Leave** in the menu, then *Request leave*.

1. **Check.** Fill in the type, the first and last day (blank last day is a
   single day), any half days or part day, and, by type: the kind of
   sickness (required for Sickness, in broad terms) and, for family leave,
   the expected start and expected return. Press *Check cost and balance*.
   Nothing is saved.
2. **Confirm.** The page shows the cost, **Remaining now** and **Balance
   after** (and any other requests still waiting on the same pot), and a
   warning if the balance would go below zero. A request beyond the balance
   is allowed: the approver sees the same warning. Press *Confirm request*
   to save it.

A pot that is not open yet reads "Not opened yet" instead of a balance
(this year's and next year's open overnight; a later year's when leave in
it is approved). The request is refused when it overlaps another live absence,
falls outside the employment, or (pot-backed) crosses the end of the leave
year. Types that need no approval are recorded as approved straight away;
otherwise the approver is emailed and the request shows as Requested.

## Deciding a request

Approvers (people with direct reports) see **Approvals (N)** in the menu, with
the count of requests waiting on them; an HR admin sees everyone's. A request from someone with no line manager
(or whose manager has left) goes to the HR admins instead. The
emailed link opens the decide page directly. It shows the request, the
requester's **Remaining now** and **Balance after** (with a warning if it
goes negative), who else in the team is off each day and how many are
present, and a warning when approving would leave the team under its
[minimum present](people.md#min-present). Approve or decline, with an
optional comment; the requester is emailed. Nobody decides their own
request: an HR admin's goes to another HR admin. Approving costs the request
afresh and writes the booking line in one transaction; declining writes
nothing to the pot.

A request already decided or cancelled (say, from an old email) opens
**read-only**, showing what happened, by whom and when, and the comment.

## Cancelling

An employee can cancel their own request at any time, and their own approved
absence **until it starts**; after that only an HR admin can, at any time.
Cancelling an approved pot-backed absence puts its cost back with a
cancellation line. **Automatic bank-holiday rows can never be cancelled** (the
nightly would only recreate them; change the policy or the pattern
instead). The approver is emailed.

## Family leave and keeping-in-touch days

Requests for the four family-leave types take an **expected start** and
**expected return**. The **actual start**, and any later correction, is
edited by HR admins in the admin (**Absences › open a family-leave
absence**): family-leave dates are the *only* thing editable on an absence
there, and the return must fall after a start. The person adds
**keeping-in-touch (KIT) days** themselves from *Leave*, one date at a time,
within the leave. KIT days are reported on the
[payroll family-leave sheet](payroll.md#the-sheets).

## The calendar

**Calendar** shows a month, for the whole practice or one team. Only
**approved** absences appear, and automatic bank-holiday rows do not (they
are not "someone off"). Colleagues see each person's name and the type's
**calendar label** and nothing else; HR admins also see the type's name
("Leave · Study leave"). Never a sickness category.

Presence counts (used for the team's minimum and the decide page): someone
off for **some hours** of a day (a part day) is still present; someone off
for an **AM or PM half day** counts as away.

## Balances

**Balances** shows the current leave year and the next, for each type the
person has an allowance in (the Bank holiday pot too). Columns: Entitlement,
Carried in, Taken (absences that have ended), Booked (yet to come), Waiting
(requests undecided), Expired, Adjustments (adjustments and TOIL earned) and
**Remaining**. **Each figure links to the ledger** for that pot filtered to the lines
behind it (`?kind=` on the ledger page: `entitlement,revision`, `carry_in`,
`booking,toil_taken,cancellation` with `&period=taken` or `booked`,
`expiry`, `adjustment,toil_earned`; Waiting lists the pending requests
because a request reaches the ledger only when approved). The running
balance column always shows the true balance, whatever the filter. A year
"not opened yet" has no pot; the nightly opens it. The next year reads "Not
employed then." for someone leaving before it starts. The Bank holiday row
shows only where the annual-leave policy's handling is "pot". HR admins also see set-up
gaps, such as a type with no policy.

**Team** (from Balances; approvers and HR admins) lists the people whose
balances you may open: direct reports for an approver, everyone for an HR
admin.

## Waiting requests

A request undecided after **`CHASE_AFTER_WORKING_DAYS`** working days (default
**3**) is "waiting": it appears on the admin dashboard, and the nightly
emails every HR admin once about it. Working days exclude weekends,
England and Wales bank holidays and closed days. If the email does not go,
the nightly tries again. The dashboard also shows whether email is set up,
and lists the last emails that failed to send. A failed email never blocks a
request; the person is told to send the link themselves.

## Email and `SITE_URL`

Links in emails (the decide page) are the site's address plus a path. Set
`SITE_URL=https://hr.example.org` in `/etc/practice-hr.env`; unset, links
are relative and cannot be opened. `check --deploy` warns (`hr.W002`).

## Pots and the ledger in the admin

**Pots** and their ledger lines are read-only in the admin: no one adds,
edits or deletes a line there. The one action is **Recalculate
entitlement** on selected pots, which writes a revision line if the
entitlement is out of step (for example after a working-pattern change).
There is **no adjustment screen**. To correct a balance or reverse a line
write an adjustment (or the opposite line) from the shell; see
[Reversing a line](year-end.md#reversing-a-line). TOIL is earned the same
way (`absence.services.toil.earn`); there is no screen for it yet.

The **Absences** list is a read-only record of every absence, apart from a
family-leave absence's dates (see [above](#family-leave-and-keeping-in-touch-days)).
