# Year end

What happens when a leave year ends, how it is run, and how HR puts a line
right. The rules it applies come from each [policy](absence.md#policies): the
carry cap, the carry-in expiry and the TOIL expiry.

## What the nightly does

`hr_nightly` (01:30 daily; see [Nightly housekeeping](sign-in.md#nightly-housekeeping))
runs the year end first, then opens the current pots, recalculates every
open pot's entitlement and bank holidays, and chases waiting requests. It is
safe to run twice: every step looks for its own earlier line and writes
nothing the second time.

**It closes every unclosed pot whose leave year has ended**, oldest first, so
a late catch-up carries forward in order. Closing a pot writes one **expiry**
line dated the last day of the year that takes the whole remaining balance,
so a closed pot stands at exactly zero, and its note says what carried and
what expired ("year end close: 5.00 carried to 2027-04-01, 2.50 expired").
A zero balance still writes a zero line: that line is the mark that the
pot is closed.

- **Carried to the cap.** The part of the balance within the cap is written as
  a **carried in** line on the next year's pot (opened if need be). The cap is
  the policy's *carry over max weeks* times the contracted amount on the new
  year's first day, rounded; it uses the policy in force on that day. A blank
  carry cap means nothing carries. The seeded policies leave it blank:
  **set it before your first year end** or everyone's unused leave expires.
- **The rest expires**, in the same closing line.
- **Negative balances carry in full**, as a negative carry-in: leave taken
  beyond the allowance comes off next year's. The cap does not apply.
- **Entitlement is recalculated first**, so a contract change or leaving
  date recorded after the year ended still reaches the pot.
- **Leavers.** If the person has no employment or contract on the new year's
  first day, nothing carries: a positive balance expires (and the line says
  "leaver"). A **negative balance** is left untouched: it is a debt, listed
  in the nightly's output as `leaver_debts` ("… 3.00 owed") each night until
  someone settles it by adjustment, and the pot stays open until then. The
  same figure reaches payroll on the [Leavers sheet](payroll.md#the-sheets).
- **A pot that cannot be closed** (no policy for the next year, or the
  contract changed unit) is listed under `failed`, rolled back whole, and the
  rest still run. The message says what is missing. A change of unit needs the
  balance settled by adjustment, and the year end then closes it at zero.
- **Requests still waiting hold the close.** While a request of the pot's
  type starting in its year is still waiting for a decision, the pot is not
  closed: it is listed under `failed` ("… 1 request(s) waiting — decide them
  first") and closed the first night after the last one is approved,
  declined or cancelled. Decide requests that span 31 March promptly.
- **A closed pot takes no more lines.** Approving, cancelling or re-costing an
  absence whose pot has closed, a new request in a closed year, and
  *Recalculate entitlement* on a closed pot are all refused with a message
  saying so: the balance has already carried forward or expired, so a line
  there would be stranded. Put the difference right on the **current**
  year's pot instead ([reversing a line](#reversing-a-line)).

### Carry-in expiry

If the policy sets *carry over expires after days*, carried-in leave not
**booked by the deadline** (the year's first day plus that many days,
usable through that day) expires. "Booked" means *approved* by then,
whatever the date of the leave; a cancellation reverses its booking. Leave
is taken from the carried-in amount first. One line at most, noted
"carry-in expired", written the day after the deadline; never more than the
pot's balance, and a negative carry-in never expires.

### TOIL

A TOIL pot's positive balance carries forward **uncapped**, as each earned
line's unused remainder, written to the next pot as a TOIL earned line dated
the day it was originally earned, so its deadline runs on unchanged. Each
lot expires by its own policy days: *TOIL expires after days* from the day it
was earned (blank means never), the policy in force on the day it was earned.
The same "booked by the deadline" rule applies, first in first out, in the
order bookings were made. An earned line whose deadline has passed by the
new year expires at the close instead of carrying. One expiry line per
earned line at most, never more than the balance.

## Running it by hand

    deploy/manage absence_year_end
    deploy/manage absence_year_end --today 2027-04-02

It does the year-end step alone (close, then the two expiries) and prints
the counts: pots closed, carried and expired totals, carry-in and TOIL expiries,
leaver debts and failures. `--today` is a date in `YYYY-MM-DD`, for catching
up or checking; the default is the practice's today.

**The first run after deployment closes every historic pot** that has one.
If you are opening balances by hand (say from BreatheHR), run the year end
*first*, then enter the carry-overs, or the nightly will close the pots you
have just filled and write its own lines beside yours.

## Reversing a line

The ledger is immutable: a line is never edited or deleted, it is put right by
a new **adjustment** line. Each expiry looks for its own earlier line before
it writes, so once it has run it never writes the same one again, and a
reversal is not undone by the next night.

**There is no adjustment screen in the admin.** Pots and their lines are
read-only there; the one action, *Recalculate entitlement* on the Pot list,
only re-syncs the entitlement. Adjustments are written from the shell, as
you, and show in the ledger with your name:

    deploy/manage shell
    >>> from decimal import Decimal
    >>> from absence.models import LedgerEntry, Pot
    >>> from absence.services import ledger
    >>> from accounts.models import User
    >>> me = User.objects.get(email="you@example.org")
    >>> pot = Pot.objects.get(pk=123)          # the pk is in the ledger page's address
    >>> ledger.write(pot, LedgerEntry.Kind.ADJUSTMENT, Decimal("2.50"), me, note="restored: agreed with the partners")

Use a positive number to give leave back (reversing an expiry) and a negative
one to take it away (reversing a carry-in). A closed pot stays closed however
it is adjusted, so to give someone back leave that expired at year end,
adjust the **current** year's pot rather than the closed one. An adjustment
that adds TOIL is treated as a new TOIL lot dated the day it is written, so
it expires on its own days from then.

Hand-entered carry-overs are written the same way with `Kind.CARRY_IN`
(dated the pot's first day) on the year's pot, which `absence.services.pots.for_day`
opens if it does not exist yet.
