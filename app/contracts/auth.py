from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.contracts.common import normalize_optional_text, normalize_trimmed
from app.models import UserRole


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{4,32}$")
PASSWORD_MIN_LENGTH = 8


class Token(BaseModel):
    access_token: str
    token_type: str


class UserCreate(BaseModel):
    username: str = Field(min_length=4, max_length=32)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)
    role: UserRole
    name: str = Field(min_length=1, max_length=80)
    grade: Optional[int] = Field(default=None, ge=1, le=9)
    class_name: Optional[str] = Field(default=None, max_length=64)

    @field_validator("username", mode="before")
    @classmethod
    def _normalize_username(cls, value: object) -> str:
        username = normalize_trimmed(value)
        if not USERNAME_PATTERN.fullmatch(username):
            raise ValueError("用户名格式应为 4-32 位字母、数字、下划线或连字符")
        return username

    @field_validator("password", mode="before")
    @classmethod
    def _normalize_password(cls, value: object) -> str:
        password = normalize_trimmed(value)
        if len(password) < PASSWORD_MIN_LENGTH:
            raise ValueError("密码至少 8 位")
        return password

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> str:
        name = normalize_trimmed(value)
        if not name:
            raise ValueError("姓名不能为空")
        return name

    @field_validator("class_name", mode="before")
    @classmethod
    def _normalize_class_name(cls, value: object) -> Optional[str]:
        return normalize_optional_text(value)

    @model_validator(mode="after")
    def _validate_role_fields(self) -> "UserCreate":
        if self.role == UserRole.STUDENT:
            if self.grade is None:
                raise ValueError("学生账号必须提供年级")
        else:
            self.grade = None
            self.class_name = None
        return self


class UserResponse(BaseModel):
    id: int
    username: str
    role: UserRole
    name: str
    grade: Optional[int]
    class_name: Optional[str]

    model_config = ConfigDict(from_attributes=True)
