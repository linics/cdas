"""作业模型定义 - 完整的跨学科作业设计。"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db import Base
from app.models.enums import (
    AssignmentType,
    InquiryDepth,
    InquirySubType,
    PracticalSubType,
    SchoolStage,
    SubmissionMode,
)


class Assignment(Base):
    """跨学科作业模型。
    
    根据产品设计文档第四章"作业设计"完整定义。
    """
    
    __tablename__ = "assignments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # === 基本信息 (4.1节) ===
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)  # 探究主题
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # 学段与年级
    school_stage: Mapped[SchoolStage] = mapped_column(Enum(SchoolStage), nullable=False)
    grade: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-9
    
    # === 学科关联 ===
    main_subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"), nullable=False
    )
    # 融合学科ID列表 (JSON数组)
    related_subject_ids: Mapped[List[int]] = mapped_column(JSON, default=list)
    
    # === 作业类型 (4.2节) ===
    assignment_type: Mapped[AssignmentType] = mapped_column(
        Enum(AssignmentType), nullable=False
    )
    # 子类型 (根据主类型选择)
    practical_subtype: Mapped[Optional[PracticalSubType]] = mapped_column(Enum(PracticalSubType))
    inquiry_subtype: Mapped[Optional[InquirySubType]] = mapped_column(Enum(InquirySubType))
    
    # === 探究深度 (4.3节) ===
    inquiry_depth: Mapped[InquiryDepth] = mapped_column(
        Enum(InquiryDepth), default=InquiryDepth.INTERMEDIATE, nullable=False
    )
    
    # === 提交设置 (6.1节) ===
    submission_mode: Mapped[SubmissionMode] = mapped_column(
        Enum(SubmissionMode), default=SubmissionMode.PHASED, nullable=False
    )
    duration_weeks: Mapped[int] = mapped_column(Integer, default=2)  # 作业周期（周）
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # === AI生成/教师填写的结构化内容 ===
    
    # 作业目标 (5.1节)
    # 格式: {"knowledge": "...", "process": "...", "emotion": "..."}
    objectives_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    # 分步骤任务引导 (5.2节)
    # 格式: [{"name": "阶段名", "order": 1, "steps": [...]}]
    phases_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    
    # 评价维度与权重 (7.1节)
    # 格式: {"dimensions": [{"name": "实践准备", "weight": 10, "description": "..."}]}
    rubric_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    
    # === 关联管理 ===
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    document_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    
    # 是否已发布
    is_published: Mapped[bool] = mapped_column(default=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # 是否已归档
    is_archived: Mapped[bool] = mapped_column(default=False)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # === 关系定义 ===
    main_subject = relationship("Subject", foreign_keys=[main_subject_id])
    creator = relationship("User", foreign_keys=[created_by])
    document = relationship("Document", back_populates="assignments")
    groups = relationship("ProjectGroup", back_populates="assignment", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="assignment", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Assignment(id={self.id}, title={self.title}, type={self.assignment_type.value})>"


class ProjectGroup(Base):
    """作业下的项目小组。"""
    
    __tablename__ = "project_groups"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # 成员列表 (JSON)
    # 格式: [{"user_id": 1, "name": "张三", "role": "组长"}]
    members_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    
    # 关系
    assignment = relationship("Assignment", back_populates="groups")
    submissions = relationship("Submission", back_populates="group", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<ProjectGroup(id={self.id}, name={self.name})>"
