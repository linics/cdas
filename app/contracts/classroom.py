from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.contracts.common import normalize_trimmed


INVITE_CODE_PATTERN = re.compile(r"^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{4,16}$")


class ClassroomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    grade: int = Field(ge=1, le=9)

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> str:
        name = normalize_trimmed(value)
        if not name:
            raise ValueError("班级名称不能为空")
        return name


class ClassroomResponse(BaseModel):
    id: int
    name: str
    grade: int
    invite_code: str
    teacher_id: int
    teacher_name: Optional[str] = None
    member_count: int = 0
    joined_group_id: Optional[int] = None
    joined_group_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClassroomListResponse(BaseModel):
    classes: List[ClassroomResponse]
    total: int


class ClassroomMemberResponse(BaseModel):
    member_id: int
    student_id: int
    student_name: str
    student_username: str
    student_grade: Optional[int] = None
    student_class_name: Optional[str] = None
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    joined_at: datetime


class ClassroomMemberListResponse(BaseModel):
    classroom: ClassroomResponse
    members: List[ClassroomMemberResponse]
    total: int


class JoinClassRequest(BaseModel):
    invite_code: str = Field(min_length=4, max_length=16)

    @field_validator("invite_code", mode="before")
    @classmethod
    def _normalize_invite_code(cls, value: object) -> str:
        code = normalize_trimmed(value).upper()
        if not INVITE_CODE_PATTERN.fullmatch(code):
            raise ValueError("邀请码格式无效")
        return code


class JoinClassResponse(BaseModel):
    classroom: ClassroomResponse
    joined: bool
    message: str


class ClassGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> str:
        name = normalize_trimmed(value)
        if not name:
            raise ValueError("小组名称不能为空")
        return name


class ClassGroupResponse(BaseModel):
    id: int
    classroom_id: int
    name: str
    member_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClassGroupMemberResponse(BaseModel):
    id: int
    classroom_id: int
    group_id: int
    student_id: int
    student_name: str
    student_username: str
    student_grade: Optional[int] = None
    student_class_name: Optional[str] = None
    assigned_at: datetime


class ClassGroupDetailResponse(ClassGroupResponse):
    members: List[ClassGroupMemberResponse] = Field(default_factory=list)


class ClassGroupListResponse(BaseModel):
    classroom: ClassroomResponse
    groups: List[ClassGroupDetailResponse]
    total: int


class ClassGroupAssignRequest(BaseModel):
    student_id: int = Field(gt=0)
