# Login accounts and signing in

**Where:** sidebar › Login accounts (a Django auth account, not an Employee
— see [Employee](people.md#employee)); `/etc/practice-hr.env` for the OIDC
provider's own key, and `/etc/practice-hr/oidc.pem` for the key itself.

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
delete a login outright, and not even a superuser can delete one that has
written to the [audit log](people.md#audit-log). Deleting one would also
take Django's record of any admin changes that person made.

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
existing one only by case. In a browser that has never used a passkey here,
the first pages after signing in carry a card offering to add one, until
they do or press *Not now*, which puts it away for thirty days in that
browser.

Five wrong passwords within an hour lock that email out of password
sign-in for an hour, wherever they come from. An address is locked too,
once five *different* emails have wrong passwords outstanding from it —
the pattern of someone trying many accounts, rather than one person's
fumbles. The practice's shared connection is safe: one colleague's fumbles
count once there, and each person's own successful login clears their own
count, and nobody else's (`accounts/axes_handler.py`).

The hour runs from the lockout. Trying again while locked doesn't restart
it, so nobody can keep a colleague out by retrying. The locked-out page
offers the two ways in that still work: a passkey still signs in during a
lockout, since it proves possession of the device (a forged assertion for a
registered passkey counts like a wrong password), and a password link by
email still works — setting a new password signs them in.

Superusers can see the record under the **System** group:
- **Access failures** is the log of failed attempts, kept to the last
  thousand per email.
- **Access attempts** is the live counter. It is cleared for an email when
  that person next signs in.
- **Access logs** records successful sign-ins.

Signed-in pages are sent with `Cache-Control: no-store`, and signing out
sends `Clear-Site-Data: "cache"`, so the next person at a shared PC cannot
page back through the last one's record.

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
`email`, `employee_id` and `admin` claims this system returns
(`accounts/oidc.py`).
With no signing key set (`OIDC_RSA_PRIVATE_KEY_FILE`, below), the provider
is switched off entirely —
`/o/` answers 404 and nothing about ordinary sign-in changes.

### OIDC_RSA_PRIVATE_KEY_FILE

The one setting the provider needs, in `/etc/practice-hr.env`: the path of
a file holding the key that signs every ID token this system issues —
`/etc/practice-hr/oidc.pem`, readable only by root and the `practice-hr`
group (the README's Deploy section has the commands). It must be set before
any relying party is registered, and never changed once one is — rotating
it invalidates every relying party's ability to verify a token it already
trusted, until they are told the key changed.

Generate it with `openssl genrsa 2048` straight into the file, as it is,
then `chmod 640` it: `openssl` writes a private key readable by its owner
alone whatever the umask, and the app reads it as the `practice-hr` user.
The key does **not** go in the environment file itself: systemd's
environment-file parser turns an unquoted `\n` into a plain `n`, so a PEM
key folded onto one line with `\n` for its newlines arrives broken. (That
one-line form, `OIDC_RSA_PRIVATE_KEY`, is still read on a dev box when no
file is named.)

If the file is named but cannot be read, the app refuses to start and says
why. `deploy/manage check --deploy` fails with `hr.E001` if the provider is
on and its key is not a PEM RSA private key.

### Registering a relying party

Run on this box, as the one place that holds this system's own database,
through `deploy/manage` (see the README's Deploy section for why every
`manage.py` command goes through it rather than being run directly):

    deploy/manage register_oidc_client --name rota --redirect-uri https://rota.example.org/oidc/callback/

`--name` identifies the relying party for future runs — using the same name
again updates its redirect URIs instead of registering a second client (and
refuses, saying so, if two clients of that name exist).
`--redirect-uri` is the exact URL the relying party will be sent back to
after authenticating; it must match what that app is configured to expect,
and in production it must be `https`.
`--post-logout-redirect-uri` is where the relying party's sign-out lands
after signing the person out here too; left out, it is the redirect URI's
origin plus `/accounts/login/` — the rota's login page. Every run also puts
the client's fixed settings back (confidential, authorization-code, RS256,
consent skipped) in case they were edited by hand.

The command prints a `client_id` and a `client_secret` **once** — the
secret is stored hashed here and cannot be shown again. Paste both into the
relying party's own environment file. If the secret is lost, or needs
rotating (a suspected leak, a routine rotation), run the command again with
the same `--name` and add `--rotate`:

    deploy/manage register_oidc_client --name rota --redirect-uri https://rota.example.org/oidc/callback/ --rotate

Without `--rotate`, re-running the command for an existing name only
updates the redirect URIs and leaves the secret as it is — the message says
so. With it, a new secret is printed and the old one stops working
immediately, so the relying party's environment file must be updated before
its next sign-in.

### What a relying party gets

The `openid` and `email` scopes only: an ID token, and the userinfo
endpoint, carrying three claims about the person:

- `email` — their login account's email.
- `employee_id` — the Employee their login is linked to, or `null` with none.
- `admin` — `true` if they are an admin of the app asking, `false`
  otherwise. Each app gets its own answer.

Who is an admin of which app is set on their login account's page, under
**Apps**: one box per registered relying party, **Admin of rota** and so
on, in name order. Tick it and save to make them an admin there; untick it
to take that away. The rota reads the claim at each sign-in, so a change
reaches it the next time that person signs in to it. Being an admin of an
app is all **Apps** controls: anyone with an active login here can sign in
to every registered app. The section is not on the add page (save the new
account first), and is left out while no relying party is registered. The
list of login accounts has an **Apps** column reading like "rota (admin)",
"rota", or blank, so the admins are visible at a glance. An HR admin can
set it on anyone's account but a superuser's, as everything else there.

Consent is skipped (`skip_authorization=True` on every
registration) — a relying party is a practice app the practice itself
operates, not a third party a person needs to approve access for each
time. PKCE is required on every authorization, and ID and access tokens
are signed RS256 and expire after ten minutes. A refresh token is issued
alongside them (the rota does not use it); it changes on every use, a
replayed one revokes the whole family, and it stops working as soon as the
login is made inactive. Only the authorization-code flow works: the
implicit and password grants are refused even for a client registered for
them, and nothing but `register_oidc_client` can register a client — the
provider's own client-management pages are not mounted.

Because consent is skipped, a session here is a session in the rota. So a
session here ends when the browser closes, and after twelve hours at most;
and signing out of the rota signs the person out here too (the rota sends
them to this system's `/o/logout/`, which returns them to the rota's login
page). On a shared surgery PC, the next person to press *Sign in with the
practice account* is asked who they are rather than signed in as the last.

## Migrating logins from the rota

Before the rota signed everyone in through this system, it had its own
passwords and its own admins. `import_logins` moves them here, once, so
nobody has to choose a new password and the rota's admins stay admins.
Register the rota first ([above](#registering-a-relying-party)), then, in
this order:

1. On the rota's box, write its logins to a file (the rota's own sign-in
   guide has the details):

       deploy/manage export_logins --file /var/lib/rota/logins.json

2. Copy the file to this box as `/var/lib/practice-hr/rota-logins.json`
   (`cp` instead of `scp` if both apps run on one box; `hr` here is this
   box's name):

       scp /var/lib/rota/logins.json hr:/var/lib/practice-hr/rota-logins.json

   `deploy/manage` runs commands as the `practice-hr` user, which can read
   that directory and nobody else can. Make the file that user's alone:

       chown practice-hr:practice-hr /var/lib/practice-hr/rota-logins.json
       chmod 600 /var/lib/practice-hr/rota-logins.json

3. Import it here. `--dry-run` first prints the same counts and writes
   nothing; then run it for real:

       deploy/manage import_logins --file /var/lib/practice-hr/rota-logins.json --app rota --dry-run
       deploy/manage import_logins --file /var/lib/practice-hr/rota-logins.json --app rota

4. Delete the file on both boxes. It holds every rota login's password hash.

`--app` names the registered relying party whose admins the file
describes; it defaults to `rota`, and the command stops if no relying party
of that name is registered. It also stops, before writing anything, on a
file that is not a rota export; a password that is not a password hash is
one of the things it refuses. One bad login stops the whole import, so
nothing is half-done. It never prints a password or a hash.

It prints one count per line:

- **created** — logins that did not exist here and do now, with the rota's
  email, active or not as they were in the rota. No invitation is sent.
- **passwords_set** — logins here with no password yet (just created, or
  invited and never set up) that now have their rota password. They sign
  in here with it: both apps store a password as the same kind of hash, so
  the hash moves and the password itself is never seen. That includes an
  HR admin's login that was invited but never set up: their rota password
  now opens this admin too, and with it pay and health records. It is the
  same person, but worth knowing before you run it.
- **password_kept** — logins that already had a password here. It is kept,
  and the rota's is ignored.
- **linked** — employee records whose work email matched (whatever its
  case) and that had no login yet, now linked to this one.
- **admins** — logins that are admins of the rota, from its own flag.
  Every login gets its **Apps** row; this counts those ticked.

Then it lists, by email, anyone with **no matching employee** (no Employee
has that work email: link them by hand, from the Employee's
[User](people.md#user) field, if they should have one), and anyone whose
**employee is already linked to another login** (it is left alone: check
which login is right).

A login whose rota account had no password (a passkey only, or never set
up) has none here either: send it an invitation from its page. A login that
already existed here keeps its own Active setting. The rota's superuser
flag is not read: superusers here are made with `createsuperuser`. Running
the import again changes nothing for passwords, but it puts the rota's
admin flags back over any **Apps** change made here since; so run it once.
