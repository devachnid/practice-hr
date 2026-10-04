# HR-only sign-in: app roles on the HR login, rota passwords migrated, rota password form retired

Approved design (conversation, 4 Oct 2026). Spec: `docs/superpowers/specs/2026-09-27-practice-hr-foundation-and-absence-design.md` §3 (roles, access and sign-in) and §7; this plan extends it for spec 2's sign-in part.

Two tasks, one per repository: Task 1 in `practice-hr` (this checkout, branch `feature/app-roles-signin`), Task 2 in the rota at `/home/user/rota` (branch `claude/keen-fermat-c5fsc4`, reset onto `origin/master` 5e6d999). Task 2 consumes Task 1's claim and file format, so Task 1 goes first.

## Global Constraints

- Services and management commands are the only writers of application data; views, admin and backends call them or Django's own user APIs. No view writes on GET.
- Nothing in either repository ever logs, prints or stores a plaintext password. Password hashes travel only in the export file, which is written mode 0600 and documented as something to delete after import.
- Tests make no network calls and do not expire with the calendar.
- No PII and no secrets in any file; settings only from the environment. No model identifier in code, comments, docs, migrations or commit messages.
- Ruff clean, `makemigrations --check` clean, full suite green in each repository (practice-hr: 899 at main 8b1e590; rota: 1803 collected at 5e6d999).
- Every commit message ends with exactly these two trailer lines:
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_01PkKQLdYCQnRZiVssdedFig`
- The rota's commit subjects follow its convention (`feat(auth): …`, `fix(auth): …`, `docs: …`).
- Docs: every behaviour change an operator or HR admin meets gets its sentence in `docs/admin/*.md` of the repository it belongs to; the HR user guide (`docs/guides/hr-administrator.md`) gets the one task HR admins will do (set someone as a rota admin). `tests/test_docs.py` pins wording in both repositories, so run it.
- Both repositories use Django's default password hashers (neither sets `PASSWORD_HASHERS`), so a hash string moves between them unchanged.

---

## Task 1: practice-hr — app roles on the login, the `admin` claim, the login import

**1a. Model.** `accounts/models.py`: `AppRole` with `user` (FK `User`, CASCADE, related_name `app_roles`), `application` (FK `oauth2_provider.Application`, CASCADE, related_name `roles`), `is_admin` (Boolean, default False), unique together `(user, application)`, `verbose_name = "app role"`. Migration `accounts/00NN_approle.py` (next number after the latest). `__str__`: `"<email> on <application name>: admin"` or `"… : user"`.

**1b. Admin.** On the Login accounts change page (`accounts/admin.py`, `UserChangeForm` + `get_fieldsets`), a fieldset **Apps** after **HR admin** with one checkbox per registered client (`Application.objects.filter(user__isnull=True).order_by("name")`, the rows `register_oidc_client` makes), labelled **Admin of <application name>** with help text "Whether this login is an admin of that app. Access to the app itself needs only an active login here." The form adds the fields dynamically (`app_admin_<application pk>`), initial from the existing `AppRole` rows, and `save_model`/`form.save` writes them: a ticked box gets or creates the row with `is_admin=True`, an unticked one updates an existing row to `False` (no row is created for an unticked box). Not shown on the add page. With no registered client the fieldset is omitted. HR admins and superusers can edit it under the page's existing permission guards (an HR admin never reaches a superuser's page). Also `list_display` gains a column `apps` reading like "rota (admin)" / "rota" / "" so admins are visible on the changelist.

**1c. Claim.** `accounts/oidc.py:Validator.get_additional_claims(request)` adds `"admin": <bool>`: True when an `AppRole` row exists for `request.user` and `request.client` with `is_admin=True`, else False. `request.client` is the requesting `Application` on both the ID-token and the userinfo paths; verify it is set on both by extending the existing code-flow test (`tests/test_oidc_provider.py::test_the_code_flow_gives_exactly_sub_email_and_employee_id`, which asserts the exact claim set) to include `admin`, both for a login with the role and one without, and the userinfo endpoint too if that test does not already read it. Unit tests for `get_additional_claims` with and without a role. The docstring at the top of `accounts/oidc.py` lists what leaves the system: add the claim.

**1d. Import command.** `accounts/management/commands/import_logins.py`: `import_logins --file PATH [--app NAME, default "rota"] [--dry-run]`. The file is JSON: `{"exported_at": "<iso>", "logins": [{"email": "...", "password": "<django hash or !unusable>", "is_active": true, "is_rota_admin": false, "is_superuser": false}]}` (the rota's `export_logins` in Task 2 writes exactly this). For each login, in one transaction (rolled back under `--dry-run`):
  - match the HR `User` by email, case-insensitively; none → create it with that email, `is_active` from the file, no usable password (counted `created`);
  - if the HR user has no usable password and the file's hash is usable (does not start with `!`), set `user.password` to the hash as it is, never re-hashed (counted `passwords_set`); a user who already has a usable password is left alone (counted `password_kept`);
  - link the `Employee` whose `work_email` matches case-insensitively and has no `user` yet (counted `linked`); an employee already linked to another login is reported, not changed;
  - set the `AppRole` for the application named by `--app` (must exist, ownerless; otherwise `CommandError`) to `is_admin = is_rota_admin` (get or create; counted `admins`);
  - `is_superuser` in the file is ignored (HR superusers are made with `createsuperuser`).
  It prints one line per count and lists the emails with no matching employee and the emails whose employee was already linked elsewhere. It never prints a hash. Refuses a file that is not the documented shape with a clear `CommandError`. Tests in `tests/test_import_logins.py`: creates and links; sets a password only where none is set and the imported hash then checks (`check_password` against a known hash made with `make_password` in the test); keeps an existing password; sets and clears the admin role; dry run writes nothing; unknown app refused; malformed file refused; nothing printed contains a hash (assert on `capsys`).

**1e. Docs.** `docs/admin/sign-in.md`: the claims section lists `admin` and explains the Apps fieldset; a new section "Migrating logins from the rota" with the two commands in order (rota `export_logins` → copy the file → HR `deploy/manage import_logins --file … --app rota` → delete the file) and what each count means. README: one line in the commands list. `docs/guides/hr-administrator.md` under "Logins, passkeys and lockouts": "How to make someone an admin of the rota" (Admin › Access › Login accounts, open the person, under **Apps** tick **Admin of rota**, **Save**; it takes effect at their next sign-in to the rota).

---

## Task 2: rota — `export_logins`, sign-in through HR only, admin from the claim

Branch `claude/keen-fermat-c5fsc4` at `/home/user/rota`, reset onto `origin/master` 5e6d999. Run from that directory with its own `.venv`.

**2a. Export command.** `accounts/management/commands/export_logins.py`: `export_logins --file PATH` writes the JSON of Task 1d for every `User` (active and inactive, superusers included, flagged), `password` as stored (`!…` for unusable), created with mode 0600 (`os.open` with `O_CREAT|O_EXCL|O_WRONLY`, 0o600; refuse to overwrite), and prints only the count written and the path. Test: file shape, mode, refusal to overwrite, no hash on stdout.

**2b. Sign-in through HR only.** With `settings.PRACTICE_HR_URL` set:
  - `templates/registration/login.html` shows the **Sign in with the practice account** button only: no password form, no "Rota password (superusers only)" details, no forgotten-password link, no passkey button. Without the setting the page is exactly as before.
  - `accounts/views.py`: `_password_accounts()` returns no accounts when configured; `LoginForm.clean` refuses every password sign-in with the message `"Sign in with the practice account."` (constant `PRACTICE_ACCOUNT_ONLY`, reworded) before `authenticate` runs, so nothing is counted towards a lockout; the password-reset request form sends nobody a link; a reset or invitation link for anyone opens the "link no longer valid" page; `accounts/recent_auth.py:password_allowed` is False for everyone.
  - Passkeys retired when configured: `passkey_login_options`/`passkey_login` answer 404; `passkey_register_options`/`passkey_register` answer 404; the account page replaces the Passkeys section and the Change password button with one sentence: "You sign in with the practice account. Passwords and passkeys are managed on the HR system." linking to `PRACTICE_HR_URL + "/accounts/account/"`. Existing `Passkey` rows are left in place (they work again if the setting is removed).
  - Superusers sign in through HR like everyone else: `accounts/oidc.py:PracticeAccountBackend` drops the `.exclude(is_superuser=True)` and the module docstring's superuser bullet. `is_superuser` stays a local flag (feedback emails, sign-in logs in the admin), set only in the rota admin by a superuser.
  - The admin's Login accounts page: `is_rota_admin` is read-only when configured, with the help text "Set on the HR system: Login accounts › Apps › Admin of rota. It is updated at each sign-in." (`accounts/admin.py` `get_readonly_fields`, and the add form drops the field when configured).

**2c. Admin from the claim.** `PracticeAccountBackend.create_user` and `update_user` set `user.is_rota_admin = bool(claims.get("admin"))` on every sign-in (saved only when it changed, with `oidc_sub` as now). A claim missing entirely (an older HR) reads as False.

**2d. Break-glass.** `docs/admin/sign-in.md`: rewrite "The rota's password form is for the superuser" as "There is no rota password while the practice account is on", and add "If the HR system is unreachable": remove `PRACTICE_HR_URL` from `/etc/rota.env` and restart the rota; the local password form and passkeys return for accounts that still have them (the superuser's, and anyone whose password was never cleared); put the line back once HR is up. Also the sign-in doc's first-sign-in section: `admin` claim sets rota admin; superusers included. `docs/admin/people.md` Login accounts: rota admin is set on the HR system when the practice account is on. README's deploy/sign-in paragraph if it mentions the superuser form.

**2e. Tests.** Update `tests/test_oidc_signin.py` (and any login/passkey/reset tests) for the new rules: the login page with and without the setting; password sign-in refused for the superuser too with no axes row; reset link sends nobody; passkey endpoints 404; account page sentence; backend signs in a superuser; `is_rota_admin` follows the claim both ways and survives a missing claim as False; export command tests from 2a. Keep the existing "five staff typing right passwords leave no axes rows" regression.

---

## Execution notes

Executed as two subagent-driven tasks run in parallel, one per repository, each with a full review and one fix wave: practice-hr PR #11 (branch `feature/app-roles-signin`, 945 tests) and rota PR #54 (branch `claude/keen-fermat-c5fsc4`, 1835 tests).

**Rulings made while executing:**

- Superusers sign in through HR like everyone else; `is_superuser` stays a local rota flag for feedback emails and the sign-in logs. Break-glass is removing `PRACTICE_HR_URL` and restarting.
- The per-app role carries admin only; access to an app is any active HR login. An access flag can be added later if wanted.
- The import sets a password only where the HR login has none, so a password chosen on HR is never overwritten.
- The two tasks ran in parallel in separate repositories with the claim name and the file shape pinned in both briefs; the one contract gap found (an empty rota password aborting the import) was closed on the rota side by exporting it as unusable.
- The rota checks the claim with `is True` rather than truthiness, so a stray string could never grant admin.
- Each branch being one task with its own review, those reviews stood as the whole-branch reviews, followed by one fix wave and one scoped re-review each.
- The rota's own routes while HR sign-in is on: password form, reset and invitation links, passkey endpoints, `password_change/` and the locked-out page's alternatives are all closed; admin "add login" sends no invitation. The admin page's send buttons remain and send links that open the invalid-link page (documented).

**Deferred (recorded, not blocking):** the admin's AppRole writes leave no audit entry beyond Django's own log; an empty `sub` claim would apply the admin flag to an email-matched row that never binds (OIDC requires `sub`); the HR docs could say a rota whose hashes used an unconfigured algorithm would be refused wholesale.
