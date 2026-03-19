# Scope Freeze Baseline (T0)

## Purpose

Lock a reviewable commit boundary in the mixed mono-repo working tree and prevent accidental cross-scope commits.

## Snapshot

- Date: 2026-03-02
- Workspace: `<repo-root>`
- Branch: `main`
- Working tree state: mixed changes (feature integration + hardening + docs + runtime artifact untracking)

## Baseline Verification

1. Backend quality baseline
   - Command: `python scripts/check_backend_quality.py`
   - Result: PASS
2. Frontend quality gates
   - Command: `npm run check:lint && npm run check:typecheck && npm run check:test && npm run check:build`
   - Result: PASS
3. Integration API e2e
   - Command: `npm run check:api-e2e`
   - Result: PASS (`run_id=1772446572_y0cn`)
4. Runtime health
   - Command: `curl http://127.0.0.1:8000/health`
   - Result: PASS (`{"status":"ok"}`)
5. Frontend dependency security
   - Command: `npm audit --json`
   - Result: PASS (`0 vulnerabilities`)

## Scope Freeze Decision

### In-scope for hardening/normalization closure

- Backend startup and migration hardening:
  - `app/main.py`
  - `app/migrations.py`
- Backend dependency baseline:
  - `requirements.txt`
- Frontend security patch level:
  - `frontend/package.json`
  - `frontend/package-lock.json`
- Release/verification traceability docs:
  - `frontend/docs/integration/pre-release-checklist.md`
  - `frontend/docs/integration/verification-log.md`
  - `frontend/docs/integration/normalization-execution-log.md`
  - `frontend/docs/integration/scope-freeze-baseline.md`

### Out-of-scope for hardening closure (separate review batches)

- Large frontend app structure replacement under `frontend/src/`.
- Class/group/archive feature payload across backend API/model files.
- CI/workflow introduction under `.github/`.
- Runtime artifact untracking deletions under `storage/chroma`, `storage/documents/*`, `storage/uvicorn.pid`.

## Commit Cut Recommendation

1. Cut A (hardening closure): only in-scope files listed above.
2. Cut B (runtime artifact hygiene): `.gitignore` + storage index removals.
3. Cut C (feature integration payload): remaining backend/frontend feature files.

## Guardrails

- Do not re-add `storage/chroma`, `storage/documents/[0-9]*/`, `storage/uvicorn.pid`.
- Keep release checklist single entry at `docs/integration/release-gate-checklist.md`.
- Keep backend quality runner reproducible on fresh CI environments (`pytest` included in dependencies).
