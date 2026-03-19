"""数据库连接与会话管理。"""

from contextlib import contextmanager
from typing import Generator, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


settings = get_settings()


class Base(DeclarativeBase):
    """SQLAlchemy 基类。"""

    pass


# SQLite 需要 ``check_same_thread=False`` 以支持多线程；其他数据库可忽略
engine = create_engine(
    settings.database_url, connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    """提供事务范围的 Session 上下文管理器。"""

    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入函数，提供数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



def ensure_sqlite_assignments_schema(db_engine: Engine) -> None:
    """Legacy wrapper to run versioned migrations for SQLite."""
    from app.migrations import run_migrations
    run_migrations(db_engine)

