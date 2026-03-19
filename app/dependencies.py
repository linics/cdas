"""FastAPI 依赖注入工具。"""

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.db import SessionLocal


def get_db() -> Iterator[Session]:
    """FastAPI 依赖，用于获取数据库会话。"""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
