# Migration and Integration Data Cleanup SOP

## Scope

- Backend repo: `<repo-root>`
- Frontend repo (in-repo): `frontend`
- Applies to local dev, integration verification, and pre-release checks.

## Safety Rules

- Prefer **selective cleanup** only:
  - `python scripts/clean_integration_artifacts.py`
- Do **not** use destructive cleanup in shared or long-lived environments.
- Full destructive cleanup script now requires explicit `--force`:
  - `python scripts/clean_test_data.py --force`
- Never run destructive cleanup against real production-like data.

## Migration Execution Procedure

1. Ensure backend dependencies installed.
2. Run backend quality baseline:

```bash
python scripts/check_backend_quality.py
```

3. Start backend (migrations auto-run on startup):

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

4. Verify migration state:

```bash
python -c "from sqlalchemy import text; from app.db import engine; \
with engine.begin() as c: print([r[0] for r in c.execute(text('SELECT version FROM schema_migrations ORDER BY version')).fetchall()])"
```

## Integration Regression Procedure

From frontend directory:

```bash
npm run check:all
```

Expected:

- frontend build passes
- API e2e script passes

## Post-Regression Cleanup Procedure

From backend root:

```bash
python scripts/clean_integration_artifacts.py --dry-run
python scripts/clean_integration_artifacts.py
```

Expected:

- only test artifacts (`teacher_*`, `student_*`, integration assignments/documents) removed
- real user/business data preserved

## Rollback Guidance (SQLite Local)

- Startup migration runner creates `.bak` backup for SQLite database.
- If rollback is needed:
  1. stop backend process
  2. restore latest `storage/cdas.db.bak` as `storage/cdas.db`
  3. restart backend and verify `/health`

## Release-Day Minimum Command Set

1. `python scripts/check_backend_quality.py`
2. `npm run check:all` (in `frontend/`)
3. `python scripts/clean_integration_artifacts.py`
4. `GET /health` returns `200`
