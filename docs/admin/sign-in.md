# Login accounts and signing in

**Where:** sidebar › Login accounts (a Django auth account, not an Employee
— see [Employee](people.md#employee)); `/etc/practice-hr.env` for the OIDC
provider's own key.

## Login accounts

`/admin/accounts/user/` — who can sign in, and how. A login account is
separate from an Employee; the Employee's [User](people.md#user) field links
the two, and is optional — someone can exist as an Employee with no login,
or (a superuser created by `createsuperuser`) have a login with no Employee
record at all.

### Adding someone

**Add login account** asks for two things: their email, and whether they
are an [HR admin](#admin-status). There is no password to type. Saving
sends an **invitation** — an email with a link to choose their own password
— and opens their page, which reads *Invited 4 Sep, link expires 11 Sep*
until they use it, then *Set up — last link sent 4 Sep 14:02*. A link lasts
seven days and works once; using it signs them straight in.

If outgoing email is not set up, or the relay refuses, the admin is shown
the link once instead, to copy into an email by hand. Nobody — not even an
HR admin — ever sees anyone's password.

### The State field and the send button

Every account's page carries a **State** and one button in the save row,
chosen by it:

- **Send invitation again** while they have no password yet — for a link
  that expired or never arrived.
- **Send password-reset link** once they have one — for someone who has
  forgotten it. They can also do this themselves with *Forgotten your
  password?* on the login page.

Pressing either saves the page and sends. To invite a whole practice at
once, tick several accounts on the list and choose **Send invitation or
reset link**; each gets whichever it needs.

### Admin status

Tick **Admin status** (`is_hr_admin`) on anyone who should use this admin,
decide any request, and see restricted records — [NI numbers](people.md#ni-number)
and [pay records](people.md#pay-record). There is no separate staff flag to
set: Django's `is_staff` follows admin status automatically.

An HR admin cannot see a **superuser's** account in the list, open it, or
grant superuser to anyone. Only a superuser sees the System fieldset
(Active, Superuser status), and only a superuser can reach the direct
set-password form — by URL alone, an emergency tool nothing links to.

### Deactivating

Untick **Active**. An inactive account cannot sign in by password or
passkey, its links are refused, and its history stays. Only a superuser can
delete a login outright.

`hr_nightly` (see [below](#nightly-housekeeping)) does this automatically
for anyone whose employment has ended.

### Passkeys

A person adds passkeys to their own account from **Account** (in the menu
under their name): their phone's Face ID or fingerprint, a laptop's Windows
Hello or Touch ID, or a password manager. That page lists each passkey with
when it was added and last used, and lets them remove one. Their password
still works, and is how they get back in if a device is lost.

Adding a passkey asks for the password again unless they signed in within
the last ten minutes, and the owner is emailed each time one is added — so
someone who finds a computer left signed in cannot quietly add one of their
own. A passkey keeps working after a password change; the password-reset
form can remove all of an account's passkeys at once, for the case where
one appears that the owner did not add.

You cannot add a passkey for someone — only the device that holds the key
can — but an HR admin can revoke one: open their login account, and under
**Passkeys** each row shows its name, the authenticator's id, and when it
was added and last used; delete the lost device's row and save.

**Passkeys are bound to the site's address** (`ALLOWED_HOSTS`, the tunnel's
hostname). Moving the app to a different domain invalidates every passkey —
everyone signs in with their password and enrols again.

### Signing in and lockouts

People sign in with their email and password, or with a passkey. The email
is matched case-insensitively — "Tom.Hodges@…" and "tom.hodges@…" are the
same account, and the add form refuses a second account differing from an
existing one only by case. Five wrong passwords within an hour lock that
email out of password sign-in for an hour; an address is locked too once
five *different* emails have failures outstanding from it, which is the
spraying pattern rather than one person's fumbles. A passkey still signs in
during a lockout, since it proves possession of the device.

## Nightly housekeeping

`hr_nightly` (`deploy/hr-nightly.timer`, 01:30 daily) disables the login of
anyone whose employment has ended and who has no employment spell starting
on or after today — a leaver with no returning spell already on the books.
It is idempotent: running it twice in a night, or against someone already
disabled, does nothing extra. It never re-enables anyone — a returner's
login is turned back on by hand, from their account page, once their new
Employment spell is added.

## The OpenID Connect provider

This system is an OpenID Connect **provider** for the practice's other
apps — currently the rota. Once a relying party (an app like the rota) is
registered, that app's own login page can offer "sign in with the practice
account": a person authenticates here, and the relying party trusts the
`email` and `employee_id` claims this system returns (`accounts/oidc.py`).
With no `OIDC_RSA_PRIVATE_KEY` set, the provider is switched off entirely —
`/o/` answers 404 and nothing about ordinary sign-in changes.

### OIDC_RSA_PRIVATE_KEY

The one environment variable the provider needs, in `/etc/practice-hr.env`
(see the README's Deploy section for the file's format). It signs every ID
token this system issues, so it must be set before any relying party is
registered, and never changed once one is — rotating it invalidates every
relying party's ability to verify a token it already trusted, until they
are told the key changed.

Generate it with:

    openssl genrsa 2048

and put it in the environment file **as one line**, with the PEM's actual
newlines written as the two characters `\n` — `config/settings.py` reverses
that (`.replace("\\n", "\n")`) before handing the key to the OIDC library.
A key pasted in with real newlines is not one line and breaks the
environment file's format; a key with the `\n` step skipped is read as a
single unparseable line instead of a valid PEM key, and the provider fails
to start.

### Registering a relying party

Run on this box, as the one place that holds this system's own database:

    register_oidc_client --name rota --redirect-uri https://rota.example.org/oidc/callback/

`--name` identifies the relying party for future runs — using the same name
again updates its redirect URI instead of registering a second client.
`--redirect-uri` is the exact URL the relying party will be sent back to
after authenticating; it must match what that app is configured to expect.

The command prints a `client_id` and a `client_secret` **once** — the
secret is stored hashed here and cannot be shown again. Paste both into the
relying party's own environment file. If the secret is lost, or needs
rotating (a suspected leak, a routine rotation), run the command again with
the same `--name` and add `--rotate`:

    register_oidc_client --name rota --redirect-uri https://rota.example.org/oidc/callback/ --rotate

Without `--rotate`, re-running the command for an existing name only
updates the redirect URI and leaves the secret as it is — the message says
so. With it, a new secret is printed and the old one stops working
immediately, so the relying party's environment file must be updated before
its next sign-in.

### What a relying party gets

The `openid` and `email` scopes only: an ID token carrying `email` and
`employee_id`. Consent is skipped (`skip_authorization=True` on every
registration) — a relying party is a practice app the practice itself
operates, not a third party a person needs to approve access for each
time. PKCE is required on every authorization, and tokens are signed RS256
and expire after ten minutes.
