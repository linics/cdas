# Normalization Execution Log

## Day 1 - Governance Baseline

- Completed:
  - Added 2-week normalization plan document.
  - Added repository governance policy and canonical repo declaration.
  - Linked normalization phase in integration phase plan.
- Files:
  - `docs/integration/normalization-plan-2weeks.md`
  - `docs/integration/repo-governance.md`
  - `docs/integration/phase-plan.md`

## Day 2 - Frontend Quality Baseline (Completed)

- Completed:
  - Added standardized quality scripts in `package.json`:
    - `check:build`
    - `check:api-e2e`
    - `check:all`
  - Replaced frontend README with canonical repo and quality command guidance.
  - Verified quality commands:
    - `npm run check:build` PASS
    - `python scripts/run_api_e2e.py` PASS
    - `npm run check:all` PASS
  - Cleaned integration artifacts after regression run.
- Files:
  - `package.json`
  - `README.md`

## Day 3 - Backend Quality Baseline (Completed)

- Completed:
  - Added backend unified quality runner script:
    - `<repo-root>/scripts/check_backend_quality.py`
  - Added backend quality baseline matrix document:
    - `docs/integration/backend-quality-baseline.md`
  - Updated backend README with normalization quality commands.
  - Verified backend baseline checks:
    - `pytest -q` PASS (21 passed)
    - `python scripts/check_backend_quality.py` PASS
  - Observation:
    - current baseline emits deprecation warnings (FastAPI lifespan, Pydantic class Config, PyPDF2 deprecation), to be tracked under future technical-debt cleanup.
- Files:
  - `docs/integration/backend-quality-baseline.md`
  - `<repo-root>/scripts/check_backend_quality.py`
  - `<repo-root>/README.md`

## Day 4 - API Contract Governance (Completed)

- Completed:
  - Added `/api/v2` contract governance document with stability policy, change rules, and error semantics.
  - Updated API mapping doc to align with current delivered capabilities (archive, class lifecycle, assignment-group lifecycle).
  - Linked API governance document in phase plan.
  - Verified OpenAPI availability and active `/api/v2` paths from runtime spec.
- Files:
  - `docs/integration/api-contract-governance.md`
  - `docs/integration/api-mapping.md`
  - `docs/integration/phase-plan.md`

## Day 5 - README and Onboarding Alignment (Completed)

- Completed:
  - Updated backend README to point to canonical frontend repo and clarify legacy frontend policy.
  - Added backend `.env.example` with current config variables.
  - Added frontend `.env.example` for API base URL override.
  - Updated frontend README with `.env` setup notes and backend template reference.
  - Added 15-minute onboarding playbook covering backend + frontend + baseline checks.
  - Updated release and manual QA docs to reflect current deferred scope and latest baseline run id.
  - Re-verified frontend integration baseline command after docs alignment:
    - `npm run check:api-e2e` PASS
  - Cleaned integration artifacts after regression run.
- Files:
  - `<repo-root>/README.md`
  - `<repo-root>/.env.example`
  - `.env.example`
  - `README.md`
  - `docs/integration/onboarding-15min.md`
  - `docs/integration/pre-release-checklist.md`
  - `docs/integration/manual-test-script.md`
  - `docs/integration/phase-plan.md`

## Day 6 - CI Gate Design (Completed)

- Completed:
  - Added CI gate design document with canonical gate matrix, required check names, and workflow split strategy.
  - Linked CI gate design doc in phase plan normalization section.
- Files:
  - `docs/integration/ci-gate-design.md`
  - `docs/integration/phase-plan.md`

## Day 7 - CI Gate Implementation (Completed)

- Completed:
  - Added frontend CI workflow:
    - `.github/workflows/frontend-quality.yml`
    - includes `frontend-build` and feature-flagged `integration-e2e`
  - Added backend CI workflow:
    - `.github/workflows/backend-quality.yml`
    - includes `backend-quality`
  - Updated CI gate design document with phased required-check rollout and integration gate activation conditions.
  - Re-verified frontend build gate after workflow introduction:
    - `npm run check:build` PASS
- Files:
  - `.github/workflows/frontend-quality.yml`
  - `.github/workflows/backend-quality.yml`
  - `docs/integration/ci-gate-design.md`

## Repository Consolidation (Requested)

- Completed:
  - Canonical frontend has been consolidated into backend repo at `frontend/`.
  - Previous in-repo legacy frontend is preserved as backup snapshot:
    - `frontend_legacy_20260302_131428`
  - Root CI workflows now live under backend repo `.github/workflows/`.
  - Nested frontend-local `.github` workflow directory was removed to avoid duplicated CI definitions.
  - Re-validated merged frontend baseline:
    - `npm run check:all` PASS (run id `1772428833_vmq4`)
  - Re-validated backend baseline in merged workspace:
    - `python scripts/check_backend_quality.py` PASS
  - Cleaned integration artifacts after validation run.

## Day 7 Impact Check After Consolidation (Completed)

- Completed:
  - Verified Day 7 CI workflow paths remain valid after frontend merge into `frontend/`.
  - Confirmed root workflow files exist:
    - `.github/workflows/frontend-quality.yml`
    - `.github/workflows/backend-quality.yml`
  - Re-verified quality commands in merged workspace:
    - `npm run check:all` PASS
    - `python scripts/check_backend_quality.py` PASS

## Day 8 - Migration and Cleanup SOP (Completed)

- Completed:
  - Added migration and integration-data cleanup SOP document.
  - Added destructive-script safeguard (`clean_test_data.py` requires `--force`).
  - Linked migration/cleanup SOP in phase plan.
- Files:
  - `docs/integration/migration-cleanup-sop.md`
  - `scripts/clean_test_data.py`
  - `docs/integration/phase-plan.md`

## Day 9 - Release Checklist Standardization (Completed)

- Completed:
  - Added standardized release-gate checklist with consolidated command matrix.
  - Linked release-gate checklist from phase plan.
  - Added references in legacy pre-release checklist and manual QA script.
  - Verified command matrix execution:
    - `npm run check:all` PASS (run id `1772440789_2nzp`)
    - `python scripts/check_backend_quality.py` PASS
  - Cleaned integration artifacts after command-matrix verification run.
- Files:
  - `docs/integration/release-gate-checklist.md`
  - `docs/integration/pre-release-checklist.md`
  - `docs/integration/manual-test-script.md`
  - `docs/integration/phase-plan.md`

## Day 10 - Dry Run Closure (Completed)

- Completed:
  - Added normalization closure report with delivered outcomes and residual technical-debt tracking.
  - Linked closure report in phase plan.
  - Confirmed release matrix commands and post-run cleanup are passing.
- Files:
  - `docs/integration/normalization-closure-report.md`
  - `docs/integration/phase-plan.md`

## Status

- 2-week normalization plan: completed.

## Post-Plan Hardening (T backlog)

- T1 in progress:
  - Added change-batch split plan for safer review/commit sequencing.
  - File: `docs/integration/change-batch-plan.md`
- T2 completed:
  - Runtime artifacts untracked from git index (`storage/chroma`, `storage/documents/[0-9]*`, `storage/uvicorn.pid`).
  - `.gitignore` updated to prevent re-tracking.
- T3 completed:
  - `frontend/scripts/run_api_e2e.py` now reads base URL from env (`CDAS_API_BASE_URL` / `VITE_API_BASE_URL`) with local fallback.
- T4 completed:
  - CI check-name alignment documented after mono-repo consolidation in `docs/integration/ci-gate-design.md`.
- T5 completed:
  - Added frontend lint/typecheck/test gates and minimal test baseline.
  - Added `eslint.config.js`, `tsconfig.json`, `vitest.config.ts`, and `src/app/utils/id.test.ts`.
  - Updated frontend CI `frontend-build` job to include lint/typecheck/test/build gate chain.
  - Verified `npm run check:all` PASS (run id `1772444843_7fwg`).
- T6 completed:
  - Replaced deprecated Pydantic class `Config` usage with `ConfigDict` across v2 API schemas.
  - Migrated FastAPI startup hook from `on_event("startup")` to lifespan context.
  - Updated startup migration guard test to use lifespan context.
  - Migrated PDF parser dependency from `PyPDF2` to `pypdf` and updated requirements.
  - Verified `python scripts/check_backend_quality.py` PASS with warnings eliminated.
  - Re-verified integration e2e after startup/lifespan migration:
    - `npm run check:api-e2e` PASS (run id `1772445617_5qwb`).
- T7 completed:
  - Updated startup migration order to prefer migrations first, with `create_all` only as fallback for missing-table bootstrap.
  - Optimized migration backup behavior to create DB backup only when pending migrations exist.
  - Re-verified backend quality and integration e2e:
    - `python scripts/check_backend_quality.py` PASS
    - `npm run check:api-e2e` PASS (run id `1772446044_x2jr`).
- T8 completed:
  - Hardened runtime responses for production baseline:
    - `/health` returns minimal payload `{"status":"ok"}`.
    - global middleware logs unhandled exceptions via `cdas.api` logger and returns HTTP 500.
  - Runtime verification:
    - `curl http://127.0.0.1:8000/health` PASS (`{"status":"ok"}`).
- T9 completed:
  - Upgraded frontend security-sensitive toolchain dependencies:
    - `vite` -> `6.4.1`
    - `vitest` -> `4.0.18`
  - `npm audit` result after upgrade: `0 vulnerabilities`.
  - Re-verified frontend gates:
    - `npm run check:lint` PASS
    - `npm run check:typecheck` PASS
    - `npm run check:test` PASS
    - `npm run check:build` PASS
    - `npm run check:api-e2e` PASS (run id `1772446572_y0cn`).
- T10 completed:
  - Consolidated release documentation entry point:
    - archived `docs/integration/pre-release-checklist.md` into redirect-style historical note.
    - retained single active release gate doc: `docs/integration/release-gate-checklist.md`.
- T11 completed:
  - Final dry-run acceptance verification executed on merged mono-repo workspace:
    - backend quality: `python scripts/check_backend_quality.py` PASS
    - frontend gate chain: lint/typecheck/test/build PASS
    - integration e2e: `npm run check:api-e2e` PASS (run id `1772446572_y0cn`)
    - backend health: `GET /health` PASS (`200`, `{"status":"ok"}`)
- T0 completed:
  - Performed baseline cleanup verification and scope-freeze cut definition in mixed working tree.
  - Added explicit in-scope/out-of-scope boundary and commit-cut recommendation:
    - `docs/integration/scope-freeze-baseline.md`
  - Linked scope-freeze note in change batch plan.
