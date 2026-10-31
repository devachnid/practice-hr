# Staff management: requirements interview brief

**For:** the practice manager
**From:** the development side (rota and HR systems)
**Date:** 2026-10-28
**Purpose:** to get the requirements for team rotas and leave management out
of the practice manager's head and onto paper, in a form the developers can
turn into implementation plans.

---

## Part A — For the practice manager (read this first)

### What this is

We want to bring three things together into one staff management system for
the practice:

1. **The GP rota** we already run (session-based, AM/PM).
2. **The HR system** we have started (people, contracts, working patterns,
   leave, compliance, training, and the sign-in for the practice's apps).
3. **Rotas for every other team** — admin, reception, nursing, pharmacy —
   working the way FindMyShift does, which you know and like, **but with leave
   calculated correctly for people whose contract and pattern are in hours.**

Before we write any code we need a specification written from your point of
view: what the practice does, what you need the system to do, what FindMyShift
gets right and wrong, and — most importantly — worked examples of leave
calculations with the answers you expect.

### How to use this

1. Open a new conversation with Claude (a Project is best, so you can upload
   files and come back to it across several sittings).
2. Copy **everything in Part B below** — from the line "PROMPT STARTS" to the
   line "PROMPT ENDS" — and paste it in as your first message.
3. Claude will interview you, one topic at a time. It will ask short
   questions, often with options to pick from. Answer in your own words; "I
   don't know" and "it depends" are fine answers — it will ask what it
   depends on.
4. Expect **three to five sittings of 45–60 minutes**. You can stop at any
   point; ask Claude for a "where we got to" summary before you stop, and
   paste it back in when you resume if you aren't using a Project.
5. At the end Claude will write the specification documents. Read them,
   correct anything wrong, and send the whole set back to us.

### What to have to hand (gather before the first sitting if you can)

You do not need all of these to start. Upload what you have.

- **Screenshots of FindMyShift** — the schedule view for each team, the
  staff app, the time-off request screen, the allowance/balance screens,
  reports you use, settings pages you rely on.
- **Two or three real leave mistakes FindMyShift made** — the person's
  contract, pattern, what FindMyShift said, and what the right answer was.
  These are the most valuable thing you can bring.
- **The practice's leave policy** / staff handbook section on annual leave,
  bank holidays, carry-over, TOIL, sickness reporting.
- **Contract templates or summaries** by staff group (hours, entitlement in
  days or hours, service-related increases, whether on Agenda for Change–style
  terms).
- **An example rota for each team** — a typical week, and a difficult week
  (school holidays, a bank holiday week, flu clinic season).
- **Minimum staffing rules** you work to, written or unwritten ("never fewer
  than three on the phones at 8am").
- **A list of who is who**: teams, roles, line managers, who approves whose
  leave. Use roles or initials rather than full names if you prefer.

**Please don't upload** patient information of any kind, staff health
details, bank details or NI numbers. Use initials or made-up names in
examples — the numbers are what matter, not who they are.

### What happens next

You send the documents back. We check them against what the GP rota and HR
system already do, come back to you with any questions, then write the
implementation plans and build in stages, starting with whatever you tell us
matters most.

---

## Part B — The prompt

```
PROMPT STARTS
```

You are going to interview me, the practice manager of a UK GP practice, and
then write a requirements specification for a staff management system. I am
not a software developer. The specification you write will be handed to the
practice's developer, who will use it (with their own Claude) to write
implementation plans and code. Your job is to capture **what** the practice
needs and **why**, in enough detail and with enough concrete examples that a
developer can build it without guessing — and to capture it in my words,
not to design the software.

### 1. Background you need

**The practice already has two systems, built in-house:**

**(a) The GP rota.** A web app (Django, Python) for the GPs only. It works in
**sessions** — each day has an AM and a PM half, and a GP's working pattern,
leave and duties are counted in sessions. It has: an eight-week rota grid;
automatic filling of sessions against coverage rules (how many of which
session type per site per half-day) and fairness; GP trainees; recurring
commitments; locum bookings; shift swaps between GPs; personal requirements
("each GP does one of X every N weeks"); a "My Schedule" view; mobile
layouts. It currently reads GPs' time off from FindMyShift through
FindMyShift's API, as a stop-gap. It deliberately holds almost no personal
data and no leave balances.

**(b) The HR system ("Practice HR").** A separate web app, built to replace
BreatheHR, and the **sign-in for all the practice's apps** (one account per
person, with passkeys; other apps sign in through it). It holds: people,
employments (dated spells, with a continuous-service date), contracts
(several can overlap — e.g. 18.75 h permanent plus 18.75 h fixed-term),
working patterns (a dated weekly pattern with AM and PM amounts per day),
teams, line managers, pre-employment checks, documents, policies to sign,
starter/leaver checklists, professional registration checks (GMC, NMC,
GPhC), and training compliance. Its **leave design** is already written and
built but **not yet live**. The decisions in it, which I want you to test
against my real cases rather than take for granted:

- The **unit is set per contract type**: sessions for GPs, **hours for
  everyone else**.
- Annual entitlement is expressed in **weeks per year** and multiplied by the
  contracted weekly amount (e.g. 5.6 weeks × 22.5 h = 126 h). Service-based
  increases are extra weeks after N years.
- Entitlement **accrues day by day** across the leave year, so starters,
  leavers, an hours change mid-year, a fixed-term contract ending and a
  service step mid-year are all handled by one calculation.
- A leave year is either **fixed** (e.g. 1 April) or the **anniversary** of
  the start date, set per policy.
- Booking a day of leave **costs what the person's pattern says they would
  have worked that day/half-day** (a 7.5 h Monday costs 7.5 h; a 4 h Friday
  costs 4 h). Hours-based staff can also book **part of a day** in hours.
- **Bank holidays** — one of three handlings per policy: practice closed and
  not charged; a separate pro-rata bank-holiday allowance; or bank holidays
  included in annual leave and deducted automatically when they fall on a
  working day.
- Carry-over has a maximum and an optional expiry; TOIL can expire.
- Every balance is a list of dated entries (entitlement, bookings,
  cancellations, adjustments) that adds up — nothing is a typed-in number,
  so every figure can be explained.
- Everyone requests their own leave; **line managers approve**; the practice
  manager oversees and can override.
- Payroll is an external bureau; the system sends a monthly changes report
  and does **no statutory pay calculation** (SSP, SMP etc.).
- Not yet covered: alternating-week patterns, irregular-hours/bank staff,
  buying and selling leave, delegation of approval while a manager is away.

**What we want next:**

1. **Rotas for the other teams** — admin, reception, nursing, pharmacy (and
   any others I name) — with the **interface and ease of use of
   FindMyShift**, which I have used and like.
2. **Full leave management for all staff and the GPs**, including the
   calculations, in one place.
3. All of it brought together into one staff management solution. It may end
   up as one app or two or three apps, but **people have one account across
   all of it**.

**Why not just keep FindMyShift:** it does not calculate leave correctly for
staff whose leave or working pattern is in hours. Otherwise I like its
interface. I can describe it but you cannot see it — rely on what I tell
you and the screenshots I upload, and ask me to describe screens rather than
assuming how FindMyShift works. We are building our own system that works
the way I want, not copying FindMyShift's branding or wording.

### 2. How to run the interview

- **One question at a time.** Wait for my answer before the next. Where you
  can, offer 2–4 options to choose from plus "something else", with the one
  you think most likely first.
- **Plain English, no jargon.** If you need a technical term, explain it.
  Don't ask me about databases, frameworks or architecture. If I volunteer a
  technical preference, record it as a preference.
- **Ask for real examples.** Whenever I describe a rule, ask for a real case
  (anonymised) and what should happen. Whenever I say "usually", ask about
  the unusual case. Whenever I say "it depends", ask what on.
- **Work the numbers with me.** For every leave rule, build a worked example
  together and agree the expected answer before moving on (see section 4).
  Show your arithmetic so I can check it.
- **Challenge gently.** If something I say conflicts with something earlier,
  or with the HR system decisions above, point it out and ask which is right.
  If a rule I describe looks like it might fall short of UK employment law
  (e.g. statutory minimum holiday, holiday for irregular-hours workers),
  say so neutrally and record it as a question for the practice to check
  with its HR/legal adviser — **don't give legal advice and don't refuse to
  record what I say.**
- **Keep a running log.** After each topic, give me a short summary of what
  we decided and what is still open, and ask me to confirm it. Keep a list of
  open questions I couldn't answer (who to ask, by when).
- **Keep momentum.** If I'm unsure, record the uncertainty and move on; we
  can come back. Tell me roughly where we are in the plan ("topic 4 of 11").
- **Stopping and resuming.** If I say I need to stop, give me a "where we got
  to" summary I can paste in next time: topics done, decisions, open
  questions, and the next question you were going to ask.
- **Privacy.** If I start giving patient information, staff health details,
  bank details or other sensitive personal data, stop me and ask for an
  anonymised version.

### 3. Interview plan

Cover these topics in roughly this order. The questions under each are a
starting point, not a script — follow up where the answers lead, and skip
what clearly doesn't apply.

**Topic 1 — The practice and the people**
- Sites (how many, opening hours each, extended access / evenings /
  Saturdays), approximate headcount per team.
- Teams and roles: admin, reception, secretaries, nursing (practice nurses,
  HCAs, phlebotomists), pharmacy (clinical pharmacists, pharmacy
  technicians), management, GPs, others (care coordinators, social
  prescribers, physician associates, paramedics, mental-health
  practitioners).
- **Who employs whom**: practice-employed, PCN-employed (ARRS roles),
  federation, agency, locum, bank/casual, trainees and students. Which of
  these need rotas, which need leave managed here, which only need to appear
  on a rota, and which need a login.
- People in more than one team or role (e.g. a receptionist who also does
  admin, an HCA who also does reception), and how that should look.
- Who are the managers, who approves leave for whom, who builds each team's
  rota, who is allowed to change it.

**Topic 2 — How the rotas work today, team by team**
For **each** team (admin, reception, nursing, pharmacy, and any other):
- What is being rota'd — shifts with clock times (08:00–13:00), sessions
  (AM/PM), clinics, desk/phone positions, rooms, tasks?
- How far ahead is the rota built and published? How often does it change
  after publishing, and who needs to know?
- Is it mostly the same every week (template), rotating (week 1 / week 2,
  alternate Saturdays), or built fresh?
- Breaks: paid/unpaid, fixed or flexible, do they need covering?
- Minimum staffing and skill rules ("two on phones 08:00–10:00", "one
  person trained in X on every session", "a chaperone available") — and
  what should happen when a rule is broken (warning, block, alert someone).
- Nursing specifics: clinic types and lengths, skills/competencies that
  limit who can do what (cervical screening, immunisations, diabetes
  reviews), rooms, flu/COVID campaign clinics.
- Pharmacy specifics: practice vs PCN time, working across practices.
- Cover: how gaps are filled today (overtime, bank staff, swaps, asking in a
  WhatsApp group), and how you'd like it to work.
- Does any rota need to match the clinical system's appointment book
  (EMIS / SystmOne)? (Record the need; don't solve it.)
- The relationship with the GP rota: does anything in the other teams'
  rotas depend on which GPs are in (e.g. reception or HCA cover for GP
  sessions)? Should there be one view of "who is in today" across
  everyone?

**Topic 3 — FindMyShift: what to keep, what to change**
Ask me to walk through FindMyShift screen by screen (screenshots help). For
each screen or feature: do I use it, who uses it, what I like, what annoys
me, and whether the new system must have it, should have it, or doesn't
need it. Make sure you ask about at least:
- the schedule grid (by person / by day / by week; colours; drag and drop;
  copy and repeat weeks; shift templates)
- publishing and notifying staff; the staff's own view and the mobile app
- open (unfilled) shifts and staff claiming them
- shift swaps and drop requests, and who approves them
- availability and preferences staff can set
- time-off requests and allowances, and **exactly where the calculations go
  wrong**
- timesheets, clock in/out, actual vs planned hours, overtime
- wage costs and budgets
- reports and exports (what, for whom, how often)
- messaging, notes, announcements
- printing / displaying the rota (e.g. on the staff room wall)
- settings that took effort to set up and that we must not lose
Then: **what is missing** from FindMyShift that I wish it did.

**Topic 4 — Working patterns and contracts**
- How contracts are expressed per staff group: hours per week, days per
  week, sessions, annualised hours, term-time only, zero-hours / bank.
- Patterns: fixed weekly, alternating weeks, rotating (e.g. 1 in 3
  Saturdays), different hours on different days, patterns that change with
  the season.
- How often hours or patterns change, and whether a change is ever
  backdated.
- What "a day" means for someone with uneven days (Mon 7.5 h, Tue 4 h).
- Overlapping contracts, secondments, acting-up, fixed-term extra hours.
- Staff who work at more than one site or for more than one employer.

**Topic 5 — Leave rules (the core of this exercise)**
For **each** staff group, find out:
- Entitlement: in days, hours or weeks? Including or excluding bank
  holidays? Statutory minimum, contractual extra, service-related increases
  (after how many years, how much, from when — the anniversary or the next
  leave year?). Agenda for Change–style terms or practice-specific?
- How a days-based entitlement is converted to hours for part-timers and
  people with uneven days (and what the rounding rule is).
- Leave year: fixed date or anniversary? Same for everyone?
- Starters and leavers: pro-rata method, rounding, what happens to leave
  taken in excess or not taken when someone leaves (record the rule; the
  pay is payroll's job).
- Hours changes mid-year: how the remaining entitlement should change.
- Bank holidays: closed? Who works them? How part-timers and people who
  don't work Mondays are treated. What happens when a bank holiday falls in
  someone's booked leave. Extra bank holidays (coronations etc.).
- Booking: whole days, half days, hours, minimum unit? What a half day
  means for someone working 5 h or 9 h that day.
- Carry-over: how much, until when, who can authorise exceptions; the
  statutory rules for sickness and family leave carry-over.
- TOIL and overtime: how earned, approved, recorded, taken, expire.
- Other leave types: study, compassionate, dependants, jury service,
  unpaid, sickness, maternity/paternity/adoption/shared parental, keeping-
  in-touch days, medical appointments, special leave. For each: does it
  come out of an allowance, does it need approval, does it go to payroll,
  who can see it.
- Irregular-hours and part-year workers (bank, casual, zero-hours, term
  time): how their holiday is calculated or paid today.
- Buying/selling leave, leave in advance, negative balances.
- **For every rule, a worked example with the expected answer** (section 4).

**Topic 6 — Requesting and approving leave**
- Who can request for whom (self, manager on someone's behalf, admin).
- What the requester should see while requesting (balance before/after,
  who else is off, rota clash).
- Rules that block or warn: maximum off per team at once, blackout periods
  (flu season, Christmas, QOF year end), notice periods, minimum staffing.
- Approval: who, how many levels, what if they're away, deadlines,
  reminders.
- What happens to the rota when leave is approved: remove the person's
  shifts? flag them as gaps? notify the rota builder?
- Cancelling and changing approved leave; leave in the past.
- GPs specifically: is GP leave approved the same way, by whom, with what
  rules (e.g. maximum GPs off in a session)?
- Sickness: who records it, when, return-to-work, how it shows on the rota.

**Topic 7 — Accounts, roles and permissions**
- Who needs to log in (everyone? only some groups? people not employed by
  the practice?).
- Roles: staff member, team leader, rota builder, line manager, HR admin,
  practice manager, partners, GP rota admin — what each can see and do.
- What colleagues can see about each other (names and "off", or the reason
  too?), what managers see, what is restricted (sickness reasons, pay).
- Devices: work PCs, personal phones, shared reception PCs; logging in on a
  shared machine.

**Topic 8 — Notifications, views and day-to-day use**
- What the staff member needs on their phone: my shifts, my leave balance,
  request leave, swap, claim open shifts, see who's in.
- Notifications: email, push, SMS? Which events? Daily/weekly digests?
- Views a manager needs every day: today's cover across all teams, gaps,
  pending requests, who is off this week.
- Any wall display / "who's in today" board.
- Accessibility needs among staff (screen readers, larger text, colour
  blindness).

**Topic 9 — Reports and integrations**
- Reports needed, by whom, how often: leave taken and remaining, sickness,
  hours worked vs contracted, overtime, cost, rota coverage, payroll
  changes. Examples of reports you produce manually today.
- Payroll: who the bureau is, what they need, in what format, by when.
- Other systems: clinical system, NHSmail calendars, Microsoft 365/Teams,
  the PCN, the ICB, CQC inspection evidence.

**Topic 10 — Moving across and going live**
- What must be brought over from FindMyShift and Breathe: staff, patterns,
  current balances, booked future leave, history (how far back)?
- Opening balances: who will check them, and against what?
- Running in parallel: for how long, which team first?
- Training staff: who, how, how much time is realistic.
- Dates that matter: leave-year start, FindMyShift renewal date, busy
  periods to avoid.

**Topic 11 — Priorities**
- If we can only deliver one thing first, what is it? Then second, third?
- Must have / should have / could have / won't have (for now) for
  everything we've discussed.
- What would make this a failure in your eyes? What would make staff stop
  using it?
- What does "it works" look like in six months?

### 4. Leave calculation worked examples (non-negotiable)

The single most important output is a set of **worked leave calculations
with agreed expected answers**, because getting hours-based leave right is
the reason this project exists. The developer will turn each one into an
automated test. Build these with me, one at a time, showing the arithmetic.
Aim for **at least 20**, covering at least:

1. Full-time, hours-based, whole year (e.g. 37.5 h/week).
2. Part-time, equal days (e.g. 3 days × 7.5 h).
3. Part-time, **uneven days** (e.g. Mon 7.5, Tue 7.5, Thu 4) — entitlement,
   and the cost of booking each different day.
4. A half day for someone with uneven days.
5. Partial-day leave in hours (e.g. 1.5 h for an appointment).
6. Starter part-way through the leave year.
7. Leaver part-way through the year, with leave taken in excess and with
   leave untaken.
8. Hours increase mid-year; hours decrease mid-year, with leave already
   booked after the change.
9. Two overlapping contracts (permanent plus fixed-term), with the
   fixed-term ending mid-year.
10. Service-related increase stepping in mid-year.
11. Bank holiday falling on a working day, and on a non-working day, for a
    part-timer — under the practice's actual bank-holiday rule.
12. A week's leave spanning a bank holiday.
13. Someone who does not work Mondays (most bank holidays).
14. Extra one-off bank holiday.
15. Carry-over within the limit, over the limit, and expiring.
16. TOIL earned and taken, and expiring.
17. Alternating-week or rotating pattern (if the practice has any).
18. Bank / zero-hours / irregular-hours worker.
19. A GP in sessions (e.g. 6 sessions a week), for comparison.
20. **Each real case where FindMyShift got it wrong** — what it showed,
    what is right, and why.

For each example record, in a table:

| Field | Example |
|---|---|
| ID | LV-07 |
| Situation in one line | Part-timer starts mid-year on uneven days |
| Staff group / contract type | Reception, hours |
| Contract(s) | 22.5 h/week permanent from 2026-09-01 |
| Pattern | Mon 7.5, Tue 7.5, Thu 7.5 |
| Leave year | 1 Apr 2026 – 31 Mar 2027 |
| Policy | 5.6 weeks incl. bank holidays; round to nearest 0.25 h |
| Events | Starts 1 Sep; books Tue 3 Nov; bank holiday Mon 28 Dec (Boxing Day substitute) |
| Expected answer(s) | Entitlement 126 h × 212/365 days = 73.25 h; 3 Nov costs 7.5 h; 28 Dec deducts 7.5 h; … |
| Working | step-by-step arithmetic |
| What FindMyShift did (if known) | … |
| Confidence | Agreed / needs checking with adviser |

(The numbers in that row are illustrative — work out the real ones with me.)

If an expected answer depends on a rule we haven't settled, mark it, record
the open question, and move on.

### 5. What to write at the end

When we've covered the topics (or when I ask), write the specification as a
set of Markdown documents. If you can create files, make one file per
document; otherwise produce them one after another in the conversation,
each starting with its file name as a heading, so I can copy them out.

1. **`00-overview.md`** — the practice in a page; the goal; who the users
   are; what's in and out of scope; a glossary of the practice's own terms
   (session, shift, clinic, TOIL, ARRS, etc.).
2. **`01-people-teams-and-roles.md`** — staff groups, employers, teams,
   reporting lines, who approves what, who builds which rota; people in
   several teams.
3. **`02-team-rotas.md`** — one section per team: what's rota'd, patterns,
   templates, staffing and skill rules, cover, publishing, changes; plus what
   is common to all teams and how it relates to the GP rota.
4. **`03-findmyshift-feature-review.md`** — a table of every FindMyShift
   feature discussed: used? by whom? keep / change / drop / add; priority;
   my comments. Then the list of things it lacks.
5. **`04-contracts-and-working-patterns.md`** — how contracts and patterns
   are expressed and change.
6. **`05-leave-policy.md`** — every leave type and rule, per staff group,
   written as plain rules ("A part-timer's annual entitlement is…").
   Where a rule matches or differs from the HR system decisions in section 1
   of this prompt, say so explicitly.
7. **`06-leave-worked-examples.md`** — all the worked examples from
   section 4, in the table format, numbered LV-01 onwards.
8. **`07-requests-approvals-and-notifications.md`** — leave and swap
   workflows step by step, blocking and warning rules, who is told what,
   when, how.
9. **`08-access-and-privacy.md`** — who logs in, roles, who sees what (as a
   table), devices, sensitive data.
10. **`09-reports-integrations-and-payroll.md`** — each report (purpose,
    audience, frequency, contents), payroll needs, other systems.
11. **`10-migration-and-go-live.md`** — what to bring across, opening
    balances, parallel running, order of teams, key dates, training.
12. **`11-priorities.md`** — must/should/could/won't for every requirement
    (refer to them by ID), the first release in my words, and the success
    and failure measures.
13. **`12-decisions-and-open-questions.md`** — a decisions table (decision,
    reason, date) and an open-questions table (question, who can answer,
    blocking which requirement).

**Writing rules for the documents:**
- Write requirements as numbered, testable statements with IDs
  (`ROTA-REC-04`, `LEAVE-12`, `ACC-03`), each with a short "why".
  "The system should be easy to use" is not testable; "a receptionist can
  request a half day from their phone in under a minute" is.
- Use my words and the practice's terms. Don't invent requirements I didn't
  give you; if you think something's missing, put it in open questions.
- Describe **what** and **why**, not **how**. No database tables, no
  technology choices — except where I stated a preference, which you record
  as a preference.
- Every leave rule in `05` should point to at least one worked example in
  `06` that tests it.
- Mark anything uncertain clearly (**[UNCONFIRMED]**) rather than smoothing
  it over.
- Include a short "Not needed, on purpose" list in each document for things
  we discussed and decided against — that is as useful to the developer as
  what is needed.

Before writing, give me a one-page summary of the requirements and the list
of open questions, and ask me to confirm. After writing, ask me to read each
document and tell you what's wrong, and revise until I'm happy.

**Start now:** introduce yourself in two or three sentences, tell me how the
interview will run and roughly how long it will take, ask what files I have
to upload, then ask your first question from Topic 1.

```
PROMPT ENDS
```

---

## Part C — What to send back

- All the documents Claude produced (`00` to `12`), after you've read and
  corrected them.
- Any screenshots or policy documents you uploaded, with personal details
  removed.
- Anything you think Claude got wrong but couldn't get it to fix — a note is
  fine.

Thank you — the time you spend on the worked examples in particular will
save a great deal of rework later.
