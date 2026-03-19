# CI Gate Design (Day 6)

## Goal

Define minimum merge/release gates for canonical frontend and backend repositories.

## Canonical Repositories

- Frontend: `frontend`
- Backend: `<repo-root>`

## Gate Principles

- Fail-fast on quality regressions.
- Keep checks deterministic and command-based.
- Use the same commands in local and CI.
- Separate repository-local checks from cross-repo integration checks.

## Required Gate Matrix

### Frontend Repo Gates

1. Install dependencies
   - `npm ci`
2. Frontend quality gates
   - `npm run check:lint`
   - `npm run check:typecheck`
   - `npm run check:test`
   - `npm run check:build`
3. Backend integration regression (requires backend service reachable)
   - `npm run check:api-e2e`

### Backend Repo Gates

1. Python dependency install
   - `pip install -r requirements.txt`
2. Backend unified quality baseline
   - `python scripts/check_backend_quality.py`

## Workflow Split Strategy

- **Frontend CI** (in canonical mono-repo workflow, frontend working directory)
  - Trigger: pull_request, push (main branches)
  - Jobs:
    - `frontend-build`
    - `integration-e2e` (spins up backend service dependency or targets test environment)

- **Backend CI** (in canonical mono-repo workflow)
  - Trigger: pull_request, push (main branches)
  - Jobs:
    - `backend-quality`

## Required Check Names (Branch Protection)

- Phase 1 (immediate required checks):
  - Frontend: `frontend-build`
  - Backend: `backend-quality`
- Phase 2 (enable when integration target env is configured):
  - Frontend: `integration-e2e`

## Environment Inputs

- Frontend CI:
  - `VITE_API_BASE_URL` (optional, if explicit target needed)
- Backend CI:
  - SQLite defaults are acceptable for baseline tests.
  - API keys are optional for baseline quality checks unless AI-path tests are expanded.

## Failure Handling Rules

- Any required check failure blocks merge.
- Retry only after code or configuration fix.
- No manual override for failing required checks during normalization window.

## Day 7 Implementation Targets

1. Add backend GitHub Actions workflow at repository root:
   - `.github/workflows/backend-quality.yml`
2. Add frontend GitHub Actions workflow at repository root:
   - `.github/workflows/frontend-quality.yml`
3. Confirm check names align with branch protection config.

## Day 7 Implementation Note

- Frontend integration gate is implemented with feature flag:
  - requires repo variable `CDAS_ENABLE_INTEGRATION_E2E=true`
  - requires secret `CDAS_API_BASE_URL`
- Until both are configured, `integration-e2e` remains non-required.

## Post-Consolidation Validation (T4)

- Workflow files validated at repo root:
  - `.github/workflows/frontend-quality.yml`
  - `.github/workflows/backend-quality.yml`
- Job/check names to match branch protection:
  - `frontend-build`
  - `backend-quality`
  - `integration-e2e` (phase 2 required)
