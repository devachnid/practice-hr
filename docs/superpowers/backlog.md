# Backlog

What is agreed but not built, in rough priority order. Each larger item gets
its own design conversation, spec and plan before it is started. Smaller
items can go straight into a tidy-up branch.

## Next

1. **Go live.** Deploy both systems, run the login migration (rota
   `export_logins` → HR `import_logins`), switch the rota to HR sign-in,
   enter people and contracts, let the first nightly run, then opening
   balances as adjustments. The HR guide's first-month checklist is the
   sequence.
2. **Rota integration (spec 2).** The rota reads people, working patterns
   and approved absences from the HR read API instead of Breathe, and sends
   sessions worked back as TOIL earned lines. The HR side of the API exists;
   the rota side and the TOIL feed do not.
3. **Professional registration checks.** For clinicians, record the
   registration body and number, and check that the registration is valid
   and active, both on demand (the result shown to the person who asked) and
   on a schedule (an email to the managers only when something is wrong:
   lapsed, suspended, conditions, not found, or a number that does not match
   the name). Registers by role:
   - GPs: the GMC register, and the medical performers list for Wales (held
     by NHS Wales Shared Services Partnership).
   - Nurses: the NMC register.
   - Pharmacists and pharmacy technicians: the GPhC register.

   To settle at design time: which of these offer a lookup an application
   may use (the GMC has a data service under agreement; the NMC and GPhC
   publish web searches and employer confirmation routes rather than public
   APIs; the Welsh performers list is published as a document), how often to
   check, what to store from a check (date, outcome, the register's own
   status text), and how this fits the training-compliance reminder engine
   (spec 4) so there is one place for "something expires or has lapsed".
4. **Onboarding, offboarding and documents (spec 3).** Checklist templates
   by role, checks with expiry dates, a document store with read-and-sign.
5. **Training compliance (spec 4).** Role-to-course matrix, evidence,
   renewals, and the reminder engine shared with item 3 and spec 3.
6. **Later.** Sickness case management, appraisals, restricted case files.

## Smaller items

- Alternating-week working patterns (the field exists; the UI and costing
  do not).
- Delegated approval while a manager is away.
- A screen for entering opening balances as carry-in rather than
  adjustments, so the carry-over expiry rule applies to them.
- A page where HR sees another person's absences with a Cancel control
  (today only the admin page has it).
- Reminder emails to the manager as well as HR.
- An employee user guide to match the two written.
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
