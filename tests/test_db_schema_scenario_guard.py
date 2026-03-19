from sqlalchemy import create_engine, text
import asyncio

from app.migrations import run_migrations


def test_migrations_fill_missing_topic() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE assignments ("
                "id INTEGER PRIMARY KEY, "
                "title TEXT, "
                "topic TEXT"
                ")"
            )
        )
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
        conn.execute(
            text(
                "INSERT INTO assignments (id, title, topic) "
                "VALUES (1, 'Title', NULL)"
            )
        )

    run_migrations(engine)

    with engine.begin() as conn:
        topic = conn.execute(
            text("SELECT topic FROM assignments WHERE id = 1")
        ).scalar_one()

    assert topic == "Title"


def test_startup_uses_migrations(monkeypatch) -> None:
    from app import main

    called = {"value": False}

    def mark_called(*_args, **_kwargs) -> None:
        called["value"] = True

    monkeypatch.setattr(main, "run_migrations", mark_called)
    monkeypatch.setattr(main, "engine", create_engine("sqlite:///:memory:"))

    app = main.create_app()

    async def run_lifespan() -> None:
        async with app.router.lifespan_context(app):
            pass

    asyncio.run(run_lifespan())
    assert called["value"]
