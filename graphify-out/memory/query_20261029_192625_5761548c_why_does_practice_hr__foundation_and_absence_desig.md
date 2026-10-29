---
type: "query"
date: "2026-10-29T19:26:25.117602+00:00"
question: "Why does Practice HR: foundation and absence design (spec 1) connect Specs and Plans Index to Absence Ledger Plan, Absence Workflow Plan, People Domain Concepts, Compliance Reminder Digest, Foundation Plan?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["Practice HR: foundation and absence design (spec 1)", "Absence ledger implementation plan", "Absence workflow, payroll and API implementation plan", "Practice HR foundation implementation plan", "Spec 4: Training compliance", "Onboarding, offboarding and documents design (spec 3)", "employments.py"]
---

# Q: Why does Practice HR: foundation and absence design (spec 1) connect Specs and Plans Index to Absence Ledger Plan, Absence Workflow Plan, People Domain Concepts, Compliance Reminder Digest, Foundation Plan?

## Answer

Expanded from original query via vocab: [foundation, absence, design, spec, plan, ledger, workflow, compliance, digest]. BFS was too broad (738 nodes), so traced the spec 1 node's ego network directly. Spec 1 bridges by citation, not content: 10 edges, all EXTRACTED doc-to-doc. The three 2026-09-28 plans cite it; the tidy-up and HR-only sign-in plans reference it; it names spec 2 (rota), spec 4 (training compliance) and is referenced by spec 3. Plans map to layers: foundation -> people/services (employments, access, positions, contracts, audit) and accounts/oidc; ledger -> absence/models/ledger, bookings, signals, costing, accrual; workflow -> year_end, api/views, notify, request and approval views. Compliance Reminder Digest is reached via Spec 4 -> DueItem contract; People Domain Concepts via spec 3 -> Services are the only writers. Gap: only 3 of spec 1's 43 concept nodes link to the spec node and none link to code; they reach code only through plan concepts. The 19 import cycles all run through one deferred import in people/services/employments.py:84-85 (_cancel_after imports absence bookings and bank_holidays to cancel a leaver's later absences); absence services import people.services at module top (policies.py:7, bookings.py:11, bank_holidays.py:11).

## Outcome

- Signal: useful

## Source Nodes

- Practice HR: foundation and absence design (spec 1)
- Absence ledger implementation plan
- Absence workflow, payroll and API implementation plan
- Practice HR foundation implementation plan
- Spec 4: Training compliance
- Onboarding, offboarding and documents design (spec 3)
- employments.py