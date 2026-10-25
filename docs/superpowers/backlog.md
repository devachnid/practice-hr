# Backlog

What is agreed but not built, in rough priority order. Each larger item gets
its own design conversation, spec and plan before it is started. Smaller
items can go straight into a tidy-up branch.

## Next

1. **Go live.** Deploy both systems, run the login migration (rota
   `export_logins` → HR `import_logins`), switch the rota to HR sign-in,
   enter people and contracts, let the first nightly run, then opening
   balances as adjustments. The HR guide's first-month checklist is the
   sequence. For spec 3 (merged as #16): de-duplicate position-title
   variants before migrating, read the NI-number migration's report,
   make the media root writable by the app user, and record everyone's
   existing checks before assigning titles to the check types (the HR
   guide's Going live section has the order). Since #18, adding an
   employee record makes and invites their login from the work email, so
   logins are no longer a separate step; the login migration from the
   rota still runs first for people who already have rota passwords
   (`import_logins` links by email, and the add page links an unlinked
   login that already has the work email rather than making another).
2. **Rota integration (spec 2).** The rota reads people, working patterns
   and approved absences from the HR read API instead of Breathe, and sends
   sessions worked back as TOIL earned lines. The HR side of the API exists;
   the rota side and the TOIL feed do not.
3. **Training compliance (spec 4).** Role-to-course matrix, evidence,
   renewals. The reminder engine, the evidence store and the expiry
   pattern all exist from spec 3 (checks with validity, files, the
   compliance digest), so this is a new app contributing `due_items`
   rather than new plumbing.
4. **Later.** Sickness case management, appraisals, restricted case files.
   The GMC sells a full-register download service; if the practice ever
   wants a sanctioned machine interface in place of reading the public
   search page, that is the route (an agreement, and a new adapter).

## Smaller items

- Capture the register page fixtures per
  `registers/adapters/fixtures/README.md`, so the four register bodies
  become verified and their scheduled lookups start. The registration
  checks themselves are built (spec
  `2026-10-05-professional-registrations-design.md`); until the pages are
  saved, every lookup is on demand.
- Accept a known name difference (married or maiden name) on a
  registration so it stops alerting: today a register name that does not
  match the record's surname is a *Name does not match* alert on every
  lookup until the record or the register changes.
- The Welsh medical performers list URL is plain `http` and, like the
  other three, unverified against a real page; confirm its address (and an
  `https` one) when its pages are captured.
- Alternating-week working patterns (the field exists; the UI and costing
  do not).
- Delegated approval while a manager is away.
- A screen for entering opening balances as carry-in rather than
  adjustments, so the carry-over expiry rule applies to them.
- A page where HR sees another person's absences with a Cancel control
  (today only the admin page has it).
- Reminder emails to the manager as well as HR.
- An employee user guide to match the two written (the manager guide now
  has a "your own" section covering policies, checks, documents and the
  checklist, which is most of it).
- A retention deletion path for checks, files and signatures: the
  retention report lists them by category, but `File` and `Signature`
  protect their employee, so deleting a person under retention needs its
  own steps (and the file bytes).
- Prune the `ReminderSent` log (it grows forever; nothing reads rows
  older than the longest cadence).
- Reopen a "no policies to sign yet" checklist item when the first policy
  that applies to the person is issued (today the policy reminders cover
  it and the item stays closed).
- The compliance pages use a fixed 60-day "due soon" window while the
  reminders use the practice's own setting; use the setting on the pages.
- A confirmation on Remove on HR's checklist page.
- People past the recent-start window with no open details item cannot
  enter their own bank details (HR does it); a way to reopen the form.
- A Compliance tab and dashboard card that are computed on every load;
  cache if the practice grows.
- Hide the rota admin's "send invitation" and "send reset link" buttons
  while HR sign-in is on (the links they send open the invalid-link page).
- An HR-side note that a rota whose hashes used an unconfigured algorithm
  would be refused wholesale by `import_logins`.
- A Breathe CSV import, only if typing opening balances is too slow.
- Anniversary-year policy moves that straddle a window.
- An **Admin status** tick on the employee add page, so an HR admin's
  login need not be edited under Login accounts after it is made.
- Reopen or re-invite from the employee page: a **Send invitation again**
  there, rather than through Login accounts, for a starter whose link
  expired.

## Excluded on purpose (spec §"Not done")

Buying and selling leave; statutory pay arithmetic; fit notes, return-to-work
and Bradford factor; automatic deletion under retention; multi-practice.

## Technical loose ends (recorded, low risk)

- Registration lookups are never pruned (with the `ReminderSent` log).
- `charge_again` checks the passed row's status rather than a locked
  re-read; its only caller re-reads first.
- No test for the API rate limiter's "unknown address" fallback.
- `AppRole` writes from the Login accounts page leave no audit entry beyond
  Django's own admin log.
- An empty `sub` claim would apply the admin flag to an email-matched rota
  row that never binds (OIDC requires `sub`, so theoretical).
- `checks.state` and `policies.state` run a query per row; the pre-start
  gate and the nav flag add a few queries per page.
- `ReminderSchedule.get()` creates the singleton row on first read, which
  can be an admin GET.
- Starter and leaver checklist items keep a manager owner who has since
  left or changed position; a historical end date builds a leaver
  checklist that is overdue at once; the "leaving date cleared" marker
  lives in the free-text gaps field.
- A renewal request on a due-soon or lapsed check is outside the manager's
  awaiting count.
- A password signature on a policy also opens the passkey-enrolment
  window, as any password confirmation does.
- Login accounts › Add still sends its invitation inside the add
  transaction (the relay call holds SQLite's write lock for up to the
  email timeout); the employee add page sends on commit instead. Move the
  Login accounts send to `transaction.on_commit` the same way.
