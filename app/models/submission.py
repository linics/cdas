"""提交与评价模型定义。"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db import Base
from app.models.document import ParsingStatus
from app.models.enums import EvaluationLevel, EvaluationType, SubmissionStatus


class Submission(Base):
    """作业提交模型 - 支持过程性提交。
    
    根据产品设计文档第六章"作业提交"设计。
    """
    
    __tablename__ = "submissions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # 关联
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    group_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("project_groups.id", ondelete="CASCADE")
    )
    
    # 阶段与步骤索引 (用于过程性提交)
    phase_index: Mapped[int] = mapped_column(Integer, default=0)  # 阶段序号
    step_index: Mapped[Optional[int]] = mapped_column(Integer)    # 步骤序号
    
    # 状态
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus), default=SubmissionStatus.DRAFT
    )
    
    # 提交内容 (6.2节)
    # 格式: {"text": "...", "type": "text/document/image/video"}
    content_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    # 附件列表
    # 格式: [{"filename": "...", "url": "...", "type": "pdf", "size_bytes": 1024}]
    attachments_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    
    # 检查点完成情况
    # 格式: {"checkpoint_id": true/false}
    checkpoints_json: Mapped[Dict[str, bool]] = mapped_column(JSON, default=dict)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    
    # 关系
    assignment = relationship("Assignment", back_populates="submissions")
    student = relationship("User", foreign_keys=[student_id])
    group = relationship("ProjectGroup", back_populates="submissions")
    evaluations = relationship("Evaluation", back_populates="submission", cascade="all, delete-orphan")
    attachment_assets = relationship(
        "SubmissionAttachmentAsset",
        back_populates="submission",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<Submission(id={self.id}, assignment_id={self.assignment_id}, phase={self.phase_index})>"


class SubmissionAttachmentAsset(Base):
    """学生上传附件资产。"""

    __tablename__ = "submission_attachment_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    uploader_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(20), default="upload", nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    parsing_status: Mapped[ParsingStatus] = mapped_column(
        Enum(ParsingStatus),
        default=ParsingStatus.UPLOADED,
        nullable=False,
    )
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

    submission = relationship("Submission", back_populates="attachment_assets")
    uploader = relationship("User", foreign_keys=[uploader_id])
    analysis = relationship(
        "SubmissionAttachmentAnalysis",
        back_populates="attachment",
        cascade="all, delete-orphan",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<SubmissionAttachmentAsset(id={self.id}, submission_id={self.submission_id}, status={self.parsing_status.value})>"


class SubmissionAttachmentAnalysis(Base):
    """学生附件解析结果。"""

    __tablename__ = "submission_attachment_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attachment_id: Mapped[int] = mapped_column(
        ForeignKey("submission_attachment_assets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    extracted_text: Mapped[str | None] = mapped_column(Text)
    summary_text: Mapped[str | None] = mapped_column(Text)
    error_msg: Mapped[str | None] = mapped_column(Text)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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

    attachment = relationship("SubmissionAttachmentAsset", back_populates="analysis")

    def __repr__(self) -> str:
        return f"<SubmissionAttachmentAnalysis(attachment_id={self.attachment_id})>"


class Evaluation(Base):
    """评价模型 - 支持教师评价/自评/互评。
    
    根据产品设计文档第七章"作业批改与评价"设计。
    """
    
    __tablename__ = "evaluations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # 关联
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False
    )
    evaluator_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    
    # 评价类型 (7.3节)
    evaluation_type: Mapped[EvaluationType] = mapped_column(
        Enum(EvaluationType), nullable=False
    )
    
    # 评分 (7.2节)
    score_level: Mapped[EvaluationLevel] = mapped_column(Enum(EvaluationLevel))  # excellent/good/pass/improve
    score_numeric: Mapped[Optional[int]] = mapped_column(Integer)  # 1-4
    
    # 各维度得分 (7.1节)
    # 格式: {"实践准备": 4, "实践参与": 3, ...}
    dimension_scores_json: Mapped[Dict[str, int]] = mapped_column(JSON, default=dict)
    
    # 反馈内容
    feedback: Mapped[Optional[str]] = mapped_column(Text)
    
    # AI辅助标记 (7.4节)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_suggestions_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    
    # 自评专用字段 (7.3节 学生自评内容)
    # 格式: {"completion": 4, "effort": 3, "difficulties": "...", "gains": "...", "improvement": "..."}
    self_evaluation_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    
    # 互评专用字段 (7.3节 学生互评内容)
    # 格式: {"quality": 4, "clarity": 3, "highlights": "...", "suggestions": "..."}
    peer_evaluation_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    
    # 是否匿名 (互评时)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    
    # 关系
    submission = relationship("Submission", back_populates="evaluations")
    evaluator = relationship("User", foreign_keys=[evaluator_id])
    
    def __repr__(self) -> str:
        return f"<Evaluation(id={self.id}, type={self.evaluation_type.value}, level={self.score_level})>"
