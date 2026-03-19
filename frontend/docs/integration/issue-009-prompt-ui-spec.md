# ISSUE-009 Prompt and UI Spec (v1.0)

## Goal

Upgrade the core teaching workflow quality for assignment design, grading, and student response by defining strict prompt constraints and frontend interaction rules.

## Scope

- Assignment design page:
  - AI preview (`/api/v2/assignments/preview`)
  - Lesson-plan one-click generation (`/api/v2/assignments/from-lesson-plan`)
- Grading page:
  - AI assist scoring (`/api/v2/evaluations/ai-assist`)
- Student response page:
  - phase-step presentation and guidance wording

## Design Principles

1. Lesson-plan first: generated drafts must stay faithful to uploaded lesson plans.
2. Lightweight RAG enhancement: add only top-k relevant chunks (recommended 3-5) as support context.
3. Actionable outputs: each step must be executable and verifiable.
4. Narrative continuity: include a coherent scenario thread across phases.
5. Compatibility first: keep existing `objectives/phases/rubric` contract.
6. Reliable fallback: timeout/error must degrade gracefully to editable defaults.

## Prompt Architecture

### Prompt-A: Assignment AI Preview (Generic)

Purpose: generate structured draft from teacher-entered context.

Hard constraints:
- output JSON only
- include `objectives.knowledge/process/emotion`
- include `phases[].name/order/steps`
- each `step` includes `name/description/checkpoints`
- each step has 1-2 checkpoints only
- avoid repetitive formulaic wording
- phase progression must show: problem framing -> evidence gathering -> analysis -> expression/reflection

### Prompt-B: Lesson-Plan One-Click Generation (Dedicated)

Purpose: transform uploaded lesson plan into assignment draft while preserving teaching logic.

Hard constraints:
- keep lesson-plan objective-activity-output-evaluation mapping
- do not fabricate core conclusions not grounded in source text
- allow concise scaffolding language in step descriptions
- preserve `objectives/phases/rubric` structure for frontend compatibility

### Prompt-C: AI Grading Suggestion

Purpose: provide teacher-facing scoring support, not automatic final scoring.

Hard constraints:
- each rubric dimension requires score + evidence + reason
- dimensions must match rubric names exactly
- feedback should include highlights, gaps, and next action

## RAG Strategy

- Default: lesson-plan direct extraction.
- Optional enhancement: append top-k retrieved chunks.
- Query template: `title + topic + description + assignment_type + grade`.
- Filter priority:
  1) selected `document_id`
  2) main/related subjects
  3) system knowledge base supplements

Prompt context budget:
- recommended RAG injection text: <= 1200-1800 chars
- avoid full-document raw injection when using retrieval mode

## Frontend Interaction Constraints

## Assignment Designer

Default step editing mode should use 3 core fields only:
1. Task action (`stepName`)
2. Learning scaffold (`description`)
3. Evidence to submit (`evidence`)

Advanced fields (collapsed by default):
- phase name
- lesson time suggestion
- evaluation points

UI intent:
- reduce cognitive load
- keep value density per field
- keep structured compatibility with existing backend payload

## Feedback/Status

- success/warning/error must appear in closable floating bubble
- timeout message must include clear next action guidance

## Data Compatibility

Keep API schema unchanged:
- `objectives_json`
- `phases_json`
- `rubric_json`

Semantic mapping:
- `phase.title` for scenario stage headline
- `step.description` for scaffolding text
- `checkpoints` for verifiable outputs

## Performance and Fallback

- frontend timeout for lesson-plan generation can be higher than default request timeout
- backend lesson-plan prompt path should use fast-fail timeout and fallback defaults
- fallback must keep draft editable and publishable

## Acceptance Criteria

1. Generated drafts are less formulaic and show clearer scenario continuity.
2. Default step editor is compact (3 core fields), with optional advanced fields.
3. Timeout/failure does not block teacher workflow.
4. Existing API e2e flow remains passing.

## Implementation Plan

1. Phase 1: Prompt refinement (A/B), keep schema unchanged.
2. Phase 2: Designer UI compact mode + advanced toggle.
3. Phase 3: Grading prompt strengthening and student-side guidance wording.
4. Phase 4: Sample-based quality review and parameter tuning.
