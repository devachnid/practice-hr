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

Eight annual-leave policies are seeded, one per seeded contract type, from
1 Jan 2020, with **no carry-over** (see below):

- **Hours types** (Practice nurse, HCA, Reception, Administration,
  Management) have the practice's standard contract: a leave year from
  1 January, 22 days full time, 23 after one complete year, 25 after three
  and 27 after five, earned in [monthly twelfths](#accrual-accrual), rounded
  to 0.25 hour, plus the bank holidays as a [pot](#bank-holiday-handling-bank_holiday_handling)
  (each also has a bank-holiday policy in the same year). Part-timers get
  the same pro rata to their contracted hours.
- **Sessions types** (Partner, Salaried GP, GP trainee): 5.6 weeks, a leave
  year from 1 April, earned daily, rounded to 0.5 session, bank holidays
  "closed".

The hours types were first seeded like the sessions ones; the move to the
standard contract changed only the policies still exactly as seeded, and
only for contract types whose staff had no annual-leave or bank-holiday
pot yet. A policy you had already edited, or a type already in use, was
left as it was: to move a type in use, see
[Moving a type in use to a January year](#moving-a-type-in-use-to-a-january-year).

### Entitlement: full-time days or weeks (`days_per_year`, `weeks_per_year`)

The policy stores the entitlement in **weeks**, multiplied by each
person's contracted weekly amount (37.5 hours, 9 sessions…).

- **Hours contract types:** the page asks for **Full-time days per year**
  (`days_per_year`) instead, the days someone full time gets before bank
  holidays (22, say). It is stored as weeks at five days to a full-time
  week, days ÷ 5, and shown beside the field ("= 4.4 weeks"); reopening the
  policy shows the days again. So 22 days is 4.4 weeks, which is 165 hours a
  year at 37.5 hours a week and 82.5 at 18.75. Days must be above zero and
  a multiple of 0.05 (weeks are kept to two places).
- **Sessions contract types** (GPs) keep **Weeks per year** as it is.
- **Adding a policy:** the add page offers both until it is saved. Give days
  for an hours contract type and weeks for a sessions one; the wrong one is
  refused with a message saying which to use.

*Too low or too high* simply gives everyone the wrong allowance, and it
revises every open pot at once. The bank-holiday pot's policy has no
entitlement field at all: its pot comes from the calendar (see
[Bank holiday handling](#bank-holiday-handling-bank_holiday_handling)).

### Accrual (`accrual`)

How the year's entitlement is earned when someone is not there all year,
or their hours or tier change part way through:

- **Daily** (the default, and the sessions seeds): earned day by day across
  the leave year for the days the person is employed with a contract, so a
  contract change changes the rate from that day.
- **Monthly twelfths** (the hours seeds): a twelfth of the year's
  entitlement for each month of the leave year (see below) in which the person
  is employed with a contract on any day. **A part month counts as a full
  month, for starters and leavers alike.** Someone starting on 15 March
  gets March to December, 10/12; someone leaving on 3 September gets
  January to September, 9/12. A month is worked out on its **last day
  employed with a contract**: the hours, the policy and the tier in force
  that day count for the whole month, so hours cut from 20 June count at
  the new hours for all of June, and a tier reached on 10 May counts from
  May.

The twelve months are counted from the start of the leave year, on the same
day of the month (the month's last day where it is shorter): a 1 January
year has the calendar months, and a year from 15 March (fixed, or the
anniversary of a 15 March start) has 15 March to 14 April, and so on to
15 February to 14 March. Someone starting on 20 April in that year gets
11/12. Every leave year has exactly twelve. The bank-holiday pot does not
use the accrual basis.

### Leave year basis (`leave_year_basis`)

**Fixed date:** the year starts on **Year start month / day** (default 1
April). **Anniversary of start:** the year starts on the anniversary of the
*employment's start date* (not the continuous service date). Decide it
once: pots keep the dates they were opened with, and a day counts only
towards the pot of the leave year its policy puts it in. So once anyone on
the contract type has a pot of that absence type, the basis and the year
start of its policy **cannot be changed**: saving is refused with "This
type has leave pots on the current year. End this policy and add a new one
from the new year's first day instead (see the admin guide)", and nothing
is saved. Follow the next section instead. A policy whose type has no pots
yet can be changed freely. A leave request that runs across the end of the leave
year is refused ("book the two leave years separately").

#### Moving a type in use to a January year

To move a contract type whose staff already have April pots, do not edit
its year start: end its April policy on 31 December and add a January
policy (year from 1 January) effective from 1 January, then let the nightly
close the April pots when they end on 31 March, so their carry-in lands in
the January pot. Do the same with its bank-holiday policy, so the
bank-holiday pot follows the same year.

Each day then counts once. The April pots earn 1 April to 31 December
under the old policy; January to March belong to the January policy's
year, so they count in the new pots and not in the April ones too. For
37.5 hours moving from 5.6 weeks to 22 days: the 2026/27 pot is 158.25
(210 × 275/365) and the 2027 pot 165.00; the 2026/27 bank-holiday pot has
the seven holidays of April to December 2026 (52.50) and 2027's has all
eight (60.00).

### Carry over max weeks (`carry_over_max_weeks`)

The most that carries into the next year, in weeks times the contracted
amount on the new year's first day, rounded. For an hours contract type the
page asks for **Carry over max days** (`carry_over_days`) instead, full-time
days stored as weeks (days ÷ 5). **Blank means nothing carries**:
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
  pot, counted from the [calendar](#bank-holidays-and-closed-days): **one
  working day for each bank holiday** in the pot's year on which the person
  is employed with a contract, a working day being their weekly amount that
  day ÷ 5, pro rata to their contracted hours whatever days they work. With
  the eight England and Wales holidays in a January to December year that
  is 8 × 7.5 = 60 hours at 37.5 hours a week, 30 at 18.75; someone starting
  on 15 March 2026 gets the seven still to come, 52.5 hours. It is rounded
  to the bank-holiday policy's step and does not use the accrual basis.
  Each bank holiday that falls on a day they work is charged to it
  automatically at that day's pattern. The pot and the charges need not
  match: someone on 18.75 hours over Monday to Wednesday has a 30.00 pot
  but is charged 6.25 for each holiday on a working day, and five of
  2026's fall on a Monday (31.25), so the balance can end slightly
  negative (carried in full) or, for other patterns, in surplus (which
  expires); that is the contract's pro-rata rule.
- **Included in annual leave:** each is charged to the Annual leave pot
  instead.

The charge is an automatic, approved absence row per bank holiday, created
when the pot opens and kept in step nightly (removed if the pattern or policy
no longer implies it; re-costed from today if the pattern changes). *The
pot option needs a Bank holiday policy for the same contract type* to give
the pot its leave year and rounding; without one the nightly reports the gap
instead of charging nothing. Give it the same leave year as the
annual-leave policy. Its page shows what the pot comes to ("8 bank holidays
in 2026, one working day each, pro rata to contracted hours") in place of an
entitlement, and has no handling of its own (annual leave's decides) and no
tiers.

### TOIL expires after days (`toil_expires_after_days`)

On a TOIL policy: how long earned TOIL may be used, counted from the day it
was earned. Blank means never. See [Year end](year-end.md#toil).

### Tiers

The inline on a policy adds leave for service: **After years** and, for an
hours contract type, **Full-time days**, the new *total* days a year from
then on ("23 days after 1 year"), stored as extra weeks over the policy's
own days and shown beside it ("+0.2 weeks"). A tier cannot give fewer days
than the policy itself, nor a later tier fewer than an earlier one; change
the policy's days and the tiers keep their totals. For a sessions contract
type the inline takes **Extra weeks**, the *total* extra at that point, not
added on top of earlier tiers (a 5-year tier of 1 and a 10-year tier of 2
give one extra week at 6 years, two at 11). Service is counted from the
employment's continuous service date, and the entitlement steps up from the
day a tier is reached (under monthly twelfths, from the month).

### Historic terms (TUPE and other groups)

A group on different terms, such as staff who joined under TUPE in 2019 or
reception staff kept on an older contract, needs no code: **create a
contract type per group** (People › Contract types, say "Reception (TUPE
2019)"), **give it its own policy** here with that group's days, tiers,
leave year and accrual (and a bank-holiday policy if its annual leave uses
the pot), and put the group's contracts on that type. Everyone else keeps
the standard contract.

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

## Recording leave for someone else

A manager records a report's absence on the day (a phone call saying they
are ill, or leave agreed in person), and an HR admin anyone's, from
**Record leave for …**: on *Leave* (under "Record leave for someone else")
and on the **Team** balances page, one link per person. It is the same
two-step form, at `/absence/request/<employee>/`, showing *their* balances.
Only the person the employee's requests go to (their line manager) and HR
admins may use it; anyone else gets "forbidden". Because the person
recording it is the one who would have approved it, it is **approved at
once** (audited as requested and approved by you, with the comment
"Recorded by …"), and the employee is emailed the decision. Your own
absences go through the ordinary request.

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
request: an HR admin's goes to (and is emailed to) the other HR admins. Approving costs the request
afresh and writes the booking line in one transaction; declining writes
nothing to the pot.

A request already decided or cancelled (say, from an old email) opens
**read-only**, showing what happened, by whom and when, and the comment.

## Cancelling

An employee can cancel their own request at any time, and their own approved
absence **until it starts**; after that only an HR admin can, at any time.
An HR admin's own absences follow the employee's rule: another HR admin
cancels one that has started.
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

**Pots** and their ledger lines are read-only in the admin: no one edits or
deletes a line there. Two actions write through the ledger service:
**Recalculate entitlement** on selected pots (the Pot list), which writes a
revision line if the entitlement is out of step (for example after a
working-pattern change), and **Adjust balance** on a pot's own page (HR
admins), which writes one audited adjustment line with your note; see
[Adjusting a balance](year-end.md#adjusting-a-balance). Both refuse a pot
whose leave year has been closed. TOIL is earned from the shell
(`absence.services.toil.earn`); there is no screen for it yet.

The **Absences** list is a read-only record of every absence, apart from a
family-leave absence's dates (see [above](#family-leave-and-keeping-in-touch-days)).
