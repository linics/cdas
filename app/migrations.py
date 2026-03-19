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

    pending = [
        path
        for path in _iter_migration_files()
        if path.stem.split("_", 1)[0] not in applied
    ]

    if not pending:
        return

    _backup_sqlite_db(engine)

    for path in pending:
        version = path.stem.split("_", 1)[0]
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
