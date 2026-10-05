# Payroll changes report

A spreadsheet of what changed in a month, for the payroll bureau. HR admins
only. Open **Payroll** in the admin menu (or `/absence/payroll/`), enter a
month as `YYYY-MM` and generate: the file downloads and is kept.

On the server, `deploy/manage payroll_report --period 2026-06` does the
same and prints where the file went.

## The sheets

| Sheet | Holds |
|---|---|
| Starters | Employments that began in the month, with their contract on the first day and their bank details |
| Leavers | Employments that ended in the month, with the reason, and each leaver's balance in every allowance-backed leave type at the end of their last day (other ledger lines dated after it are left out; the entitlement, pro-rated for leaving, is always counted). A negative balance is leave taken beyond the allowance; a positive one is leave unused. Blank means no allowance was open then |
| Contract changes | Contracts that began or ended in the month, with their notes |
| Pay changes | [Pay records](people.md) that began in the month |
| Sickness | Dates within the month, and whether the absence was self-certified (seven calendar days or fewer); never the kind of sickness |
| Unpaid | Approved unpaid absences, with the units they cost. An absence that runs across a month end is split: each month shows only its own days and their cost |
| Family leave | The days within the month, expected and actual dates, and the keeping-in-touch days within the month |
| TOIL | TOIL earned and taken in the month. An approved [claim](absence.md#toil) is listed in the month it was **approved**, with the day worked beside it, so a claim approved after its month's report was made still reaches payroll, once. Other TOIL earned (from the shell) and TOIL taken are listed in the month of their date. TOIL carried forward at the year end is not listed again |

Columns, in order:

- **Starters:** Name, Start, Contract type, Weekly amount, Unit, Account name,
  Sort code, Account number (the starter's [bank details](people.md#bank-details),
  blank until entered).
- **Leavers:** Name, Last day, Reason, Unit, then one "*type* balance" column
  per allowance-backed type ([the rule](#the-leaver-balance-rule)).
- **Contract changes:** Name, From, To, Weekly amount, Unit, Basis, Notes.
- **Pay changes:** Name, From, Basis, Amount, Reason.
- **Sickness:** Name, From, To, Self-certified (Yes or No).
- **Unpaid:** Name, From, To, Units, Unit, Type.
- **Family leave:** Name, Type, From, To, Expected start, Actual start,
  Expected return, KIT days.
- **TOIL:** Name, Date (the approval date for a claim, otherwise the
  line's date), Units, Kind (earned or taken), Note, Day worked (earned
  TOIL), Approved (claims only).

Which absence goes on which sheet follows the type's settings, never its
name: an absence appears only if its type has **Payroll reportable** ticked;
then **Health sensitive** types are on Sickness, family-leave types on
Family leave, and any other type that is not **Paid** on Unpaid. The TOIL
sheet lists the ledger lines of allowance-backed types that are both Paid
and Payroll reportable. A type you add yourself follows the same rules, so
set those boxes deliberately.

## Months that an absence spans

An absence that runs across a month end is **clipped to the month**: each
month's file shows only its own days (first and last day are the clipped
ones, KIT days only those inside), so consecutive months never report the
same day twice. On the Unpaid sheet the units are costed for the days inside
the month only, by the same rules as booking (working pattern, half days,
closed days and bank holidays skipped).

Each month is **rounded on its own**, to the policy's step (0.25 if the type
has no policy), so the months of a spanning absence can add up to slightly
more or less than the whole absence's cost shown elsewhere. Payroll should
work from the monthly figures. Automatic bank-holiday rows are never listed:
payroll pays bank holidays as part of the month.

## The leaver balance rule

On the Leavers sheet each allowance-backed type has a column, "balance at the
end of the last day". It is the pot current on the leaver's last day: its
ledger lines **dated on or before that day**, plus its entitlement lines
whatever their date. The second part matters because a leaver's entitlement is
pro-rated by a revision line written when the end date is recorded, which can
be after the last day. Lines dated later (a booking for after they left) are
left out. A negative figure is leave taken beyond the allowance (a debt the
[year end](year-end.md#what-the-nightly-does) also reports); a positive one is
leave unused. **Blank means no pot was open** that day: never opened, or no
contract or policy to open one from.

## Files and runs

Each month's file is `payroll/YYYY-MM.xlsx` under `MEDIA_ROOT`
(`/var/lib/practice-hr/media` in production, see the README) and is
included in the nightly backup. Generating a month again rebuilds it from
the current data and **replaces** that file; every generation is recorded
as a run on the Payroll page and in the [audit log](people.md#audit-log),
with who ran it, when, and how many rows each sheet held.
