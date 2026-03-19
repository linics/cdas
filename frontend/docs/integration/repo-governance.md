# Repository Governance

## Canonical Repositories

- Frontend development and release source of truth: `frontend`
- Backend development and release source of truth: `<repo-root>`

## Legacy Directory Policy

- Legacy standalone frontend path: `(archived legacy frontend)`
- This directory is retained for historical reference only.
- Do not introduce new feature development in the legacy standalone frontend directory.
- Bug fixes or alignment work should be implemented in `CDAS-test2\CDAS-test2\frontend`.

## Branch and Change Discipline

- During normalization window, freeze new product features.
- Prioritize standards, tooling, docs, CI, and release governance.
- Every standards change must include:
  - command verification evidence
  - docs update in `docs/integration`

## Required Validation Baseline

- Frontend: `npm run build`
- Integration regression: `python scripts/run_api_e2e.py`
- Backend health endpoint: `GET /health` returns `200`
