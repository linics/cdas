# Change Batch Plan (T1)

## Goal

Reduce mixed working-tree risk by splitting changes into reviewable batches.

## Batch B1 - Frontend Consolidation Baseline

- Scope:
  - `frontend/` merged canonical app structure
  - route/page/api integration changes already validated
- Representative paths:
  - `frontend/src/app/`
  - `frontend/docs/integration/`
  - `frontend/package.json`

## Batch B2 - Runtime Artifact Hygiene

- Scope:
  - stop tracking runtime-generated `storage` artifacts
  - preserve source `storage/raw` curriculum files
- Paths:
  - `.gitignore`
  - `storage/chroma/*` (index removal)
  - `storage/documents/[0-9]*/` (index removal)
  - `storage/uvicorn.pid` (index removal)

## Batch B3 - CI and E2E Contract Alignment

- Scope:
  - ensure CI path correctness after mono-repo consolidation
  - ensure e2e base URL can be configured from environment
- Paths:
  - `.github/workflows/frontend-quality.yml`
  - `.github/workflows/backend-quality.yml`
  - `frontend/scripts/run_api_e2e.py`

## Batch B4 - Normalization Documentation Closure

- Scope:
  - Day 8/9/10 docs and checklist consolidation
- Paths:
  - `frontend/docs/integration/migration-cleanup-sop.md`
  - `frontend/docs/integration/release-gate-checklist.md`
  - `frontend/docs/integration/normalization-closure-report.md`
  - `frontend/docs/integration/normalization-execution-log.md`

## Review Sequence

1. B2 (safety, low behavior risk)
2. B3 (CI reliability)
3. B4 (governance traceability)
4. B1 (largest feature payload, final comprehensive review)

## T0 Scope Freeze Addendum

- Baseline scope freeze snapshot and cut boundary:
  - `docs/integration/scope-freeze-baseline.md`
- Hardening closure cut should exclude large feature payload and keep only T7/T8/T9/T10/T11 related files.
