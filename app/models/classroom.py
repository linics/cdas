"""班级、入班成员与班级小组模型。"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Classroom(Base):
    """教师创建的班级实体。"""

    __tablename__ = "classrooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    invite_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
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

    teacher = relationship("User", foreign_keys=[teacher_id])
    members = relationship(
        "ClassMember",
        back_populates="classroom",
        cascade="all, delete-orphan",
    )
    groups = relationship(
        "ClassGroup",
        back_populates="classroom",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Classroom(id={self.id}, name={self.name}, grade={self.grade})>"


class ClassMember(Base):
    """学生入班关系。"""

    __tablename__ = "class_members"
    __table_args__ = (
        UniqueConstraint("classroom_id", "student_id", name="uq_classroom_student"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    classroom_id: Mapped[int] = mapped_column(
        ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    classroom = relationship("Classroom", back_populates="members")
    student = relationship("User", foreign_keys=[student_id])

    def __repr__(self) -> str:
        return f"<ClassMember(classroom_id={self.classroom_id}, student_id={self.student_id})>"


class ClassGroup(Base):
    """班级内小组。"""

    __tablename__ = "class_groups"
    __table_args__ = (
        UniqueConstraint("classroom_id", "name", name="uq_class_group_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    classroom_id: Mapped[int] = mapped_column(
        ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
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

    classroom = relationship("Classroom", back_populates="groups")
    members = relationship(
        "ClassGroupMember",
        back_populates="group",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ClassGroup(id={self.id}, classroom_id={self.classroom_id}, name={self.name})>"


class ClassGroupMember(Base):
    """班级小组成员关系。"""

    __tablename__ = "class_group_members"
    __table_args__ = (
        UniqueConstraint("classroom_id", "student_id", name="uq_class_group_student"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    classroom_id: Mapped[int] = mapped_column(
        ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey("class_groups.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    classroom = relationship("Classroom")
    group = relationship("ClassGroup", back_populates="members")
    student = relationship("User", foreign_keys=[student_id])

    def __repr__(self) -> str:
        return (
            f"<ClassGroupMember(classroom_id={self.classroom_id}, "
            f"group_id={self.group_id}, student_id={self.student_id})>"
        )
