# Integration Phase Plan (Scheme 1)

## Phase A Completed: Core Workflow Connection

Scope completed in rebuilt frontend:

1. Authentication (teacher/student) against backend auth APIs
2. Teacher assignment design/preview/create/publish
3. Student assignment list and phased submission flow
4. Teacher grading with AI assist entrypoint and numeric scoring
5. Student feedback viewing via received evaluations
6. Knowledge base upload/list/delete against documents API

Acceptance baseline:

- Frontend compiles successfully with backend API integration code
- Core pages no longer rely on local seed/storage for these workflows

## Phase B Stabilization (Completed for QA)

1. Route and navigation hardening
   - completed: role-based redirects for teacher/student route boundaries
   - completed: not-found fallback route for invalid paths
2. End-to-end verification with live backend
   - completed: teacher register/login -> create/publish
   - completed: student login -> view assignment -> submit phased task
   - completed: teacher evaluate -> student feedback visible
   - completed: document upload/index/list/delete
   - completed: historical failed document reindex and status recovery
3. Error handling polish
   - completed: strict E2E check marks document indexing `failed` as test failure
   - completed: core teacher/student pages use unified state cards for loading/error/permission states
   - completed: secondary cards and header-level notices are standardized with shared status banner
   - completed: dashboard statistics wording and iconography consistency polishing

Phase B delivery status: completed for formal QA handoff.

## Phase C Deferred Feature Recovery (In Progress)

1. Implement class invite/group lifecycle APIs and UI
   - progress: class invite + class group lifecycle has been connected end-to-end
   - pending: deep collaboration parity shifts to item 4 (group submission/evaluation)
2. Add archived assignment lifecycle support
   - progress: backend and frontend core archive/unarchive lifecycle is delivered
   - pending: minor UX consistency refinements in teacher workspace
3. Expand profile/settings persistence
4. Complete group collaboration and group evaluation parity
   - progress: assignment-group creation/member-edit + group submission shared visibility + group evaluation shared visibility delivered
   - progress: teacher submission list now supports group-based filtering for grading navigation
   - progress: group member operations now support quick class switching and student search; group progress includes latest submission/evaluation timestamps
   - progress: assignment detail now supports one-click high-risk filtering for group triage
   - progress: grading panel now supports group-aggregated grading view with risk cues, scoring distribution summary, and quick submission switching
   - pending: deeper collaboration UX and analytics parity
5. Connect notifications and search to backend services

Detailed priority sequencing is documented in `docs/integration/phase-c-priority.md`.

## Operating Rules for Deferred Work

- Keep all deferred gaps documented in `docs/integration/feature-gap-backlog.md`
- Avoid blocking Phase A core workflow with non-critical parity items
- Prefer additive API and UI changes that preserve current working flow

## Phase D Engineering Normalization (2-week)

- Objective: standardize quality gates, repo governance, and release discipline without expanding business feature scope.
- Plan document: `docs/integration/normalization-plan-2weeks.md`
- Repo governance: `docs/integration/repo-governance.md`
- Backend quality baseline: `docs/integration/backend-quality-baseline.md`
- API contract governance: `docs/integration/api-contract-governance.md`
- 15-minute onboarding: `docs/integration/onboarding-15min.md`
- CI gate design: `docs/integration/ci-gate-design.md`
- Migration and cleanup SOP: `docs/integration/migration-cleanup-sop.md`
- Release gate checklist: `docs/integration/release-gate-checklist.md`
- Normalization closure report: `docs/integration/normalization-closure-report.md`
- CI workflows implemented:
  - frontend: `.github/workflows/frontend-quality.yml`
  - backend: `.github/workflows/backend-quality.yml`
