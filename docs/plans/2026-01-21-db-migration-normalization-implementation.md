# Database Migration Normalization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace runtime schema patching with a versioned SQL migration system for core tables.

**Architecture:** Add a lightweight migration runner that executes ordered SQL files and records versions in `schema_migrations`, plus a core-table normalization migration. Startup runs migrations instead of dynamic schema patching.

**Tech Stack:** Python, SQLAlchemy, SQLite

---

### Task 1: Add migration runner (backup + schema_migrations + SQL execution)

**Files:**
- Create: `app/migrations.py`
- Test: `tests/test_migrations_runner.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from sqlalchemy import create_engine, text

from app.migrations import run_migrations


def test_run_migrations_applies_core_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE assignments (id INTEGER PRIMARY KEY, title TEXT)"))
        conn.execute(text("CREATE TABLE submissions (id INTEGER PRIMARY KEY, assignment_id INTEGER)"))
        conn.execute(
            text(
                "CREATE TABLE evaluations ("
                "id INTEGER PRIMARY KEY, "
                "submission_id INTEGER, "
                "evaluation_type TEXT"
                ")"
            )
        )

    run_migrations(engine)

    with engine.begin() as conn:
        cols = {
            row[1] for row in conn.execute(text("PRAGMA table_info(assignments)")).fetchall()
        }
        assert "topic" in cols
        versions = conn.execute(
            text("SELECT version FROM schema_migrations")
        ).fetchall()
        assert versions
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_migrations_runner.py::test_run_migrations_applies_core_schema -v`  
Expected: FAIL with `ModuleNotFoundError: app.migrations` (or similar).

**Step 3: Write minimal implementation**

```python
# app/migrations.py
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations" / "sql"


def run_migrations(engine: Engine) -> None:
    if engine.url.drivername != "sqlite":
        return

    _backup_sqlite_db(engine)

    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version TEXT PRIMARY KEY, "
                "applied_at DATETIME DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
        )
        applied = {
            row[0]
            for row in conn.execute(text("SELECT version FROM schema_migrations")).fetchall()
        }

    for path in _iter_migration_files():
        version = path.stem.split("_", 1)[0]
        if version in applied:
            continue
        sql = path.read_text(encoding="utf-8")
        statements = _split_sql(sql)
        with engine.begin() as conn:
            for stmt in statements:
                if not stmt.strip():
                    continue
                try:
                    conn.execute(text(stmt))
                except OperationalError as exc:
                    if _is_ignorable_sqlite_error(exc):
                        continue
                    raise
            conn.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": version},
            )


def _iter_migration_files() -> Iterable[Path]:
    if not MIGRATIONS_DIR.exists():
        return []
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def _split_sql(sql: str) -> list[str]:
    return [stmt.strip() for stmt in sql.split(";") if stmt.strip()]


def _is_ignorable_sqlite_error(exc: OperationalError) -> bool:
    message = str(exc).lower()
    return "duplicate column name" in message or "already exists" in message


def _backup_sqlite_db(engine: Engine) -> None:
    db_path = engine.url.database
    if not db_path:
        return
    source = Path(db_path)
    if source.exists():
        backup = source.with_suffix(source.suffix + ".bak")
        shutil.copy2(source, backup)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_migrations_runner.py::test_run_migrations_applies_core_schema -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add app/migrations.py tests/test_migrations_runner.py
git commit -m "Add lightweight SQL migration runner"
```

---

### Task 2: Add core table normalization SQL migration

**Files:**
- Create: `migrations/sql/001_core_tables.sql`

**Step 1: Write the failing test**

```python
def test_run_migrations_adds_submission_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE submissions (id INTEGER PRIMARY KEY, assignment_id INTEGER)"))

    run_migrations(engine)

    with engine.begin() as conn:
        cols = {
            row[1] for row in conn.execute(text("PRAGMA table_info(submissions)")).fetchall()
        }
        assert "student_id" in cols
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_migrations_runner.py::test_run_migrations_adds_submission_fields -v`  
Expected: FAIL because migration SQL is missing.

**Step 3: Write minimal migration SQL**

```sql
-- migrations/sql/001_core_tables.sql
-- assignments
ALTER TABLE assignments ADD COLUMN topic VARCHAR(255);
ALTER TABLE assignments ADD COLUMN description TEXT;
ALTER TABLE assignments ADD COLUMN school_stage VARCHAR(50);
ALTER TABLE assignments ADD COLUMN grade INTEGER;
ALTER TABLE assignments ADD COLUMN main_subject_id INTEGER;
ALTER TABLE assignments ADD COLUMN related_subject_ids JSON;
ALTER TABLE assignments ADD COLUMN assignment_type VARCHAR(50);
ALTER TABLE assignments ADD COLUMN practical_subtype VARCHAR(50);
ALTER TABLE assignments ADD COLUMN inquiry_subtype VARCHAR(50);
ALTER TABLE assignments ADD COLUMN inquiry_depth VARCHAR(50);
ALTER TABLE assignments ADD COLUMN submission_mode VARCHAR(50);
ALTER TABLE assignments ADD COLUMN duration_weeks INTEGER;
ALTER TABLE assignments ADD COLUMN deadline DATETIME;
ALTER TABLE assignments ADD COLUMN objectives_json JSON;
ALTER TABLE assignments ADD COLUMN phases_json JSON;
ALTER TABLE assignments ADD COLUMN rubric_json JSON;
ALTER TABLE assignments ADD COLUMN created_by INTEGER;
ALTER TABLE assignments ADD COLUMN document_id INTEGER;
ALTER TABLE assignments ADD COLUMN created_at DATETIME;
ALTER TABLE assignments ADD COLUMN updated_at DATETIME;
ALTER TABLE assignments ADD COLUMN is_published BOOLEAN;
ALTER TABLE assignments ADD COLUMN published_at DATETIME;

UPDATE assignments
SET topic = COALESCE(NULLIF(topic, ''), title, '未设置')
WHERE topic IS NULL OR topic = '';

-- submissions
ALTER TABLE submissions ADD COLUMN student_id INTEGER;
ALTER TABLE submissions ADD COLUMN group_id INTEGER;
ALTER TABLE submissions ADD COLUMN phase_index INTEGER;
ALTER TABLE submissions ADD COLUMN step_index INTEGER;
ALTER TABLE submissions ADD COLUMN status VARCHAR(50);
ALTER TABLE submissions ADD COLUMN content_json JSON;
ALTER TABLE submissions ADD COLUMN attachments_json JSON;
ALTER TABLE submissions ADD COLUMN checkpoints_json JSON;
ALTER TABLE submissions ADD COLUMN created_at DATETIME;
ALTER TABLE submissions ADD COLUMN submitted_at DATETIME;
ALTER TABLE submissions ADD COLUMN updated_at DATETIME;

UPDATE submissions SET student_id = COALESCE(student_id, 1);
UPDATE submissions SET phase_index = COALESCE(phase_index, 0);
UPDATE submissions SET status = COALESCE(status, 'DRAFT');
UPDATE submissions SET content_json = COALESCE(content_json, '{}');
UPDATE submissions SET attachments_json = COALESCE(attachments_json, '[]');
UPDATE submissions SET checkpoints_json = COALESCE(checkpoints_json, '{}');
UPDATE submissions SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP);
UPDATE submissions SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP);
UPDATE submissions SET status = UPPER(status);

-- evaluations
ALTER TABLE evaluations ADD COLUMN score_level VARCHAR(50);
ALTER TABLE evaluations ADD COLUMN score_numeric INTEGER;
ALTER TABLE evaluations ADD COLUMN dimension_scores_json JSON;
ALTER TABLE evaluations ADD COLUMN feedback TEXT;
ALTER TABLE evaluations ADD COLUMN ai_generated BOOLEAN;
ALTER TABLE evaluations ADD COLUMN ai_suggestions_json JSON;
ALTER TABLE evaluations ADD COLUMN self_evaluation_json JSON;
ALTER TABLE evaluations ADD COLUMN peer_evaluation_json JSON;
ALTER TABLE evaluations ADD COLUMN is_anonymous BOOLEAN;
ALTER TABLE evaluations ADD COLUMN created_at DATETIME;

UPDATE evaluations SET evaluation_type = UPPER(evaluation_type);

CREATE INDEX IF NOT EXISTS idx_submissions_assignment_id ON submissions (assignment_id);
CREATE INDEX IF NOT EXISTS idx_submissions_student_id ON submissions (student_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_submission_id ON evaluations (submission_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_evaluator_id ON evaluations (evaluator_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_type ON evaluations (evaluation_type);
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_migrations_runner.py::test_run_migrations_adds_submission_fields -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add migrations/sql/001_core_tables.sql tests/test_migrations_runner.py
git commit -m "Add core tables normalization migration"
```

---

### Task 3: Replace runtime patching with migrations on startup

**Files:**
- Modify: `app/main.py`
- Modify: `app/db.py`
- Modify: `tests/test_db_schema_scenario_guard.py`

**Step 1: Write the failing test**

```python
from sqlalchemy import create_engine, text

from app.migrations import run_migrations


def test_migrations_fill_missing_topic() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE assignments (id INTEGER PRIMARY KEY, title TEXT, topic TEXT)"))
        conn.execute(text("INSERT INTO assignments (id, title, topic) VALUES (1, 'Title', NULL)"))

    run_migrations(engine)

    with engine.begin() as conn:
        topic = conn.execute(text("SELECT topic FROM assignments WHERE id = 1")).scalar_one()
    assert topic == "Title"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_db_schema_scenario_guard.py::test_migrations_fill_missing_topic -v`  
Expected: FAIL because test still targets `ensure_sqlite_assignments_schema`.

**Step 3: Write minimal implementation**

- Update `app/main.py` to import and call `run_migrations(engine)` instead of `ensure_sqlite_assignments_schema(engine)`.
- Remove `ensure_sqlite_assignments_schema` (or leave it unused) from `app/db.py`.
- Update `tests/test_db_schema_scenario_guard.py` to use `run_migrations` as above.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_db_schema_scenario_guard.py::test_migrations_fill_missing_topic -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add app/main.py app/db.py tests/test_db_schema_scenario_guard.py
git commit -m "Use migrations instead of runtime schema patching"
```

---

### Task 4: Run full test suite

**Step 1: Run tests**

Run: `pytest -q`  
Expected: PASS (warnings acceptable).

**Step 2: Commit (if needed)**

```bash
git add tests/test_migrations_runner.py
git commit -m "Update migration tests"
```

---

Plan complete and saved to `docs/plans/2026-01-21-db-migration-normalization-implementation.md`. Two execution options:

1. Subagent-Driven (this session) - I dispatch fresh subagent per task, review between tasks, fast iteration
2. Parallel Session (separate) - Open new session with executing-plans, batch execution with checkpoints

Which approach?
