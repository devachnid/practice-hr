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
   guide's Going live section has the order).
2. **Rota integration (spec 2).** The rota reads people, working patterns
   and approved absences from the HR read API instead of Breathe, and sends
   sessions worked back as TOIL earned lines. The HR side of the API exists;
   the rota side and the TOIL feed do not.
3. **Professional registration checks.** For clinicians, record the
   registration body and number, and check that the registration is valid
   and active, both on demand (the result shown to the person who asked) and
   on a schedule (an email to the managers only when something is wrong:
   lapsed, suspended, conditions, not found, or a number that does not match
   the name). Spec 3 added `professional_registration` as a check type
   with an expiry, so the number, body and renewal date can be recorded
   now; this item adds the lookup. Registers by role:
   - GPs: the GMC register, and the medical performers list for Wales (held
     by NHS Wales Shared Services Partnership).
   - Nurses: the NMC register.
   - Pharmacists and pharmacy technicians: the GPhC register.

   To settle at design time: which of these offer a lookup an application
   may use (the GMC has a data service under agreement; the NMC and GPhC
   publish web searches and employer confirmation routes rather than public
   APIs; the Welsh performers list is published as a document), how often to
   check, what to store from a check (date, outcome, the register's own
   status text), and how a failed lookup feeds the compliance reminders
   (spec 3's `compliance` app: each app contributes `due_items`, the
   nightly digest sends them on the practice's cadence).
4. **Training compliance (spec 4).** Role-to-course matrix, evidence,
   renewals. The reminder engine, the evidence store and the expiry
   pattern all exist from spec 3 (checks with validity, files, the
   compliance digest), so this is a new app contributing `due_items`
   rather than new plumbing.
5. **Later.** Sickness case management, appraisals, restricted case files.

## Smaller items

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

## Excluded on purpose (spec §"Not done")

Buying and selling leave; statutory pay arithmetic; fit notes, return-to-work
and Bradford factor; automatic deletion under retention; multi-practice.

## Technical loose ends (recorded, low risk)

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
