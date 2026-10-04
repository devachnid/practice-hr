# Admin guide

Reference for everything configurable at `/admin/`. One page per area, every
field explained — what it does, what depends on it, and what goes wrong if
it is set incorrectly.

The `README.md` in the project root has the *sequence* for a first-time
setup. This is the *reference* for what each setting means once you are in
there.

| Page | Covers |
|---|---|
| [People](people.md) | Employees, employments, positions, teams, contract types, contracts, working patterns, pay records, the audit log, the retention report |
| [Absence and leave](absence.md) | Absence types and their flags, policies and every field, tiers, bank holidays and closed days, how a request is costed, requesting, deciding and cancelling, TOIL claims, family leave, the calendar, balances |
| [Year end](year-end.md) | What the nightly closes at the end of a leave year: carry cap, expiry, TOIL, leavers' debts; running it by hand; reversing a line |
| [Payroll changes report](payroll.md) | The monthly spreadsheet for the payroll bureau: what each sheet holds, which absence types reach it, spanning months, leaver balances, where the files live |
| [Compliance](compliance.md) | Check types and the titles that need them, recording a check, what each status means, asking the person for evidence, the DBS rule on not storing certificates |
| [The read API](api.md) | The three JSON endpoints the rota polls, the token in `HR_API_TOKENS`, and the shapes they return |
| [Login accounts and signing in](sign-in.md) | Login accounts, admin status, passkeys, invitations, nightly housekeeping, the OpenID Connect provider and who is an admin of each app, and migrating the rota's logins |

## The mental model

**Employee is the person; everything dated hangs off Employment.** A
returner gets a new Employment row, never an edit to the old one — see
[People](people.md#the-mental-model).

**Positions, contracts and pay records only end.** Changing a title, a
team, a contract's amount or a line manager is a new row plus an end date
on the old one, never an edit in place — see
[Changing something](people.md#changing-something).

**Nothing is deleted.** There is no delete button anywhere in People or
Login accounts. History stays intact whatever changes.

**Restricted data is gated and logged.** NI numbers and pay records are
visible to [HR admins](sign-in.md#admin-status) only, and opening an
Employment page with pay records writes an entry to the
[audit log](people.md#audit-log).

**Leave is a ledger.** A balance is the sum of a pot's lines, which are only
ever added; a mistake is put right by a new line, never an edit — see
[Absence and leave](absence.md#the-mental-model) and
[Adjusting a balance](year-end.md#adjusting-a-balance).
