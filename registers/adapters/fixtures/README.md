# Register page fixtures

The parsers in `registers/adapters/` are tested against saved copies of
real result pages kept here, one folder per body: `gmc/`, `mpl_wales/`,
`nmc/`, `gphc/`. A body is **verified** (and its scheduled checks run, and
its lookups record checks) only when its folder holds `clear.html`,
`not_found.html` and at least one problem page (`problem*.html`, such as
`problem.html` or `problem-suspended.html`): the problem path is the one
that matters. The build sandbox cannot reach the regulators' sites, so a
person captures them.

## How to capture a page

1. On a machine that can reach the site, with this app checked out, pick
   a real number you know the answer for (your own, or a colleague's with
   their agreement).
2. Fetch the page exactly as a lookup does, with the app's own address,
   user agent, timeout and size limit:

   ```
   DEBUG=1 .venv/bin/python manage.py registers_fetch gmc 1234567 registers/adapters/fixtures/gmc/clear.html
   ```

   It checks the number's format, saves the reply to the file you name and
   prints only the HTTP status and the size. The same with curl, if the app
   cannot run there: `curl -A "<user agent>" "<url>"`, saving its output as
   the file, where the user agent is the one the app sends
   (`PracticeHR/1.0 (+<SITE_URL>; registration checks)`) and the URL is the
   body's search URL with the number (the `PUBLIC` address in the body's
   adapter file). Do not save the page from a browser: what a browser
   shows after its scripts run is not what the app reads.
3. Name the file for the outcome the page shows: `clear.html`,
   `problem.html` (any lapsed, suspended, conditions, erased, no-licence
   or not-on-the-GP-register page; several may be saved as
   `problem-suspended.html`, `problem-conditions.html` and so on),
   `not_found.html` (a number that does not exist), and optionally
   `unreadable.html` (a page that is not a result at all, such as an
   error page).
4. Beside each `clear` or `problem` page put a `<stem>.surname` file holding
   the surname the page shows, e.g. `clear.surname` containing `Patel`, so
   the name check is tested too. If the number the page was captured for
   matters to the parser (the Welsh list picks its row by number), put it
   in a `<stem>.number` file the same way, e.g. `clear.number`.
5. Trim nothing by hand: the page must be what the app fetches.
6. Run the parser on it:

   ```
   DEBUG=1 .venv/bin/python manage.py registers_parse gmc registers/adapters/fixtures/gmc/clear.html --surname Patel
   ```

   `--surname` is the surname on the person's record and is required; add
   `--number 1234567` for the Welsh list. It runs the page through the
   same steps as a lookup (the name check included) and prints what the
   lookup would record: the outcome, the status words, the name it found
   and whether the surname matches. If the
   outcome is wrong, the body's adapter needs the page's actual words.
   Each adapter reads a status only from a labelled field, so adjust these
   in that body's file, one at a time:

   - `LABELS`: the field names the status sits under (for example
     "Registration status" or "Status").
   - `RESTRICTION_LABELS`: the fields that hold a restriction, condition or
     sanction; a value in one other than none turns a clear result into a
     problem. List the singular and the plural label (`Warning` and
     `Warnings`) when the page might use either.
   - `NOT_FOUND`: the wording of a page for a number that does not exist.
     It is consulted only when the page has no status field.
   - `CLEAR`: the status values that are clear. A value is clear only when,
     ignoring case, spaces and punctuation, it is exactly one of these; a
     value with anything more ("Registered - suspension pending") is not.
   - `PROBLEM`: the body's own problem wordings, matched on whole words. A
     value is also a problem when it contains any of the shared stems in
     `PROBLEM_STEMS` (`registers/adapters/base.py`: suspen, restrict,
     condition, interim, lapse, ...); any other value is unreadable. The
     GMC's GP Register field is read against `GP_REGISTER_CLEAR` the same
     way.
   - `NAME_MARKER`: the pattern for the label of the number (for example
     "GMC number", "PIN", "Registration number"). The name is read from the
     line just before it and must look like a name.

   The Welsh list (`mpl_wales`) has no `LABELS`, `RESTRICTION_LABELS` or
   `NAME_MARKER`: it finds the row by the number, and expects the number,
   the name and the status on consecutive lines. It is tuned by `CLEAR`,
   `PROBLEM`, `NOT_FOUND` and that row layout.

   Keep the tests in `tests/test_registers_adapters.py` passing, and run the
   parser again.
7. Run the suite: `.venv/bin/python -m pytest -q tests/test_registers_adapters.py`.
   The captured pages are picked up automatically and must parse as their
   file names say, with the surname and number from the sidecars.
8. Commit the pages. The next nightly run marks the body verified.

Pages contain a real person's name and registration number, which are
public on the register; nothing else personal should be in them. Do not
capture a page for anyone who has not agreed.
