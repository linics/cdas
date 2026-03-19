# Frontend-Backend API Mapping (Scheme 1)

This project uses `CDAS-test2/CDAS-test2/frontend` as the primary frontend and maps to backend APIs in `CDAS-test2`.

Contract governance reference: `docs/integration/api-contract-governance.md`.

## Base and Auth

- Base path: `/api` (Vite proxy forwards to backend)
- Auth routes:
  - `POST /api/v2/auth/register`
  - `POST /api/v2/auth/login`
  - `GET /api/v2/auth/me`
- Token storage: local key `cdas_token`
- Temporary account rule: teacher/student identity code is stored as `username`

## Subject Mapping

- `GET /api/v2/subjects/`
- Frontend-to-backend subject code normalization:
  - `infoTech -> it`
  - `arts -> art`
  - `sports -> pe`
- Reverse normalization is applied for UI display/edit.

## Assignment Mapping

- Routes used:
  - `POST /api/v2/assignments/preview`
  - `POST /api/v2/assignments/`
  - `GET /api/v2/assignments/`
  - `GET /api/v2/assignments/{id}`
  - `PUT /api/v2/assignments/{id}`
  - `POST /api/v2/assignments/{id}/publish`
  - `POST /api/v2/assignments/{id}/archive`
  - `POST /api/v2/assignments/{id}/unarchive`
  - `POST /api/v2/assignments/{id}/groups`
  - `GET /api/v2/assignments/{id}/groups`
  - `PUT /api/v2/assignments/{id}/groups/{group_id}/members`
  - `DELETE /api/v2/assignments/{id}/groups/{group_id}`
  - `DELETE /api/v2/assignments/{id}`
- Field normalization:
  - Inquiry depth: `medium <-> intermediate`
  - Grade code: `p1..p6/j7..j9 <-> 1..9`
  - Lesson steps are converted to/from backend `phases_json`
- Current status mapping:
  - Frontend `published` = backend `is_published=true`
  - Frontend `draft` = backend `is_published=false`
  - Frontend `archived` = backend `is_archived=true`

## Submission and Evaluation Mapping

- Submission routes:
  - `POST /api/v2/submissions/`
  - `GET /api/v2/submissions/my`
  - `GET /api/v2/submissions/{id}`
  - `PUT /api/v2/submissions/{id}`
  - `POST /api/v2/submissions/{id}/submit`
  - `GET /api/v2/submissions/assignment/{assignment_id}`
- Next-phase flow:
  - backend `next_submission_id` is used to chain phased submissions in student flow
- Group submission behavior:
  - `group_id` submission supports shared read/write for group members
  - response includes `group_name`, `group_members`, `teacher_evaluated_at`
- Evaluation routes:
  - `POST /api/v2/evaluations/teacher`
  - `GET /api/v2/evaluations/submission/{id}`
  - `POST /api/v2/evaluations/ai-assist`
  - `GET /api/v2/evaluations/my-received`
- Score model:
  - Teacher final score uses numeric scale `1..4`

## Class and Invite Mapping

- Routes used:
  - `POST /api/v2/classes/`
  - `GET /api/v2/classes/my`
  - `POST /api/v2/classes/join`
  - `GET /api/v2/classes/{class_id}/members`
  - `POST /api/v2/classes/{class_id}/invite-code/reset`
  - `GET /api/v2/classes/{class_id}/groups`
  - `POST /api/v2/classes/{class_id}/groups`
  - `POST /api/v2/classes/{class_id}/groups/{group_id}/members`
  - `DELETE /api/v2/classes/{class_id}/groups/{group_id}/members/{student_id}`
  - `DELETE /api/v2/classes/{class_id}/groups/{group_id}`
- Behavior:
  - Teacher can manage class roster and class groups.
  - Student can join via invite code and receive joined group context.

## Knowledge Base Mapping

- Routes used:
  - `GET /api/documents`
  - `POST /api/documents/upload`
  - `GET /api/documents/{id}`
  - `DELETE /api/documents/{id}`
- Frontend groups system and user docs using `source` and supports polling while status is `uploaded/indexing`.
