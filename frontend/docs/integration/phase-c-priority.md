# Phase C Priority Plan (Deferred Features)

## Goal

Recover deferred capabilities after Scheme 1 core workflow delivery, without regressing main teacher-student flow.

## Priority Order

### P0 - Class Invite and Group Lifecycle (GAP-01)

Current status:

- completed (core)
- delivered: class create/invite-reset/join/list/member-list APIs and teacher/student UI wiring
- delivered: class group create/list/delete + member assignment/unassignment lifecycle
- pending: deep assignment-level group collaboration parity (tracked in GAP-04)

Why first:

- Unlocks real class-scoped publishing and student join path
- Most visible functional gap in current UI placeholders

Suggested backend additions:

- `POST /api/v2/classes/` create class
- `POST /api/v2/classes/{id}/invite-code/reset`
- `POST /api/v2/classes/join` (invite code)
- `GET /api/v2/classes/my`
- `POST /api/v2/classes/{id}/groups` and membership endpoints

Frontend target pages:

- `TeacherClassManager.tsx` replace placeholder with real CRUD/join/group UI
- `StudentDashboard.tsx` enable class join and class context display

Acceptance:

- Teacher can create class and issue invite code
- Student can join with valid code and appears in class roster
- Basic group creation and member assignment works end-to-end

### P1 - Archived Assignment Lifecycle

Current status:

- mostly delivered
- delivered: archive/unarchive APIs, archive fields, teacher UI actions, student visibility exclusion
- pending: incremental filter/UX polish where needed

Why second:

- Needed for teacher workspace hygiene and long-term assignment management

Suggested backend additions:

- assignment status enum with `draft/published/archived`
- `POST /api/v2/assignments/{id}/archive`
- `POST /api/v2/assignments/{id}/unarchive`

Frontend target pages:

- `Dashboard.tsx` and `AssignmentDesigner.tsx` archive filters and actions

Acceptance:

- Archived assignments excluded from student visible lists
- Teacher can archive/unarchive without data loss

### P2 - Profile and Settings Persistence

Why third:

- Improves account completeness, but not blocking core teaching flow

Suggested backend additions:

- user profile fields update endpoint (`phone`, optional metadata)
- settings endpoint for personal preferences

Frontend target pages:

- `Root.tsx` profile area and future settings panel
- `Auth.tsx` optional fields persistence alignment

Acceptance:

- Profile edits persist and reflect in session `/me`

### P3 - Notification and Search Integration

Why fourth:

- Improves efficiency and discoverability after main operations stabilize

Suggested backend additions:

- notifications listing/read APIs
- search endpoint for assignments/documents

Frontend target pages:

- `Root.tsx` header bell + search input wiring

Acceptance:

- Notification unread count and basic search results available

## Execution Rule

- Implement in P0 -> P3 order
- Keep `docs/integration/feature-gap-backlog.md` as source of truth for gap status updates
- Run `npm run build` and `python scripts/run_api_e2e.py` after each feature batch
