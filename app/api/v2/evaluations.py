"""作业评价API - 教师评价/自评/互评。"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.contracts.evaluation import (
    AIAssistEvaluationResponse,
    AIEvaluationSuggestion,
    EvaluationListResponse,
    EvaluationResponse,
    PeerEvaluationCreate,
    SelfEvaluationCreate,
    TeacherEvaluationCreate,
)
from app.db import get_db
from app.models import (
    Assignment,
    AssignmentType,
    Evaluation,
    ProjectGroup,
    Submission,
    SubmissionAttachmentAsset,
    User,
    EvaluationType,
    EvaluationLevel,
    SubmissionStatus,
)
from app.api.v2.auth import get_current_user, require_teacher
from app.prompts.evaluation_prompts import EvaluationPromptContext, build_evaluation_prompt
from app.prompts.registry import EVALUATION_AI_ASSIST_PROMPT
from app.services.ai import DeepSeekJSONClient, generate_ai_request_id

router = APIRouter()
logger = logging.getLogger("cdas.api")


_LEVEL_LABELS = {
    "excellent": "优秀",
    "good": "良好",
    "pass": "合格",
    "improve": "需改进",
}


def _level_label(level: str) -> str:
    return _LEVEL_LABELS.get(level, "")


def _normalize_level_input(value: Any) -> str:
    if isinstance(value, EvaluationLevel):
        return value.value
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in _LEVEL_LABELS:
            return cleaned
        if cleaned in {"a", "b", "c", "d"}:
            return {"a": "excellent", "b": "good", "c": "pass", "d": "improve"}[cleaned]
        if cleaned in {"优秀", "良好", "合格", "需改进"}:
            return {
                "优秀": "excellent",
                "良好": "good",
                "合格": "pass",
                "需改进": "improve",
            }[cleaned]
    try:
        numeric = int(float(value))
    except Exception:
        return "improve"
    if numeric >= 90:
        return "excellent"
    if numeric >= 75:
        return "good"
    if numeric >= 60:
        return "pass"
    if numeric >= 4:
        return "excellent"
    if numeric == 3:
        return "good"
    if numeric == 2:
        return "pass"
    return "improve"


def _normalize_rubric_dimensions(rubric: Dict[str, Any]) -> List[Dict[str, Any]]:
    dimensions = rubric.get("dimensions") or []
    normalized: List[Dict[str, Any]] = []
    if isinstance(dimensions, list):
        for idx, dim in enumerate(dimensions, start=1):
            if isinstance(dim, dict):
                name = dim.get("name") or dim.get("dimension") or f"Dimension {idx}"
                levels = dim.get("levels") if isinstance(dim.get("levels"), dict) else {}
                normalized.append({"name": name, "levels": levels})
            elif isinstance(dim, str):
                normalized.append({"name": dim, "levels": {}})
    return normalized


def _default_rubric_dimension_names(assignment_type: AssignmentType) -> List[str]:
    if assignment_type == AssignmentType.PRACTICAL:
        return ["实践准备", "实践参与", "过程记录", "跨学科运用", "成果表达", "反思能力"]
    if assignment_type == AssignmentType.PROJECT:
        return ["问题分析", "规划协作", "迭代改进", "成果质量", "展示汇报", "复盘反思"]
    return ["问题意识", "方案设计", "探究过程", "结论质量", "反思能力"]


def _validate_teacher_dimension_scores(
    assignment: Assignment,
    dimension_scores_json: Dict[str, int],
) -> None:
    dimension_names = [item["name"] for item in _normalize_rubric_dimensions(assignment.rubric_json or {})]
    if not dimension_names:
        return
    if dimension_names == _default_rubric_dimension_names(assignment.assignment_type):
        return

    provided_names = list(dimension_scores_json.keys())
    if set(provided_names) != set(dimension_names):
        raise HTTPException(status_code=400, detail="dimension_scores_json 必须与 rubric 维度严格一致")


def _clamp_score(value: Any) -> int:
    try:
        score = int(float(value))
    except Exception:
        return 1
    return max(1, min(4, score))


def _level_to_score(level: str) -> int:
    return {
        "excellent": 4,
        "good": 3,
        "pass": 2,
        "improve": 1,
    }.get(level, 2)


def _normalize_dimension_scores(
    dimensions: List[Dict[str, Any]],
    scores: Dict[str, Any],
    fallback: int = 2,
) -> Dict[str, int]:
    normalized: Dict[str, int] = {}
    for index, dim in enumerate(dimensions, start=1):
        raw_name = dim.get("name")
        name = raw_name if isinstance(raw_name, str) and raw_name else f"Dimension {index}"
        raw_value = scores.get(name, fallback)
        level = _normalize_level_input(raw_value)
        normalized[name] = _clamp_score(_level_to_score(level))
    return normalized


def _compute_average_score(scores: Dict[str, int]) -> int:
    if not scores:
        return 0
    average = sum(scores.values()) / len(scores)
    return _clamp_score(int(average + 0.5))


def _build_dimension_labels(scores: Dict[str, int]) -> Dict[str, str]:
    labels: Dict[str, str] = {}
    for name, score in scores.items():
        labels[name] = _level_label(_score_to_level(score))
    return labels


def _build_evaluation_response(evaluation: Evaluation) -> EvaluationResponse:
    response = EvaluationResponse.model_validate(evaluation, from_attributes=True)
    if response.score_level is not None:
        response.score_level_label = _level_label(response.score_level.value)
    response.dimension_level_labels = _build_dimension_labels(response.dimension_scores_json or {})
    return response


def _truncate_ai_text(
    value: str,
    *,
    limit: int,
    warning_key: str,
    warnings: List[str],
) -> str:
    text = value or ""
    if len(text) <= limit:
        return text
    if warning_key not in warnings:
        warnings.append(warning_key)
    return f"{text[:limit]}..."


def _compact_prompt_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _truncate_compact_prompt_text(value: Any, max_length: Optional[int]) -> str:
    text = _compact_prompt_text(value)
    if max_length is None or len(text) <= max_length:
        return text
    if max_length <= 3:
        return text[:max_length]
    return f"{text[: max_length - 3]}..."


def _normalize_json_prompt_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {_compact_prompt_text(key): _normalize_json_prompt_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_json_prompt_value(item) for item in value]
    if isinstance(value, str):
        return _compact_prompt_text(value)
    return value


def _compact_json_prompt_value(
    value: Any,
    *,
    key_limit: Optional[int],
    string_limit: Optional[int],
    list_limit: Optional[int],
    dict_limit: Optional[int],
) -> Any:
    if isinstance(value, dict):
        items = list(value.items())
        if dict_limit is not None:
            items = items[:dict_limit]
        return {
            _truncate_compact_prompt_text(key, key_limit): _compact_json_prompt_value(
                item,
                key_limit=key_limit,
                string_limit=string_limit,
                list_limit=list_limit,
                dict_limit=dict_limit,
            )
            for key, item in items
        }
    if isinstance(value, list):
        items = value if list_limit is None else value[:list_limit]
        return [
            _compact_json_prompt_value(
                item,
                key_limit=key_limit,
                string_limit=string_limit,
                list_limit=list_limit,
                dict_limit=dict_limit,
            )
            for item in items
        ]
    if isinstance(value, str):
        return _truncate_compact_prompt_text(value, string_limit)
    return value


def _dump_prompt_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _serialize_json_for_prompt(
    value: Any,
    *,
    limit: int,
    warning_key: str,
    warnings: List[str],
) -> str:
    normalized = _normalize_json_prompt_value(value)
    serialized = _dump_prompt_json(normalized)
    if len(serialized) <= limit:
        return serialized

    if warning_key not in warnings:
        warnings.append(warning_key)

    profiles = [
        {"key_limit": None, "string_limit": 160, "list_limit": None, "dict_limit": None},
        {"key_limit": 96, "string_limit": 96, "list_limit": None, "dict_limit": 16},
        {"key_limit": 72, "string_limit": 64, "list_limit": 8, "dict_limit": 12},
        {"key_limit": 48, "string_limit": 48, "list_limit": 4, "dict_limit": 8},
        {"key_limit": 32, "string_limit": 32, "list_limit": 2, "dict_limit": 4},
        {"key_limit": 20, "string_limit": 20, "list_limit": 1, "dict_limit": 2},
        {"key_limit": 12, "string_limit": 12, "list_limit": 1, "dict_limit": 1},
        {"key_limit": 8, "string_limit": 8, "list_limit": 1, "dict_limit": 1},
        {"key_limit": 4, "string_limit": 4, "list_limit": 1, "dict_limit": 1},
        {"key_limit": 1, "string_limit": 1, "list_limit": 1, "dict_limit": 1},
    ]

    last_serialized = serialized
    for profile in profiles:
        candidate = _compact_json_prompt_value(
            normalized,
            key_limit=profile["key_limit"],
            string_limit=profile["string_limit"],
            list_limit=profile["list_limit"],
            dict_limit=profile["dict_limit"],
        )
        serialized = _dump_prompt_json(candidate)
        if len(serialized) <= limit:
            return serialized
        last_serialized = serialized

    return last_serialized


def _serialize_rubric_json_for_prompt(
    dimensions: List[Dict[str, Any]],
    *,
    limit: int,
    warning_key: str,
    warnings: List[str],
) -> str:
    normalized_dimensions: List[Dict[str, Any]] = []
    for index, dim in enumerate(dimensions, start=1):
        name = _compact_prompt_text(dim.get("name") if isinstance(dim, dict) else None) or f"Dimension {index}"
        levels = dim.get("levels") if isinstance(dim, dict) and isinstance(dim.get("levels"), dict) else {}
        normalized_dimensions.append(
            {
                "name": name,
                "levels": {
                    str(level): _compact_prompt_text(text)
                    for level, text in levels.items()
                    if _compact_prompt_text(text)
                },
            }
        )

    serialized = _dump_prompt_json({"dimensions": normalized_dimensions})
    if len(serialized) <= limit:
        return serialized

    if warning_key not in warnings:
        warnings.append(warning_key)

    def _build_candidate_dimensions(
        *,
        include_levels: bool,
        level_limit: Optional[int],
        name_limit: Optional[int],
        max_dimensions: Optional[int],
    ) -> List[Dict[str, Any]]:
        source_dimensions = normalized_dimensions if max_dimensions is None else normalized_dimensions[:max_dimensions]
        candidate_dimensions: List[Dict[str, Any]] = []

        for index, dim in enumerate(source_dimensions, start=1):
            name = _truncate_compact_prompt_text(dim["name"], name_limit) or f"D{index}"
            item: Dict[str, Any] = {"name": name}
            if include_levels:
                levels = {
                    level: _truncate_compact_prompt_text(text, level_limit)
                    for level, text in dim.get("levels", {}).items()
                    if _truncate_compact_prompt_text(text, level_limit)
                }
                if levels:
                    item["levels"] = levels
            candidate_dimensions.append(item)

        return candidate_dimensions

    level_profiles = [
        {"include_levels": True, "level_limit": 160},
        {"include_levels": True, "level_limit": 96},
        {"include_levels": True, "level_limit": 64},
        {"include_levels": True, "level_limit": 32},
        {"include_levels": False, "level_limit": None},
    ]
    name_limits = [96, 64, 48, 32, 24, 16, 12, 8, 4, 1]

    last_serialized = serialized
    for profile in level_profiles:
        serialized = _dump_prompt_json(
            {"dimensions": _build_candidate_dimensions(name_limit=None, max_dimensions=None, **profile)}
        )
        if len(serialized) <= limit:
            return serialized
        last_serialized = serialized

    for name_limit in name_limits:
        for profile in level_profiles:
            serialized = _dump_prompt_json(
                {"dimensions": _build_candidate_dimensions(name_limit=name_limit, max_dimensions=None, **profile)}
            )
            if len(serialized) <= limit:
                return serialized
            last_serialized = serialized

    for max_dimensions in range(max(len(normalized_dimensions) - 1, 1), 0, -1):
        for name_limit in name_limits:
            for profile in level_profiles:
                serialized = _dump_prompt_json(
                    {
                        "dimensions": _build_candidate_dimensions(
                            name_limit=name_limit,
                            max_dimensions=max_dimensions,
                            **profile,
                        )
                    }
                )
                if len(serialized) <= limit:
                    return serialized
                last_serialized = serialized

    serialized = _dump_prompt_json({"dimensions": [{"name": "D"}]})
    if len(serialized) <= limit:
        return serialized

    return last_serialized


def _build_attachment_prompt_payload(db: Session, submission: Submission) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for item in submission.attachments_json or []:
        payload.append(
            {
                "filename": item.get("filename") or "",
                "source": "link",
                "type": item.get("type") or "link",
                "url": item.get("url") or "",
            }
        )

    assets = (
        db.query(SubmissionAttachmentAsset)
        .options(joinedload(SubmissionAttachmentAsset.analysis))
        .filter(SubmissionAttachmentAsset.submission_id == submission.id)
        .order_by(SubmissionAttachmentAsset.created_at.asc())
        .all()
    )
    for asset in assets:
        analysis = asset.analysis
        excerpt = None
        if analysis and analysis.extracted_text:
            excerpt = _truncate_compact_prompt_text(analysis.extracted_text, 240)
        payload.append(
            {
                "filename": asset.original_filename,
                "source": "upload",
                "type": (asset.original_filename.rsplit(".", 1)[-1].lower() if "." in asset.original_filename else "file"),
                "parsing_status": asset.parsing_status.value,
                "summary_text": analysis.summary_text if analysis else None,
                "excerpt": excerpt,
                "error_msg": analysis.error_msg if analysis else None,
            }
        )
    return payload


def _classify_ai_assist_fallback_reason(error: Exception) -> str:
    lowered = f"{type(error).__name__}: {error}".lower()
    if "timeout" in lowered or "timed out" in lowered:
        return "timeout"
    if "json" in lowered or "parse" in lowered or "decode" in lowered:
        return "parse_error"
    return "request_error"


def _build_ai_assist_meta(
    *,
    source: str,
    request_id: str,
    fallback_reason: str = "none",
    warnings: List[str] | None = None,
    input_truncated: bool = False,
) -> Dict[str, Any]:
    return {
        "source": source,
        "prompt_id": EVALUATION_AI_ASSIST_PROMPT.prompt_id,
        "prompt_version": EVALUATION_AI_ASSIST_PROMPT.version,
        "used_rag": False,
        "fallback_reason": fallback_reason,
        "stage": "evaluation_ai_assist",
        "request_id": request_id,
        "warnings": warnings or [],
        "input_truncated": input_truncated,
    }


def _score_to_level(score: int) -> str:
    return _normalize_level_input(score)


def _format_phase_context(phase: Dict[str, Any] | None) -> str:
    if not phase:
        return "N/A"
    title = phase.get("title") or phase.get("name") or "Phase"
    lines = [f"{title}"]
    steps = phase.get("steps") or []
    if isinstance(steps, dict):
        steps = [steps]
    for idx, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        primary = step.get("content") or step.get("description") or step.get("name") or f"Step {idx}"
        lines.append(f"- Step {idx}: {primary}")
        desc = step.get("description")
        if desc and desc != primary:
            lines.append(f"  - Description: {desc}")
        checkpoints = step.get("checkpoints") or []
        if isinstance(checkpoints, dict):
            checkpoints = [checkpoints]
        for cp in checkpoints:
            if isinstance(cp, dict):
                cp_text = cp.get("content") or cp.get("text") or cp.get("description") or ""
            else:
                cp_text = str(cp)
            if cp_text:
                lines.append(f"  - Checkpoint: {cp_text}")
    return "\n".join(lines)


def _extract_member_ids(members_json: Any) -> set[int]:
    member_ids: set[int] = set()
    if not isinstance(members_json, list):
        return member_ids
    for item in members_json:
        if isinstance(item, dict):
            raw_user_id = (
                item.get("user_id")
                or item.get("student_id")
                or item.get("id")
            )
        else:
            raw_user_id = item
        try:
            if raw_user_id is None:
                continue
            user_id = int(str(raw_user_id))
        except Exception:
            continue
        if user_id > 0:
            member_ids.add(user_id)
    return member_ids


def _student_can_access_submission(db: Session, submission: Submission, student_id: int) -> bool:
    if submission.student_id == student_id:
        return True
    if not submission.group_id:
        return False
    group = db.query(ProjectGroup).filter(ProjectGroup.id == submission.group_id).first()
    if not group:
        return False
    return student_id in _extract_member_ids(group.members_json or [])


def _group_ids_for_student(db: Session, student_id: int) -> List[int]:
    groups = db.query(ProjectGroup).all()
    matched: List[int] = []
    for group in groups:
        if student_id in _extract_member_ids(group.members_json or []):
            matched.append(group.id)
    return matched


# === API 端点 ===

@router.post("/teacher", response_model=EvaluationResponse)
async def create_teacher_evaluation(
    data: TeacherEvaluationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher)
):
    """教师评价。"""
    submission = db.query(Submission).filter(Submission.id == data.submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="提交不存在")
    assignment = db.query(Assignment).filter(Assignment.id == submission.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")

    level_map = {
        4: EvaluationLevel.EXCELLENT,
        3: EvaluationLevel.GOOD,
        2: EvaluationLevel.PASS,
        1: EvaluationLevel.IMPROVE,
    }
    if data.score_numeric not in level_map:
        raise HTTPException(status_code=400, detail="score_numeric 必须在 1-4 之间")
    score_level = data.score_level or level_map[data.score_numeric]
    if data.score_level is not None and data.score_level != level_map[data.score_numeric]:
        raise HTTPException(status_code=400, detail="score_level 与 score_numeric 不一致")
    _validate_teacher_dimension_scores(assignment, data.dimension_scores_json)
    
    evaluation = Evaluation(
        submission_id=data.submission_id,
        evaluator_id=current_user.id,
        evaluation_type=EvaluationType.TEACHER,
        score_level=score_level,
        score_numeric=data.score_numeric,
        dimension_scores_json=data.dimension_scores_json,
        feedback=data.feedback,
        ai_generated=False,
        is_anonymous=False,
    )
    db.add(evaluation)
    
    # 更新提交状态为已评分
    submission.status = SubmissionStatus.GRADED
    
    db.commit()
    db.refresh(evaluation)
    return _build_evaluation_response(evaluation)


@router.post("/self", response_model=EvaluationResponse)
async def create_self_evaluation(
    data: SelfEvaluationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """学生自评。"""
    submission = db.query(Submission).filter(Submission.id == data.submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="提交不存在")
    if not _student_can_access_submission(db, submission, current_user.id):
        raise HTTPException(status_code=403, detail="只能对自己或本组可见的提交进行自评")
    
    # 检查是否已有自评
    existing = db.query(Evaluation).filter(
        Evaluation.submission_id == data.submission_id,
        Evaluation.evaluator_id == current_user.id,
        Evaluation.evaluation_type == EvaluationType.SELF
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="已提交过自评")
    
    evaluation = Evaluation(
        submission_id=data.submission_id,
        evaluator_id=current_user.id,
        evaluation_type=EvaluationType.SELF,
        self_evaluation_json={
            "completion": data.completion,
            "effort": data.effort,
            "difficulties": data.difficulties,
            "gains": data.gains,
            "improvement": data.improvement,
        },
        is_anonymous=False,
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return _build_evaluation_response(evaluation)


@router.post("/peer", response_model=EvaluationResponse)
async def create_peer_evaluation(
    data: PeerEvaluationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """学生互评。"""
    submission = db.query(Submission).filter(Submission.id == data.submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="提交不存在")
    if _student_can_access_submission(db, submission, current_user.id):
        raise HTTPException(status_code=400, detail="不能给自己或本组提交互评")
    
    # 检查是否已评过
    existing = db.query(Evaluation).filter(
        Evaluation.submission_id == data.submission_id,
        Evaluation.evaluator_id == current_user.id,
        Evaluation.evaluation_type == EvaluationType.PEER
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="已对该提交进行过互评")
    
    evaluation = Evaluation(
        submission_id=data.submission_id,
        evaluator_id=current_user.id,
        evaluation_type=EvaluationType.PEER,
        peer_evaluation_json={
            "quality": data.quality,
            "clarity": data.clarity,
            "highlights": data.highlights,
            "suggestions": data.suggestions,
        },
        is_anonymous=True,  # 互评默认匿名
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return _build_evaluation_response(evaluation)


@router.get("/submission/{submission_id}", response_model=EvaluationListResponse)
async def list_submission_evaluations(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取某提交的所有评价。"""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="提交不存在")
    
    # 学生只能看自己的提交的评价
    from app.models.user import UserRole
    if current_user.role == UserRole.STUDENT and not _student_can_access_submission(db, submission, current_user.id):
        raise HTTPException(status_code=403, detail="无权查看此提交的评价")
    
    evaluations = db.query(Evaluation).filter(Evaluation.submission_id == submission_id).all()
    return {"evaluations": [_build_evaluation_response(item) for item in evaluations], "total": len(evaluations)}


@router.post("/ai-assist", response_model=AIAssistEvaluationResponse)
async def ai_assist_evaluation(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher)
):
    """AI-assisted evaluation suggestion."""
    request_id = generate_ai_request_id()
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="提交不存在")

    assignment = db.query(Assignment).filter(Assignment.id == submission.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")

    rubric = assignment.rubric_json or {}
    rubric_dims = _normalize_rubric_dimensions(rubric)
    phase = None
    if isinstance(assignment.phases_json, list) and assignment.phases_json:
        if submission.phase_index is not None and submission.phase_index < len(assignment.phases_json):
            phase = assignment.phases_json[submission.phase_index]
    phase_context = _format_phase_context(phase)

    content_json = submission.content_json or {}
    submission_text = content_json.get("text") if isinstance(content_json, dict) else None
    if not submission_text:
        submission_text = json.dumps(content_json, ensure_ascii=False)

    attachments = _build_attachment_prompt_payload(db, submission)
    checkpoints = submission.checkpoints_json or {}
    warnings: List[str] = []
    submission_text = _truncate_ai_text(
        submission_text,
        limit=1800,
        warning_key="submission_text_truncated",
        warnings=warnings,
    )
    attachments_text = _serialize_json_for_prompt(
        attachments,
        limit=1200,
        warning_key="attachments_truncated",
        warnings=warnings,
    )
    checkpoints_text = _serialize_json_for_prompt(
        checkpoints,
        limit=1200,
        warning_key="checkpoints_truncated",
        warnings=warnings,
    )
    rubric_text = _serialize_rubric_json_for_prompt(
        rubric_dims,
        limit=1800,
        warning_key="rubric_text_truncated",
        warnings=warnings,
    )
    objectives_text = _serialize_json_for_prompt(
        assignment.objectives_json or {},
        limit=1200,
        warning_key="objectives_text_truncated",
        warnings=warnings,
    )
    phase_context = _truncate_ai_text(
        phase_context,
        limit=1200,
        warning_key="phase_context_truncated",
        warnings=warnings,
    )
    prompt_context = EvaluationPromptContext(
        assignment_title=assignment.title,
        assignment_topic=assignment.topic,
        assignment_description=assignment.description or "",
        objectives_json=objectives_text,
        phase_context=phase_context,
        submission_text=submission_text,
        attachments=attachments_text,
        checkpoints=checkpoints_text,
        rubric_text=rubric_text,
    )
    system_prompt, user_prompt = build_evaluation_prompt(prompt_context)

    settings = get_settings()
    client = DeepSeekJSONClient(settings, temperature=0.2, max_output_tokens=1200)
    logger.info(
        "ai_assist called prompt=%s target=%s request_id=%s",
        EVALUATION_AI_ASSIST_PROMPT.log_label(),
        EVALUATION_AI_ASSIST_PROMPT.target_api,
        request_id,
    )
    suggestion: AIEvaluationSuggestion | None = None
    meta = _build_ai_assist_meta(
        source="fallback" if not client.is_available else "ai",
        request_id=request_id,
        fallback_reason="provider_unavailable" if not client.is_available else "none",
        warnings=warnings,
        input_truncated=bool(warnings),
    )
    if client.is_available:
        try:
            suggestion = client.structured_predict(AIEvaluationSuggestion, system_prompt, user_prompt)
            meta = _build_ai_assist_meta(
                source="ai",
                request_id=request_id,
                warnings=warnings,
                input_truncated=bool(warnings),
            )
        except Exception as exc:
            logger.exception("ai_assist failed request_id=%s", request_id)
            meta = _build_ai_assist_meta(
                source="fallback",
                request_id=request_id,
                fallback_reason=_classify_ai_assist_fallback_reason(exc),
                warnings=warnings,
                input_truncated=bool(warnings),
            )
            suggestion = None

    if suggestion is None:
        fallback_scores = {dim["name"]: 2 for dim in rubric_dims}
        overall = _compute_average_score(fallback_scores)
        suggestion = AIEvaluationSuggestion(
            suggested_level=_score_to_level(overall),
            suggested_score=overall,
            dimension_scores=fallback_scores,
            feedback="请补充更具体的证据，并逐项对照评价量规完善表达与结论。",
            evidence=[],
            action_items=[
                "补充关键步骤证据并标注来源。",
                "对照量表逐项优化表达与结论。",
            ],
        )

    normalized_scores = _normalize_dimension_scores(
        rubric_dims,
        suggestion.dimension_scores,
        fallback=suggestion.suggested_score,
    )
    overall_score = _compute_average_score(normalized_scores)
    suggestion.suggested_score = overall_score
    suggestion.suggested_level = _score_to_level(overall_score)
    suggestion.dimension_scores = normalized_scores

    message = "AI 评分建议已生成" if meta["source"] == "ai" else "AI 评分建议已降级为本地建议草稿"
    return {
        "message": message,
        "suggestion": suggestion.model_dump(),
        "meta": meta,
    }


@router.get("/my-received", response_model=EvaluationListResponse)
async def list_my_received_evaluations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """学生查看自己收到的所有评价。"""
    # 找到学生的个人提交
    my_submissions = db.query(Submission).filter(Submission.student_id == current_user.id).all()
    submission_ids = {s.id for s in my_submissions}

    # 加入学生所在作业小组的提交
    group_ids = _group_ids_for_student(db, current_user.id)
    if group_ids:
        group_submissions = db.query(Submission).filter(Submission.group_id.in_(group_ids)).all()
        for submission in group_submissions:
            submission_ids.add(submission.id)

    if not submission_ids:
        return {"evaluations": [], "total": 0}

    evaluations = db.query(Evaluation).filter(Evaluation.submission_id.in_(submission_ids)).all()
    return {"evaluations": [_build_evaluation_response(item) for item in evaluations], "total": len(evaluations)}
