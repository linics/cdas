# Two-Week Normalization Plan

## Objective

Stabilize engineering standards and delivery process without adding new product features.

## Scope and Baseline

- Frontend canonical repo: `frontend`
- Backend canonical repo: `<repo-root>`
- Legacy standalone frontend (reference only, not active development): `(archived legacy frontend)`
- Business feature scope is frozen during this plan.

## Execution Window

- Duration: 2 weeks (10 work days)
- Mode: light normalization (no large refactor)

## Week 1 - Baseline and Standards

### D1 - Scope Freeze and Governance

- Freeze feature scope and define normalization boundaries.
- Publish canonical repo policy and legacy repo handling.
- Output: governance doc and owner matrix.

### D2 - Frontend Quality Baseline

- Add standardized quality scripts in frontend (`build`, regression checks).
- Define pass/fail criteria for local pre-merge checks.
- Output: runnable quality commands and command references.

### D3 - Backend Quality Baseline

- Define backend quality command set (tests, migration sanity, syntax checks).
- Output: backend checklist commands and expected pass criteria.

### D4 - API Contract Rules

- Freeze `/api/v2` contract change rules (compatibility, error semantics, naming).
- Output: API governance addendum.

### D5 - Documentation Alignment

- Align README and integration docs with real startup paths and current architecture.
- Output: corrected readme and onboarding consistency checks.

## Week 2 - CI and Release Discipline

### D6 - CI Gate Design

- Define minimum CI gates for frontend, backend, and integration checks.

### D7 - CI Gate Implementation

- Implement CI workflow skeleton and required checks.

### D8 - Migration and Data SOP

- Standardize migration execution and cleanup boundaries.
- Document safe usage of cleanup scripts for integration-only data.

### D9 - Release Checklist Standardization

- Merge QA scripts and release checks into one operational checklist.

### D10 - Dry Run and Closure

- Run full process once end-to-end and publish normalization report.

## Definition of Done

- Frontend has standardized quality commands and can run them locally.
- Backend has standardized quality commands and migration safety notes.
- Integration regression command is treated as required validation.
- Docs are aligned with real directories, commands, and ownership.
- Legacy frontend is explicitly marked as non-canonical in docs.
