# The read API for the rota

Three read-only JSON endpoints under `/api/v1/` that the rota polls for
people, working patterns and absences. Nothing here is written to, and
nothing is pushed: the rota asks. Sign-in for the rota's users is separate
(the [OpenID Connect provider](sign-in.md#the-openid-connect-provider)).

## The token

Every request needs `Authorization: Bearer <token>` (the word `Bearer` in
any case), where the token is one of **`HR_API_TOKENS`**: a comma-separated
list in `/etc/practice-hr.env`. Give each client its own so one can be
retired alone. Generate a token with

    openssl rand -hex 32

then

    HR_API_TOKENS=<token for the rota>

(`<first>,<second>` for more than one), and restart the service. Tokens are
compared in constant time and never logged. With none set, **every request
is refused with 401**, and `check --deploy` warns (`hr.W001`). To rotate,
add the new token beside the old, change the rota, then remove the old one.

A missing or wrong token is `401 {"error": "unauthorised"}` with
`WWW-Authenticate: Bearer`; with a valid token, anything but GET is `405`; a bad query string is
`400 {"error": "<what is wrong>"}`. Every response is
`Cache-Control: no-store` (it is people's names and when they are away).
Dates are ISO (`YYYY-MM-DD`).

## Matching people: `id`, not `email`

The rota should match people by the **`id`** field, which is the employee
record's id. It is the same value the sign-in provider sends as the
`employee_id` claim, and the `employee` field of `/absences` refers to it.
The **`email`** in `/people` is the employee record's **work email**
(*People › Employees › Work email*), which is unique across employees whatever its
case. It is **not** the sign-in account's email, which is what the rota
receives when someone signs in; the two can differ, so do not join on email.
See [Work email](people.md#work-email).

## `GET /api/v1/people`

Everyone with an employment, past leavers included: today's employment if
there is one, otherwise the latest.

    {"people": [{
        "id": 12,
        "first_name": "Sam", "last_name": "Patel", "name": "Sam Patel",
        "email": "sam@practice.example",
        "contract_type": "Reception" | null,
        "unit": "hours" | "sessions" | null,
        "employment": {"start": "2026-04-01", "end": null},
        "positions": [{"title": "Receptionist", "team": "Reception"}]
    }]}

`contract_type` and `unit` are those of today's first contract (null if
none); `positions` are today's.

## `GET /api/v1/patterns?employee=<id>`

    {"patterns": [{
        "effective_from": "2026-04-01",
        "days": [{"weekday": 0, "am": "3.75", "pm": "3.75"}]
    }]}

Oldest first; each holds from its date. Weekday 0 is Monday. `am` and `pm`
are units in the contract's unit, as strings. Patterns of every employment
the person has had are included, so a rehire's earlier spell is there too.
A missing or unknown `employee` is a 400.

## `GET /api/v1/absences?from=YYYY-MM-DD&to=YYYY-MM-DD`

    {"absences": [{
        "id": 7, "employee": 12,
        "type": "AL", "label": "Leave",
        "status": "approved" | "requested",
        "start": "2026-05-25", "end": "2026-06-12",
        "start_half": "" | "PM", "end_half": "" | "AM",
        "partial": null | {"start_time": "09:00", "end_time": "11:00", "hours": "2.00"}
    }]}

Every **approved or requested** absence that overlaps the window (`from` and
`to` inclusive), including one that starts before `from` or ends after
`to`. Not returned: declined and cancelled absences, and the automatic
bank-holiday rows (the rota has its own bank-holiday calendar). `label` is
the type's [calendar label](absence.md#calendar-label), except that a
[health-sensitive](absence.md#health-sensitive) type is always `"Sick"`.
**No field carries the illness category**, and the type's name is never
sent. `employee` is the `id` from `/people`.
