# Payroll changes report

A spreadsheet of what changed in a month, for the payroll bureau. HR admins
only. Open **Payroll** in the admin menu (or `/absence/payroll/`), enter a
month as `YYYY-MM` and generate: the file downloads and is kept.

On the server, `deploy/manage payroll_report --period 2026-06` does the
same and prints where the file went.

## The sheets

| Sheet | Holds |
|---|---|
| Starters | Employments that began in the month, with their contract on the first day |
| Leavers | Employments that ended in the month, with the reason, and each leaver's balance in every allowance-backed leave type on their last day. A negative balance is leave taken beyond the allowance; a positive one is leave unused. Blank means no allowance was open then |
| Contract changes | Contracts that began or ended in the month, with their notes |
| Pay changes | [Pay records](people.md) that began in the month |
| Sickness | Dates only, never the kind of sickness |
| Unpaid | Approved unpaid absences, with the units they cost |
| Family leave | Expected and actual dates and the number of keeping-in-touch days |
| TOIL | TOIL earned and taken in the month |

Which absence goes on which sheet follows the type's settings, never its
name: an absence appears only if its type has **Payroll reportable** ticked;
then **Health sensitive** types are on Sickness, family-leave types on
Family leave, and any other type that is not **Paid** on Unpaid. The TOIL
sheet lists the ledger lines of allowance-backed types that are both Paid
and Payroll reportable. A type you add yourself follows the same rules, so
set those boxes deliberately.

## Files and runs

Each month's file is `payroll/YYYY-MM.xlsx` under `MEDIA_ROOT`
(`/var/lib/practice-hr/media` in production, see the README) and is
included in the nightly backup. Generating a month again rebuilds it from
the current data and **replaces** that file; every generation is recorded
as a run on the Payroll page and in the [audit log](people.md#audit-log),
with who ran it, when, and how many rows each sheet held.
