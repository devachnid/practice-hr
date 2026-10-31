# Graph Report - practice-hr  (2026-10-29)

## Corpus Check
- 218 files · ~302,271 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 5182 nodes · 15739 edges · 209 communities (149 shown, 60 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 1223 edges (avg confidence: 0.91)
- Token cost: 1,404,017 input · 0 output

## Community Hubs (Navigation)
- People Services Core
- Absence Booking Tests
- Year-End and TOIL Ledger
- Absence Models and Types
- Test Factories
- Training Models and Pages
- Absence and Leave Docs
- Training Service
- Registration Service Tests
- Absence Services Core
- Register Adapter Tests
- Registration Checks Summary
- Checks Model and Service
- Onboarding Pages Tests
- Training Views and Forms
- README and Platform Docs
- Absence Calendar Tests
- TOIL and Approval View Tests
- Employee and Employment Tests
- Email Delivery
- Onboarding Checklist Tests
- Document Files
- Compliance Due Items
- Onboarding Checklist Service
- Training Admin and Plan
- Register Models and Lookups
- Onboarding Design Models
- Access Rules and Roles
- Positions and Titles Tests
- Balance Views Tests
- Register Page Parsers
- Passkey Reauth Tests
- Passkey Registration and Reauth
- Accrual Calculation Tests
- Base Layout and My Record
- Foundation Domain Concepts
- Absence Policy Form Tests
- Employment Lifecycle
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
- People and Training Docs
- Register Fetch and Name Match
- People Test Factories
- Policy Lookup and Seed Tests
- Training Matrix
- Specs and Backlog Index
- Bank Holiday Sync
- OIDC Provider Tests
- People Models
- Axes Lockout Tests
- Login Import Tests
- Auto Login Tests
- CI Workflow
- Onboarding Checklist Items
- Onboarding Admin
- Absence Forms and Payroll View
- Payroll Report and Nightly
- Absence Notification Tests
- Compliance Admin Docs
- Checklist Templates and Gates
- Colour Palette Engine
- Audit Log and Employee Service
- Absence Costing Tests
- Ops Hardening and Settings
- TOIL Claim Tests
- Foundation Plan
- App Roles
- Register Check Now
- Register Due Items Tests
- Absence Ledger Plan
- Payroll Report Tests
- Client IP and CSP Middleware
- Compliance Digest Service
- Deploy and PBS Tests
- Retention Report Tests
- Absence Admin Actions
- App Configs
- Policy Issue and Sign
- Absence Notifications
- My Absences Page
- Navigation and Email Case Tests
- Register Admin and Unpause
- Policy Signing Views
- Absence Workflow Plan
- Approval Decisions and Units
- Upload Sniffing and Forms
- TOIL Claim Approval Tests
- NI Number Normalising
- Shared Validity Helpers
- HR-Only Sign-In Plan
- OIDC Signing Key
- HR Onboarding Detail
- CSP Tests
- Employment Admin Validation
- HR Guide Compliance Tasks
- Accounts Views and Mail
- Getting Started and Pre-Start
- Reminder Schedule
- Absence Admin Registry
- Approver Queue and Decide
- Ledger Page and Balances
- Security Middleware
- Policy Admin
- Policy Admin Display
- Absence and Type Models
- Passkeys JavaScript
- Form Rendering Tests
- Approval Routing and HR Role
- Evidence Upload
- File Supersede Admin
- People Admin Classes
- Policy Forms
- Cancel and Decline Claims
- Calendar and Dashboard Templates
- Deploy Checks and Login Hooks
- API Token Auth
- Retention Report
- Positions and Reporting Line
- Docs Link Checker
- Leave Year and Closed Pots
- Check Record Form
- User and Password Link
- Axes Lockout Handler
- Rota Read API
- TOIL Views and Ops Tests
- HR Admin Site and Backend
- Compliance Dashboard Tests
- Django Entry Points
- OIDC Client Registration
- Private Pages Tests
- Ledger Entry Inline
- Contract Rows Helper
- Entitlement Resync Signals
- Login Import Command
- Policy Version Inline
- Absence Nightly Job
- TOIL Claim Cancel
- OIDC Token Validator
- People Models and Admin
- OIDC Claims Tests
- Policy Tier Formset
- Service Years and Tiers
- User Model and OIDC Claims
- Training Admin Navigation
- Policy Year Governance
- Policy Tier Form
- Pot Admin
- Design Palette Tag
- NI Number Migration
- GP Register Fixtures
- Policy Resync Snapshot
- Standard Contract Seed
- Pot Month Helpers
- HR Admin Site Config
- Contract Unit Checks
- Year-End Command
- Bank Holiday Policy Seed
- Cancel Reason Migration
- Zero Expiry Migration
- Accounts Admin and User
- Check Types Seed
- Leaver Absence Cancel
- Onboarding Config Hooks
- Working Pattern Inline
- Working Pattern Model
- Bank Holiday Horizon Tests
- Bank Holidays 2029-2030 Seed
- No Policy Error
- TOIL Claim Rules Check
- Invite Form
- Emergency Contact Formset
- Emergency Contact Form
- Entitlement Sync
- Bank Holiday Seed Horizon
- TOIL Claim Step
- Access Rules and Routing
- Media Fixture

## God Nodes (most connected - your core abstractions)
1. `make_employee()` - 297 edges
2. `hours_employee()` - 273 edges
3. `absence_type()` - 259 edges
4. `make_employment()` - 160 edges
5. `request()` - 112 edges
6. `for_day()` - 105 edges
7. `File` - 94 edges
8. `make_team()` - 94 edges
9. `make_contract_type()` - 87 edges
10. `CheckType` - 79 edges

## Surprising Connections (you probably didn't know these)
- `Policy sign form (password or passkey credential)` --semantically_similar_to--> `confirm_password()`  [INFERRED] [semantically similar]
  templates/documents/sign.html → accounts/recent_auth.py
- `claim_decided()` --references--> `email/toil_decided.txt (TOIL claim decided email)`  [INFERRED]
  absence/services/notify.py → templates/absence/email/toil_decided.txt
- `submit()` --implements--> `Two-step request without JavaScript (validate, show cost and balance, confirm)`  [INFERRED]
  absence/views/requests.py → docs/superpowers/plans/2026-09-28-absence-workflow.md
- `_oidc_private_key()` --implements--> `Secrets from the environment only`  [INFERRED]
  config/settings.py → docs/superpowers/plans/2026-09-28-foundation.md
- `files.supersede` --references--> `supersede()`  [INFERRED]
  docs/superpowers/plans/2026-10-04-onboarding-documents.md → documents/services/files.py

## Import Cycles
- 3-file cycle: `documents/services/policies.py -> people/services/employments.py -> onboarding/services/checklists.py -> documents/services/policies.py`
- 3-file cycle: `absence/services/bank_holidays.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bank_holidays.py`
- 3-file cycle: `checks/services/checks.py -> people/services/employments.py -> onboarding/services/checklists.py -> checks/services/checks.py`
- 3-file cycle: `absence/services/bookings.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bookings.py`
- 3-file cycle: `absence/services/bookings.py -> people/services/access.py -> people/services/employments.py -> absence/services/bookings.py`
- 3-file cycle: `onboarding/services/checklists.py -> people/services/access.py -> people/services/employments.py -> onboarding/services/checklists.py`
- 3-file cycle: `onboarding/services/checklists.py -> people/services/positions.py -> people/services/employments.py -> onboarding/services/checklists.py`
- 4-file cycle: `documents/services/policies.py -> people/services/access.py -> people/services/employments.py -> onboarding/services/checklists.py -> documents/services/policies.py`
- 4-file cycle: `documents/services/policies.py -> people/services/positions.py -> people/services/employments.py -> onboarding/services/checklists.py -> documents/services/policies.py`
- 4-file cycle: `absence/services/bank_holidays.py -> absence/services/bookings.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bank_holidays.py`
- 4-file cycle: `absence/services/bank_holidays.py -> absence/services/bookings.py -> people/services/access.py -> people/services/employments.py -> absence/services/bank_holidays.py`
- 4-file cycle: `absence/services/bank_holidays.py -> absence/services/costing.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bank_holidays.py`
- 4-file cycle: `absence/services/bank_holidays.py -> absence/services/pots.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bank_holidays.py`
- 4-file cycle: `checks/services/checks.py -> people/services/access.py -> people/services/employments.py -> onboarding/services/checklists.py -> checks/services/checks.py`
- 4-file cycle: `checks/services/checks.py -> people/services/positions.py -> people/services/employments.py -> onboarding/services/checklists.py -> checks/services/checks.py`
- 4-file cycle: `absence/services/bookings.py -> absence/services/costing.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bookings.py`
- 4-file cycle: `absence/services/bookings.py -> absence/services/pots.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bookings.py`
- 4-file cycle: `absence/services/bookings.py -> absence/services/year_end.py -> absence/services/policies.py -> people/services/employments.py -> absence/services/bookings.py`
- 4-file cycle: `absence/services/bookings.py -> people/services/access.py -> people/services/positions.py -> people/services/employments.py -> absence/services/bookings.py`
- 4-file cycle: `onboarding/services/checklists.py -> people/services/access.py -> people/services/positions.py -> people/services/employments.py -> onboarding/services/checklists.py`

## Hyperedges (group relationships)
- **Append-only compliance records (superseded or new rows, never edited)** — docs_superpowers_specs_2026_10_04_onboarding_documents_design_file, docs_superpowers_specs_2026_10_04_onboarding_documents_design_check, docs_superpowers_specs_2026_10_04_onboarding_documents_design_signature, docs_superpowers_specs_2026_10_04_onboarding_documents_design_checklist [EXTRACTED 1.00]
- **Entitlement re-sync flow: change triggers, nightly safety net, sync to the accrual integral** — docs_superpowers_plans_2026_09_28_absence_ledger_resync_signals, docs_superpowers_plans_2026_09_28_absence_ledger_i2_policy_resync_in_admin, docs_superpowers_plans_2026_09_28_absence_ledger_nightly_safety_net, docs_superpowers_plans_2026_09_28_absence_ledger_entitlement_sync_revision, docs_superpowers_plans_2026_09_28_absence_ledger_accrual_integral [EXTRACTED 1.00]
- **Practice-account sign-in: HR OIDC provider, client registration, rota relying party** — docs_superpowers_plans_2026_09_28_foundation_oidc_provider, docs_superpowers_plans_2026_09_28_foundation_register_oidc_client, docs_superpowers_plans_2026_09_28_foundation_practice_account_signin, docs_superpowers_plans_2026_09_28_foundation_rota [EXTRACTED 1.00]
- **Sickness category never disclosed outside restricted views (calendar, payroll report, read API)** — docs_superpowers_plans_2026_09_28_absence_workflow_calendar_labels_only, docs_superpowers_plans_2026_09_28_absence_workflow_payroll_changes_report, docs_superpowers_plans_2026_09_28_absence_workflow_read_api [EXTRACTED 1.00]
- **Emailed password-link flow (invitation and reset)** — accounts_mail_send_password_link, templates_registration_invitation_email, templates_registration_invitation_subject, templates_registration_password_reset_email, templates_registration_password_reset_form, templates_registration_password_reset_done, templates_registration_password_reset_confirm [INFERRED 0.85]
- **Leave request approval flow (request, notify, queue, decide, outcome email)** — templates_absence_request, templates_absence_email_submitted, templates_absence_queue, templates_absence_decide, templates_absence_email_decided [INFERRED 0.85]
- **Pages rendered through the site FormRenderer (div.html + field.html)** — config_forms_formrenderer, templates_django_forms_div, templates_django_forms_field, templates_people_me, templates_registration_login, templates_registration_password_change_form, templates_registration_password_reset_confirm, templates_registration_password_reset_form [INFERRED 0.85]
- **TOIL claim approval flow (claim, notify, queue, decide, outcome email, TOIL card)** — templates_absence_toil_claim, templates_absence_email_toil_submitted, templates_absence_queue, templates_absence_toil_decide, templates_absence_email_toil_decided, templates_absence__toil_card [INFERRED 0.85]
- **Balances to ledger drill-down** — templates_absence_balances, templates_absence__balance_year, templates_absence_ledger, templates_absence_balances_ledger_drilldown [INFERRED 0.95]
- **Training record lifecycle through the service (record, self-record, verify, reject, set expiry)** — training_services_training_record, training_services_training_self_record, training_services_training_verify, training_services_training_reject, training_services_training_set_expiry, training_services_sessions_record_session [EXTRACTED 1.00]
- **Readers of training.state / build_row: pages, digest, dashboard, Compliance tab and matrix** — training_services_training_state, people_views_me, people_views_team, training_views_person, training_services_due_due_items, training_services_matrix_build, people_admin_employeeadmin_compliance_summary, absence_admin_dashboard_compliance_people [EXTRACTED 1.00]
- **Checks and training share compliance.validity's expiry arithmetic and status rule** — compliance_validity_expires_from, compliance_validity_status, checks_services_checks_expires_from, checks_services_checks_status, training_services_training_build_row, training_services_training_new_record [EXTRACTED 1.00]
- **Nightly register lookups to morning digest alerts** — registers_services_nightly_run, registers_services_nightly_sync_verified, registers_services_lookups_scheduled, registers_services_lookups_run, registers_adapters_init_lookup, registers_services_lookups_record_check, registers_services_due_due_items, compliance_services_digest [EXTRACTED 1.00]
- **Four register adapters supplying url() and parse()** — registers_adapters_gmc, registers_adapters_mpl_wales, registers_adapters_nmc, registers_adapters_gphc, registers_adapters_base [EXTRACTED 1.00]
- **Global safety and privacy constraints on register lookups** — docs_superpowers_plans_2026_10_05_professional_registrations_one_network_function, docs_superpowers_plans_2026_10_05_professional_registrations_page_never_stored, docs_superpowers_plans_2026_10_05_professional_registrations_no_pii_in_logs, docs_superpowers_plans_2026_10_05_professional_registrations_politeness_rules, docs_superpowers_plans_2026_10_05_professional_registrations_lookup_never_raises [EXTRACTED 1.00]
- **Hook-based auto-closing of linked checklist items** — docs_superpowers_plans_2026_10_04_onboarding_documents_recorded_hooks, docs_superpowers_plans_2026_10_04_onboarding_documents_signed_hooks, docs_superpowers_plans_2026_10_04_onboarding_documents_added_hooks, docs_superpowers_plans_2026_10_04_onboarding_documents_onboardingconfig_ready, docs_superpowers_plans_2026_10_04_onboarding_documents_checklists_linked_done, docs_superpowers_plans_2026_10_04_onboarding_documents_link_strings [EXTRACTED 1.00]
- **Morning compliance digest pipeline (due-items contract, cadence, sent log)** — docs_superpowers_plans_2026_10_04_onboarding_documents_checks_due_items, docs_superpowers_plans_2026_10_04_onboarding_documents_documents_due_items, docs_superpowers_plans_2026_10_04_onboarding_documents_onboarding_due_items, docs_superpowers_plans_2026_10_04_onboarding_documents_dueitem, docs_superpowers_plans_2026_10_04_onboarding_documents_should_send, docs_superpowers_plans_2026_10_04_onboarding_documents_reminderschedule, docs_superpowers_plans_2026_10_04_onboarding_documents_remindersent, docs_superpowers_plans_2026_10_04_onboarding_documents_digest_run, docs_superpowers_plans_2026_10_04_onboarding_documents_compliance_nightly [EXTRACTED 1.00]
- **Pre-start starter flow (gate, Getting started, self-service details)** — docs_superpowers_plans_2026_10_04_onboarding_documents_is_pre_start, docs_superpowers_plans_2026_10_04_onboarding_documents_prestartgate, docs_superpowers_plans_2026_10_04_onboarding_documents_getting_started_view, docs_superpowers_plans_2026_10_04_onboarding_documents_details_view, docs_superpowers_plans_2026_10_04_onboarding_documents_checklists_start [INFERRED 0.85]
- **Registration lookup pipeline: fetch, parse, log, record check, alert** — docs_superpowers_specs_2026_10_05_professional_registrations_design_registers_http_get, docs_superpowers_specs_2026_10_05_professional_registrations_design_adapter_interface, docs_superpowers_specs_2026_10_05_professional_registrations_design_lookups_run, docs_superpowers_specs_2026_10_05_professional_registrations_design_lookup, docs_superpowers_specs_2026_10_05_professional_registrations_design_check_recording, docs_superpowers_specs_2026_10_05_professional_registrations_design_registration_due_items [INFERRED 0.85]
- **Self-recorded training verification flow** — docs_superpowers_specs_2026_10_25_training_compliance_design_self_record, docs_superpowers_specs_2026_10_25_training_compliance_design_to_verify, docs_superpowers_specs_2026_10_25_training_compliance_design_verify_reject, docs_superpowers_specs_2026_10_25_training_compliance_design_training_due_items, docs_admin_compliance_verifying [INFERRED 0.85]
- **Morning compliance digest: sources, schedule and sent log** — docs_admin_compliance_reminders, docs_admin_compliance_reminder_settings, docs_admin_compliance_sent_log, docs_superpowers_specs_2026_10_05_professional_registrations_design_registration_due_items, docs_superpowers_specs_2026_10_25_training_compliance_design_training_due_items, docs_superpowers_specs_2026_10_04_onboarding_documents_design_digest [INFERRED 0.85]
- **Register fixture capture-to-verified flow** — registers_adapters_fixtures_readme_page_capture, registers_management_commands_registers_fetch, registers_management_commands_registers_parse, tests_test_registers_adapters, registers_services_nightly_sync_verified, registers_adapters_fixtures_readme_verified_body [INFERRED 0.85]
- **Training compliance workflow (require, record, verify, report, remind)** — docs_guides_hr_administrator_course_requirements, docs_guides_hr_administrator_training_verification, docs_guides_hr_administrator_training_session, docs_guides_hr_administrator_training_matrix, docs_guides_hr_administrator_things_due_email [INFERRED 0.85]
- **Professional registration problem handling** — docs_guides_hr_administrator_professional_registrations, docs_guides_hr_administrator_check_now, docs_guides_hr_administrator_registration_failure_handling, docs_guides_hr_administrator_register_pause, docs_guides_manager_registration_problem_email [INFERRED 0.85]
- **Admin action form pages (act as you through a service)** — templates_checks_admin_ask, templates_checks_admin_complete, templates_documents_admin_issue, templates_documents_admin_supersede [INFERRED 0.85]
- **Checklist item completion surfaces posting to onboarding:complete** — templates_onboarding__checklist, templates_onboarding__todo_card, templates_onboarding_hr_detail_item_actions, onboarding_views_complete, onboarding_views_back [INFERRED 0.85]
- **Policy issue-and-sign flow** — templates_documents_admin_issue, templates_documents_policies, templates_documents_sign, static_documents_sign, documents_views_sign, documents_services_policies_sign [INFERRED 0.85]
- **Confirm on GET, act on POST pages** — templates_registers_admin_unpause, templates_registers_check_now, templates_training_admin_verify, templates_training_admin_reject, templates_training_reject [INFERRED 0.85]
- **Training self-record, verify or reject lifecycle** — templates_people__training, training_views_self_record, templates_training_person, training_services_training_verify, training_services_training_reject, templates_training_reject, templates_training_admin_verify, templates_training_admin_reject [INFERRED 0.85]
- **Shared compliance status badge mapping (current ok; due soon, lapsed, missing warning)** — templates_people__checks, templates_people__training, templates_training_matrix, templates_training_person [INFERRED 0.95]

## Communities (209 total, 60 thin omitted)

### Community 0 - "People Services Core"
Cohesion: 0.04
Nodes (29): DateInput, home(), Duplicated admin refusal guard (training/admin.py, checks/admin.py), DateInput, PolicyVersion, Meta, Owed, contact_formset() (+21 more)

### Community 1 - "Absence Booking Tests"
Cohesion: 0.04
Nodes (118): summary(), record(), recost(), request(), entitlement_lines_total(), resync_contract_type(), sync_entitlement(), run() (+110 more)

### Community 2 - "Year-End and TOIL Ledger"
Cohesion: 0.05
Nodes (83): AdjustForm, adjust(), balance(), write(), earn(), _bookings(), check_open(), close() (+75 more)

### Community 3 - "Absence Models and Types"
Cohesion: 0.03
Nodes (39): Migration, Migration, Migration, Migration, Migration, Migration, Migration, Migration (+31 more)

### Community 4 - "Test Factories"
Cohesion: 0.07
Nodes (70): policy_for(), _cap(), _stays(), PatternDay, Meta, active_on(), add(), contracted_amount() (+62 more)

### Community 5 - "Training Models and Pages"
Cohesion: 0.06
Nodes (56): Course delivery: online (self-record needs the certificate) or face to face (usually a session), A Course says who needs it (position titles, or required of everyone) and how long it lasts, A face-to-face session recorded once: one verified record per attendee and one shared attendance sheet, Reminder wording by delivery ('complete the e-learning and upload your certificate' / 'ask your manager about the next session'), Training audit fields (recorded, self_recorded, verified, rejected, session_recorded, expires_on, certificate), Three kinds of training record: verified (counts), awaiting verification (pending), rejected, record_session (one transaction per group session), _cast() (+48 more)

### Community 6 - "Absence and Leave Docs"
Cohesion: 0.07
Nodes (63): Absence and leave (admin reference), Absence type, Accrual basis (daily / monthly twelfths), Accrues flag (earned vs accrued), Automatic bank-holiday absence row (Charge again), Balances page, Bank holiday handling (closed / pot / included in annual leave), Bank holidays and closed days calendar (+55 more)

### Community 7 - "Training Service"
Cohesion: 0.07
Nodes (54): Training compliance (courses, verification, sessions, matrix), Recording a training session, Verifying uploaded training (Verify or Reject), Team training seen in full (record, verify, sessions), training.verify/reject pending check without a lock, Awaiting verification replaces missing or lapsed while a pending record waits, Required courses: active everyone courses plus those the current primary position's title needs; no employment, nothing, Verify makes a pending record count; Reject needs a note and emails the person (+46 more)

### Community 8 - "Registration Service Tests"
Cohesion: 0.09
Nodes (59): Result, Registration, Meta, run(), scheduled(), missing(), set_number(), _change_post() (+51 more)

### Community 9 - "Absence Services Core"
Cohesion: 0.10
Nodes (14): Migration, seed(), KitDay, Meta, BankHoliday, Meta, LedgerEntry, Meta (+6 more)

### Community 10 - "Register Adapter Tests"
Cohesion: 0.05
Nodes (40): lookup(), url(), verified(), FetchError, get(), user_agent(), _page(), test_a_gp_register_value_other_than_a_known_yes_is_a_problem() (+32 more)

### Community 11 - "Registration Checks Summary"
Cohesion: 0.04
Nodes (32): Professional registration checks implementation plan, Register page fixture capture guide, Lookups service (run and scheduled), registers_fetch command, registers_parse management command, Registration problems dashboard count, Registrations service (numbers on people), Registrations table on the Compliance tab (+24 more)

### Community 12 - "Checks Model and Service"
Cohesion: 0.09
Nodes (58): Check, DbsLevel, Meta, Outcome, CheckType, Evidence, Meta, ask() (+50 more)

### Community 13 - "Onboarding Pages Tests"
Cohesion: 0.05
Nodes (45): Self-service details view and DetailsForm, add_item(), _contacts_summary(), set_emergency_contacts(), _asked_rtw(), cast(), _due_for_details(), _is_login() (+37 more)

### Community 14 - "Training Views and Forms"
Cohesion: 0.05
Nodes (38): _back(), My record Training card with one self-record form (a course select), A person's training page /training/<pk>/ (note, record form and Verify / Reject for those who may record), Recording your own completion: pending until HR or your manager verifies it, Session form offers HR everyone employed today and a manager today's reports; the service checks the day held, A starter records training from Getting started before day one (/training/ allowed through the pre-start gate), download(), employee_is_pre_start() (+30 more)

### Community 15 - "README and Platform Docs"
Cohesion: 0.06
Nodes (60): PBS_PASSWORD_FILE, pbs-push.sh script, The read API for the rota (admin reference), GET /api/v1/absences, HR_API_TOKENS bearer tokens, GET /api/v1/patterns, GET /api/v1/people, Rota read API (/api/v1/) (+52 more)

### Community 16 - "Absence Calendar Tests"
Cohesion: 0.08
Nodes (51): add_kit_day(), approve(), _copy_back(), decline(), _lock(), set_family_dates(), days_for(), _halves() (+43 more)

### Community 17 - "TOIL and Approval View Tests"
Cohesion: 0.08
Nodes (53): roles(), _decide(), _setup(), test_a_cancelled_request_reads_as_cancelled(), test_a_double_post_shows_the_read_only_page_and_writes_nothing(), test_a_non_approver_has_no_waiting_count(), test_a_refused_decision_shows_why_and_tells_nobody(), test_a_routed_approver_sees_a_decided_request_read_only() (+45 more)

### Community 18 - "Employee and Employment Tests"
Cohesion: 0.06
Nodes (40): create_for_employee(), create(), diff(), update(), make_employee(), test_an_earned_expiry_is_only_for_a_type_that_does_not_accrue(), test_an_earned_expiry_of_zero_is_refused(), test_audit_rows_are_immutable() (+32 more)

### Community 19 - "Email Delivery"
Cohesion: 0.07
Nodes (30): record_failure(), send(), email_is_configured(), link_expires(), LinkToCopy, password_link(), send_password_link(), _stamp() (+22 more)

### Community 20 - "Onboarding Checklist Tests"
Cohesion: 0.10
Nodes (50): Checklist, Meta, ChecklistTemplate, Meta, complete(), for_hr(), gaps(), get_or_create() (+42 more)

### Community 21 - "Document Files"
Cohesion: 0.10
Nodes (45): File, Category, Meta, add(), supersede(), _client_for(), _docx_bytes(), media() (+37 more)

### Community 22 - "Compliance Due Items"
Cohesion: 0.07
Nodes (31): compliance_counts(), compliance_people(), dashboard(), _row(), owed_status(), due_items(), active_email(), DueItem (+23 more)

### Community 23 - "Onboarding Checklist Service"
Cohesion: 0.07
Nodes (37): ADDED_HOOKS (files), checklists.start / leave (_build), Execution notes and rulings (2026-10-04), OnboardingConfig.ready (hook registration), RECORDED_HOOKS (checks), SIGNED_HOOKS (policies), DueRule, Kind (+29 more)

### Community 24 - "Training Admin and Plan"
Cohesion: 0.05
Nodes (16): Training compliance implementation plan (spec 4), Admin record list status filter: pending / verified / rejected, with a name search, The latest counting record by done_on is the one that counts (a renewal wins), Pre-commit verification (task tests, ruff check, makemigrations --check; whole suite before the final commit), set_expiry: HR's one edit after the fact, the expiry of a verified record (audited), Subagent-driven execution on feature/training-compliance (implementer and review per task; 1596 passed, 1 skipped), Training app architecture (Course, append-only TrainingRecord, TrainingSession on the shared compliance pieces), Training records admin: add through training.record, change only a verified record's expiry, Verify / Reject actions, never deleted (+8 more)

### Community 25 - "Register Models and Lookups"
Cohesion: 0.06
Nodes (23): Lookup outcomes: clear, problem, not_found, name_mismatch, unreadable, Fixture file naming by outcome (clear, problem*, not_found, unreadable), Capturing a register page (registers_fetch or curl), Verified register body (clear, not_found and problem fixtures), Lookup, Meta, Outcome, Trigger (+15 more)

### Community 26 - "Onboarding Design Models"
Cohesion: 0.06
Nodes (47): Courses admin, Training sessions, Emergency contacts (the one deletable inline), Course levels and equivalence, Import e-learning completion export (Blue Stream Academy, e-LfH), Training bookings and calendar, Onboarding, offboarding and documents implementation plan, Check model (outcome, DBS level, awaiting, evidence) (+39 more)

### Community 27 - "Access Rules and Roles"
Cohesion: 0.06
Nodes (33): decides_at_once(), _may_see_queue(), team(), Line manager keeps training and can_view rights outside employment, Every training file is a documents.File written by files.add and read through files.open, A line manager opens a report's training certificate and the attendance sheet of a session a report was at, My team Training column (counts and next expiry) and a Record a training session link, Training access rules (can_view_training, may_record_training_for, may_verify, can_view_file) (+25 more)

### Community 28 - "Positions and Titles Tests"
Cohesion: 0.07
Nodes (35): PositionTitle, Meta, run(), make_position(), test_leaver_login_disabled_returner_kept(), test_a_title_is_a_row_and_a_position_points_at_it(), test_renaming_a_title_moves_every_position_with_it(), test_the_api_still_sends_the_title_as_text() (+27 more)

### Community 29 - "Balance Views Tests"
Cohesion: 0.07
Nodes (36): after(), _nothing_yet(), rows(), _year(), bounds(), lookup(), _pot_day(), _balance() (+28 more)

### Community 30 - "Register Page Parsers"
Cohesion: 0.10
Nodes (22): Adapter registry and Result dataclass, GMC register adapter, GPhC register adapter, NMC register adapter, classify(), find(), has_word(), name_near() (+14 more)

### Community 31 - "Passkey Reauth Tests"
Cohesion: 0.09
Nodes (24): Passkey, Meta, SoftAuthenticator, _Broken, _enrol(), _post_json(), _reset_form(), _stale() (+16 more)

### Community 32 - "Passkey Registration and Reauth"
Cohesion: 0.07
Nodes (20): signed_in_recently(), send_passkey_added(), confirm_password(), is_recent(), mark(), account(), ChangePasswordView, _credential_from() (+12 more)

### Community 33 - "Accrual Calculation Tests"
Cohesion: 0.12
Nodes (40): bank_holiday_entitlement(), daily_rates(), _days(), entitlement(), _step(), round_to(), al(), _bank_holiday_pot() (+32 more)

### Community 34 - "Base Layout and My Record"
Cohesion: 0.06
Nodes (23): calendar_view(), _month(), _shift(), lockout_response(), RequestPasswordLinkView, SetPasswordFromLinkView, BoundField, FormRenderer (+15 more)

### Community 35 - "Foundation Domain Concepts"
Cohesion: 0.08
Nodes (39): Compliance and registrations lines in the nightly output, API fixed-window rate limit (API_RATE_LIMIT_PER_MINUTE, 429), Bank-holiday seeds 2029-2030 and the bank_holidays_seeded_to warning, Leaver audit note lists not-cancelled absences first (_cancel_after), Absence.cancel_reason and the bank-holiday opt-out (NOT_IMPLIED), bank_holidays.charge_again admin action, PolicyForm._check_year (leave-year lock on add), My absences always lists still-requested absences (+31 more)

### Community 36 - "Absence Policy Form Tests"
Cohesion: 0.10
Nodes (37): bank_holiday_summary(), _year_label(), bank_holidays_between(), _add(), _add_post(), _april_type_in_use(), _change(), _end() (+29 more)

### Community 37 - "Employment Lifecycle"
Cohesion: 0.06
Nodes (26): people.services.employments.start / end, guarded(), _record_failure(), check_employment(), EmploymentForm, Meta, Employment, LeavingReason (+18 more)

### Community 38 - "Checks Admin Actions"
Cohesion: 0.07
Nodes (8): CheckAdmin, CheckTypeAdmin, AskForm, CompleteForm, Meta, checks/admin/ask.html (Ask for evidence page), checks/admin/complete.html (Record the result page), _Refusable

### Community 39 - "Absence Request and Admin Tests"
Cohesion: 0.12
Nodes (40): _auto_row(), _confirmed(), _form(), _in_this_year(), _me(), _report_and_manager(), test_a_manager_does_not_cancel_a_reports_automatic_row(), test_a_manager_records_sickness_for_a_report_approved_audited_and_emailed() (+32 more)

### Community 40 - "Policy Signing Tests"
Cohesion: 0.13
Nodes (36): Signature, Meta, Method, owed(), _assertion(), _enrol(), _policy(), _staff() (+28 more)

### Community 41 - "Request Chase"
Cohesion: 0.08
Nodes (22): ClosedDay, Meta, EmailFailure, Meta, _non_working_dates(), notify_once(), waiting(), _working_days_between() (+14 more)

### Community 42 - "Registrations Admin Docs"
Cohesion: 0.07
Nodes (37): Name does not match rule, When a register page cannot be read (pausing and Unpause), Professional registrations (admin), Recording a check, Recording a registration number, Register bodies admin (Positions, Active, Verified, Paused), Registration lookups log (read-only), The registration lookup schedule (+29 more)

### Community 43 - "Read API Tests"
Cohesion: 0.08
Nodes (25): api_tokens(), api(), _fresh_rate_counts(), _hit(), test_absences_need_an_ordered_window(), test_another_address_is_counted_separately(), test_check_quiet_in_debug(), test_check_quiet_with_a_token() (+17 more)

### Community 44 - "Compliance Digest Design"
Cohesion: 0.08
Nodes (38): Reminder settings (start, every, overdue, registration days), Reminders (morning digest), The reminder sent log (compliance.ReminderSent), Training reminders, Training statuses (Current, Due soon, Lapsed, Missing, Awaiting verification, Not required), Attendance-sheet rule in can_view_file ignores hr_only, Matrix CSV formula guard misses leading tab or carriage return, Training reminder wording keyed by delivery value (+30 more)

### Community 45 - "Login Accounts Admin"
Cohesion: 0.06
Nodes (4): CustomUserAdmin, LoginChangeForm, report_send(), _registered_clients()

### Community 46 - "Compliance Counts Tests"
Cohesion: 0.14
Nodes (30): ReminderSent, Meta, run(), _dbs_for_receptionists(), media(), _receptionist(), _rtw_asked(), test_a_failed_send_is_recorded_and_not_logged_as_sent() (+22 more)

### Community 47 - "Absence Admin Tests"
Cohesion: 0.09
Nodes (29): current_leave_year(), _auto_row(), _decided_claim(), _family_absence(), _open_pot(), _opted_out(), _policy_data(), _policy_post() (+21 more)

### Community 48 - "Passkeys and Reauth"
Cohesion: 0.11
Nodes (13): complete_registration(), _could_not_verify(), login_options(), origin(), PasskeyError, reauth_options(), registration_options(), rp_id() (+5 more)

### Community 49 - "People and Training Docs"
Cohesion: 0.10
Nodes (29): Health sensitive flag, Checklist templates and default items, People (admin reference), Audit log, Continuous service date, Employment (spell of work), Ending an employment cancels later absences, Line manager (approval routing) (+21 more)

### Community 50 - "Register Fetch and Name Match"
Cohesion: 0.08
Nodes (10): Shared fetch, parse and name-check flow, _original_name(), run(), _Text, Command, surnames_match(), _tokens(), _without_particles() (+2 more)

### Community 51 - "People Test Factories"
Cohesion: 0.07
Nodes (19): _employment_add(), _employment_base(), test_a_login_whose_email_differs_from_the_work_email_is_warned_about(), test_a_past_spell_can_be_added_before_a_current_one(), test_an_added_spell_keeps_its_end_date_and_reason(), test_an_overlapping_add_is_shown_on_the_form_not_a_500(), test_an_overlapping_spell_on_the_employee_page_is_shown_on_its_row(), test_audit_log_is_read_only() (+11 more)

### Community 52 - "Policy Lookup and Seed Tests"
Cohesion: 0.10
Nodes (22): Policy, Accrual, Basis, Meta, PolicyTier, Meta, _back_to_0004(), _reseed() (+14 more)

### Community 53 - "Training Matrix"
Cohesion: 0.12
Nodes (19): Training matrix (filters, Problems only, CSV download), Matrix CSV download (one row per person, 'Status, date' cells, no note, filters and date in the filename), Training matrix: people employed today down, courses needed or held across, filtered by course, team, name and show, courses(), media(), _people(), test_filters_by_course_team_and_name(), test_the_csv_does_not_let_a_cell_run_as_a_formula() (+11 more)

### Community 54 - "Specs and Backlog Index"
Cohesion: 0.09
Nodes (29): Backlog, Breathe CSV import, Certificate pack download (zip for inspection), Excluded on purpose (spec Not done), Go live, Opening balances carry-in screen, Rota integration (spec 2), Known limitations left for a follow-up (+21 more)

### Community 55 - "Bank Holiday Sync"
Cohesion: 0.14
Nodes (24): charge_again(), _sync(), sync_auto_absences(), _booked_pot(), cancel(), test_a_booking_on_the_bank_holiday_costs_nothing_and_the_auto_row_still_charges(), test_a_cancelled_automatic_row_stays_cancelled(), test_a_row_the_sync_cancelled_comes_back_when_implied_again() (+16 more)

### Community 56 - "OIDC Provider Tests"
Cohesion: 0.09
Nodes (16): _store(), _b64url_json(), _register(), _signed_in_flow(), test_a_client_someone_owns_is_never_taken_over(), test_a_sign_out_to_an_unregistered_address_is_refused(), test_an_inactive_login_cannot_refresh(), test_client_management_is_not_mounted() (+8 more)

### Community 57 - "People Models"
Cohesion: 0.07
Nodes (13): Migration, Migration, Migration, Migration, Migration, Migration, Contract, Basis (+5 more)

### Community 58 - "Axes Lockout Tests"
Cohesion: 0.17
Nodes (16): _login(), _make(), test_a_passkey_sign_in_clears_only_its_own_account(), test_a_single_account_is_still_locked_after_repeated_failures(), test_a_spoofed_header_cannot_be_rotated_to_evade_the_limit(), test_a_success_clears_the_signed_in_persons_own_failures_everywhere(), test_an_account_holder_cannot_reset_a_colleagues_counter(), test_an_unrelated_address_is_not_caught_by_someone_elses_lockout() (+8 more)

### Community 59 - "Login Import Tests"
Cohesion: 0.19
Nodes (24): _counts(), _file(), hashed(), _login(), rota(), _run(), test_a_file_not_of_the_documented_shape_is_refused(), test_a_hash_this_system_cannot_check_is_refused_as_such() (+16 more)

### Community 60 - "Auto Login Tests"
Cohesion: 0.12
Nodes (23): BrokenBackend, _messages(), post(), _post(), _run(), relay(), test_a_change_post_cannot_smuggle_the_login_fields(), test_a_failed_send_keeps_the_login_and_shows_the_link() (+15 more)

### Community 61 - "CI Workflow"
Cohesion: 0.07
Nodes (29): ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, DEBUG, DEFAULT_FROM_EMAIL, EMAIL_HOST, HR_API_TOKENS, OIDC_RSA_PRIVATE_KEY, SECRET_KEY (+21 more)

### Community 62 - "Onboarding Checklist Items"
Cohesion: 0.11
Nodes (17): checklists.items_owned_by and the manager To do card, pre_start(), ChecklistItem, Meta, State, Owner, details_submitted(), items_owned_by() (+9 more)

### Community 63 - "Onboarding Admin"
Cohesion: 0.08
Nodes (7): ChecklistAdmin, ChecklistItemInline, ChecklistTemplateAdmin, TemplateItemInline, link_problem(), TemplateItem, Meta

### Community 64 - "Absence Forms and Payroll View"
Cohesion: 0.08
Nodes (11): DecisionForm, KitDayForm, PayrollPeriodForm, RequestForm, ToilClaimForm, TypeSelect, PayrollRun, Meta (+3 more)

### Community 65 - "Payroll Report and Nightly"
Cohesion: 0.09
Nodes (12): Command, _absences(), _balance(), _leavers(), month(), _name(), run(), _starters() (+4 more)

### Community 66 - "Absence Notification Tests"
Cohesion: 0.12
Nodes (23): decide_url(), request_submitted(), request_for(), submit(), _request_page(), _submit_message(), email/submitted.txt (leave request submitted email), _pair() (+15 more)

### Community 67 - "Compliance Admin Docs"
Cohesion: 0.12
Nodes (27): Compliance (admin reference), Asking the person for evidence, Check statuses (Current, Due soon, Lapsed, Missing, Awaiting, Not required), Check types (titles, validity, evidence, remind person), Checklist gaps, Checklist item links (details, upload, sign_policies, check), Starter and leaver checklists, The Compliance card (seven numbers) (+19 more)

### Community 68 - "Checklist Templates and Gates"
Cohesion: 0.10
Nodes (23): access.can_view_checks, access.can_view_file, ChecklistTemplate, TemplateItem, Checklist and ChecklistItem models, checklists.complete, not_needed and may_complete, checklists.linked_done, Getting started page view (onboarding:getting_started), access.is_pre_start, Checklist item link strings (details, upload:<category>, sign_policies, check:<code>) (+15 more)

### Community 69 - "Colour Palette Engine"
Cohesion: 0.15
Nodes (17): base(), _between(), _ordered(), primary(), token(), _build(), contrast_ratio(), hex_to_rgb() (+9 more)

### Community 70 - "Audit Log and Employee Service"
Cohesion: 0.11
Nodes (16): AuditEntry, Kind, Meta, _email(), _label(), record(), viewed(), test_a_login_with_audit_rows_cannot_be_deleted() (+8 more)

### Community 71 - "Absence Costing Tests"
Cohesion: 0.15
Nodes (21): check_family_dates(), overlaps(), preview(), cost(), cost_between(), halves_covered(), _policy(), test_a_toil_booking_is_rounded_to_the_annual_leave_step() (+13 more)

### Community 72 - "Ops Hardening and Settings"
Cohesion: 0.10
Nodes (11): _dev_secret_key(), _oidc_private_key(), main(), access(), _settings_value(), test_a_csrf_failure_reaches_the_security_log(), test_a_password_links_token_never_reaches_the_log(), test_an_authorization_code_never_reaches_the_log() (+3 more)

### Community 73 - "TOIL Claim Tests"
Cohesion: 0.22
Nodes (21): _claim(), _old_claim(), _people(), test_a_claim_for_today_is_allowed_and_for_tomorrow_refused(), test_a_claim_is_for_more_than_zero(), test_a_claim_needs_employment_and_a_contract_on_the_day(), test_a_claim_older_than_the_expiry_window_is_refused(), test_a_claim_says_why() (+13 more)

### Community 74 - "Foundation Plan"
Cohesion: 0.13
Nodes (13): backup.sh script, Practice HR foundation implementation plan, accounts app copied from the rota at commit f1cdc4d, Breathe (previous HR integration; settings removed), Deployment: gunicorn on loopback 8322, nightly timer 01:30, backup with media, django-oauth-toolkit, django-unfold admin, hr_nightly runs every app's nightly job (+5 more)

### Community 75 - "App Roles"
Cohesion: 0.18
Nodes (19): AppRole, Meta, _apps_heading(), _client(), _save(), test_a_role_reads_as_who_on_what(), test_a_superuser_can_set_it_too_and_an_hr_admin_never_reaches_a_superusers(), test_an_existing_user_role_is_ticked_to_admin() (+11 more)

### Community 76 - "Register Check Now"
Cohesion: 0.08
Nodes (15): Registration number formats and duplicate warning, Welsh medical performers list adapter, RegisterBody (bodies a position title needs), registers app architecture, Registration: one per person per body, Four seeded register bodies (GMC, Welsh list, NMC, GPhC), Migration, seed() (+7 more)

### Community 77 - "Register Due Items Tests"
Cohesion: 0.17
Nodes (20): _gp(), _items(), _manager(), quiet(), test_a_changed_number_drops_the_old_numbers_alert_until_the_new_one_is_looked_up(), test_a_clear_result_and_a_fresh_registration_produce_nothing(), test_a_leaver_and_an_unneeded_body_raise_nothing(), test_a_missing_number_is_hrs_from_the_employment_start() (+12 more)

### Community 78 - "Absence Ledger Plan"
Cohesion: 0.14
Nodes (7): BankHolidays, _target_type(), _skip(), Absence ledger implementation plan, Bank-holiday handling modes (closed not charged / pro-rata pot / included in annual), ClosedDay (practice closure that is never charged), Seeded absence types (AL, BH, STUDY, TOIL, SICK, MAT, PAT, SPL, ADOPT, COMP, DEP, UNPAID, OTHER)

### Community 79 - "Payroll Report Tests"
Cohesion: 0.18
Nodes (21): build(), make_pot(), _cells(), _sheet(), test_a_spanning_sickness_absence_is_clipped_to_the_month(), test_a_spanning_unpaid_absence_is_split_between_the_months(), test_automatic_bank_holiday_rows_are_never_reported(), test_command_writes_the_month() (+13 more)

### Community 80 - "Client IP and CSP Middleware"
Cohesion: 0.14
Nodes (11): client_ip(), _request(), test_a_forwarded_header_from_anywhere_else_is_ignored(), test_axes_is_wired_to_this_resolver(), test_ipv6_is_supported_and_normalised(), test_junk_in_the_header_falls_back_rather_than_being_stored(), test_no_header_falls_back_to_the_peer_address(), test_the_forwarded_address_is_used_when_it_comes_from_the_tunnel() (+3 more)

### Community 81 - "Compliance Digest Service"
Cohesion: 0.10
Nodes (12): _body(), _collect(), pending(), _when(), run(), should_send(), compliance nightly step (compliance.services.nightly.run), email/compliance_digest.txt (Compliance digest email) (+4 more)

### Community 82 - "Deploy and PBS Tests"
Cohesion: 0.10
Nodes (11): _database_name(), _service_directives(), _setting(), test_db_path_moves_the_database(), test_gunicorn_keeps_only_the_state_directory_writable(), test_media_root_moves_into_the_state_directory(), test_production_environment_sets_media_root_in_the_state_directory(), test_the_pbs_secrets_stay_out_of_the_app_users_reach() (+3 more)

### Community 83 - "Retention Report Tests"
Cohesion: 0.11
Nodes (15): _left(), _settings_run(), test_a_category_is_due_only_after_its_last_day(), test_a_current_employee_is_never_due(), test_an_invalid_retention_value_is_a_clear_configuration_error(), test_due_lists_leavers_past_period(), test_due_reports_when_the_period_ended_and_when_it_fell_due(), test_page_is_read_only() (+7 more)

### Community 84 - "Absence Admin Actions"
Cohesion: 0.11
Nodes (3): AbsenceAdmin, admin/cancel_absence.html (Cancel absence confirm), admin/charge_again.html (Charge bank holiday again confirm)

### Community 85 - "App Configs"
Cohesion: 0.08
Nodes (7): AbsenceConfig, ChecksConfig, ComplianceConfig, DocumentsConfig, PeopleConfig, RegistersConfig, TrainingConfig

### Community 86 - "Policy Issue and Sign"
Cohesion: 0.12
Nodes (14): Policy, Meta, applies_to(), confirmation(), current(), issue(), sign(), signable() (+6 more)

### Community 87 - "Absence Notifications"
Cohesion: 0.18
Nodes (17): absence_cancelled(), approver_addresses(), claim_decide_url(), claim_decided(), claim_submitted(), _claim_unit(), _deliver(), hr_admin_addresses() (+9 more)

### Community 88 - "My Absences Page"
Cohesion: 0.12
Nodes (11): _bank_groups(), cancel(), kit_day(), _leave_year(), _may_cancel(), mine(), _my_employment(), request_leave() (+3 more)

### Community 89 - "Navigation and Email Case Tests"
Cohesion: 0.13
Nodes (10): test_lockout_attempts_share_one_counter_across_case_variants(), test_the_invite_form_refuses_a_case_variant_of_an_existing_address(), test_two_accounts_cannot_differ_by_case_alone(), _approver_of(), _employee(), _split(), test_an_approver_also_sees_approvals(), test_an_employee_sees_leave_calendar_and_balances_but_not_approvals() (+2 more)

### Community 90 - "Register Admin and Unpause"
Cohesion: 0.11
Nodes (5): Register pause after three unreadable lookups (Unpause), LookupAdmin, RegisterBodyAdmin, unpause(), registers/admin/unpause.html (Unpause register body confirm)

### Community 91 - "Policy Signing Views"
Cohesion: 0.12
Nodes (11): SignForm, state(), _status(), passkey_options(), policies_page(), _reauthenticate(), sign(), documents/policies.html (My policies page) (+3 more)

### Community 92 - "Absence Workflow Plan"
Cohesion: 0.16
Nodes (12): Kind, Balance summary (entitlement, carried in, taken, booked, pending, expired, adjustments, remaining), Deferred to plan 3 (carry-over, expiry, TOIL earned, year end, chase, calendar, request pages, payroll, API), LedgerEntry kinds (entitlement, revision, carry-in, expiry, booking, cancellation, TOIL earned/taken, adjustment), Absence workflow, payroll and API implementation plan, Admin dashboard card (waiting requests, email not configured), Carry-in expiry after carry_over_expires_after_days, Family-leave dates and KIT days (+4 more)

### Community 93 - "Approval Decisions and Units"
Cohesion: 0.15
Nodes (16): position(), units(), _toil(), claim(), _claim_page(), submit(), _balances.html (balances this leave year card), _toil_card.html (TOIL position card) (+8 more)

### Community 94 - "Upload Sniffing and Forms"
Cohesion: 0.10
Nodes (10): UploadForm, Meta, _is_docx(), _limit(), sniff(), _too_big(), AdminRecordForm, Meta (+2 more)

### Community 95 - "TOIL Claim Approval Tests"
Cohesion: 0.16
Nodes (16): approve(), claim(), _toil_marker(), _january_people(), _leaver_claim(), _on(), test_a_claim_for_a_closed_year_lands_on_the_current_pot_dated_the_day_worked(), test_a_claim_for_an_ended_year_with_no_pot_opens_none_for_it() (+8 more)

### Community 96 - "NI Number Normalising"
Cohesion: 0.16
Nodes (13): EmployeeForm, Meta, normalise(), _ni(), _store(), test_a_whitespace_only_ni_number_becomes_blank_and_is_not_reported(), test_my_record_with_a_stale_bad_ni_number_shows_an_error_not_a_500(), test_the_admin_employee_form_normalises_the_ni_number() (+5 more)

### Community 97 - "Shared Validity Helpers"
Cohesion: 0.13
Nodes (13): _status(), expires_from(), status(), Expiry adds calendar months clipped to the month end; a blank validity never expires, WINDOW_DAYS = 60 due-soon window (the reminder schedule's start_days_before overrides), Shared validity helpers move into compliance/validity.py (Task 1), Training statuses and labels (Current, Due soon, Lapsed, Missing, Not required, Awaiting verification; PROBLEMS), Status rule: not_required, missing, current, due_soon (window, today included), lapsed (+5 more)

### Community 98 - "HR-Only Sign-In Plan"
Cohesion: 0.14
Nodes (16): admin OIDC claim (Validator.get_additional_claims), AppRole (per-application admin flag on the HR login), Break-glass: remove PRACTICE_HR_URL and restart the rota, export_logins management command (rota), Sign-in through HR only (PRACTICE_HR_URL set): rota passwords and passkeys closed, import_logins management command (HR), Login export JSON file (mode 0600, deleted after import), PracticeAccountBackend (rota OIDC backend) (+8 more)

### Community 99 - "OIDC Signing Key"
Cohesion: 0.20
Nodes (15): oidc_signing_key(), _env(), _pem(), _rsa_pem(), _settings(), test_a_good_key_passes(), test_a_key_that_is_not_rsa_fails(), test_a_named_file_that_cannot_be_read_stops_the_app() (+7 more)

### Community 100 - "HR Onboarding Detail"
Cohesion: 0.22
Nodes (17): checklists.gaps (set-up problems recorded at build), checklists.summary, HR Starters and leavers list and detail pages, HR Starters and leavers page (gaps listed at the top), AddItemForm, summary(), add_item(), complete() (+9 more)

### Community 101 - "CSP Tests"
Cohesion: 0.13
Nodes (11): _policy(), _templates(), test_app_pages_carry_the_policy(), test_form_action_is_self_alone_with_no_client(), test_form_action_lets_sign_in_and_sign_out_finish_at_the_rota(), test_no_template_has_inline_script_or_handlers(), test_rendered_pages_hold_no_inline_script(), test_the_admin_renders_and_is_left_alone() (+3 more)

### Community 102 - "Employment Admin Validation"
Cohesion: 0.13
Nodes (9): add_error(), ContractInlineFormSet, EmploymentInlineFormSet, PositionInlineFormSet, _rows(), check_add(), check_end(), _primary_clash() (+1 more)

### Community 103 - "HR Guide Compliance Tasks"
Cohesion: 0.13
Nodes (17): Asking someone for evidence, Self-closing checklist items (What ticks itself off), Admin home Compliance card (seven numbers), Who needs a course (Required of everyone or Positions), When emails do not go (Email failures), Professional registration lookups (GMC, NMC, GPhC, Welsh performers list), Recording a check (check types, outcomes, expiry), When a registration check fails (+9 more)

### Community 104 - "Accounts Views and Mail"
Cohesion: 0.12
Nodes (5): check_available(), existing_for(), is_superuser(), _item(), _nav_item()

### Community 105 - "Getting Started and Pre-Start"
Cohesion: 0.13
Nodes (10): asked_of(), DetailsForm, Meta, pre_start(), PreStartGate, getting_started(), accept_typed(), Pre-start navigation (Getting started only) (+2 more)

### Community 106 - "Reminder Schedule"
Cohesion: 0.16
Nodes (9): ReminderScheduleAdmin, ReminderSchedule, Meta, Check professional registrations every (days) setting, test_a_request_before_the_start_date_is_not_yet_owed(), test_an_unanswered_request_for_a_required_check_is_reminded_of_as_missing(), test_defaults_and_singleton(), test_the_settings_are_one_row_edited_in_place() (+1 more)

### Community 107 - "Absence Admin Registry"
Cohesion: 0.15
Nodes (6): AbsenceTypeAdmin, BankHolidayAdmin, ClosedDayAdmin, EmailFailureAdmin, ToilClaimAdmin, Emails that did not go list

### Community 108 - "Approver Queue and Decide"
Cohesion: 0.13
Nodes (10): claims_for(), _may_open(), queue(), queue_for(), routed(), _routed_to(), _closed(), decide() (+2 more)

### Community 109 - "Ledger Page and Balances"
Cohesion: 0.20
Nodes (12): balances_for(), balances_view(), _filters(), ledger_view(), _links(), _render(), _rows(), Balances for this leave year and next, linked to ledger lines (+4 more)

### Community 110 - "Security Middleware"
Cohesion: 0.12
Nodes (4): ContentSecurityPolicyMiddleware, PrivatePagesMiddleware, _relying_party_origins(), RequestLogMiddleware

### Community 111 - "Policy Admin"
Cohesion: 0.14
Nodes (4): PolicyAdmin, SignatureAdmin, IssueForm, documents/admin/issue.html (Issue policy version page)

### Community 112 - "Policy Admin Display"
Cohesion: 0.22
Nodes (4): as_days(), mode(), plain(), PolicyAdmin

### Community 113 - "Absence and Type Models"
Cohesion: 0.13
Nodes (6): Absence, Category, Meta, Status, AbsenceType, Meta

### Community 114 - "Passkeys JavaScript"
Cohesion: 0.29
Nodes (14): armConditional(), b64urlToBytes(), bytesToB64url(), cancelConditional(), creationOptions(), credentialToJSON(), csrfToken(), enrol() (+6 more)

### Community 115 - "Form Rendering Tests"
Cohesion: 0.22
Nodes (10): Demo, _field_div(), test_a_checkbox_sits_inside_its_label(), test_a_single_field_group_uses_the_same_template(), test_dates_times_numbers_and_short_text_are_short(), test_errors_are_alerts_and_mark_the_field_invalid(), test_every_field_is_wrapped_labelled_without_a_colon_and_helped(), test_radios_keep_their_row_and_hidden_fields_are_rendered_once() (+2 more)

### Community 116 - "Approval Routing and HR Role"
Cohesion: 0.17
Nodes (5): HrAdminBackend, _is_hr_admin(), Notification routing: routed manager's work email or every active HR admin, Recording an absence for someone else (absence:request_for), HR admin role (is_hr_admin)

### Community 117 - "Evidence Upload"
Cohesion: 0.15
Nodes (9): _after(), _attach(), complete(), _takes_file(), upload(), checks.ask, upload_evidence and complete (evidence request flow), checks.expires_from (validity month arithmetic), people/_check_upload.html (Check evidence upload partial) (+1 more)

### Community 118 - "File Supersede Admin"
Cohesion: 0.15
Nodes (3): FileAdmin, SupersedeForm, documents/admin/supersede.html (Supersede file page)

### Community 119 - "People Admin Classes"
Cohesion: 0.17
Nodes (5): AuditEntryAdmin, ContractTypeAdmin, PositionTitleAdmin, TeamAdmin, WorkingPatternAdmin

### Community 120 - "Policy Forms"
Cohesion: 0.21
Nodes (5): _hours_chosen(), PolicyForm, Meta, _Stores, to_weeks()

### Community 121 - "Cancel and Decline Claims"
Cohesion: 0.16
Nodes (10): cancel(), _copy_back(), _decidable(), decline(), _lock(), _own(), test_a_decided_claim_emails_the_claimant(), test_an_approved_claim_is_not_cancelled_hr_adjusts_instead() (+2 more)

### Community 122 - "Calendar and Dashboard Templates"
Cohesion: 0.21
Nodes (6): _hours(), off_chip(), off_title(), status_tone(), when(), admin/index.html (Admin dashboard override)

### Community 123 - "Deploy Checks and Login Hooks"
Cohesion: 0.18
Nodes (6): AccountsConfig, on_login(), Approver link built from SITE_URL + notify.DECIDE_PATH (hr.W002), site_url(), test_check_quiet_with_a_site_url_or_in_debug(), test_check_warns_when_site_url_is_unset_outside_debug()

### Community 124 - "API Token Auth"
Cohesion: 0.19
Nodes (6): _over_limit(), token_required(), wrapped(), _valid(), API hardening (hmac token compare, csrf_exempt, no-store, hr.W001), Bearer token auth from HR_API_TOKENS

### Community 125 - "Retention Report"
Cohesion: 0.16
Nodes (9): _retention_days(), Retention categories checks, files, signatures (2190 days), Training records retention category (RETENTION_DAYS training, 2190 days), Retention periods and retention report, Retention categories: checks, files, signatures, RETENTION_DAYS_TRAINING (six years), due(), retention_report() (+1 more)

### Community 126 - "Positions and Reporting Line"
Cohesion: 0.30
Nodes (9): add(), end(), test_add_and_primary_on(), test_cycle_refused(), test_end_position(), test_extending_a_primary_position_over_a_later_one_refused(), test_second_primary_on_same_dates_refused(), test_self_management_refused() (+1 more)

### Community 127 - "Docs Link Checker"
Cohesion: 0.19
Nodes (5): _anchors(), _links(), _slug(), test_every_relative_link_and_anchor_resolves(), test_the_link_checker_catches_a_broken_anchor()

### Community 128 - "Leave Year and Closed Pots"
Cohesion: 0.19
Nodes (5): _check_leave_year(), bounds(), _safe_date(), Leave-year basis: fixed date or anniversary (29 Feb safe date), Pot (one employment's allowance for one type and one leave year)

### Community 129 - "Check Record Form"
Cohesion: 0.19
Nodes (4): RecordForm, Meta, _Result, validate()

### Community 130 - "User and Password Link"
Cohesion: 0.18
Nodes (4): User, Meta, RequestPasswordLinkForm, test_a_saved_address_keeps_its_local_part_but_not_a_shouted_domain()

### Community 132 - "Rota Read API"
Cohesion: 0.30
Nodes (6): absences(), _bad_request(), _iso(), patterns(), people(), on()

### Community 133 - "TOIL Views and Ops Tests"
Cohesion: 0.27
Nodes (8): admin_client(), configured(), employee_client(), employee_user(), hr_admin(), no_seeded_policies(), _oidc_test_key(), superuser_client()

### Community 135 - "Compliance Dashboard Tests"
Cohesion: 0.24
Nodes (10): _overdue_policy(), _receptionist(), test_a_tab_with_no_checks_is_not_audited_and_the_checks_list_is_not(), test_compliance_counts(), test_dashboard_card_counts(), test_each_number_links_to_the_people_it_counts(), test_employee_admin_has_a_compliance_tab(), test_opening_the_tab_writes_only_the_audit_of_the_checks_view() (+2 more)

### Community 141 - "Entitlement Resync Signals"
Cohesion: 0.39
Nodes (3): _contract_saved(), _employment_saved(), resync_employment()

### Community 142 - "Login Import Command"
Cohesion: 0.25
Nodes (3): _client(), Command, _read()

### Community 144 - "Absence Nightly Job"
Cohesion: 0.25
Nodes (5): bank_holiday_pot_used(), _open_pots(), _pot_covering(), _reported(), _why()

### Community 145 - "TOIL Claim Cancel"
Cohesion: 0.25
Nodes (4): may_cancel(), cancel(), claim_for(), submit()

### Community 147 - "People Models and Admin"
Cohesion: 0.25
Nodes (5): PayRecord, Basis, Meta, add(), amend()

### Community 148 - "OIDC Claims Tests"
Cohesion: 0.36
Nodes (6): _app(), _claims(), test_claims_carry_email_and_employee_id(), test_claims_without_employee(), test_no_role_is_no_admin(), test_the_admin_claim_is_the_login_s_role_in_the_requesting_app()

### Community 150 - "Service Years and Tiers"
Cohesion: 0.38
Nodes (5): tier_extra_weeks(), Service tiers (PolicyTier extra weeks after N years), _anniversary(), service_years(), test_service_years_reads_service_date()

### Community 152 - "Training Admin Navigation"
Cohesion: 0.33
Nodes (6): training is an HR app with Courses, Training records, Training sessions and Training matrix in the Compliance sidebar, navigation(), test_compliance_sidebar_lists_check_types_and_checks(), test_reminder_settings_in_the_compliance_sidebar(), test_the_matrix_is_in_the_compliance_sidebar(), test_the_app_is_an_hr_app_with_its_courses_in_the_compliance_sidebar()

### Community 153 - "Policy Year Governance"
Cohesion: 0.47
Nodes (3): governing(), in_force(), _year()

### Community 157 - "NI Number Migration"
Cohesion: 0.40
Nodes (3): Migration, normalise(), normalise_ni_numbers()

### Community 158 - "GP Register Fixtures"
Cohesion: 0.33
Nodes (3): gmc_only(), gp_bodies(), no_waiting()

### Community 160 - "Standard Contract Seed"
Cohesion: 0.50
Nodes (3): _as_seeded(), Migration, seed()

### Community 161 - "Pot Month Helpers"
Cohesion: 0.40
Nodes (3): _month_start(), _months(), _rates()

### Community 163 - "Contract Unit Checks"
Cohesion: 0.40
Nodes (3): check_add(), check_end(), _unit_clash()

### Community 174 - "Bank Holiday Horizon Tests"
Cohesion: 0.50
Nodes (3): _latest_bank_holiday(), test_nightly_says_how_far_the_bank_holidays_run(), test_nightly_warns_when_the_bank_holidays_are_running_out()

## Ambiguous Edges - Review These
- `Hand-entered carry-overs (shell)` → `Going live: first month checklist`  [AMBIGUOUS]
  docs/guides/hr-administrator.md · relation: conceptually_related_to
- `Signing with re-authentication (password or passkey)` → `policies.sign`  [AMBIGUOUS]
  docs/superpowers/plans/2026-10-04-onboarding-documents.md · relation: implements
- `Training (admin)` → `Who can open a file`  [AMBIGUOUS]
  docs/admin/compliance.md · relation: conceptually_related_to

## Knowledge Gaps
- **45 isolated node(s):** `PBS_PASSWORD_FILE`, `passkey_added_subject.txt (Passkey added subject)`, `invitation_subject.txt (Invitation email subject)`, `django-axes 8.3.1`, `django-unfold 0.104.1` (+40 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1425 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **60 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `make_employee()` connect `Employee and Employment Tests` to `People Services Core`, `Absence Booking Tests`, `Test Factories`, `Training Models and Pages`, `Compliance Dashboard Tests`, `Registration Service Tests`, `Training Service`, `Checks Model and Service`, `Onboarding Pages Tests`, `Training Views and Forms`, `Absence Calendar Tests`, `TOIL and Approval View Tests`, `OIDC Claims Tests`, `Document Files`, `Onboarding Checklist Tests`, `Register Models and Lookups`, `Access Rules and Roles`, `Positions and Titles Tests`, `Balance Views Tests`, `Employment Lifecycle`, `Absence Request and Admin Tests`, `Policy Signing Tests`, `Compliance Counts Tests`, `Absence Admin Tests`, `People Test Factories`, `Training Matrix`, `OIDC Provider Tests`, `Login Import Tests`, `Auto Login Tests`, `Absence Notification Tests`, `Checklist Templates and Gates`, `Audit Log and Employee Service`, `TOIL Claim Tests`, `Register Due Items Tests`, `Payroll Report Tests`, `Retention Report Tests`, `Policy Issue and Sign`, `Navigation and Email Case Tests`, `TOIL Claim Approval Tests`, `NI Number Normalising`, `CSP Tests`, `Reminder Schedule`, `Form Rendering Tests`, `Positions and Reporting Line`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **What connects `PBS_PASSWORD_FILE`, `passkey_added_subject.txt (Passkey added subject)`, `invitation_subject.txt (Invitation email subject)` to the rest of the system?**
  _45 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `People Services Core` be split into smaller, more focused modules?**
  _Cohesion score 0.03636858334844912 - nodes in this community are weakly interconnected._
- **Why does `Practice HR README` connect `README and Platform Docs` to `People Services Core`, `Payroll Report and Nightly`, `Compliance Admin Docs`, `Absence and Leave Docs`, `HR Guide Compliance Tasks`, `Absence Services Core`, `OIDC Client Registration`, `People and Training Docs`, `Specs and Backlog Index`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Should `Absence Booking Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.0446543580936024 - nodes in this community are weakly interconnected._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Hand-entered carry-overs (shell)` and `Going live: first month checklist`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Signing with re-authentication (password or passkey)` and `policies.sign`?**
  _Edge tagged AMBIGUOUS (relation: implements) - confidence is low._