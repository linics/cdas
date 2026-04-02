"""核心 SQLAlchemy 模型定义入口。

导出所有模型供其他模块使用。
"""

# 保留旧模型中的 Document 和 ParsingStatus (知识库模块)
from app.models.document import Document, ParsingStatus

# 新模型
from app.models.enums import (
    AssignmentType,
    EvaluationLevel,
    EvaluationType,
    InquiryDepth,
    InquirySubType,
    PracticalSubType,
    SchoolStage,
    SubmissionMode,
    SubmissionStatus,
)
from app.models.user import User, UserRole
from app.models.subject import Subject, PRESET_SUBJECTS
from app.models.assignment import Assignment, ProjectGroup
from app.models.submission import (
    Evaluation,
    Submission,
    SubmissionAttachmentAnalysis,
    SubmissionAttachmentAsset,
)
from app.models.classroom import Classroom, ClassMember, ClassGroup, ClassGroupMember

__all__ = [
    # 文档模块 (保留)
    "Document",
    "ParsingStatus",
    # 用户模块
    "User",
    "UserRole",
    # 学科模块
    "Subject",
    "PRESET_SUBJECTS",
    # 班级模块
    "Classroom",
    "ClassMember",
    "ClassGroup",
    "ClassGroupMember",
    # 枚举
    "AssignmentType",
    "PracticalSubType",
    "InquirySubType",
    "InquiryDepth",
    "SubmissionMode",
    "SubmissionStatus",
    "EvaluationType",
    "EvaluationLevel",
    "SchoolStage",
    # 作业模块
    "Assignment",
    "ProjectGroup",
    # 提交与评价模块
    "Submission",
    "Evaluation",
    "SubmissionAttachmentAsset",
    "SubmissionAttachmentAnalysis",
]
