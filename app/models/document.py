"""文档模型定义 - 知识库模块。

从旧版 __init__.py 提取，保持向后兼容。
"""

import enum
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import BigInteger, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db import Base


class ParsingStatus(str, enum.Enum):
    """文档解析状态机。"""

    UPLOADED = "uploaded"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class Document(Base):
    """上传文档元数据与解析状态。"""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    upload_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    parsing_status: Mapped[ParsingStatus] = mapped_column(
        Enum(ParsingStatus), default=ParsingStatus.UPLOADED, nullable=False
    )
    file_path: Mapped[Optional[str]] = mapped_column(String(512))
    mime_type: Mapped[Optional[str]] = mapped_column(String(50))
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    error_msg: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="user")

    assignments: Mapped[List["Assignment"]] = relationship(
        "Assignment", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename={self.filename}, status={self.parsing_status.value})>"
