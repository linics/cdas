from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.contracts.assignment import AIGenerationMeta
from app.contracts.common import normalize_optional_text, normalize_trimmed
from app.models import EvaluationLevel, EvaluationType


class TeacherEvaluationCreate(BaseModel):
    submission_id: int = Field(gt=0)
    score_numeric: int
    score_level: Optional[EvaluationLevel] = None
    dimension_scores_json: Dict[str, int] = Field(default_factory=dict)
    feedback: str = Field(min_length=1, max_length=2000)

    @field_validator("dimension_scores_json", mode="before")
    @classmethod
    def _normalize_dimension_scores(cls, value: object) -> Dict[str, int]:
        if not isinstance(value, dict):
            return {}
        normalized: Dict[str, int] = {}
        for raw_key, raw_score in value.items():
            key = normalize_trimmed(raw_key)
            if not key:
                raise ValueError("评价维度名称不能为空")
            score = int(raw_score)
            if score < 1 or score > 4:
                raise ValueError("维度分数必须在 1-4 之间")
            normalized[key] = score
        return normalized

    @field_validator("feedback", mode="before")
    @classmethod
    def _normalize_feedback(cls, value: object) -> str:
        text = normalize_trimmed(value)
        if not text:
            raise ValueError("反馈不能为空")
        return text


class SelfEvaluationCreate(BaseModel):
    submission_id: int = Field(gt=0)
    completion: int = Field(ge=1, le=4)
    effort: int = Field(ge=1, le=4)
    difficulties: str = Field(default="", max_length=1000)
    gains: str = Field(default="", max_length=1000)
    improvement: str = Field(default="", max_length=1000)

    @field_validator("difficulties", "gains", "improvement", mode="before")
    @classmethod
    def _normalize_text(cls, value: object) -> str:
        return normalize_trimmed(value)


class PeerEvaluationCreate(BaseModel):
    submission_id: int = Field(gt=0)
    quality: int = Field(ge=1, le=4)
    clarity: int = Field(ge=1, le=4)
    highlights: str = Field(default="", max_length=1000)
    suggestions: str = Field(default="", max_length=1000)

    @field_validator("highlights", "suggestions", mode="before")
    @classmethod
    def _normalize_text(cls, value: object) -> str:
        return normalize_trimmed(value)


class EvaluationResponse(BaseModel):
    id: int
    submission_id: int
    evaluator_id: int
    evaluation_type: EvaluationType
    score_level: Optional[EvaluationLevel]
    score_numeric: Optional[int]
    dimension_scores_json: Dict[str, int]
    score_level_label: Optional[str] = None
    dimension_level_labels: Dict[str, str] = Field(default_factory=dict)
    feedback: Optional[str]
    ai_generated: bool
    is_anonymous: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationListResponse(BaseModel):
    evaluations: List[EvaluationResponse]
    total: int


class AIEvaluationSuggestion(BaseModel):
    suggested_level: str
    suggested_score: int
    dimension_scores: Dict[str, int] = Field(default_factory=dict)
    feedback: str = ""
    evidence: List[Dict[str, str]] = Field(default_factory=list)
    action_items: List[str] = Field(default_factory=list)


class AIAssistEvaluationResponse(BaseModel):
    message: str
    suggestion: AIEvaluationSuggestion
    meta: Optional[AIGenerationMeta] = None
