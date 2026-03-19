"""用户模型定义 - 教师/学生双角色。"""

import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UserRole(str, enum.Enum):
    """用户角色枚举。"""
    TEACHER = "teacher"
    STUDENT = "student"


class User(Base):
    """用户模型 - 支持教师和学生两种角色。
    
    根据产品设计文档 8.1 节：
    - 教师：作业的设计者、发布者、评价者
    - 学生：作业的执行者、提交者
    """
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # 学生特有字段
    grade: Mapped[Optional[int]] = mapped_column(Integer)  # 年级 1-9
    class_name: Mapped[Optional[str]] = mapped_column(String(50))  # 班级名称
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, role={self.role.value})>"
