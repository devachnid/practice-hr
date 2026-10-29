# Graph Report - practice-hr  (2026-10-29)

## Corpus Check
- 285 files · ~175,559 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 18 file(s) not represented in the graph (top: .service 5, .css 4, .timer 3)

## Summary
- 3133 nodes · 9215 edges · 149 communities (108 shown, 41 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 296 edges (avg confidence: 0.89)
- Token cost: 906,063 input · 0 output

## Community Hubs (Navigation)
- TOIL Claim Tests
- Absence Models and Types
- People Models and Admin
- Absence Request and Admin Tests
- TOIL Views and Ops Tests
- Absence Services Core
- People Test Factories
- Accounts Views and Mail
- Absence Request Services
- Absence Policy Form Tests
- Absence Booking Tests
- Passkey Registration and Reauth
- Policy Lookup and Seed Tests
- Accrual Calculation Tests
- Passkey Reauth Tests
- Audit Log and Employee Service
- Client IP and CSP Middleware
- Read API Tests
- Absence Calendar Tests
- OIDC Provider Tests
- Employment Service
- Contract and Pattern Factories
- Approval Decisions and Units
- Bank Holiday Sync
- Entitlement Sync
- Access Rules and Routing
- Balance Views Tests
- Account Mail Delivery
- Absence Nightly Job
- Axes Lockout Tests
- Year-End Close Tests
- Absence Admin Docs
- Sign-in and API Docs
- README and Deployment
- CI Workflow
- TOIL Lots and Expiry
- Absence Ledger Plan
- Request Chase
- Base Layout and People Pages
- Login Import Tests
- Retention Report Tests
- Deploy and PBS Tests
- Approval Views Tests
- Payroll Report Service
- Absence Workflow Plan
- App Roles
- Passkey Service
- HR and Manager Guides
- People Admin Docs
- Positions and Reporting Line
- Absence Notifications
- Payroll Report Tests
- People Admin Classes
- Carry-In Expiry
- Policy Admin Display
- Contracts and FTE
- User Admin
- Foundation Plan
- Onboarding Compliance Records
- Absence Admin Registry
- Rota Read API
- Colour Palette Engine
- Absence Domain Concepts
- Absence Costing
- Calendar and Dashboard Templates
- Accounts Admin and User
- Form Rendering
- OIDC Signing Key
- CSP Tests
- Deploy Checks and Login Hooks
- HR Admin Site and Backend
- Backlog and Roadmap
- HR-Only Sign-In Plan
- Policy Forms
- Payroll Run Command
- Balance Adjustment and Pot Lock
- Working Patterns
- My Absences Page
- Employment Admin Validation
- Cancel and Charge Again
- Recost and Decline
- People Domain Concepts
- Compliance Reminder Digest
- Passkeys JavaScript
- Form Rendering Tests
- Pot Lookup and Leave Year
- Docs Link Checker
- Request Form and Submit
- Calendar Service
- Django Entry Points
- User Model and OIDC Claims
- Absence Admin Permissions
- Ledger Page and Balances
- Invitation and Reset Links
- Axes Lockout Handler
- Year-End Command
- OIDC Client Registration
- Navigation Tests
- Settings and Retention
- Access Rules Tests
- Roles and Compliance Access
- Contract Rows Helper
- Entitlement Resync Signals
- Request Form Templates
- Login Import Command
- Admin Theme
- App Configs
- Login Change Form
- Leaver Note Tests
- Policy Tier Formset
- Absence Preview and Overlap
- Policy Year Governance
- Ledger Entry Inline
- Service Years and Tiers
- Approver Queue
- Design Palette Tag
- Specs and Plans Index
- Bank Holiday Tidy-Up
- Onboarding Checklists
- Policy Resync Snapshot
- Standard Contract Seed
- Password Link Form
- HR Admin Site Config
- Cancel Reason Migration
- Zero Expiry Migration
- Pot Month Helpers
- Undecided Requests
- Working Pattern Inline
- PBS Push Script
- Broken Email Backend
- Rota Test Fixtures
- Password Link URL
- Link Handout Stamp

## God Nodes (most connected - your core abstractions)
1. `hours_employee()` - 271 edges
2. `absence_type()` - 259 edges
3. `make_employee()` - 137 edges
4. `make_employment()` - 117 edges
5. `request()` - 112 edges
6. `for_day()` - 106 edges
7. `make_contract_type()` - 87 edges
8. `make_policy()` - 65 edges
9. `approve()` - 63 edges
10. `make_team()` - 59 edges

## Surprising Connections (you probably didn't know these)
- `Emails that did not go list` --semantically_similar_to--> `LinkToCopy`  [INFERRED] [semantically similar]
  templates/admin/index.html → accounts/mail.py
- `Leave requests and TOIL claims waiting card` --shares_data_with--> `waiting()`  [INFERRED]
  templates/admin/index.html → absence/services/chase.py
- `request_decided()` --references--> `email/decided.txt (request decided email)`  [INFERRED]
  absence/services/notify.py → templates/absence/email/decided.txt
- `absence_cancelled()` --references--> `email/cancelled.txt (absence cancelled email)`  [INFERRED]
  absence/services/notify.py → templates/absence/email/cancelled.txt
- `Outgoing email not configured notice` --shares_data_with--> `email_is_configured()`  [INFERRED]
  templates/admin/index.html → accounts/mail.py

## Import Cycles
- 3-file cycle: `absence/services/bank_holidays.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bank_holidays.py`
- 3-file cycle: `absence/services/bookings.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bookings.py`
- 3-file cycle: `absence/services/bookings.py -> people/services/access.py -> people/services/employments.py -> absence/services/bookings.py`
- 4-file cycle: `absence/services/bank_holidays.py -> absence/services/pots.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bank_holidays.py`
- 4-file cycle: `absence/services/bookings.py -> absence/services/pots.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bookings.py`
- 4-file cycle: `absence/services/bank_holidays.py -> absence/services/bookings.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bank_holidays.py`
- 4-file cycle: `absence/services/bank_holidays.py -> absence/services/bookings.py -> people/services/access.py -> people/services/employments.py -> absence/services/bank_holidays.py`
- 4-file cycle: `absence/services/bank_holidays.py -> absence/services/costing.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bank_holidays.py`
- 4-file cycle: `absence/services/bookings.py -> absence/services/year_end.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bookings.py`
- 4-file cycle: `absence/services/bookings.py -> absence/services/costing.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bookings.py`
- 4-file cycle: `absence/services/bookings.py -> people/services/access.py -> people/services/positions.py -> people/services/employments.py -> absence/services/bookings.py`
- 5-file cycle: `absence/services/bank_holidays.py -> absence/services/bookings.py -> absence/services/pots.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bank_holidays.py`
- 5-file cycle: `absence/services/bookings.py -> absence/services/ledger.py -> absence/services/pots.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bookings.py`
- 5-file cycle: `absence/services/bookings.py -> absence/services/year_end.py -> absence/services/pots.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bookings.py`
- 5-file cycle: `absence/services/bank_holidays.py -> absence/services/bookings.py -> absence/services/costing.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bank_holidays.py`
- 5-file cycle: `absence/services/bank_holidays.py -> absence/services/bookings.py -> absence/services/year_end.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bank_holidays.py`
- 5-file cycle: `absence/services/bank_holidays.py -> absence/services/bookings.py -> people/services/access.py -> people/services/positions.py -> people/services/employments.py -> absence/services/bank_holidays.py`
- 5-file cycle: `absence/services/accrual.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bookings.py -> absence/services/ledger.py -> absence/services/accrual.py`
- 5-file cycle: `absence/services/bookings.py -> absence/services/ledger.py -> absence/services/year_end.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bookings.py`

## Hyperedges (group relationships)
- **Immutable history: nothing deleted, rows only end, ledger only appended** — docs_admin_readme_nothing_is_deleted, docs_admin_people_only_end_rule, docs_admin_absence_ledger, docs_admin_year_end_adjust_balance, docs_admin_people_audit_log [EXTRACTED 1.00]
- **hr_nightly housekeeping steps** — docs_admin_sign_in_nightly_housekeeping, docs_admin_sign_in_deactivating, docs_admin_year_end_year_end_close, docs_admin_absence_pot, docs_admin_absence_auto_bank_holiday_row, docs_admin_absence_waiting_requests [EXTRACTED 1.00]
- **Absence type flags route absences to payroll sheets** — docs_admin_absence_absence_type, docs_admin_absence_payroll_reportable, docs_admin_absence_health_sensitive, docs_admin_absence_family_leave_kit_days, docs_admin_payroll_sheets [EXTRACTED 1.00]
- **Sickness category never disclosed outside restricted views (calendar, payroll report, read API)** — docs_superpowers_plans_2026_09_28_absence_workflow_calendar_labels_only, docs_superpowers_plans_2026_09_28_absence_workflow_payroll_changes_report, docs_superpowers_plans_2026_09_28_absence_workflow_read_api [EXTRACTED 1.00]
- **Entitlement re-sync flow: change triggers, nightly safety net, sync to the accrual integral** — docs_superpowers_plans_2026_09_28_absence_ledger_resync_signals, docs_superpowers_plans_2026_09_28_absence_ledger_i2_policy_resync_in_admin, docs_superpowers_plans_2026_09_28_absence_ledger_nightly_safety_net, docs_superpowers_plans_2026_09_28_absence_ledger_entitlement_sync_revision, docs_superpowers_plans_2026_09_28_absence_ledger_accrual_integral [EXTRACTED 1.00]
- **Practice-account sign-in: HR OIDC provider, client registration, rota relying party** — docs_superpowers_plans_2026_09_28_foundation_oidc_provider, docs_superpowers_plans_2026_09_28_foundation_register_oidc_client, docs_superpowers_plans_2026_09_28_foundation_practice_account_signin, docs_superpowers_plans_2026_09_28_foundation_rota [EXTRACTED 1.00]
- **Append-only compliance records (superseded or new rows, never edited)** — docs_superpowers_specs_2026_10_04_onboarding_documents_design_file, docs_superpowers_specs_2026_10_04_onboarding_documents_design_check, docs_superpowers_specs_2026_10_04_onboarding_documents_design_signature, docs_superpowers_specs_2026_10_04_onboarding_documents_design_checklist [EXTRACTED 1.00]
- **Hook lists that close linked checklist items** — docs_superpowers_plans_2026_10_04_onboarding_documents_recorded_hooks, docs_superpowers_plans_2026_10_04_onboarding_documents_signed_hooks, docs_superpowers_plans_2026_10_04_onboarding_documents_added_hooks, docs_superpowers_plans_2026_10_04_onboarding_documents_onboardingconfig_ready, docs_superpowers_plans_2026_10_04_onboarding_documents_checklists_linked_done [EXTRACTED 1.00]
- **Nightly compliance reminder digest pipeline** — docs_superpowers_specs_2026_10_04_onboarding_documents_design_dueitem, docs_superpowers_specs_2026_10_04_onboarding_documents_design_reminderschedule, docs_superpowers_specs_2026_10_04_onboarding_documents_design_remindersent, docs_superpowers_plans_2026_10_04_onboarding_documents_should_send, docs_superpowers_plans_2026_10_04_onboarding_documents_checks_due_items, docs_superpowers_plans_2026_10_04_onboarding_documents_digest_run, docs_superpowers_specs_2026_09_27_practice_hr_foundation_and_absence_design_hr_nightly [EXTRACTED 1.00]
- **Leave request approval flow (request, notify, queue, decide, outcome email)** — templates_absence_request, templates_absence_email_submitted, templates_absence_queue, templates_absence_decide, templates_absence_email_decided [INFERRED 0.85]
- **TOIL claim approval flow (claim, notify, queue, decide, outcome email, TOIL card)** — templates_absence_toil_claim, templates_absence_email_toil_submitted, templates_absence_queue, templates_absence_toil_decide, templates_absence_email_toil_decided, templates_absence__toil_card [INFERRED 0.85]
- **Balances to ledger drill-down** — templates_absence_balances, templates_absence__balance_year, templates_absence_ledger, templates_absence_balances_ledger_drilldown [INFERRED 0.95]
- **Pages rendered through the site FormRenderer (div.html + field.html)** — config_forms_formrenderer, templates_django_forms_div, templates_django_forms_field, templates_people_me, templates_registration_login, templates_registration_password_change_form, templates_registration_password_reset_confirm, templates_registration_password_reset_form [INFERRED 0.85]
- **Emailed password-link flow (invitation and reset)** — accounts_mail_send_password_link, templates_registration_invitation_email, templates_registration_invitation_subject, templates_registration_password_reset_email, templates_registration_password_reset_form, templates_registration_password_reset_done, templates_registration_password_reset_confirm [INFERRED 0.85]
- **Passkey enrolment, sign-in and notification UI** — static_js_passkeys, templates_accounts_account, templates_base_passkey_nudge, templates_registration_login, templates_registration_passkey_added_email, accounts_views_passkey_register, accounts_mail_send_passkey_added [INFERRED 0.85]

## Communities (149 total, 41 thin omitted)

### Community 0 - "TOIL Claim Tests"
Cohesion: 0.05
Nodes (68): record_failure(), absence_cancelled(), approver_addresses(), claim_decide_url(), claim_decided(), claim_submitted(), _claim_unit(), decide_url() (+60 more)

### Community 1 - "Absence Models and Types"
Cohesion: 0.03
Nodes (33): Migration, Migration, Migration, Migration, Migration, Migration, Migration, Migration (+25 more)

### Community 2 - "People Models and Admin"
Cohesion: 0.04
Nodes (36): ContractInline, EmergencyContactInline, EmploymentInline, ContractForm, Meta, EmployeeForm, Meta, PositionForm (+28 more)

### Community 3 - "Absence Request and Admin Tests"
Cohesion: 0.05
Nodes (71): make_position(), _auto_row(), _decided_claim(), _family_absence(), _open_pot(), _opted_out(), _policy_data(), test_a_manager_does_not_cancel_from_the_admin() (+63 more)

### Community 4 - "TOIL Views and Ops Tests"
Cohesion: 0.05
Nodes (47): admin_client(), configured(), employee_client(), employee_user(), hr_admin(), no_seeded_policies(), _oidc_test_key(), superuser_client() (+39 more)

### Community 5 - "Absence Services Core"
Cohesion: 0.10
Nodes (12): Migration, seed(), BankHoliday, Meta, ClosedDay, Meta, LedgerEntry, Meta (+4 more)

### Community 6 - "People Test Factories"
Cohesion: 0.06
Nodes (38): make_employee(), make_employment(), days_for(), test_a_missing_contract_still_shows_its_message_to_the_employee(), test_name_prefers_preferred_name(), test_str_is_name(), test_work_email_unique_case_insensitive(), test_active_on_respects_both_bounds() (+30 more)

### Community 7 - "Accounts Views and Mail"
Cohesion: 0.05
Nodes (12): dashboard(), _row(), EmailFailure, Meta, ToilClaim, Meta, _submit_message(), email_is_configured() (+4 more)

### Community 8 - "Absence Request Services"
Cohesion: 0.08
Nodes (10): DecisionForm, KitDayForm, PayrollPeriodForm, ToilClaimForm, TypeSelect, claims_for(), calendar_view(), _month() (+2 more)

### Community 9 - "Absence Policy Form Tests"
Cohesion: 0.09
Nodes (42): bank_holiday_summary(), _year_label(), bank_holidays_between(), _policy_post(), _add(), _add_post(), _april_type_in_use(), _bank_holiday_policy() (+34 more)

### Community 10 - "Absence Booking Tests"
Cohesion: 0.10
Nodes (46): _sum(), summary(), record(), request(), submit(), absence_type(), test_an_absence_shows_its_cancel_reason_read_only(), test_other_absences_stay_read_only_in_admin() (+38 more)

### Community 11 - "Passkey Registration and Reauth"
Cohesion: 0.06
Nodes (20): signed_in_recently(), send_passkey_added(), confirm_password(), is_recent(), mark(), account(), ChangePasswordView, _credential_from() (+12 more)

### Community 12 - "Policy Lookup and Seed Tests"
Cohesion: 0.08
Nodes (33): Policy, Accrual, BankHolidays, Basis, Meta, NoPolicy, policy_for(), _back_to_0004() (+25 more)

### Community 13 - "Accrual Calculation Tests"
Cohesion: 0.12
Nodes (41): bank_holiday_entitlement(), daily_rates(), _days(), entitlement(), _rates(), _step(), al(), _bank_holiday_pot() (+33 more)

### Community 14 - "Passkey Reauth Tests"
Cohesion: 0.09
Nodes (23): Passkey, Meta, SoftAuthenticator, _enrol(), _post_json(), _reset_form(), _stale(), test_a_borrowed_session_cannot_add_one() (+15 more)

### Community 15 - "Audit Log and Employee Service"
Cohesion: 0.07
Nodes (25): AuditEntry, Kind, Meta, _email(), _label(), record(), viewed(), create() (+17 more)

### Community 16 - "Client IP and CSP Middleware"
Cohesion: 0.07
Nodes (15): client_ip(), ContentSecurityPolicyMiddleware, PrivatePagesMiddleware, _relying_party_origins(), RequestLogMiddleware, _request(), test_a_forwarded_header_from_anywhere_else_is_ignored(), test_axes_is_wired_to_this_resolver() (+7 more)

### Community 17 - "Read API Tests"
Cohesion: 0.08
Nodes (25): api(), _fresh_rate_counts(), _hit(), test_a_health_sensitive_type_is_always_sick_whatever_its_label(), test_a_partial_absence_carries_its_times(), test_absences_need_an_ordered_window(), test_another_address_is_counted_separately(), test_automatic_bank_holidays_are_not_returned() (+17 more)

### Community 18 - "Absence Calendar Tests"
Cohesion: 0.15
Nodes (33): approve(), month(), off_on(), present(), make_team(), _cell(), _decide_setup(), _may() (+25 more)

### Community 19 - "OIDC Provider Tests"
Cohesion: 0.08
Nodes (21): _app(), _b64url_json(), _claims(), _register(), _signed_in_flow(), test_a_client_someone_owns_is_never_taken_over(), test_a_sign_out_to_an_unregistered_address_is_refused(), test_an_inactive_login_cannot_refresh() (+13 more)

### Community 20 - "Employment Service"
Cohesion: 0.08
Nodes (23): check_employment(), EmploymentForm, Meta, active_on(), amend(), check_amend(), check_end(), check_start() (+15 more)

### Community 21 - "Contract and Pattern Factories"
Cohesion: 0.14
Nodes (34): bounds(), add(), make_contract(), make_contract_type(), make_pattern(), make_policy(), test_a_change_of_unit_inside_one_pot_is_refused(), test_adding_a_contract_in_another_unit_is_refused_while_the_pot_is_open() (+26 more)

### Community 22 - "Approval Decisions and Units"
Cohesion: 0.09
Nodes (25): check(), position(), step(), _toil(), units(), decide(), queue(), _toil() (+17 more)

### Community 23 - "Bank Holiday Sync"
Cohesion: 0.12
Nodes (27): _sync(), sync_auto_absences(), _booked_pot(), cancel(), Ending an employment cancels live absences after the leaving date, _cancel_after(), test_a_booking_on_the_bank_holiday_costs_nothing_and_the_auto_row_still_charges(), test_a_cancelled_automatic_row_stays_cancelled() (+19 more)

### Community 24 - "Entitlement Sync"
Cohesion: 0.11
Nodes (28): running(), entitlement_lines_total(), resync_contract_type(), sync_entitlement(), for_day(), _open(), open_pots(), current_leave_year() (+20 more)

### Community 25 - "Access Rules and Routing"
Cohesion: 0.10
Nodes (24): decides_at_once(), may_cancel(), _own(), _closed(), _may_see_queue(), routed(), balances_for(), balances_view() (+16 more)

### Community 26 - "Balance Views Tests"
Cohesion: 0.11
Nodes (27): rows(), _lines(), _manager_of(), _me(), test_a_filtered_ledger_keeps_the_true_running_balance(), test_a_get_opens_no_pot_and_writes_no_line(), test_a_manager_sees_a_reports_balances_and_ledger_but_not_a_peers(), test_an_employee_is_not_shown_the_admin_text_for_a_type_with_no_policy() (+19 more)

### Community 27 - "Account Mail Delivery"
Cohesion: 0.13
Nodes (19): LinkToCopy, send_password_link(), invitation_subject.txt (Invitation email subject), _link_in(), _request(), test_a_connection_failure_is_a_reason_too(), test_a_failed_public_send_does_not_start_the_throttle(), test_a_refusing_relay_returns_the_link_and_the_reason() (+11 more)

### Community 28 - "Absence Nightly Job"
Cohesion: 0.11
Nodes (22): bank_holiday_pot_used(), _bank_holidays_seeded_to(), _open_pots(), _pot_covering(), _reported(), run(), _why(), end() (+14 more)

### Community 29 - "Axes Lockout Tests"
Cohesion: 0.17
Nodes (16): _login(), _make(), test_a_passkey_sign_in_clears_only_its_own_account(), test_a_single_account_is_still_locked_after_repeated_failures(), test_a_spoofed_header_cannot_be_rotated_to_evade_the_limit(), test_a_success_clears_the_signed_in_persons_own_failures_everywhere(), test_an_account_holder_cannot_reset_a_colleagues_counter(), test_an_unrelated_address_is_not_caught_by_someone_elses_lockout() (+8 more)

### Community 30 - "Year-End Close Tests"
Cohesion: 0.15
Nodes (26): close(), _close_toil(), _next_pot(), _closed_2026(), _leaver(), _next_pot(), _pot_2026(), test_a_leavers_negative_balance_is_left_and_reported() (+18 more)

### Community 31 - "Absence Admin Docs"
Cohesion: 0.14
Nodes (22): Absence and leave (admin reference), Absence type, Accrual basis (daily / monthly twelfths), Accrues flag (earned vs accrued), Bank holiday handling (closed / pot / included in annual leave), Bank holidays and closed days calendar, Absence calendar, Calendar label (+14 more)

### Community 32 - "Sign-in and API Docs"
Cohesion: 0.16
Nodes (20): The read API for the rota (admin reference), GET /api/v1/absences, HR_API_TOKENS bearer tokens, GET /api/v1/patterns, GET /api/v1/people, Rota read API (/api/v1/), Employee, Employee User field (link to login account) (+12 more)

### Community 33 - "README and Deployment"
Cohesion: 0.13
Nodes (22): Payroll changes report (monthly xlsx), Retention report, Practice HR README, Deploy checks (check --deploy: hr.W001, hr.W002, hr.E001), CI pipeline (tests.yml), Expired session clearing (hr-clearsessions.timer), Cloudflare tunnel, HTTPS redirect (SECURE_SSL_REDIRECT) (+14 more)

### Community 34 - "CI Workflow"
Cohesion: 0.07
Nodes (29): ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, DEBUG, DEFAULT_FROM_EMAIL, EMAIL_HOST, HR_API_TOKENS, OIDC_RSA_PRIVATE_KEY, SECRET_KEY (+21 more)

### Community 35 - "TOIL Lots and Expiry"
Cohesion: 0.17
Nodes (24): balance(), write(), earn(), expire_toil(), _toil_lots(), test_write_and_balance(), _take_toil(), test_a_toil_adjustment_expires_by_the_policy_days() (+16 more)

### Community 36 - "Absence Ledger Plan"
Cohesion: 0.13
Nodes (8): _target_type(), _safe_date(), Absence ledger implementation plan, Bank-holiday handling modes (closed not charged / pro-rata pot / included in annual), ClosedDay (practice closure that is never charged), Leave-year basis: fixed date or anniversary (29 Feb safe date), Pot (one employment's allowance for one type and one leave year), Seeded absence types (AL, BH, STUDY, TOIL, SICK, MAT, PAT, SPL, ADOPT, COMP, DEP, UNPAID, OTHER)

### Community 37 - "Request Chase"
Cohesion: 0.12
Nodes (17): _non_working_dates(), notify_once(), waiting(), _working_days_between(), _old_request(), test_a_bank_holiday_is_not_a_working_day(), test_a_closed_day_is_not_a_working_day(), test_a_retry_after_a_failure_stamps_once_email_works() (+9 more)

### Community 38 - "Base Layout and People Pages"
Cohesion: 0.11
Nodes (17): lockout_response(), RequestPasswordLinkView, me(), PersonalDetailsForm, Meta, retention_report(), team(), base.html (Site base layout) (+9 more)

### Community 39 - "Login Import Tests"
Cohesion: 0.22
Nodes (22): _counts(), _file(), _login(), _run(), test_a_file_not_of_the_documented_shape_is_refused(), test_a_hash_this_system_cannot_check_is_refused_as_such(), test_a_login_already_linked_is_left_as_it_is(), test_a_missing_file_is_refused() (+14 more)

### Community 40 - "Retention Report Tests"
Cohesion: 0.12
Nodes (16): due(), _left(), _settings_run(), test_a_category_is_due_only_after_its_last_day(), test_a_current_employee_is_never_due(), test_an_invalid_retention_value_is_a_clear_configuration_error(), test_due_lists_leavers_past_period(), test_due_reports_when_the_period_ended_and_when_it_fell_due() (+8 more)

### Community 41 - "Deploy and PBS Tests"
Cohesion: 0.10
Nodes (12): _database_name(), _service_directives(), _setting(), test_db_path_moves_the_database(), test_gunicorn_keeps_only_the_state_directory_writable(), test_media_root_moves_into_the_state_directory(), test_production_environment_sets_media_root_in_the_state_directory(), test_the_pbs_push_script_is_executable_and_valid_shell() (+4 more)

### Community 42 - "Approval Views Tests"
Cohesion: 0.17
Nodes (22): _decide(), _setup(), test_a_cancelled_request_reads_as_cancelled(), test_a_double_post_shows_the_read_only_page_and_writes_nothing(), test_a_non_approver_has_no_waiting_count(), test_a_refused_decision_shows_why_and_tells_nobody(), test_a_routed_approver_sees_a_decided_request_read_only(), test_a_stranger_gets_403_on_a_decided_request_too() (+14 more)

### Community 43 - "Payroll Report Service"
Cohesion: 0.10
Nodes (11): Absence, Category, Meta, Status, PayrollRun, Meta, _absences(), _balance() (+3 more)

### Community 44 - "Absence Workflow Plan"
Cohesion: 0.14
Nodes (13): Kind, Balance summary (entitlement, carried in, taken, booked, pending, expired, adjustments, remaining), Deferred to plan 3 (carry-over, expiry, TOIL earned, year end, chase, calendar, request pages, payroll, API), LedgerEntry kinds (entitlement, revision, carry-in, expiry, booking, cancellation, TOIL earned/taken, adjustment), Absence workflow, payroll and API implementation plan, Admin dashboard card (waiting requests, email not configured), Notification routing: routed manager's work email or every active HR admin, Carry-in expiry after carry_over_expires_after_days (+5 more)

### Community 45 - "App Roles"
Cohesion: 0.18
Nodes (19): AppRole, Meta, _apps_heading(), _client(), _save(), test_a_role_reads_as_who_on_what(), test_a_superuser_can_set_it_too_and_an_hr_admin_never_reaches_a_superusers(), test_an_existing_user_role_is_ticked_to_admin() (+11 more)

### Community 46 - "Passkey Service"
Cohesion: 0.16
Nodes (10): complete_registration(), _could_not_verify(), login_options(), origin(), PasskeyError, registration_options(), rp_id(), _spend() (+2 more)

### Community 47 - "HR and Manager Guides"
Cohesion: 0.19
Nodes (17): Automatic bank-holiday absence row (Charge again), Balances page, Cancelling an absence, Family leave and keeping-in-touch days, Pot (one person's allowance of one type for one leave year), Recalculate entitlement action, TOIL (time off in lieu) claims, Waiting request chasing (CHASE_AFTER_WORKING_DAYS) (+9 more)

### Community 48 - "People Admin Docs"
Cohesion: 0.18
Nodes (19): Deciding a request (approval routing), Health sensitive flag, People (admin reference), Audit log, Continuous service date, Contract, Employment (spell of work), Line manager (approval routing) (+11 more)

### Community 49 - "Positions and Reporting Line"
Cohesion: 0.17
Nodes (16): add(), check_add(), check_end(), end(), manager_of(), on(), _primary_clash(), primary_on() (+8 more)

### Community 50 - "Absence Notifications"
Cohesion: 0.15
Nodes (20): send(), request_decided(), request_submitted(), _pair(), test_a_request_routed_to_hr_never_goes_to_the_requester(), test_a_template_fault_never_reaches_the_caller(), test_bad_address_is_a_failure_not_an_exception(), test_cancelled_goes_to_the_approver() (+12 more)

### Community 51 - "Payroll Report Tests"
Cohesion: 0.20
Nodes (20): build(), end(), make_pot(), _cells(), _sheet(), test_a_spanning_sickness_absence_is_clipped_to_the_month(), test_a_spanning_unpaid_absence_is_split_between_the_months(), test_automatic_bank_holiday_rows_are_never_reported() (+12 more)

### Community 52 - "People Admin Classes"
Cohesion: 0.10
Nodes (6): AuditEntryAdmin, ContractTypeAdmin, EmployeeAdmin, EmploymentAdmin, TeamAdmin, WorkingPatternAdmin

### Community 53 - "Carry-In Expiry"
Cohesion: 0.15
Nodes (18): _bookings(), expire_carry_in(), _lock(), _sum(), _book(), _booked_on(), _carried(), _request_on() (+10 more)

### Community 54 - "Policy Admin Display"
Cohesion: 0.15
Nodes (5): as_days(), mode(), plain(), PolicyAdmin, PolicyTierInline

### Community 55 - "Contracts and FTE"
Cohesion: 0.12
Nodes (14): _starters(), _cap(), _stays(), active_on(), contracted_amount(), fte(), _fmt(), set_pattern() (+6 more)

### Community 57 - "Foundation Plan"
Cohesion: 0.14
Nodes (10): Validator, backup.sh script, Practice HR foundation implementation plan, Deployment: gunicorn on loopback 8322, nightly timer 01:30, backup with media, django-oauth-toolkit, django-unfold admin, hr_nightly runs every app's nightly job, mozilla-django-oidc (+2 more)

### Community 58 - "Onboarding Compliance Records"
Cohesion: 0.14
Nodes (21): ADDED_HOOKS (files), checklists.linked_done, checks.record, files.add, files.sniff (content sniffing), OnboardingConfig.ready (hook registration), policies.owed, Migration people 0013_positiontitle (hand-written data migration) (+13 more)

### Community 59 - "Absence Admin Registry"
Cohesion: 0.12
Nodes (6): AbsenceTypeAdmin, BankHolidayAdmin, ClosedDayAdmin, EmailFailureAdmin, PotAdmin, ToilClaimAdmin

### Community 60 - "Rota Read API"
Cohesion: 0.14
Nodes (15): _over_limit(), token_required(), wrapped(), _valid(), absences(), _bad_request(), _iso(), patterns() (+7 more)

### Community 61 - "Colour Palette Engine"
Cohesion: 0.18
Nodes (12): _build(), contrast_ratio(), hex_to_rgb(), hue_distance(), _linear_to_srgb(), nearest_tint(), oklch_to_hex(), _readable_fg() (+4 more)

### Community 62 - "Absence Domain Concepts"
Cohesion: 0.14
Nodes (18): PolicyForm._check_year (leave-year lock on add), My absences always lists still-requested absences, Leaver's late TOIL claim lands on the pot of their last day (_pot_day), Recorded absence carries 'Recorded by <name>' (bookings.record), ToilClaimAdmin (read-only list of TOIL claims), Absence (range or partial-day booking), absence app, Absence Policy and PolicyTier (rules as data) (+10 more)

### Community 63 - "Absence Costing"
Cohesion: 0.29
Nodes (17): cost(), halves_covered(), hours_employee(), absence(), test_automatic_bank_holiday_is_charged_whatever_its_own_policy_handling_says(), test_bank_holiday_closed_not_charged(), test_closed_day_never_charged(), test_full_days() (+9 more)

### Community 64 - "Calendar and Dashboard Templates"
Cohesion: 0.14
Nodes (11): _hours(), off_chip(), off_title(), status_tone(), when(), calendar.html (Who is off calendar), Presence headcount (N of M present), admin/index.html (Admin dashboard override) (+3 more)

### Community 65 - "Accounts Admin and User"
Cohesion: 0.11
Nodes (6): InviteForm, Meta, PasskeyInline, User, Meta, test_a_saved_address_keeps_its_local_part_but_not_a_shouted_domain()

### Community 66 - "Form Rendering"
Cohesion: 0.13
Nodes (7): SetPasswordFromLinkView, BoundField, FormRenderer, div.html (Site form layout), field.html (Design-system field markup), password_reset_confirm.html (Set password from link page), password_reset_email.txt (Password reset email body)

### Community 67 - "OIDC Signing Key"
Cohesion: 0.21
Nodes (15): oidc_signing_key(), _env(), _pem(), _rsa_pem(), _settings(), test_a_good_key_passes(), test_a_key_that_is_not_rsa_fails(), test_a_named_file_that_cannot_be_read_stops_the_app() (+7 more)

### Community 68 - "CSP Tests"
Cohesion: 0.13
Nodes (11): _policy(), _templates(), test_app_pages_carry_the_policy(), test_form_action_is_self_alone_with_no_client(), test_form_action_lets_sign_in_and_sign_out_finish_at_the_rota(), test_no_template_has_inline_script_or_handlers(), test_rendered_pages_hold_no_inline_script(), test_the_admin_renders_and_is_left_alone() (+3 more)

### Community 69 - "Deploy Checks and Login Hooks"
Cohesion: 0.13
Nodes (10): AccountsConfig, on_login(), Approver link built from SITE_URL + notify.DECIDE_PATH (hr.W002), api_tokens(), site_url(), test_check_quiet_in_debug(), test_check_quiet_with_a_token(), test_check_warns_when_no_tokens_outside_debug() (+2 more)

### Community 70 - "HR Admin Site and Backend"
Cohesion: 0.13
Nodes (4): HrAdminBackend, _is_hr_admin(), HrAdminSite, is_hr_admin()

### Community 71 - "Backlog and Roadmap"
Cohesion: 0.17
Nodes (18): Backlog, Alternating-week working patterns, GMC register, GPhC register, NMC register, Onboarding, offboarding and documents (spec 3), Opening balances carry-in screen, Professional registration checks (+10 more)

### Community 72 - "HR-Only Sign-In Plan"
Cohesion: 0.15
Nodes (14): admin OIDC claim (Validator.get_additional_claims), AppRole (per-application admin flag on the HR login), Break-glass: remove PRACTICE_HR_URL and restart the rota, export_logins management command (rota), Sign-in through HR only (PRACTICE_HR_URL set): rota passwords and passkeys closed, import_logins management command (HR), Login export JSON file (mode 0600, deleted after import), PracticeAccountBackend (rota OIDC backend) (+6 more)

### Community 73 - "Policy Forms"
Cohesion: 0.16
Nodes (7): _hours_chosen(), PolicyForm, Meta, PolicyTierForm, Meta, _Stores, to_weeks()

### Community 74 - "Payroll Run Command"
Cohesion: 0.12
Nodes (9): Command, month(), run(), payroll_view(), payroll.html (Payroll changes page), Monthly payroll changes run, test_generating_a_period_again_records_a_second_run_and_replaces_the_file(), test_run_saves_file_and_row() (+1 more)

### Community 75 - "Balance Adjustment and Pot Lock"
Cohesion: 0.15
Nodes (10): AdjustForm, adjust(), check_open(), _closing_lines(), is_closed(), admin/adjust_pot.html (Adjust pot balance), test_adjust_refuses_a_closed_pot(), test_adjust_writes_one_audited_adjustment_line_today() (+2 more)

### Community 76 - "Working Patterns"
Cohesion: 0.16
Nodes (11): cost_between(), _policy(), _skip(), round_to(), pattern_on(), units_on(), weekly_total(), test_round_to() (+3 more)

### Community 77 - "My Absences Page"
Cohesion: 0.18
Nodes (11): _bank_groups(), cancel(), kit_day(), _leave_year(), _may_cancel(), mine(), _my_employment(), request_leave() (+3 more)

### Community 78 - "Employment Admin Validation"
Cohesion: 0.15
Nodes (8): add_error(), ContractInlineFormSet, EmploymentInlineFormSet, PositionInlineFormSet, _rows(), check_add(), check_end(), _unit_clash()

### Community 79 - "Cancel and Charge Again"
Cohesion: 0.17
Nodes (3): charge_again(), admin/cancel_absence.html (Cancel absence confirm), admin/charge_again.html (Charge bank holiday again confirm)

### Community 80 - "Recost and Decline"
Cohesion: 0.18
Nodes (11): add_kit_day(), _copy_back(), decline(), _lock(), recost(), set_family_dates(), Family-leave dates and KIT days, _approved_mon_to_wed() (+3 more)

### Community 81 - "People Domain Concepts"
Cohesion: 0.20
Nodes (14): API fixed-window rate limit (API_RATE_LIMIT_PER_MINUTE, 429), Leaver audit note lists not-cancelled absences first (_cancel_after), Employee.work_email help text correction, Onboarding, offboarding and documents implementation plan, AuditEntry (audit log), Contract (may overlap; contracted_amount is their sum), Employee, Employment (dated spell, continuous service date) (+6 more)

### Community 82 - "Compliance Reminder Digest"
Cohesion: 0.18
Nodes (15): checks due_items (checks/services/due.py), checks.state and the check status rules, compliance Django app (ReminderSchedule, ReminderSent, schedule, digest), compliance_counts (admin dashboard Compliance card), digest.run and digest.pending, schedule.should_send (reminder cadence), hr_nightly job, mail.py email delivery (never raises into a page) (+7 more)

### Community 83 - "Passkeys JavaScript"
Cohesion: 0.29
Nodes (14): armConditional(), b64urlToBytes(), bytesToB64url(), cancelConditional(), creationOptions(), credentialToJSON(), csrfToken(), enrol() (+6 more)

### Community 84 - "Form Rendering Tests"
Cohesion: 0.22
Nodes (10): Demo, _field_div(), test_a_checkbox_sits_inside_its_label(), test_a_single_field_group_uses_the_same_template(), test_dates_times_numbers_and_short_text_are_short(), test_errors_are_alerts_and_mark_the_field_invalid(), test_every_field_is_wrapped_labelled_without_a_colon_and_helped(), test_radios_keep_their_row_and_hidden_fields_are_rendered_once() (+2 more)

### Community 85 - "Pot Lookup and Leave Year"
Cohesion: 0.15
Nodes (9): _nothing_yet(), _year(), _check_leave_year(), bounds(), lookup(), _pot_day(), test_lookup_finds_an_open_pot_and_never_creates_one(), test_lookup_names_a_missing_policy() (+1 more)

### Community 86 - "Docs Link Checker"
Cohesion: 0.21
Nodes (5): _anchors(), _links(), _slug(), test_every_relative_link_and_anchor_resolves(), test_the_link_checker_catches_a_broken_anchor()

### Community 87 - "Request Form and Submit"
Cohesion: 0.14
Nodes (8): RequestForm, after(), _balance(), _fields(), submit(), _request_page(), Two-step request without JavaScript (validate, show cost and balance, confirm), test_after_for_toil_with_no_pot_starts_from_zero()

### Community 88 - "Calendar Service"
Cohesion: 0.27
Nodes (9): days_for(), _halves(), _load(), _members(), cell(), _off(), _present(), _public() (+1 more)

### Community 92 - "Ledger Page and Balances"
Cohesion: 0.23
Nodes (7): _filters(), ledger_view(), _links(), Balances for this leave year and next, linked to ledger lines, _balance_year.html (one leave year's balance row), balances.html (Balances page), ledger.html (Pot ledger page)

### Community 93 - "Invitation and Reset Links"
Cohesion: 0.20
Nodes (4): _report(), link_expires(), invitation_email.txt (Invitation email body), test_link_expiry_follows_the_setting()

### Community 95 - "Year-End Command"
Cohesion: 0.20
Nodes (7): Command, run(), _why(), test_run_expires_carry_in_and_toil_on_open_pots(), test_toil_at_year_end_carries_forward_with_its_earned_date(), test_toil_year_end_twice_writes_nothing(), _toil_2026_27()

### Community 97 - "Navigation Tests"
Cohesion: 0.36
Nodes (7): _approver_of(), _employee(), _split(), test_an_approver_also_sees_approvals(), test_an_employee_sees_leave_calendar_and_balances_but_not_approvals(), test_an_hr_admin_sees_approvals_and_admin(), test_the_mobile_tab_bar_holds_at_most_five_items()

### Community 98 - "Settings and Retention"
Cohesion: 0.20
Nodes (4): _dev_secret_key(), _oidc_private_key(), _retention_days(), test_the_dev_key_is_private_to_the_checkout()

### Community 99 - "Access Rules Tests"
Cohesion: 0.31
Nodes (7): roles(), _person(), test_can_view(), test_employee_for(), test_roles_context_processor_memoises_per_request(), test_route_to_admin_group_when_manager_has_left(), test_route_without_manager_goes_to_admin_group()

### Community 100 - "Roles and Compliance Access"
Cohesion: 0.24
Nodes (9): access.can_view_file, files.open (access check and viewed audit), access.is_pre_start, PreStartGate middleware, Approval routing to the line manager, Position (dated job, line manager, primary flag), Roles and access (HR admin, employee, derived approver), Compliance access rules (people/services/access.py) (+1 more)

### Community 102 - "Entitlement Resync Signals"
Cohesion: 0.39
Nodes (3): _contract_saved(), _employment_saved(), resync_employment()

### Community 103 - "Request Form Templates"
Cohesion: 0.28
Nodes (3): _balances.html (balances this leave year card), Leave-year pots open overnight, request.html (Request / record leave form)

### Community 104 - "Login Import Command"
Cohesion: 0.25
Nodes (3): _client(), Command, _read()

### Community 105 - "Admin Theme"
Cohesion: 0.36
Nodes (5): base(), _between(), _ordered(), primary(), token()

### Community 108 - "Leaver Note Tests"
Cohesion: 0.32
Nodes (6): _end_note(), _leaver_with_absences(), test_a_leaver_note_that_overflows_ends_with_an_ellipsis(), test_a_leaver_note_with_nothing_left_over_is_just_the_cancelled_part(), test_the_leaver_note_lists_what_was_not_cancelled_first_even_when_it_is_long(), _weekdays()

### Community 110 - "Absence Preview and Overlap"
Cohesion: 0.29
Nodes (4): check_family_dates(), overlaps(), preview(), test_a_toil_booking_is_rounded_to_the_annual_leave_step()

### Community 111 - "Policy Year Governance"
Cohesion: 0.47
Nodes (3): governing(), in_force(), _year()

### Community 113 - "Service Years and Tiers"
Cohesion: 0.47
Nodes (4): tier_extra_weeks(), Service tiers (PolicyTier extra weeks after N years), _anniversary(), service_years()

### Community 114 - "Approver Queue"
Cohesion: 0.33
Nodes (3): _may_open(), queue_for(), _routed_to()

### Community 116 - "Specs and Plans Index"
Cohesion: 0.40
Nodes (6): Known limitations left for a follow-up, Tidy-up plan: follow-ups from plans 1-3 and the TOIL work, HR-only sign-in plan: app roles, rota passwords migrated, rota password form retired, Practice HR: foundation and absence design (spec 1), BreatheHR (system being replaced), Spec 2: Rota integration

### Community 117 - "Bank Holiday Tidy-Up"
Cohesion: 0.40
Nodes (5): Bank-holiday seeds 2029-2030 and the bank_holidays_seeded_to warning, Absence.cancel_reason and the bank-holiday opt-out (NOT_IMPLIED), bank_holidays.charge_again admin action, BankHoliday and automatic bank-holiday charging, costing.cost

### Community 118 - "Onboarding Checklists"
Cohesion: 0.53
Nodes (6): checklists.start / leave (_build), people.services.employments.start / end, Checklist and ChecklistItem (owner: HR, manager or person), ChecklistTemplate and TemplateItem, onboarding app, HR Starters and leavers page (gaps listed at the top)

### Community 120 - "Standard Contract Seed"
Cohesion: 0.50
Nodes (3): _as_seeded(), Migration, seed()

## Ambiguous Edges - Review These
- `Hand-entered carry-overs (shell)` → `Going live: first month checklist`  [AMBIGUOUS]
  docs/guides/hr-administrator.md · relation: conceptually_related_to
- `Hand-entered carry-overs (shell)` → `Go live`  [AMBIGUOUS]
  docs/superpowers/backlog.md · relation: conceptually_related_to
- `compliance package (due-items contract and digest)` → `compliance Django app (ReminderSchedule, ReminderSent, schedule, digest)`  [AMBIGUOUS]
  docs/superpowers/plans/2026-10-04-onboarding-documents.md · relation: implements
- `Signing with re-authentication (password or passkey)` → `policies.sign`  [AMBIGUOUS]
  docs/superpowers/plans/2026-10-04-onboarding-documents.md · relation: implements

## Knowledge Gaps
- **18 isolated node(s):** `PBS_PASSWORD_FILE`, `Expired session clearing (hr-clearsessions.timer)`, `whitenoise 6.12.0`, `Seeded absence types (AL, BH, STUDY, TOIL, SICK, MAT, PAT, SPL, ADOPT, COMP, DEP, UNPAID, OTHER)`, `BreatheHR (system being replaced)` (+13 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 875 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **41 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Practice HR: foundation and absence design (spec 1)` connect `Specs and Plans Index` to `Absence Ledger Plan`, `Absence Workflow Plan`, `People Domain Concepts`, `Compliance Reminder Digest`, `Foundation Plan`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `request()` (e.g. with `submit()` and `submit()`) actually correct?**
  _`request()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `PBS_PASSWORD_FILE`, `Expired session clearing (hr-clearsessions.timer)`, `whitenoise 6.12.0` to the rest of the system?**
  _18 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `TOIL Claim Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.05133161512027491 - nodes in this community are weakly interconnected._
- **Why does `absence_type()` connect `Absence Booking Tests` to `TOIL Claim Tests`, `Absence Request and Admin Tests`, `Absence Services Core`, `Absence Policy Form Tests`, `Policy Lookup and Seed Tests`, `Accrual Calculation Tests`, `Read API Tests`, `Absence Calendar Tests`, `Contract and Pattern Factories`, `Bank Holiday Sync`, `Entitlement Sync`, `Balance Views Tests`, `Absence Nightly Job`, `Year-End Close Tests`, `TOIL Lots and Expiry`, `Request Chase`, `Retention Report Tests`, `Approval Views Tests`, `Absence Notifications`, `Payroll Report Tests`, `Carry-In Expiry`, `Absence Costing`, `Balance Adjustment and Pot Lock`, `Recost and Decline`, `Pot Lookup and Leave Year`, `Request Form and Submit`, `Year-End Command`, `Leaver Note Tests`, `Absence Preview and Overlap`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Hand-entered carry-overs (shell)` and `Going live: first month checklist`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Hand-entered carry-overs (shell)` and `Go live`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._