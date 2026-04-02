from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.contracts.common import normalize_optional_text, normalize_trimmed
from app.models import SubmissionStatus


class AttachmentSchema(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    url: str
    type: str = Field(min_length=1, max_length=32)
    size_bytes: Optional[int] = Field(default=None, ge=0)

    @field_validator("filename", "type", mode="before")
    @classmethod
    def _normalize_required_text(cls, value: object) -> str:
        text = normalize_trimmed(value)
        if not text:
            raise ValueError("附件名称和类型不能为空")
        return text

    @field_validator("url", mode="before")
    @classmethod
    def _normalize_url(cls, value: object) -> str:
        url = normalize_trimmed(value)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("附件链接必须为 http/https URL")
        return url


class SubmissionAttachmentResponse(BaseModel):
    filename: str
    url: str
    type: str
    size_bytes: Optional[int] = None
    attachment_id: Optional[int] = None
    source: Literal["link", "upload"] = "link"
    parsing_status: Optional[str] = None
    mime_type: Optional[str] = None
    error_msg: Optional[str] = None
    summary_text: Optional[str] = None


class SubmissionCreate(BaseModel):
    assignment_id: int = Field(gt=0)
    phase_index: int = Field(ge=0)
    step_index: Optional[int] = Field(default=None, ge=0)
    group_id: Optional[int] = Field(default=None, gt=0)
    content_json: Dict[str, Any] = Field(default_factory=dict)
    attachments_json: List[AttachmentSchema] = Field(default_factory=list)
    checkpoints_json: Dict[str, bool] = Field(default_factory=dict)

    def attachments_payload(self) -> List[Dict[str, Any]]:
        return [item.model_dump() for item in self.attachments_json]


class SubmissionUpdate(BaseModel):
    content_json: Optional[Dict[str, Any]] = None
    attachments_json: Optional[List[AttachmentSchema]] = None
    checkpoints_json: Optional[Dict[str, bool]] = None

    def attachments_payload(self) -> Optional[List[Dict[str, Any]]]:
        if self.attachments_json is None:
            return None
        return [item.model_dump() for item in self.attachments_json]


class AssignmentBrief(BaseModel):
    id: int
    title: str
    topic: str
    description: Optional[str]
    assignment_type: str
    phases_json: List[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)


class SubmissionResponse(BaseModel):
    id: int
    assignment_id: int
    student_id: int
    group_id: Optional[int]
    group_name: Optional[str] = None
    group_members: List[Dict[str, Any]] = Field(default_factory=list)
    phase_index: int
    step_index: Optional[int]
    status: SubmissionStatus
    content_json: Dict[str, Any]
    attachments_json: List[SubmissionAttachmentResponse]
    checkpoints_json: Dict[str, bool]
    created_at: datetime
    submitted_at: Optional[datetime]
    teacher_evaluated_at: Optional[datetime] = None
    assignment: Optional[AssignmentBrief] = None
    next_submission_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class SubmissionListResponse(BaseModel):
    submissions: List[SubmissionResponse]
    total: int


class SubmissionAttachmentListResponse(BaseModel):
    attachments: List[SubmissionAttachmentResponse]
    total: int


class SubmissionDraftValidationResult(BaseModel):
    has_text: bool
    has_attachments: bool
    has_checkpoints: bool



def normalize_submission_text(content_json: Dict[str, Any] | None) -> str:
    if not isinstance(content_json, dict):
        return ""
    direct = content_json.get("text")
    if direct is not None:
        return normalize_trimmed(direct)
    for value in content_json.values():
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""



def normalize_feedback_text(value: object) -> Optional[str]:
    return normalize_optional_text(value)
