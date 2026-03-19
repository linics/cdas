from pathlib import Path

from sqlalchemy import create_engine, text

from app.migrations import run_migrations


def test_run_migrations_applies_core_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE assignments (id INTEGER PRIMARY KEY, title TEXT)"))
        conn.execute(
            text(
                "CREATE TABLE submissions ("
                "id INTEGER PRIMARY KEY, "
                "assignment_id INTEGER"
                ")"
            )
        )
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
            row[1]
            for row in conn.execute(text("PRAGMA table_info(assignments)")).fetchall()
        }
        assert "topic" in cols
        versions = conn.execute(
            text("SELECT version FROM schema_migrations")
        ).fetchall()
        assert versions


def test_run_migrations_adds_submission_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE assignments (id INTEGER PRIMARY KEY, title TEXT)"))
        conn.execute(
            text(
                "CREATE TABLE submissions ("
                "id INTEGER PRIMARY KEY, "
                "assignment_id INTEGER"
                ")"
            )
        )
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
            row[1]
            for row in conn.execute(text("PRAGMA table_info(submissions)")).fetchall()
        }
        assert "student_id" in cols
