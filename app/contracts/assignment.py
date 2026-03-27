from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.contracts.common import EvidenceType, normalize_int_list, normalize_optional_text, normalize_trimmed
from app.models import (
    AssignmentType,
    InquiryDepth,
    InquirySubType,
    PracticalSubType,
    SchoolStage,
    SubmissionMode,
)


class CheckpointSchema(BaseModel):
    content: str = Field(min_length=1, max_length=200)
    evidence_type: EvidenceType = EvidenceType.TEXT

    @field_validator("content", mode="before")
    @classmethod
    def _normalize_content(cls, value: object) -> str:
        content = normalize_trimmed(value)
        if not content:
            raise ValueError("checkpoint 内容不能为空")
        return content


class StepSchema(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    content: Optional[str] = Field(default=None, max_length=500)
    checkpoints: List[CheckpointSchema] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_checkpoint(cls, values: Any) -> Any:
        if isinstance(values, dict) and "checkpoint" in values and "checkpoints" not in values:
            values = {**values, "checkpoints": [values["checkpoint"]]}
        return values

    @field_validator("name", "description", mode="before")
    @classmethod
    def _normalize_required_text(cls, value: object) -> str:
        text = normalize_trimmed(value)
        if not text:
            raise ValueError("步骤名称和描述不能为空")
        return text

    @field_validator("content", mode="before")
    @classmethod
    def _normalize_content(cls, value: object) -> Optional[str]:
        return normalize_optional_text(value)


class PhaseSchema(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    order: int = Field(ge=1)
    title: Optional[str] = Field(default=None, max_length=100)
    steps: List[StepSchema] = Field(default_factory=list)

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> str:
        name = normalize_trimmed(value)
        if not name:
            raise ValueError("阶段名称不能为空")
        return name

    @field_validator("title", mode="before")
    @classmethod
    def _normalize_title(cls, value: object) -> Optional[str]:
        return normalize_optional_text(value)


class ObjectivesSchema(BaseModel):
    knowledge: str = Field(default="", max_length=500)
    process: str = Field(default="", max_length=1000)
    emotion: str = Field(default="", max_length=500)

    @field_validator("knowledge", "process", "emotion", mode="before")
    @classmethod
    def _normalize_text(cls, value: object) -> str:
        return normalize_trimmed(value)


class RubricDimensionSchema(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    levels: Dict[str, str] = Field(default_factory=dict)
    description: Optional[str] = Field(default=None, max_length=300)
    weight: Optional[int] = Field(default=None, ge=1, le=100)

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> str:
        name = normalize_trimmed(value)
        if not name:
            raise ValueError("评价维度名称不能为空")
        return name

    @field_validator("description", mode="before")
    @classmethod
    def _normalize_description(cls, value: object) -> Optional[str]:
        return normalize_optional_text(value)


class RubricSchema(BaseModel):
    dimensions: List[RubricDimensionSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ensure_unique_dimensions(self) -> "RubricSchema":
        seen: set[str] = set()
        for item in self.dimensions:
            key = item.name.strip().lower()
            if key in seen:
                raise ValueError("评价维度名称不能重复")
            seen.add(key)
        return self


class AIAssignmentOutput(BaseModel):
    objectives: ObjectivesSchema
    phases: List[PhaseSchema]
    rubric: RubricSchema


class AssignmentWriteMixin(BaseModel):
    def objectives_payload(self) -> Dict[str, Any]:
        value = getattr(self, "objectives_json", None)
        return value.model_dump() if value is not None else {}

    def phases_payload(self) -> List[Dict[str, Any]]:
        value = getattr(self, "phases_json", None)
        return [item.model_dump() for item in value] if value is not None else []

    def rubric_payload(self) -> Dict[str, Any]:
        value = getattr(self, "rubric_json", None)
        return value.model_dump() if value is not None else {}


class AssignmentCreate(AssignmentWriteMixin):
    title: str = Field(min_length=1, max_length=255)
    topic: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    school_stage: SchoolStage
    grade: int = Field(ge=1, le=9)
    main_subject_id: int = Field(gt=0)
    related_subject_ids: List[int] = Field(default_factory=list)
    document_id: Optional[int] = Field(default=None, gt=0)
    assignment_type: AssignmentType
    practical_subtype: Optional[PracticalSubType] = None
    inquiry_subtype: Optional[InquirySubType] = None
    inquiry_depth: InquiryDepth = InquiryDepth.INTERMEDIATE
    submission_mode: SubmissionMode = SubmissionMode.PHASED
    duration_weeks: int = Field(default=2, ge=1, le=16)
    deadline: Optional[datetime] = None
    objectives_json: Optional[ObjectivesSchema] = None
    phases_json: Optional[List[PhaseSchema]] = None
    rubric_json: Optional[RubricSchema] = None

    @field_validator("title", "topic", mode="before")
    @classmethod
    def _normalize_required_text(cls, value: object) -> str:
        text = normalize_trimmed(value)
        if not text:
            raise ValueError("标题和主题不能为空")
        return text

    @field_validator("description", mode="before")
    @classmethod
    def _normalize_description(cls, value: object) -> Optional[str]:
        return normalize_optional_text(value)

    @field_validator("related_subject_ids", mode="before")
    @classmethod
    def _normalize_related_subjects(cls, value: object) -> List[int]:
        if isinstance(value, list):
            return normalize_int_list(value)
        return []

    @model_validator(mode="after")
    def _validate_type_combination(self) -> "AssignmentCreate":
        if self.assignment_type == AssignmentType.PRACTICAL:
            if self.inquiry_subtype is not None:
                raise ValueError("实践类作业不能设置 inquiry_subtype")
        elif self.assignment_type == AssignmentType.INQUIRY:
            if self.practical_subtype is not None:
                raise ValueError("探究类作业不能设置 practical_subtype")
        else:
            if self.practical_subtype is not None or self.inquiry_subtype is not None:
                raise ValueError("项目式作业不能设置实践/探究子类型")
        return self


class AssignmentUpdate(AssignmentWriteMixin):
    title: Optional[str] = Field(default=None, max_length=255)
    topic: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    document_id: Optional[int] = Field(default=None, gt=0)
    objectives_json: Optional[ObjectivesSchema] = None
    phases_json: Optional[List[PhaseSchema]] = None
    rubric_json: Optional[RubricSchema] = None
    deadline: Optional[datetime] = None

    @field_validator("title", "topic", mode="before")
    @classmethod
    def _normalize_optional_required_text(cls, value: object) -> Optional[str]:
        if value is None:
            return None
        text = normalize_trimmed(value)
        if not text:
            raise ValueError("标题和主题不能为空")
        return text

    @field_validator("description", mode="before")
    @classmethod
    def _normalize_description(cls, value: object) -> Optional[str]:
        if value is None:
            return None
        return normalize_optional_text(value)


class AssignmentResponse(BaseModel):
    id: int
    title: str
    topic: str
    description: Optional[str]
    school_stage: SchoolStage
    grade: int
    main_subject_id: int
    related_subject_ids: List[int] = Field(default_factory=list)
    assignment_type: AssignmentType
    practical_subtype: Optional[PracticalSubType]
    inquiry_subtype: Optional[InquirySubType]
    inquiry_depth: InquiryDepth
    submission_mode: SubmissionMode
    duration_weeks: int
    deadline: Optional[datetime]
    objectives_json: ObjectivesSchema
    phases_json: List[PhaseSchema]
    rubric_json: RubricSchema
    is_published: bool
    is_archived: bool
    archived_at: Optional[datetime]
    created_by: int
    document_id: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssignmentListResponse(BaseModel):
    assignments: List[AssignmentResponse]
    total: int


class AIGenerationMeta(BaseModel):
    source: Literal["ai", "fallback", "manual_merge"]
    prompt_id: str
    prompt_version: str
    used_rag: bool = False
    fallback_reason: str = "none"
    stage: Optional[str] = None
    request_id: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    input_truncated: bool = False
    selected_chunk_ids: List[str] = Field(default_factory=list)
    selected_document_ids: List[int] = Field(default_factory=list)
    upstream_extract_source: Optional[str] = None
    upstream_extract_fallback_reason: Optional[str] = None


class AssignmentPreviewResponse(BaseModel):
    objectives_json: ObjectivesSchema
    phases_json: List[PhaseSchema]
    rubric_json: RubricSchema
    meta: Optional[AIGenerationMeta] = None


class LessonPlanDraftRequest(BaseModel):
    document_id: int = Field(gt=0)
    school_stage: Optional[SchoolStage] = None
    grade: Optional[int] = Field(default=None, ge=1, le=9)
    main_subject_id: Optional[int] = Field(default=None, gt=0)
    related_subject_ids: List[int] = Field(default_factory=list)
    assignment_type: Optional[AssignmentType] = None
    inquiry_depth: Optional[InquiryDepth] = None
    submission_mode: Optional[SubmissionMode] = None
    duration_weeks: Optional[int] = Field(default=None, ge=1, le=16)

    @field_validator("related_subject_ids", mode="before")
    @classmethod
    def _normalize_related_subjects(cls, value: object) -> List[int]:
        if isinstance(value, list):
            return normalize_int_list(value)
        return []


class LessonPlanDraftResponse(BaseModel):
    title: str
    topic: str
    description: str
    school_stage: SchoolStage
    grade: int
    main_subject_id: int
    related_subject_ids: List[int]
    document_id: int
    assignment_type: AssignmentType
    practical_subtype: Optional[PracticalSubType] = None
    inquiry_subtype: Optional[InquirySubType] = None
    inquiry_depth: InquiryDepth
    submission_mode: SubmissionMode
    duration_weeks: int
    objectives_json: ObjectivesSchema
    phases_json: List[PhaseSchema]
    rubric_json: RubricSchema
    source_summary: str
    meta: Optional[AIGenerationMeta] = None


class LessonPlanBasicsExtraction(BaseModel):
    school_stage: Optional[str] = None
    grade: Optional[int] = None
    assignment_type: Optional[str] = None
    practical_subtype: Optional[str] = None
    inquiry_subtype: Optional[str] = None
    inquiry_depth: Optional[str] = None
    submission_mode: Optional[str] = None
    duration_weeks: Optional[int] = None
    main_subject: Optional[str] = None
    related_subjects: List[str] = Field(default_factory=list)


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    members_json: List[Dict[str, Any]] = Field(default_factory=list)

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> str:
        name = normalize_trimmed(value)
        if not name:
            raise ValueError("小组名称不能为空")
        return name


class GroupMembersUpdate(BaseModel):
    members_json: List[Dict[str, Any]] = Field(default_factory=list)


class GroupResponse(BaseModel):
    id: int
    assignment_id: int
    name: str
    members_json: List[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)
