# Release Gate Checklist (Standardized)

## Scope

- Frontend: `frontend`
- Backend: `<repo-root>`
- Runtime baseline: backend `http://127.0.0.1:8000`, frontend `http://127.0.0.1:5173`

## Required Command Matrix

### Frontend Gate Commands

Run in `frontend/`:

```bash
npm run check:build
npm run check:api-e2e
```

Or one-shot:

```bash
npm run check:all
```

### Backend Gate Commands

Run in backend root:

```bash
python scripts/check_backend_quality.py
```

### Cleanup Command (Post Regression)

Run in backend root:

```bash
python scripts/clean_integration_artifacts.py --dry-run
python scripts/clean_integration_artifacts.py
```

## Merge Gate Criteria

- `frontend-build` gate passes.
- `backend-quality` gate passes.
- `integration-e2e` gate passes when enabled by repo variable/secret.
- No unresolved blocking issues (`P0`) in active integration scope.

## Release Readiness Checklist

1. Build and quality
   - [ ] Frontend build command passes
   - [ ] Backend quality baseline command passes
2. Core end-to-end flow
   - [ ] Teacher register/login/create/publish works
   - [ ] Student view/submit/next-phase flow works
   - [ ] Teacher evaluation and student feedback flow works
3. Knowledge base
   - [ ] Upload/list/delete and ready status works
4. Safety and cleanup
   - [ ] Selective cleanup executed for integration artifacts
   - [ ] No destructive cleanup script run without explicit `--force`
5. Runtime health
   - [ ] `GET /health` returns `200`

## Manual QA Entry

- Detailed click-through steps: `docs/integration/manual-test-script.md`

## Source References

- Normalization log: `docs/integration/normalization-execution-log.md`
- Verification log: `docs/integration/verification-log.md`
- Migration/cleanup SOP: `docs/integration/migration-cleanup-sop.md`
