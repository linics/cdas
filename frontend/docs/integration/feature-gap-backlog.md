# Feature Gap Backlog (Scheme 1)

This backlog records known frontend/backend gaps intentionally deferred while delivering the core workflow.

## GAP-01 Class Invite and Group Lifecycle

- Status: completed (core lifecycle delivered)
- Frontend expectation (legacy):
  - class invite code generation/join flow
  - class-level group organization and member management UI
- Backend status:
  - delivered: class create/list/join/member-list/invite-reset APIs in `/api/v2/classes/*`
  - delivered: class group create/list/delete and member assignment/unassignment APIs
- Current handling in rebuilt frontend:
  - delivered: `TeacherClassManager.tsx` supports class creation, invite code reset, roster view, group creation, group deletion, and member assignment
  - delivered: `StudentDashboard.tsx` supports invite-code join and class context (including joined group display)
- Future target:
  - deep assignment-level group collaboration continues under `GAP-04`

## GAP-02 Assignment Archive Semantics

- Status: completed (core lifecycle delivered)
- Frontend expectation (legacy): `draft/published/archived`
- Backend status:
  - delivered: `is_archived`, `archived_at`, archive/unarchive APIs
  - delivered: assignment listing supports `include_archived`
- Current handling:
  - delivered: teacher dashboard/designer history show archive status and archive actions
  - delivered: student listing excludes archived assignments
- Future target:
  - continue UX refinement for archive filters across teacher pages as needed

## GAP-03 Personal Profile Extensions

- Status: deferred
- Frontend expectation (legacy): extra profile/contact fields
- Backend status: registration currently focuses on core fields (`username/password/role/name`, plus student grade/class)
- Current handling:
  - optional fields can be entered in UI where needed, but unsupported fields are not persisted
- Future target:
  - expand profile model and settings API

## GAP-04 Advanced Group Submission Mode

- Status: partial (core collaboration path delivered; deep parity pending)
- Frontend expectation (legacy): richer group composition and per-group coordination behavior
- Backend status:
  - delivered: assignment group create/list API with validated student membership
  - delivered: group submission read/write/submit access for all group members
  - delivered: group evaluation visibility for all group members (`/evaluations/my-received`)
- Current handling:
  - delivered: assignment detail supports teacher-side assignment group creation (class-member visual picker) and student-side group-mode submission
  - delivered: assignment detail supports existing assignment-group member editing (before submission records are generated)
  - delivered: member selection/edit supports quick class switching and student search
  - delivered: grading/detail pages show group submission context
  - delivered: grading panel supports group-aggregated view (risk badge, per-group progress, scoring distribution summary, quick jump to latest submission)
  - delivered: teacher can view group-level submission progress summary (including latest submission/evaluation timestamps) and jump to latest grading entry
  - delivered: assignment detail supports one-click high-risk filtering (`仅高风险`) from risk tags
  - delivered: teacher submission list supports group-based filtering for faster grading navigation
- Future target:
  - improve advanced collaboration UX (group workspace orchestration, richer group-level analytics and evaluation views)

## GAP-05 Full Notification and Search Integration

- Status: deferred
- Frontend expectation (legacy): meaningful notifications and global search behavior
- Backend status: no dedicated notification/search integration consumed by current pages
- Current handling:
  - header controls remain mostly presentational
- Future target:
  - wire notification/search APIs and cross-page filters
