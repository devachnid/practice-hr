# Admin guide

Reference for everything configurable at `/admin/`. One page per area, every
field explained — what it does, what depends on it, and what goes wrong if
it is set incorrectly.

The `README.md` in the project root has the *sequence* for a first-time
setup. This is the *reference* for what each setting means once you are in
there.

| Page | Covers |
|---|---|
| [People](people.md) | Employees, employments, positions, teams, contract types, contracts, working patterns, pay records, the audit log |
| [Login accounts and signing in](sign-in.md) | Login accounts, admin status, passkeys, invitations, nightly housekeeping, and the OpenID Connect provider |

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
