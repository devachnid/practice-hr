# Graph Report - practice-hr  (2026-11-01)

## Corpus Check
- 388 files · ~310,884 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 19 file(s) not represented in the graph (top: .service 5, .css 4, .timer 3)

## Summary
- 5267 nodes · 16136 edges · 212 communities (158 shown, 54 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 1255 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `70f7c8ec`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- people/models/__init__.py
- Absence Booking Tests
- Year-End and TOIL Ledger
- Absence Models and Types
- Test Factories
- TrainingRecord
- Absence and Leave Docs
- Training Service
- Registration Service Tests
- Absence Services Core
- Register Adapter Tests
- EmployeeAdmin
- Checks Model and Service
- Onboarding Pages Tests
- Training Views and Forms
- README and Platform Docs
- Absence Calendar Tests
- TOIL and Approval View Tests
- Employee and Employment Tests
- test_account_mail.py
- Onboarding Checklist Tests
- Document Files
- training/services/due.py
- Onboarding Checklist Service
- Training Admin and Plan
- people/services/__init__.py
- documents.File (opaque path, SHA-256, superseded never deleted)
- Access Rules and Roles
- test_training_admin.py
- Balance Views Tests
- Register Page Parsers
- Passkey Reauth Tests
- Passkey Registration and Reauth
- Accrual Calculation Tests
- config/forms.py
- Foundation Domain Concepts
- Absence Policy Form Tests
- check_employment
- Checks Admin Actions
- Absence Request and Admin Tests
- Policy Signing Tests
- Request Chase
- Registrations Admin Docs
- Read API Tests
- Compliance Digest Design
- Login Accounts Admin
- Compliance Counts Tests
- Absence Admin Tests
- Passkeys and Reauth
- adapters/__init__.py
- names.py
- People Test Factories
- accounts/views.py
- Training Matrix
- Specs and Backlog Index
- Bank Holiday Sync
- OIDC Provider Tests
- test_seed_demo.py
- Axes Lockout Tests
- Login Import Tests
- Auto Login Tests
- CI Workflow
- ChecklistItem
- Onboarding Admin
- approvals.py
- run
- Course
- Compliance Admin Docs
- getting_started
- Colour Palette Engine
- Professional registration checks implementation plan
- Absence Costing Tests
- Ops Hardening and Settings
- pytest
- Foundation Plan
- App Roles
- Lookup
- Register Due Items Tests
- Absence Ledger Plan
- Payroll Report Tests
- Client IP and CSP Middleware
- digest.py
- Deploy and PBS Tests
- Retention Report Tests
- Absence Admin Actions
- App Configs
- Policy Issue and Sign
- Absence Notifications
- mine
- Navigation and Email Case Tests
- Register Admin and Unpause
- Policy Signing Views
- Absence Workflow Plan
- unit
- test_training_sessions.py
- test_registers_pages.py
- NI Number Normalising
- Shared Validity Helpers
- HR-Only Sign-In Plan
- OIDC Signing Key
- ChecklistTemplate, TemplateItem, Checklist and ChecklistItem models
- CSP Tests
- Employment Admin Validation
- Guide for HR administrators
- Accounts Views and Mail
- test_absence_approval_views.py
- ReminderSchedule
- Absence Admin Registry
- Command
- Ledger Page and Balances
- Security Middleware
- FileAdmin
- Policy Admin Display
- compliance_people
- Passkeys JavaScript
- Form Rendering Tests
- Training compliance implementation plan (spec 4)
- state
- current
- People Admin Classes
- Policy Forms
- http.py
- decide
- Deploy Checks and Login Hooks
- API Token Auth
- send_password_link
- Positions and Reporting Line
- Docs Link Checker
- RegisterBody (gmc, mpl_wales, nmc, gphc)
- Check Record Form
- RequestPasswordLinkForm
- Axes Lockout Handler
- Rota Read API
- TOIL Views and Ops Tests
- HR Admin Site and Backend
- get_or_create
- Django Entry Points
- OIDC Client Registration
- Private Pages Tests
- Ledger Entry Inline
- Contract Rows Helper
- Entitlement Resync Signals
- Login Import Command
- reject
- test_absence_nightly.py
- update
- amend
- OIDC Claims Tests
- Policy Tier Formset
- _Text
- User Model and OIDC Claims
- Training Admin Navigation
- due_items
- test_training_due.py
- Lookups service (run and scheduled)
- Part B — The prompt
- NI Number Migration
- Registration
- me
- Standard Contract Seed
- Pot Month Helpers
- HR Admin Site Config
- numbers.py
- LinkToCopy
- Register page fixtures README
- Cancel Reason Migration
- Zero Expiry Migration
- Accounts Admin and User
- Check Types Seed
- _cancel_after
- linked_done
- send_passkey_added
- LoginChangeForm
- django_contrib_auth
- api_tokens
- No Policy Error
- PayrollRun
- 0002_seed_templates.py
- _Broken
- _fresh_rate_counts
- BrokenBackend
- hashed
- Media Fixture
- test_csrf_enforcement_does_not_get_in_the_way
- test_no_tokens_configured_refuses_everything
- test_overdue_checklist_items_leave_out_a_leaver_past_90_days

## God Nodes (most connected - your core abstractions)
1. `make_employee()` - 299 edges
2. `hours_employee()` - 274 edges
3. `absence_type()` - 259 edges
4. `make_employment()` - 161 edges
5. `request()` - 112 edges
6. `for_day()` - 107 edges
7. `make_team()` - 95 edges
8. `File` - 94 edges
9. `make_contract_type()` - 89 edges
10. `CheckType` - 79 edges

## Surprising Connections (you probably didn't know these)
- `Policy sign form (password or passkey credential)` --semantically_similar_to--> `confirm_password()`  [INFERRED] [semantically similar]
  templates/documents/sign.html → accounts/recent_auth.py
- `Leave requests and TOIL claims waiting card` --shares_data_with--> `waiting()`  [INFERRED]
  templates/admin/index.html → absence/services/chase.py
- `request_decided()` --references--> `email/decided.txt (request decided email)`  [INFERRED]
  absence/services/notify.py → templates/absence/email/decided.txt
- `absence_cancelled()` --references--> `email/cancelled.txt (absence cancelled email)`  [INFERRED]
  absence/services/notify.py → templates/absence/email/cancelled.txt
- `Outgoing email not configured notice` --shares_data_with--> `email_is_configured()`  [INFERRED]
  templates/admin/index.html → accounts/mail.py

## Import Cycles
- 2-file cycle: `absence/services/ledger.py -> absence/services/year_end.py -> absence/services/ledger.py`
- 2-file cycle: `onboarding/services/checklists.py -> people/services/positions.py -> onboarding/services/checklists.py`
- 2-file cycle: `absence/services/ledger.py -> absence/services/pots.py -> absence/services/ledger.py`
- 2-file cycle: `absence/services/bank_holidays.py -> absence/services/pots.py -> absence/services/bank_holidays.py`
- 3-file cycle: `absence/services/ledger.py -> absence/services/year_end.py -> absence/services/pots.py -> absence/services/ledger.py`
- 3-file cycle: `checks/services/checks.py -> people/services/positions.py -> onboarding/services/checklists.py -> checks/services/checks.py`
- 3-file cycle: `documents/services/policies.py -> people/services/positions.py -> onboarding/services/checklists.py -> documents/services/policies.py`
- 3-file cycle: `onboarding/services/checklists.py -> people/services/access.py -> people/services/positions.py -> onboarding/services/checklists.py`
- 3-file cycle: `onboarding/services/checklists.py -> people/services/positions.py -> people/services/employments.py -> onboarding/services/checklists.py`
- 3-file cycle: `checks/services/checks.py -> people/services/employments.py -> onboarding/services/checklists.py -> checks/services/checks.py`
- 3-file cycle: `absence/services/bookings.py -> people/services/access.py -> people/services/employments.py -> absence/services/bookings.py`
- 3-file cycle: `onboarding/services/checklists.py -> people/services/access.py -> people/services/employments.py -> onboarding/services/checklists.py`
- 3-file cycle: `absence/services/bookings.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bookings.py`
- 3-file cycle: `absence/services/bank_holidays.py -> absence/services/bookings.py -> absence/services/pots.py -> absence/services/bank_holidays.py`
- 3-file cycle: `documents/services/policies.py -> people/services/employments.py -> onboarding/services/checklists.py -> documents/services/policies.py`
- 3-file cycle: `absence/services/bank_holidays.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bank_holidays.py`
- 4-file cycle: `absence/services/bookings.py -> absence/services/year_end.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bookings.py`
- 4-file cycle: `absence/services/bank_holidays.py -> absence/services/bookings.py -> absence/services/year_end.py -> absence/services/pots.py -> absence/services/bank_holidays.py`
- 4-file cycle: `checks/services/checks.py -> people/services/access.py -> people/services/positions.py -> onboarding/services/checklists.py -> checks/services/checks.py`
- 4-file cycle: `documents/services/policies.py -> people/services/access.py -> people/services/positions.py -> onboarding/services/checklists.py -> documents/services/policies.py`

## Hyperedges (group relationships)
- **Append-only compliance records (superseded or new rows, never edited)** — docs_superpowers_specs_2026_10_04_onboarding_documents_design_file, docs_superpowers_specs_2026_10_04_onboarding_documents_design_check, docs_superpowers_specs_2026_10_04_onboarding_documents_design_signature, docs_superpowers_specs_2026_10_04_onboarding_documents_design_checklist [EXTRACTED 1.00]
- **Morning compliance digest pipeline (due-items contract, cadence, sent log)** — docs_superpowers_plans_2026_10_04_onboarding_documents_checks_due_items, docs_superpowers_plans_2026_10_04_onboarding_documents_documents_due_items, docs_superpowers_plans_2026_10_04_onboarding_documents_onboarding_due_items, docs_superpowers_plans_2026_10_04_onboarding_documents_dueitem, docs_superpowers_plans_2026_10_04_onboarding_documents_should_send, docs_superpowers_plans_2026_10_04_onboarding_documents_reminderschedule, docs_superpowers_plans_2026_10_04_onboarding_documents_remindersent, docs_superpowers_plans_2026_10_04_onboarding_documents_digest_run, docs_superpowers_plans_2026_10_04_onboarding_documents_compliance_nightly [EXTRACTED 1.00]
- **Hook-based auto-closing of linked checklist items** — docs_superpowers_plans_2026_10_04_onboarding_documents_recorded_hooks, docs_superpowers_plans_2026_10_04_onboarding_documents_signed_hooks, docs_superpowers_plans_2026_10_04_onboarding_documents_added_hooks, docs_superpowers_plans_2026_10_04_onboarding_documents_onboardingconfig_ready, docs_superpowers_plans_2026_10_04_onboarding_documents_checklists_linked_done, docs_superpowers_plans_2026_10_04_onboarding_documents_link_strings [EXTRACTED 1.00]
- **Readers of training.state / build_row: pages, digest, dashboard, Compliance tab and matrix** — training_services_training_state, people_views_me, people_views_team, training_views_person, training_services_due_due_items, training_services_matrix_build, people_admin_employeeadmin_compliance_summary, absence_admin_dashboard_compliance_people [EXTRACTED 1.00]
- **Training record lifecycle through the service (record, self-record, verify, reject, set expiry)** — training_services_training_record, training_services_training_self_record, training_services_training_verify, training_services_training_reject, training_services_training_set_expiry, training_services_sessions_record_session [EXTRACTED 1.00]
- **Checks and training share compliance.validity's expiry arithmetic and status rule** — compliance_validity_expires_from, compliance_validity_status, checks_services_checks_expires_from, checks_services_checks_status, training_services_training_build_row, training_services_training_new_record [EXTRACTED 1.00]
- **Entitlement re-sync flow: change triggers, nightly safety net, sync to the accrual integral** — docs_superpowers_plans_2026_09_28_absence_ledger_resync_signals, docs_superpowers_plans_2026_09_28_absence_ledger_i2_policy_resync_in_admin, docs_superpowers_plans_2026_09_28_absence_ledger_nightly_safety_net, docs_superpowers_plans_2026_09_28_absence_ledger_entitlement_sync_revision, docs_superpowers_plans_2026_09_28_absence_ledger_accrual_integral [EXTRACTED 1.00]
- **Practice-account sign-in: HR OIDC provider, client registration, rota relying party** — docs_superpowers_plans_2026_09_28_foundation_oidc_provider, docs_superpowers_plans_2026_09_28_foundation_register_oidc_client, docs_superpowers_plans_2026_09_28_foundation_practice_account_signin, docs_superpowers_plans_2026_09_28_foundation_rota [EXTRACTED 1.00]
- **Four register adapters supplying url() and parse()** — registers_adapters_gmc, registers_adapters_mpl_wales, registers_adapters_nmc, registers_adapters_gphc, registers_adapters_base [EXTRACTED 1.00]
- **Global safety and privacy constraints on register lookups** — docs_superpowers_plans_2026_10_05_professional_registrations_one_network_function, docs_superpowers_plans_2026_10_05_professional_registrations_page_never_stored, docs_superpowers_plans_2026_10_05_professional_registrations_no_pii_in_logs, docs_superpowers_plans_2026_10_05_professional_registrations_politeness_rules, docs_superpowers_plans_2026_10_05_professional_registrations_lookup_never_raises [EXTRACTED 1.00]
- **Nightly register lookups to morning digest alerts** — registers_services_nightly_run, registers_services_nightly_sync_verified, registers_services_lookups_scheduled, registers_services_lookups_run, registers_adapters_init_lookup, registers_services_lookups_record_check, registers_services_due_due_items, compliance_services_digest [EXTRACTED 1.00]
- **Sickness category never disclosed outside restricted views (calendar, payroll report, read API)** — docs_superpowers_plans_2026_09_28_absence_workflow_calendar_labels_only, docs_superpowers_plans_2026_09_28_absence_workflow_payroll_changes_report, docs_superpowers_plans_2026_09_28_absence_workflow_read_api [EXTRACTED 1.00]
- **Admin action form pages (act as you through a service)** — templates_checks_admin_ask, templates_checks_admin_complete, templates_documents_admin_issue, templates_documents_admin_supersede [INFERRED 0.85]
- **Checklist item completion surfaces posting to onboarding:complete** — templates_onboarding__checklist, templates_onboarding__todo_card, templates_onboarding_hr_detail_item_actions, onboarding_views_complete, onboarding_views_back [INFERRED 0.85]
- **Confirm on GET, act on POST pages** — templates_registers_admin_unpause, templates_registers_check_now, templates_training_admin_verify, templates_training_admin_reject, templates_training_reject [INFERRED 0.85]
- **Pre-start starter flow (gate, Getting started, self-service details)** — docs_superpowers_plans_2026_10_04_onboarding_documents_is_pre_start, docs_superpowers_plans_2026_10_04_onboarding_documents_prestartgate, docs_superpowers_plans_2026_10_04_onboarding_documents_getting_started_view, docs_superpowers_plans_2026_10_04_onboarding_documents_details_view, docs_superpowers_plans_2026_10_04_onboarding_documents_checklists_start [INFERRED 0.85]
- **Emailed password-link flow (invitation and reset)** — accounts_mail_send_password_link, templates_registration_invitation_email, templates_registration_invitation_subject, templates_registration_password_reset_email, templates_registration_password_reset_form, templates_registration_password_reset_done, templates_registration_password_reset_confirm [INFERRED 0.85]
- **Professional registration problem handling** — docs_guides_hr_administrator_professional_registrations, docs_guides_hr_administrator_check_now, docs_guides_hr_administrator_registration_failure_handling, docs_guides_hr_administrator_register_pause, docs_guides_manager_registration_problem_email [INFERRED 0.85]
- **Training compliance workflow (require, record, verify, report, remind)** — docs_guides_hr_administrator_course_requirements, docs_guides_hr_administrator_training_verification, docs_guides_hr_administrator_training_session, docs_guides_hr_administrator_training_matrix, docs_guides_hr_administrator_things_due_email [INFERRED 0.85]
- **Leave request approval flow (request, notify, queue, decide, outcome email)** — templates_absence_request, templates_absence_email_submitted, templates_absence_queue, templates_absence_decide, templates_absence_email_decided [INFERRED 0.85]
- **Morning compliance digest: sources, schedule and sent log** — docs_admin_compliance_reminders, docs_admin_compliance_reminder_settings, docs_admin_compliance_sent_log, docs_superpowers_specs_2026_10_05_professional_registrations_design_registration_due_items, docs_superpowers_specs_2026_10_25_training_compliance_design_training_due_items, docs_superpowers_specs_2026_10_04_onboarding_documents_design_digest [INFERRED 0.85]
- **Policy issue-and-sign flow** — templates_documents_admin_issue, templates_documents_policies, templates_documents_sign, static_documents_sign, documents_views_sign, documents_services_policies_sign [INFERRED 0.85]
- **Register fixture capture-to-verified flow** — registers_adapters_fixtures_readme_page_capture, registers_management_commands_registers_fetch, registers_management_commands_registers_parse, tests_test_registers_adapters, registers_services_nightly_sync_verified, registers_adapters_fixtures_readme_verified_body [INFERRED 0.85]
- **Registration lookup pipeline: fetch, parse, log, record check, alert** — docs_superpowers_specs_2026_10_05_professional_registrations_design_registers_http_get, docs_superpowers_specs_2026_10_05_professional_registrations_design_adapter_interface, docs_superpowers_specs_2026_10_05_professional_registrations_design_lookups_run, docs_superpowers_specs_2026_10_05_professional_registrations_design_lookup, docs_superpowers_specs_2026_10_05_professional_registrations_design_check_recording, docs_superpowers_specs_2026_10_05_professional_registrations_design_registration_due_items [INFERRED 0.85]
- **Pages rendered through the site FormRenderer (div.html + field.html)** — config_forms_formrenderer, templates_django_forms_div, templates_django_forms_field, templates_people_me, templates_registration_login, templates_registration_password_change_form, templates_registration_password_reset_confirm, templates_registration_password_reset_form [INFERRED 0.85]
- **TOIL claim approval flow (claim, notify, queue, decide, outcome email, TOIL card)** — templates_absence_toil_claim, templates_absence_email_toil_submitted, templates_absence_queue, templates_absence_toil_decide, templates_absence_email_toil_decided, templates_absence__toil_card [INFERRED 0.85]
- **Training self-record, verify or reject lifecycle** — templates_people__training, training_views_self_record, templates_training_person, training_services_training_verify, training_services_training_reject, templates_training_reject, templates_training_admin_verify, templates_training_admin_reject [INFERRED 0.85]
- **Self-recorded training verification flow** — docs_superpowers_specs_2026_10_25_training_compliance_design_self_record, docs_superpowers_specs_2026_10_25_training_compliance_design_to_verify, docs_superpowers_specs_2026_10_25_training_compliance_design_verify_reject, docs_superpowers_specs_2026_10_25_training_compliance_design_training_due_items, docs_admin_compliance_verifying [INFERRED 0.85]
- **Balances to ledger drill-down** — templates_absence_balances, templates_absence__balance_year, templates_absence_ledger, templates_absence_balances_ledger_drilldown [INFERRED 0.95]
- **Shared compliance status badge mapping (current ok; due soon, lapsed, missing warning)** — templates_people__checks, templates_people__training, templates_training_matrix, templates_training_person [INFERRED 0.95]

## Communities (212 total, 54 thin omitted)

### Community 0 - "people/models/__init__.py"
Cohesion: 0.03
Nodes (45): report_send(), DateInput, ContractInline, EmergencyContactInline, EmploymentInline, ContractForm, Meta, PositionForm (+37 more)

### Community 1 - "Absence Booking Tests"
Cohesion: 0.05
Nodes (109): summary(), _sync(), add_kit_day(), approve(), _booked_pot(), cancel(), check_family_dates(), _copy_back() (+101 more)

### Community 2 - "Year-End and TOIL Ledger"
Cohesion: 0.05
Nodes (89): AdjustForm, Command, adjust(), balance(), write(), earn(), _bookings(), close() (+81 more)

### Community 3 - "Absence Models and Types"
Cohesion: 0.02
Nodes (45): Migration, Migration, Migration, Migration, Migration, Migration, Migration, Migration (+37 more)

### Community 4 - "Test Factories"
Cohesion: 0.05
Nodes (94): Policy, Accrual, Basis, Meta, _starters(), policy_for(), _cap(), active_on() (+86 more)

### Community 5 - "TrainingRecord"
Cohesion: 0.14
Nodes (25): Training audit fields (recorded, self_recorded, verified, rejected, session_recorded, expires_on, certificate), Three kinds of training record: verified (counts), awaiting verification (pending), rejected, bls(), fire(), _manager(), media(), _pdf(), _receptionist() (+17 more)

### Community 6 - "Absence and Leave Docs"
Cohesion: 0.06
Nodes (64): Absence and leave (admin reference), Absence type, Accrual basis (daily / monthly twelfths), Accrues flag (earned vs accrued), Automatic bank-holiday absence row (Charge again), Balances page, Bank holiday handling (closed / pot / included in annual leave), Bank holidays and closed days calendar (+56 more)

### Community 7 - "Training Service"
Cohesion: 0.12
Nodes (34): Required courses: active everyone courses plus those the current primary position's title needs; no employment, nothing, bls(), fire(), _manager(), media(), _pdf(), _receptionist(), test_a_backdated_rejection_does_not_mark_a_current_course_but_a_later_one_does() (+26 more)

### Community 8 - "Registration Service Tests"
Cohesion: 0.16
Nodes (31): scheduled(), set_number(), _answer(), _by_body(), _gp(), _registration_check(), test_a_bad_number_is_refused_and_nothing_written(), test_a_body_the_title_no_longer_needs_does_not_hold_back_a_clear() (+23 more)

### Community 9 - "Absence Services Core"
Cohesion: 0.07
Nodes (23): Migration, seed(), Absence, Category, Meta, Status, KitDay, Meta (+15 more)

### Community 10 - "Register Adapter Tests"
Cohesion: 0.09
Nodes (28): lookup(), verified(), _page(), test_a_gp_register_value_other_than_a_known_yes_is_a_problem(), test_a_hit_without_a_name_is_unreadable_not_a_match(), test_a_known_gp_register_value_stays_clear(), test_a_no_results_page_is_not_found(), test_a_non_200_reply_carries_no_page_hash() (+20 more)

### Community 11 - "EmployeeAdmin"
Cohesion: 0.09
Nodes (14): Registration number formats and duplicate warning, Registrations service (numbers on people), Compliance tab Training table (Open, Verify or reject, or Record links), _as_of(), _day(), EmployeeAdmin, _link(), _table() (+6 more)

### Community 12 - "Checks Model and Service"
Cohesion: 0.08
Nodes (57): Check, DbsLevel, Meta, Outcome, CheckType, Evidence, Meta, _after() (+49 more)

### Community 13 - "Onboarding Pages Tests"
Cohesion: 0.05
Nodes (43): not_needed(), _contacts_summary(), set_emergency_contacts(), _asked_rtw(), cast(), _is_login(), media(), _starter() (+35 more)

### Community 14 - "Training Views and Forms"
Cohesion: 0.05
Nodes (39): lockout_response(), RequestPasswordLinkView, SetPasswordFromLinkView, Recording your own completion: pending until HR or your manager verifies it, Session form offers HR everyone employed today and a manager today's reports; the service checks the day held, download(), base.html (Site base layout), div.html (Site form layout) (+31 more)

### Community 15 - "README and Platform Docs"
Cohesion: 0.05
Nodes (68): PBS_PASSWORD_FILE, pbs-push.sh script, The read API for the rota (admin reference), GET /api/v1/absences, HR_API_TOKENS bearer tokens, GET /api/v1/patterns, GET /api/v1/people, Rota read API (/api/v1/) (+60 more)

### Community 16 - "Absence Calendar Tests"
Cohesion: 0.10
Nodes (40): days_for(), _halves(), _load(), _members(), month(), cell(), _off(), off_on() (+32 more)

### Community 17 - "TOIL and Approval View Tests"
Cohesion: 0.15
Nodes (30): _claim(), _form(), _people(), _stranger(), _stranger_post(), _stranger_queue(), test_a_claim_email_that_does_not_go_gives_the_link(), test_a_decided_claim_is_read_only() (+22 more)

### Community 18 - "Employee and Employment Tests"
Cohesion: 0.05
Nodes (40): AuditEntry, Kind, Meta, _email(), _label(), viewed(), _anniversary(), service_years() (+32 more)

### Community 19 - "test_account_mail.py"
Cohesion: 0.17
Nodes (14): link_expires(), _link_in(), _request(), test_a_refusing_relay_returns_the_link_and_the_reason(), test_a_reset_reads_as_a_reset(), test_a_signed_in_gp_is_not_named_as_the_contact(), test_an_invitation_goes_to_the_person_with_a_working_link(), test_email_is_configured_means_a_host_is_named() (+6 more)

### Community 20 - "Onboarding Checklist Tests"
Cohesion: 0.11
Nodes (48): Checklist, Meta, ChecklistTemplate, Meta, complete(), for_hr(), gaps(), end() (+40 more)

### Community 21 - "Document Files"
Cohesion: 0.08
Nodes (50): Every training file is a documents.File written by files.add and read through files.open, File, Category, Meta, _absolute(), add(), open(), _original_name() (+42 more)

### Community 22 - "training/services/due.py"
Cohesion: 0.21
Nodes (13): hr_admin_addresses(), due_items(), active_email(), DueItem, link(), state_by_date(), The line manager is told once, the first time a course lapses, naming the course, Missing training is owed from the employment start date (+5 more)

### Community 23 - "Onboarding Checklist Service"
Cohesion: 0.09
Nodes (32): Execution notes and rulings (2026-10-04), DueRule, Kind, add_item(), _already_met(), _anchor(), _auto_close(), _build() (+24 more)

### Community 24 - "Training Admin and Plan"
Cohesion: 0.06
Nodes (8): Training records admin: add through training.record, change only a verified record's expiry, Verify / Reject actions, never deleted, Reminder keys training:<employee>:<course code>:<due>:<status> and training:verify:<record>, CourseAdmin, _file_link(), AdminRejectForm, _Refusable, TrainingRecordAdmin, TrainingSessionAdmin

### Community 25 - "people/services/__init__.py"
Cohesion: 0.06
Nodes (8): Duplicated admin refusal guard (training/admin.py, checks/admin.py), DateInput, PolicyVersion, Meta, _limit(), _store(), _too_big(), Owed

### Community 26 - "documents.File (opaque path, SHA-256, superseded never deleted)"
Cohesion: 0.24
Nodes (12): documents download view (documents:download), documents.File model (categories, opaque path, sha256, superseded_by), files.add, files.open (access check and viewed audit), files.sniff (content sniffing), files.supersede, policies.issue, Policy, PolicyVersion and Signature models (+4 more)

### Community 27 - "Access Rules and Roles"
Cohesion: 0.08
Nodes (30): decides_at_once(), _own(), _closed(), _may_see_queue(), _closed(), Line manager keeps training and can_view rights outside employment, A line manager opens a report's training certificate and the attendance sheet of a session a report was at, My team Training column (counts and next expiry) and a Record a training session link (+22 more)

### Community 28 - "test_training_admin.py"
Cohesion: 0.28
Nodes (15): bls(), fire(), media(), _pdf(), _receptionist(), test_a_pending_record_is_view_only_and_a_post_to_it_writes_nothing(), test_an_expiry_before_the_date_done_is_a_message_and_changes_nothing(), test_the_add_page_records_through_the_service_and_stores_the_certificate() (+7 more)

### Community 29 - "Balance Views Tests"
Cohesion: 0.07
Nodes (39): after(), _nothing_yet(), rows(), _year(), bounds(), for_day(), lookup(), check() (+31 more)

### Community 30 - "Register Page Parsers"
Cohesion: 0.12
Nodes (15): GMC register adapter, classify(), find(), has_word(), name_near(), plain(), restriction(), status_value() (+7 more)

### Community 31 - "Passkey Reauth Tests"
Cohesion: 0.09
Nodes (23): Passkey, Meta, SoftAuthenticator, _enrol(), _post_json(), _reset_form(), _stale(), test_a_borrowed_session_cannot_add_one() (+15 more)

### Community 32 - "Passkey Registration and Reauth"
Cohesion: 0.10
Nodes (15): signed_in_recently(), confirm_password(), is_recent(), mark(), account(), ChangePasswordView, _credential_from(), _json_body() (+7 more)

### Community 33 - "Accrual Calculation Tests"
Cohesion: 0.10
Nodes (46): bank_holiday_entitlement(), daily_rates(), _days(), entitlement(), _rates(), _step(), tier_extra_weeks(), round_to() (+38 more)

### Community 34 - "config/forms.py"
Cohesion: 0.24
Nodes (3): BoundField, FormRenderer, field.html (Design-system field markup)

### Community 35 - "Foundation Domain Concepts"
Cohesion: 0.08
Nodes (38): Bank-holiday seeds 2029-2030 and the bank_holidays_seeded_to warning, Leaver audit note lists not-cancelled absences first (_cancel_after), Absence.cancel_reason and the bank-holiday opt-out (NOT_IMPLIED), bank_holidays.charge_again admin action, PolicyForm._check_year (leave-year lock on add), My absences always lists still-requested absences, Leaver's late TOIL claim lands on the pot of their last day (_pot_day), Recorded absence carries 'Recorded by <name>' (bookings.record) (+30 more)

### Community 36 - "Absence Policy Form Tests"
Cohesion: 0.10
Nodes (41): bank_holiday_summary(), _year_label(), bank_holidays_between(), _add(), _add_post(), _april_type_in_use(), _bank_holiday_policy(), _change() (+33 more)

### Community 37 - "check_employment"
Cohesion: 0.19
Nodes (8): check_employment(), EmploymentForm, Meta, check_amend(), check_end(), check_start(), _overlaps(), test_the_check_helpers_refuse_without_writing()

### Community 38 - "Checks Admin Actions"
Cohesion: 0.08
Nodes (7): CheckAdmin, CheckTypeAdmin, AskForm, CompleteForm, Meta, checks/admin/ask.html (Ask for evidence page), checks/admin/complete.html (Record the result page)

### Community 39 - "Absence Request and Admin Tests"
Cohesion: 0.11
Nodes (44): current_leave_year(), _auto_row(), _confirmed(), _form(), _in_this_year(), _me(), _report_and_manager(), test_a_manager_does_not_cancel_a_reports_automatic_row() (+36 more)

### Community 40 - "Policy Signing Tests"
Cohesion: 0.13
Nodes (36): Signature, Meta, Method, owed(), _assertion(), _enrol(), _policy(), _staff() (+28 more)

### Community 41 - "Request Chase"
Cohesion: 0.12
Nodes (17): _non_working_dates(), notify_once(), waiting(), _working_days_between(), _old_request(), test_a_bank_holiday_is_not_a_working_day(), test_a_closed_day_is_not_a_working_day(), test_a_retry_after_a_failure_stamps_once_email_works() (+9 more)

### Community 42 - "Registrations Admin Docs"
Cohesion: 0.08
Nodes (33): Health sensitive flag, Name does not match rule, Compliance and registrations lines in the nightly output, When a register page cannot be read (pausing and Unpause), Professional registrations (admin), Recording a check, Recording a registration number, Registration lookups log (read-only) (+25 more)

### Community 43 - "Read API Tests"
Cohesion: 0.10
Nodes (21): api(), _hit(), test_a_health_sensitive_type_is_always_sick_whatever_its_label(), test_a_partial_absence_carries_its_times(), test_absences_need_an_ordered_window(), test_another_address_is_counted_separately(), test_automatic_bank_holidays_are_not_returned(), test_declined_and_cancelled_are_not_returned() (+13 more)

### Community 44 - "Compliance Digest Design"
Cohesion: 0.08
Nodes (41): Reminder settings (start, every, overdue, registration days), Reminders (morning digest), The reminder sent log (compliance.ReminderSent), Training reminders, Training statuses (Current, Due soon, Lapsed, Missing, Awaiting verification, Not required), Attendance-sheet rule in can_view_file ignores hr_only, Matrix CSV formula guard misses leading tab or carriage return, Training reminder wording keyed by delivery value (+33 more)

### Community 46 - "Compliance Counts Tests"
Cohesion: 0.15
Nodes (30): ReminderSent, Meta, run(), _dbs_for_receptionists(), media(), _receptionist(), _rtw_asked(), test_a_failed_send_is_recorded_and_not_logged_as_sent() (+22 more)

### Community 47 - "Absence Admin Tests"
Cohesion: 0.09
Nodes (28): _auto_row(), _decided_claim(), _family_absence(), _open_pot(), _opted_out(), _policy_data(), _policy_post(), test_a_manager_does_not_cancel_from_the_admin() (+20 more)

### Community 48 - "Passkeys and Reauth"
Cohesion: 0.14
Nodes (13): complete_registration(), _could_not_verify(), login_options(), origin(), PasskeyError, reauth_options(), registration_options(), rp_id() (+5 more)

### Community 49 - "adapters/__init__.py"
Cohesion: 0.09
Nodes (11): url(), Command, test_urls_carry_the_number_and_only_the_number(), _bold(), test_registers_fetch_saves_what_the_app_fetches_and_prints_only_the_status_and_size(), test_the_guides_name_the_ui_labels_that_exist(), test_the_admin_guide_has_a_training_section_with_every_part(), test_the_backlog_closes_the_item_and_parks_the_rest() (+3 more)

### Community 50 - "names.py"
Cohesion: 0.27
Nodes (5): surnames_match(), _tokens(), _without_particles(), _without_post_nominals(), _words()

### Community 51 - "People Test Factories"
Cohesion: 0.07
Nodes (19): _employment_add(), _employment_base(), test_a_login_whose_email_differs_from_the_work_email_is_warned_about(), test_a_past_spell_can_be_added_before_a_current_one(), test_an_added_spell_keeps_its_end_date_and_reason(), test_an_overlapping_add_is_shown_on_the_form_not_a_500(), test_an_overlapping_spell_on_the_employee_page_is_shown_on_its_row(), test_audit_log_is_read_only() (+11 more)

### Community 52 - "accounts/views.py"
Cohesion: 0.06
Nodes (9): EmailFailure, Meta, ToilClaim, Meta, calendar_view(), _month(), _shift(), email_is_configured() (+1 more)

### Community 53 - "Training Matrix"
Cohesion: 0.08
Nodes (29): Training matrix (filters, Problems only, CSV download), Matrix CSV download (one row per person, 'Status, date' cells, no note, filters and date in the filename), Training matrix: people employed today down, courses needed or held across, filtered by course, team, name and show, make_position(), test_a_title_is_a_row_and_a_position_points_at_it(), test_get_or_create_is_case_sensitive_and_unique(), test_renaming_a_title_moves_every_position_with_it(), test_the_api_still_sends_the_title_as_text() (+21 more)

### Community 54 - "Specs and Backlog Index"
Cohesion: 0.16
Nodes (19): Backlog, Breathe CSV import, Certificate pack download (zip for inspection), Excluded on purpose (spec Not done), Opening balances carry-in screen, Rota integration (spec 2), Known limitations left for a follow-up, Tidy-up plan: follow-ups from plans 1-3 and the TOIL work (+11 more)

### Community 55 - "Bank Holiday Sync"
Cohesion: 0.15
Nodes (19): charge_again(), sync_auto_absences(), _open(), test_a_cancelled_automatic_row_stays_cancelled(), test_a_row_the_sync_cancelled_comes_back_when_implied_again(), test_a_shorter_monday_re_costs_future_monday_bank_holidays_only(), test_charge_again_brings_the_automatic_row_back_at_once(), test_charge_again_leaves_a_day_no_longer_implied_uncharged() (+11 more)

### Community 56 - "OIDC Provider Tests"
Cohesion: 0.11
Nodes (15): _b64url_json(), _register(), _signed_in_flow(), test_a_client_someone_owns_is_never_taken_over(), test_a_sign_out_to_an_unregistered_address_is_refused(), test_an_inactive_login_cannot_refresh(), test_client_management_is_not_mounted(), test_post_logout_redirect_defaults_to_the_rota_login() (+7 more)

### Community 57 - "test_seed_demo.py"
Cohesion: 0.05
Nodes (23): InviteForm, Meta, User, Meta, existing_for(), _hours(), Person, _sessions() (+15 more)

### Community 58 - "Axes Lockout Tests"
Cohesion: 0.17
Nodes (16): _login(), _make(), test_a_passkey_sign_in_clears_only_its_own_account(), test_a_single_account_is_still_locked_after_repeated_failures(), test_a_spoofed_header_cannot_be_rotated_to_evade_the_limit(), test_a_success_clears_the_signed_in_persons_own_failures_everywhere(), test_an_account_holder_cannot_reset_a_colleagues_counter(), test_an_unrelated_address_is_not_caught_by_someone_elses_lockout() (+8 more)

### Community 59 - "Login Import Tests"
Cohesion: 0.22
Nodes (22): _counts(), _file(), _login(), _run(), test_a_file_not_of_the_documented_shape_is_refused(), test_a_hash_this_system_cannot_check_is_refused_as_such(), test_a_login_already_linked_is_left_as_it_is(), test_a_missing_file_is_refused() (+14 more)

### Community 60 - "Auto Login Tests"
Cohesion: 0.14
Nodes (22): _messages(), post(), _post(), _run(), relay(), test_a_change_post_cannot_smuggle_the_login_fields(), test_a_failed_send_keeps_the_login_and_shows_the_link(), test_a_failed_send_logs_no_address() (+14 more)

### Community 61 - "CI Workflow"
Cohesion: 0.07
Nodes (29): ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, DEBUG, DEFAULT_FROM_EMAIL, EMAIL_HOST, HR_API_TOKENS, OIDC_RSA_PRIVATE_KEY, SECRET_KEY (+21 more)

### Community 62 - "ChecklistItem"
Cohesion: 0.08
Nodes (33): pre_start(), AddItemForm, BaseEmergencyContactFormSet, contact_formset(), DetailsForm, Meta, EmergencyContactForm, pre_start() (+25 more)

### Community 63 - "Onboarding Admin"
Cohesion: 0.08
Nodes (7): ChecklistAdmin, ChecklistItemInline, ChecklistTemplateAdmin, TemplateItemInline, link_problem(), TemplateItem, Meta

### Community 64 - "approvals.py"
Cohesion: 0.10
Nodes (10): DecisionForm, KitDayForm, PayrollPeriodForm, ToilClaimForm, TypeSelect, claims_for(), _may_open(), queue_for() (+2 more)

### Community 65 - "run"
Cohesion: 0.14
Nodes (8): Command, month(), run(), payroll_view(), payroll.html (Payroll changes page), Monthly payroll changes run, test_view_lists_runs_and_rejects_a_bad_period(), test_the_payroll_starters_sheet_carries_bank_details()

### Community 66 - "Course"
Cohesion: 0.09
Nodes (26): Course delivery: online (self-record needs the certificate) or face to face (usually a session), A Course says who needs it (position titles, or required of everyone) and how long it lasts, Reminder wording by delivery ('complete the e-learning and upload your certificate' / 'ask your manager about the next session'), Ten seeded courses (basic life support, fire safety, IG, IPC, safeguarding, E&D, H&S, conflict resolution, chaperone), Training app architecture (Course, append-only TrainingRecord, TrainingSession on the shared compliance pieces), can_view_file(), _cast(), media() (+18 more)

### Community 67 - "Compliance Admin Docs"
Cohesion: 0.07
Nodes (42): Compliance (admin reference), Asking the person for evidence, Check statuses (Current, Due soon, Lapsed, Missing, Awaiting, Not required), Check types (titles, validity, evidence, remind person), Checklist gaps, Checklist item links (details, upload, sign_policies, check), Starter and leaver checklists, The Compliance card (seven numbers) (+34 more)

### Community 68 - "getting_started"
Cohesion: 0.08
Nodes (23): asked_of(), access.can_view_checks, access.can_view_file, Getting started page view (onboarding:getting_started), access.is_pre_start, PreStartGate middleware, A starter records training from Getting started before day one (/training/ allowed through the pre-start gate), Compliance access rules (people/services/access.py) (+15 more)

### Community 69 - "Colour Palette Engine"
Cohesion: 0.11
Nodes (18): base(), _between(), _ordered(), primary(), token(), _build(), contrast_ratio(), hex_to_rgb() (+10 more)

### Community 70 - "Professional registration checks implementation plan"
Cohesion: 0.09
Nodes (16): run(), compliance nightly step (compliance.services.nightly.run), Professional registration checks implementation plan, Register page fixture capture guide, registers app architecture, registers_fetch command, registers_parse management command, Registration: one per person per body (+8 more)

### Community 71 - "Absence Costing Tests"
Cohesion: 0.23
Nodes (17): cost(), cost_between(), halves_covered(), _policy(), absence(), test_automatic_bank_holiday_is_charged_whatever_its_own_policy_handling_says(), test_bank_holiday_closed_not_charged(), test_closed_day_never_charged() (+9 more)

### Community 72 - "Ops Hardening and Settings"
Cohesion: 0.10
Nodes (11): _dev_secret_key(), _oidc_private_key(), main(), access(), _settings_value(), test_a_csrf_failure_reaches_the_security_log(), test_a_password_links_token_never_reaches_the_log(), test_an_authorization_code_never_reaches_the_log() (+3 more)

### Community 73 - "pytest"
Cohesion: 0.10
Nodes (46): approve(), cancel(), claim(), _copy_back(), _decidable(), decline(), _lock(), _claim() (+38 more)

### Community 74 - "Foundation Plan"
Cohesion: 0.11
Nodes (10): Validator, backup.sh script, Notification routing: routed manager's work email or every active HR admin, Practice HR foundation implementation plan, Deployment: gunicorn on loopback 8322, nightly timer 01:30, backup with media, django-oauth-toolkit, django-unfold admin, HR admin role (is_hr_admin) (+2 more)

### Community 75 - "App Roles"
Cohesion: 0.18
Nodes (19): AppRole, Meta, _apps_heading(), _client(), _save(), test_a_role_reads_as_who_on_what(), test_a_superuser_can_set_it_too_and_an_hr_admin_never_reaches_a_superusers(), test_an_existing_user_role_is_ticked_to_admin() (+11 more)

### Community 76 - "Lookup"
Cohesion: 0.17
Nodes (8): Lookup outcomes: clear, problem, not_found, name_mismatch, unreadable, Lookup, Meta, Outcome, Trigger, check_now(), registers/check_now.html (Check registration now confirm), test_the_label_comes_from_the_lookup_with_fallbacks_for_empty_words()

### Community 77 - "Register Due Items Tests"
Cohesion: 0.20
Nodes (20): run(), _gp(), _items(), _manager(), test_a_changed_number_drops_the_old_numbers_alert_until_the_new_one_is_looked_up(), test_a_clear_result_and_a_fresh_registration_produce_nothing(), test_a_leaver_and_an_unneeded_body_raise_nothing(), test_a_missing_number_is_hrs_from_the_employment_start() (+12 more)

### Community 78 - "Absence Ledger Plan"
Cohesion: 0.10
Nodes (12): BankHolidays, _target_type(), _check_leave_year(), _skip(), bounds(), _safe_date(), Absence ledger implementation plan, Bank-holiday handling modes (closed not charged / pro-rata pot / included in annual) (+4 more)

### Community 79 - "Payroll Report Tests"
Cohesion: 0.13
Nodes (25): _absences(), _balance(), build(), _leavers(), _name(), _toil(), make_pot(), _cells() (+17 more)

### Community 80 - "Client IP and CSP Middleware"
Cohesion: 0.14
Nodes (11): client_ip(), _request(), test_a_forwarded_header_from_anywhere_else_is_ignored(), test_axes_is_wired_to_this_resolver(), test_ipv6_is_supported_and_normalised(), test_junk_in_the_header_falls_back_rather_than_being_stored(), test_no_header_falls_back_to_the_peer_address(), test_the_forwarded_address_is_used_when_it_comes_from_the_tunnel() (+3 more)

### Community 81 - "digest.py"
Cohesion: 0.25
Nodes (4): _body(), _when(), A pending record silences the person and asks HR to verify ('to verify, uploaded <date>'), email/compliance_digest.txt (Compliance digest email)

### Community 82 - "Deploy and PBS Tests"
Cohesion: 0.10
Nodes (12): _database_name(), _service_directives(), _setting(), test_db_path_moves_the_database(), test_gunicorn_keeps_only_the_state_directory_writable(), test_media_root_moves_into_the_state_directory(), test_production_environment_sets_media_root_in_the_state_directory(), test_the_pbs_push_script_is_executable_and_valid_shell() (+4 more)

### Community 83 - "Retention Report Tests"
Cohesion: 0.09
Nodes (20): _retention_days(), Training records retention category (RETENTION_DAYS training, 2190 days), due(), retention_report(), people/retention.html (Retention report), _left(), _settings_run(), test_a_category_is_due_only_after_its_last_day() (+12 more)

### Community 84 - "Absence Admin Actions"
Cohesion: 0.11
Nodes (3): AbsenceAdmin, admin/cancel_absence.html (Cancel absence confirm), admin/charge_again.html (Charge bank holiday again confirm)

### Community 85 - "App Configs"
Cohesion: 0.10
Nodes (6): ChecksConfig, ComplianceConfig, DocumentsConfig, PeopleConfig, RegistersConfig, TrainingConfig

### Community 86 - "Policy Issue and Sign"
Cohesion: 0.14
Nodes (12): Policy, Meta, confirmation(), current(), issue(), sign(), signable(), test_a_starter_who_signed_everything_before_the_build_is_done_automatically() (+4 more)

### Community 87 - "Absence Notifications"
Cohesion: 0.17
Nodes (16): record_failure(), send(), absence_cancelled(), approver_addresses(), claim_decide_url(), claim_decided(), claim_submitted(), _claim_unit() (+8 more)

### Community 88 - "mine"
Cohesion: 0.08
Nodes (21): RequestForm, team(), _bank_groups(), cancel(), _fields(), kit_day(), _leave_year(), _may_cancel() (+13 more)

### Community 89 - "Navigation and Email Case Tests"
Cohesion: 0.32
Nodes (7): _approver_of(), _employee(), _split(), test_an_approver_also_sees_approvals(), test_an_employee_sees_leave_calendar_and_balances_but_not_approvals(), test_an_hr_admin_sees_approvals_and_admin(), test_the_mobile_tab_bar_holds_at_most_five_items()

### Community 90 - "Register Admin and Unpause"
Cohesion: 0.12
Nodes (6): RegisterBody (bodies a position title needs), Four seeded register bodies (GMC, Welsh list, NMC, GPhC), LookupAdmin, RegisterBodyAdmin, Migration, seed()

### Community 91 - "Policy Signing Views"
Cohesion: 0.09
Nodes (18): Employee admin Compliance tab, policies.applies_to, Policies page view (documents:policies), policies.state, SignForm, applies_to(), due(), _employment() (+10 more)

### Community 92 - "Absence Workflow Plan"
Cohesion: 0.16
Nodes (12): Kind, Balance summary (entitlement, carried in, taken, booked, pending, expired, adjustments, remaining), Deferred to plan 3 (carry-over, expiry, TOIL earned, year end, chase, calendar, request pages, payroll, API), LedgerEntry kinds (entitlement, revision, carry-in, expiry, booking, cancellation, TOIL earned/taken, adjustment), Absence workflow, payroll and API implementation plan, Admin dashboard card (waiting requests, email not configured), Carry-in expiry after carry_over_expires_after_days, Family-leave dates and KIT days (+4 more)

### Community 93 - "unit"
Cohesion: 0.12
Nodes (15): _row(), may_cancel(), position(), step(), _toil(), cancel(), claim(), claim_for() (+7 more)

### Community 94 - "test_training_sessions.py"
Cohesion: 0.09
Nodes (17): A face-to-face session recorded once: one verified record per attendee and one shared attendance sheet, _is_docx(), sniff(), bls(), media(), _team(), test_a_manager_records_a_session_for_their_own_reports(), test_a_session_makes_one_verified_record_per_attendee_sharing_the_sheet() (+9 more)

### Community 95 - "test_registers_pages.py"
Cohesion: 0.16
Nodes (23): Result, _change_post(), _count(), _gp(), gp_bodies(), quiet(), test_a_bad_number_is_a_form_error_and_blank_clears_it(), test_a_clear_then_an_unreadable_page_names_the_day_it_was_read() (+15 more)

### Community 96 - "NI Number Normalising"
Cohesion: 0.12
Nodes (14): EmployeeForm, Meta, accept_typed(), normalise(), _ni(), _store(), test_a_whitespace_only_ni_number_becomes_blank_and_is_not_reported(), test_my_record_with_a_stale_bad_ni_number_shows_an_error_not_a_500() (+6 more)

### Community 97 - "Shared Validity Helpers"
Cohesion: 0.13
Nodes (13): _status(), expires_from(), status(), Expiry adds calendar months clipped to the month end; a blank validity never expires, WINDOW_DAYS = 60 due-soon window (the reminder schedule's start_days_before overrides), Shared validity helpers move into compliance/validity.py (Task 1), Training statuses and labels (Current, Due soon, Lapsed, Missing, Not required, Awaiting verification; PROBLEMS), Status rule: not_required, missing, current, due_soon (window, today included), lapsed (+5 more)

### Community 98 - "HR-Only Sign-In Plan"
Cohesion: 0.12
Nodes (19): API fixed-window rate limit (API_RATE_LIMIT_PER_MINUTE, 429), Employee.work_email help text correction, admin OIDC claim (Validator.get_additional_claims), AppRole (per-application admin flag on the HR login), Break-glass: remove PRACTICE_HR_URL and restart the rota, export_logins management command (rota), Sign-in through HR only (PRACTICE_HR_URL set): rota passwords and passkeys closed, import_logins management command (HR) (+11 more)

### Community 99 - "OIDC Signing Key"
Cohesion: 0.17
Nodes (15): oidc_signing_key(), _env(), _pem(), _rsa_pem(), _settings(), test_a_good_key_passes(), test_a_key_that_is_not_rsa_fails(), test_a_named_file_that_cannot_be_read_stops_the_app() (+7 more)

### Community 100 - "ChecklistTemplate, TemplateItem, Checklist and ChecklistItem models"
Cohesion: 0.13
Nodes (25): Employee bank details and the payroll Starters sheet columns, ChecklistTemplate, TemplateItem, Checklist and ChecklistItem models, checklists.complete, not_needed and may_complete, checklists.gaps (set-up problems recorded at build), checklists.linked_done, checklists.start / leave (_build), checklists.summary, compliance_counts (admin dashboard Compliance card) (+17 more)

### Community 101 - "CSP Tests"
Cohesion: 0.13
Nodes (11): _policy(), _templates(), test_app_pages_carry_the_policy(), test_form_action_is_self_alone_with_no_client(), test_form_action_lets_sign_in_and_sign_out_finish_at_the_rota(), test_no_template_has_inline_script_or_handlers(), test_rendered_pages_hold_no_inline_script(), test_the_admin_renders_and_is_left_alone() (+3 more)

### Community 102 - "Employment Admin Validation"
Cohesion: 0.10
Nodes (12): ContractInlineFormSet, EmploymentInlineFormSet, PositionInlineFormSet, _rows(), check_add(), check_end(), _unit_clash(), check_add() (+4 more)

### Community 103 - "Guide for HR administrators"
Cohesion: 0.11
Nodes (31): Admin guide index, Guide for HR administrators, Asking someone for evidence, Self-closing checklist items (What ticks itself off), Admin home Compliance card (seven numbers), Who needs a course (Required of everyone or Positions), When emails do not go (Email failures), HR administrator role (+23 more)

### Community 104 - "Accounts Views and Mail"
Cohesion: 0.14
Nodes (4): check_available(), is_superuser(), _item(), _nav_item()

### Community 105 - "test_absence_approval_views.py"
Cohesion: 0.17
Nodes (22): _decide(), _setup(), test_a_cancelled_request_reads_as_cancelled(), test_a_double_post_shows_the_read_only_page_and_writes_nothing(), test_a_non_approver_has_no_waiting_count(), test_a_refused_decision_shows_why_and_tells_nobody(), test_a_routed_approver_sees_a_decided_request_read_only(), test_a_stranger_gets_403_on_a_decided_request_too() (+14 more)

### Community 106 - "ReminderSchedule"
Cohesion: 0.08
Nodes (18): ReminderScheduleAdmin, ReminderSchedule, Meta, _collect(), pending(), should_send(), Check professional registrations every (days) setting, jitter() (+10 more)

### Community 107 - "Absence Admin Registry"
Cohesion: 0.11
Nodes (7): AbsenceTypeAdmin, BankHolidayAdmin, ClosedDayAdmin, EmailFailureAdmin, PotAdmin, ToilClaimAdmin, Emails that did not go list

### Community 108 - "Command"
Cohesion: 0.12
Nodes (3): address(), Command, parse_base()

### Community 109 - "Ledger Page and Balances"
Cohesion: 0.13
Nodes (14): balances_for(), balances_view(), _filters(), ledger_view(), _links(), _render(), _rows(), Balances for this leave year and next, linked to ledger lines (+6 more)

### Community 110 - "Security Middleware"
Cohesion: 0.12
Nodes (4): ContentSecurityPolicyMiddleware, PrivatePagesMiddleware, _relying_party_origins(), RequestLogMiddleware

### Community 111 - "FileAdmin"
Cohesion: 0.05
Nodes (10): FileAdmin, PolicyAdmin, PolicyVersionInline, SignatureAdmin, IssueForm, SupersedeForm, UploadForm, Meta (+2 more)

### Community 112 - "Policy Admin Display"
Cohesion: 0.14
Nodes (5): as_days(), mode(), plain(), _policy_snapshot(), PolicyAdmin

### Community 113 - "compliance_people"
Cohesion: 0.12
Nodes (15): compliance_counts(), compliance_people(), dashboard(), owed_status(), Registration problems dashboard count, Dashboard numbers Training lapsed or missing and Training to verify open the matrix (MATRIX_SHOW), to_verify: pending records of people employed today, oldest first, still_chased() (+7 more)

### Community 114 - "Passkeys JavaScript"
Cohesion: 0.29
Nodes (14): armConditional(), b64urlToBytes(), bytesToB64url(), cancelConditional(), creationOptions(), credentialToJSON(), csrfToken(), enrol() (+6 more)

### Community 115 - "Form Rendering Tests"
Cohesion: 0.22
Nodes (10): Demo, _field_div(), test_a_checkbox_sits_inside_its_label(), test_a_single_field_group_uses_the_same_template(), test_dates_times_numbers_and_short_text_are_short(), test_errors_are_alerts_and_mark_the_field_invalid(), test_every_field_is_wrapped_labelled_without_a_colon_and_helped(), test_radios_keep_their_row_and_hidden_fields_are_rendered_once() (+2 more)

### Community 116 - "Training compliance implementation plan (spec 4)"
Cohesion: 0.11
Nodes (10): Training compliance implementation plan (spec 4), Admin record list status filter: pending / verified / rejected, with a name search, Awaiting verification replaces missing or lapsed while a pending record waits, The latest counting record by done_on is the one that counts (a renewal wins), Pre-commit verification (task tests, ruff check, makemigrations --check; whole suite before the final commit), set_expiry: HR's one edit after the fact, the expiry of a verified record (audited), Subagent-driven execution on feature/training-compliance (implementer and review per task; 1596 passed, 1 skipped), StatusFilter (+2 more)

### Community 117 - "state"
Cohesion: 0.09
Nodes (21): _asked(), _latest(), required_for(), Row, state(), summary(), _back(), upload() (+13 more)

### Community 118 - "current"
Cohesion: 0.13
Nodes (3): current(), by_name(), TestSeeded

### Community 119 - "People Admin Classes"
Cohesion: 0.17
Nodes (5): AuditEntryAdmin, ContractTypeAdmin, PositionTitleAdmin, TeamAdmin, WorkingPatternAdmin

### Community 120 - "Policy Forms"
Cohesion: 0.12
Nodes (10): _hours_chosen(), PolicyForm, governing(), in_force(), Meta, PolicyTierForm, Meta, _Stores (+2 more)

### Community 121 - "http.py"
Cohesion: 0.13
Nodes (8): FetchError, get(), user_agent(), test_lookup_matches_the_name_hashes_the_page_and_never_raises(), boom(), test_the_user_agent_names_the_practice(), test_registers_fetch_refuses_a_bad_number_and_reports_a_failed_fetch(), down()

### Community 122 - "decide"
Cohesion: 0.10
Nodes (21): _hours(), off_chip(), off_title(), status_tone(), units(), when(), _balance(), decide() (+13 more)

### Community 123 - "Deploy Checks and Login Hooks"
Cohesion: 0.27
Nodes (5): AccountsConfig, on_login(), site_url(), test_check_quiet_with_a_site_url_or_in_debug(), test_check_warns_when_site_url_is_unset_outside_debug()

### Community 124 - "API Token Auth"
Cohesion: 0.22
Nodes (4): _over_limit(), wrapped(), _valid(), API hardening (hmac token compare, csrf_exempt, no-store, hr.W001)

### Community 125 - "send_password_link"
Cohesion: 0.14
Nodes (6): password_link(), send_password_link(), _stamp(), invitation_subject.txt (Invitation email subject), password_reset_email.txt (Password reset email body), password_reset_subject.txt (Password reset email subject)

### Community 126 - "Positions and Reporting Line"
Cohesion: 0.25
Nodes (12): add(), end(), on(), primary_on(), _title(), test_add_and_primary_on(), test_cycle_refused(), test_end_position() (+4 more)

### Community 127 - "Docs Link Checker"
Cohesion: 0.19
Nodes (5): _anchors(), _links(), _slug(), test_every_relative_link_and_anchor_resolves(), test_the_link_checker_catches_a_broken_anchor()

### Community 128 - "RegisterBody (gmc, mpl_wales, nmc, gphc)"
Cohesion: 0.15
Nodes (16): Register bodies admin (Positions, Active, Verified, Paused), GMC full-register download service, Later: sickness case management, appraisals, restricted case files, Welsh medical performers list URL (plain http, unverified), General Medical Council (GMC), GMC full-register download service (not done), General Pharmaceutical Council (GPhC), Lookup (append-only register lookup log) (+8 more)

### Community 129 - "Check Record Form"
Cohesion: 0.24
Nodes (3): RecordForm, Meta, _Result

### Community 132 - "Rota Read API"
Cohesion: 0.20
Nodes (11): token_required(), absences(), _bad_request(), _iso(), patterns(), people(), Bearer token auth from HR_API_TOKENS, accounts app copied from the rota at commit f1cdc4d (+3 more)

### Community 133 - "TOIL Views and Ops Tests"
Cohesion: 0.27
Nodes (8): admin_client(), configured(), employee_client(), employee_user(), hr_admin(), no_seeded_policies(), _oidc_test_key(), superuser_client()

### Community 134 - "HR Admin Site and Backend"
Cohesion: 0.13
Nodes (4): HrAdminBackend, _is_hr_admin(), HrAdminSite, is_hr_admin()

### Community 135 - "get_or_create"
Cohesion: 0.12
Nodes (26): start(), get_or_create(), media(), _overdue_policy(), _receptionist(), test_a_starter_s_checks_are_shown_as_they_will_stand_on_day_one(), test_a_tab_with_no_checks_is_not_audited_and_the_checks_list_is_not(), test_compliance_counts() (+18 more)

### Community 141 - "Entitlement Resync Signals"
Cohesion: 0.23
Nodes (4): AbsenceConfig, _contract_saved(), _employment_saved(), resync_employment()

### Community 142 - "Login Import Command"
Cohesion: 0.25
Nodes (3): _client(), Command, _read()

### Community 143 - "reject"
Cohesion: 0.17
Nodes (12): training.verify/reject pending check without a lock, Verify makes a pending record count; Reject needs a note and emails the person, My team Training cards and person training page, training.record (HR or line manager, verified at creation), record_session (one transaction per group session), training.verify and training.reject, email/training_rejected.txt (Training record rejected email), training/admin/reject.html (Admin turn down training record) (+4 more)

### Community 144 - "test_absence_nightly.py"
Cohesion: 0.07
Nodes (31): bank_holiday_pot_used(), entitlement_lines_total(), resync_contract_type(), sync_entitlement(), _open_pots(), _pot_covering(), _reported(), run() (+23 more)

### Community 145 - "update"
Cohesion: 0.14
Nodes (10): create_for_employee(), diff(), update(), test_the_service_refuses_a_login_linked_elsewhere_and_writes_nothing(), test_update_audits_only_changed_fields(), test_update_refuses_unknown_field(), test_bank_formats_take_ascii_digits_only_and_nothing_after_the_end(), test_the_format_validators_refuse_a_trailing_newline() (+2 more)

### Community 147 - "amend"
Cohesion: 0.14
Nodes (5): EmploymentAdmin, amend(), add(), amend(), test_amend_refuses_a_start_date_overlapping_an_earlier_spell()

### Community 148 - "OIDC Claims Tests"
Cohesion: 0.36
Nodes (6): _app(), _claims(), test_claims_carry_email_and_employee_id(), test_claims_without_employee(), test_no_role_is_no_admin(), test_the_admin_claim_is_the_login_s_role_in_the_requesting_app()

### Community 150 - "_Text"
Cohesion: 0.16
Nodes (7): Adapter registry and Result dataclass, Shared fetch, parse and name-check flow, GPhC register adapter, Welsh medical performers list adapter, NMC register adapter, _Text, parse()

### Community 152 - "Training Admin Navigation"
Cohesion: 0.40
Nodes (6): training is an HR app with Courses, Training records, Training sessions and Training matrix in the Compliance sidebar, navigation(), test_compliance_sidebar_lists_check_types_and_checks(), test_reminder_settings_in_the_compliance_sidebar(), test_the_matrix_is_in_the_compliance_sidebar(), test_the_app_is_an_hr_app_with_its_courses_in_the_compliance_sidebar()

### Community 153 - "due_items"
Cohesion: 0.16
Nodes (7): Unreadable for 14 days alert, due_items(), _label(), _unreadable_since(), latest_readable(), run_start(), words()

### Community 154 - "test_training_due.py"
Cohesion: 0.27
Nodes (12): bls(), fire(), _items(), _manager(), media(), _receptionist(), test_a_face_to_face_course_asks_about_the_next_session(), test_a_leaver_and_a_not_required_course_produce_nothing() (+4 more)

### Community 155 - "Lookups service (run and scheduled)"
Cohesion: 0.19
Nodes (6): Register pause after three unreadable lookups (Unpause), Lookups service (run and scheduled), _due(), _pause_if_dead(), unpause(), registers/admin/unpause.html (Unpause register body confirm)

### Community 156 - "Part B — The prompt"
Cohesion: 0.14
Nodes (13): 1. Background you need, 2. How to run the interview, 3. Interview plan, 4. Leave calculation worked examples (non-negotiable), 5. What to write at the end, How to use this, Part A — For the practice manager (read this first), Part B — The prompt (+5 more)

### Community 157 - "NI Number Migration"
Cohesion: 0.40
Nodes (3): Migration, normalise(), normalise_ni_numbers()

### Community 158 - "Registration"
Cohesion: 0.12
Nodes (13): RegisterBody, Meta, Registration, Meta, test_a_registration_is_one_per_person_per_body(), test_admin_lists_render_and_bodies_cannot_be_deleted_or_added(), test_deleting_a_registration_removes_its_lookups(), test_the_body_page_shows_verified_and_paused_read_only() (+5 more)

### Community 159 - "me"
Cohesion: 0.18
Nodes (9): My record Training card with one self-record form (a course select), A person's training page /training/<pk>/ (note, record form and Verify / Reject for those who may record), me(), PersonalDetailsForm, Meta, _show_record_error(), Row, rows() (+1 more)

### Community 160 - "Standard Contract Seed"
Cohesion: 0.50
Nodes (3): _as_seeded(), Migration, seed()

### Community 163 - "numbers.py"
Cohesion: 0.21
Nodes (6): add_error(), check(), label(), normalise(), test_a_number_in_the_wrong_format_is_refused_with_the_format_in_words(), test_numbers_are_normalised_before_the_format_is_checked()

### Community 164 - "LinkToCopy"
Cohesion: 0.20
Nodes (5): LinkToCopy, test_a_connection_failure_is_a_reason_too(), test_a_failed_public_send_does_not_start_the_throttle(), refuse(), test_any_failure_in_sending_is_a_link_to_copy_not_a_crash()

### Community 165 - "Register page fixtures README"
Cohesion: 0.29
Nodes (6): Register page fixtures README, Fixture file naming by outcome (clear, problem*, not_found, unreadable), Capturing a register page (registers_fetch or curl), Fixture sidecar files (.surname, .number), Verified register body (clear, not_found and problem fixtures), Welsh performers list row layout (mpl_wales)

### Community 170 - "_cancel_after"
Cohesion: 0.18
Nodes (6): Ending an employment cancels live absences after the leaving date, hr_nightly runs every app's nightly job, Command, _cancel_after(), run(), test_leaver_login_disabled_returner_kept()

### Community 171 - "linked_done"
Cohesion: 0.19
Nodes (9): ADDED_HOOKS (files), OnboardingConfig.ready (hook registration), SIGNED_HOOKS (policies), OnboardingConfig, linked_done(), on_check_recorded(), on_file_added(), on_policy_signed() (+1 more)

### Community 172 - "send_passkey_added"
Cohesion: 0.22
Nodes (4): send_passkey_added(), SetPasswordFromLinkForm, passkey_added_email.txt (Passkey added notice), passkey_added_subject.txt (Passkey added subject)

### Community 175 - "django_contrib_auth"
Cohesion: 0.11
Nodes (4): test_a_saved_address_keeps_its_local_part_but_not_a_shouted_domain(), test_lockout_attempts_share_one_counter_across_case_variants(), test_the_invite_form_refuses_a_case_variant_of_an_existing_address(), test_two_accounts_cannot_differ_by_case_alone()

### Community 177 - "api_tokens"
Cohesion: 0.40
Nodes (4): api_tokens(), test_check_quiet_in_debug(), test_check_quiet_with_a_token(), test_check_warns_when_no_tokens_outside_debug()

## Ambiguous Edges - Review These
- `Going live: first month checklist` → `Hand-entered carry-overs (shell)`  [AMBIGUOUS]
  docs/guides/hr-administrator.md · relation: conceptually_related_to
- `Training (admin)` → `Who can open a file`  [AMBIGUOUS]
  docs/admin/compliance.md · relation: conceptually_related_to
- `policies.sign` → `Signing with re-authentication (password or passkey)`  [AMBIGUOUS]
  docs/superpowers/plans/2026-10-04-onboarding-documents.md · relation: implements

## Knowledge Gaps
- **45 isolated node(s):** `PBS_PASSWORD_FILE`, `Compliance tab Training table (Open, Verify or reject, or Record links)`, `Hide rota invitation and reset buttons while HR sign-in is on`, `Send invitation again from the employee page`, `Expired session clearing (hr-clearsessions.timer)` (+40 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1465 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **54 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `make_employee()` connect `Employee and Employment Tests` to `people/models/__init__.py`, `Absence Booking Tests`, `Test Factories`, `TrainingRecord`, `get_or_create`, `Registration Service Tests`, `Training Service`, `EmployeeAdmin`, `Checks Model and Service`, `Onboarding Pages Tests`, `Absence Calendar Tests`, `update`, `TOIL and Approval View Tests`, `amend`, `OIDC Claims Tests`, `Document Files`, `Onboarding Checklist Tests`, `test_training_due.py`, `Access Rules and Roles`, `test_training_admin.py`, `Balance Views Tests`, `Registration`, `check_employment`, `Absence Request and Admin Tests`, `Policy Signing Tests`, `_cancel_after`, `Compliance Counts Tests`, `Absence Admin Tests`, `People Test Factories`, `Training Matrix`, `OIDC Provider Tests`, `test_seed_demo.py`, `test_nightly.py`, `Login Import Tests`, `Auto Login Tests`, `Course`, `getting_started`, `pytest`, `Register Due Items Tests`, `Payroll Report Tests`, `test_overdue_checklist_items_leave_out_a_leaver_past_90_days`, `Retention Report Tests`, `Policy Issue and Sign`, `Navigation and Email Case Tests`, `test_training_sessions.py`, `test_registers_pages.py`, `NI Number Normalising`, `CSP Tests`, `test_absence_approval_views.py`, `ReminderSchedule`, `Form Rendering Tests`, `state`, `Positions and Reporting Line`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **What connects `PBS_PASSWORD_FILE`, `Compliance tab Training table (Open, Verify or reject, or Record links)`, `Hide rota invitation and reset buttons while HR sign-in is on` to the rest of the system?**
  _45 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `people/models/__init__.py` be split into smaller, more focused modules?**
  _Cohesion score 0.02946031746031746 - nodes in this community are weakly interconnected._
- **Why does `Practice HR README` connect `README and Platform Docs` to `people/models/__init__.py`, `Compliance Admin Docs`, `Absence and Leave Docs`, `Guide for HR administrators`, `Absence Services Core`, `Specs and Backlog Index`, `test_seed_demo.py`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Should `Absence Booking Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.049335629921259845 - nodes in this community are weakly interconnected._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Going live: first month checklist` and `Hand-entered carry-overs (shell)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Training (admin)` and `Who can open a file`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._