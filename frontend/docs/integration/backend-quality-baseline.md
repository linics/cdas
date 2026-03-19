# Backend Quality Baseline

## Canonical Backend Repo

- `<repo-root>`

## Baseline Command Matrix

1. Syntax and import-level sanity

```bash
python -m compileall -q app scripts tests
```

2. Backend test suite

```bash
python -m pytest -q
```

3. Unified quality runner (recommended)

```bash
python scripts/check_backend_quality.py
```

Optional fast mode:

```bash
python scripts/check_backend_quality.py --skip-tests
```

## Exit Criteria

- Compile step returns zero.
- Pytest suite returns zero.
- Any non-zero status blocks merge/release.

## Notes

- This baseline is the Day 3 deliverable of the 2-week normalization plan.
- Integration regression (`python scripts/run_api_e2e.py`) remains a required cross-repo check from frontend repo.
