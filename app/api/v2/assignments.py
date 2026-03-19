"""作业设计CRUD API。"""

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.contracts.assignment import (
    AIAssignmentOutput,
    AIGenerationMeta,
    AssignmentCreate,
    AssignmentListResponse,
    AssignmentPreviewResponse,
    AssignmentResponse,
    AssignmentUpdate,
    CheckpointSchema,
    GroupCreate,
    GroupMembersUpdate,
    GroupResponse,
    LessonPlanBasicsExtraction,
    LessonPlanDraftRequest,
    LessonPlanDraftResponse,
    ObjectivesSchema,
    PhaseSchema,
    RubricDimensionSchema,
    RubricSchema,
    StepSchema,
)
from app.db import SessionLocal, get_db
from app.models import (
    Assignment, 
    Document,
    ParsingStatus,
    ProjectGroup,
    Submission,
    User,
    UserRole,
    AssignmentType,
    PracticalSubType,
    InquirySubType,
    InquiryDepth,
    SubmissionMode,
    SchoolStage,
    Subject,
)
from app.api.v2.auth import get_current_user, require_teacher
from app.prompts.assignment_prompts import (
    AssignmentPreviewPromptContext,
    LessonPlanPromptContext,
    build_assignment_preview_prompt,
    build_lesson_plan_prompt,
)
from app.prompts.registry import ASSIGNMENT_LESSON_PLAN_PROMPT, ASSIGNMENT_PREVIEW_PROMPT
from app.services.ai import DeepSeekJSONClient
from app.services.inventory import InventoryService
from app.utils.text_processing import parse_document

router = APIRouter()


def _normalize_group_members_input(db: Session, members_json: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    seen_ids: set[int] = set()

    for index, item in enumerate(members_json, start=1):
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail=f"小组成员参数无效（第{index}项）")

        raw_user_id = item.get("user_id") or item.get("student_id") or item.get("id")
        username = item.get("username")

        target_user: Optional[User] = None
        if raw_user_id is not None:
            try:
                user_id = int(str(raw_user_id))
            except Exception:
                raise HTTPException(status_code=400, detail=f"小组成员 user_id 无效（第{index}项）")
            target_user = db.query(User).filter(User.id == user_id).first()
        elif isinstance(username, str) and username.strip():
            target_user = db.query(User).filter(User.username == username.strip()).first()
        else:
            raise HTTPException(status_code=400, detail=f"小组成员缺少 user_id 或 username（第{index}项）")

        if not target_user:
            raise HTTPException(status_code=400, detail=f"小组成员不存在（第{index}项）")
        if target_user.role != UserRole.STUDENT:
            raise HTTPException(status_code=400, detail=f"小组成员必须是学生（第{index}项）")
        if target_user.id in seen_ids:
            continue

        seen_ids.add(target_user.id)
        normalized.append(
            {
                "user_id": target_user.id,
                "name": target_user.name,
                "username": target_user.username,
                "role": item.get("role") or "member",
            }
        )

    return normalized


def _can_view_assignment_groups(assignment: Assignment, current_user: User) -> bool:
    if current_user.role == UserRole.TEACHER:
        return assignment.created_by == current_user.id

    if current_user.role == UserRole.STUDENT:
        if not assignment.is_published:
            return False
        if current_user.grade is not None and assignment.grade != current_user.grade:
            return False
        return True

    return False


def _validate_reference_document(db: Session, document_id: Optional[int]) -> Optional[Document]:
    if document_id is None:
        return None
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=400, detail="参考资料不存在")
    if document.parsing_status != ParsingStatus.READY:
        raise HTTPException(status_code=400, detail="参考资料尚未入库完成，请稍后重试")
    return document


def _validate_stage_grade_match(stage: SchoolStage, grade: int) -> None:
    if stage == SchoolStage.PRIMARY and not 1 <= grade <= 6:
        raise HTTPException(status_code=400, detail="小学学段年级必须在 1-6 之间")
    if stage == SchoolStage.MIDDLE and not 7 <= grade <= 9:
        raise HTTPException(status_code=400, detail="初中学段年级必须在 7-9 之间")


def _normalize_related_subject_ids(
    db: Session,
    main_subject_id: int,
    related_subject_ids: List[int],
) -> List[int]:
    main_subject = db.query(Subject).filter(Subject.id == main_subject_id).first()
    if not main_subject:
        raise HTTPException(status_code=400, detail="主学科不存在")

    seen: set[int] = {main_subject_id}
    normalized: List[int] = []
    for subject_id in related_subject_ids:
        if subject_id in seen:
            continue
        target_subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if not target_subject:
            raise HTTPException(status_code=400, detail="存在无效的融合学科")
        seen.add(subject_id)
        normalized.append(subject_id)
    return normalized


def _validate_assignment_completeness(
    *,
    title: str,
    topic: str,
    objectives: Dict[str, Any],
    phases: List[Dict[str, Any]],
    rubric: Dict[str, Any],
) -> None:
    if not title.strip() or not topic.strip():
        raise HTTPException(status_code=400, detail="发布前必须填写标题和主题")

    step_count = 0
    for phase in phases:
        if not isinstance(phase, dict):
            continue
        steps = phase.get("steps") or []
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            step_count += 1
            checkpoints = step.get("checkpoints") or []
            if not checkpoints:
                raise HTTPException(status_code=400, detail="发布前每个步骤至少需要 1 个 checkpoint")

    if step_count < 2:
        raise HTTPException(status_code=400, detail="发布前至少需要 2 个步骤")

    dimensions = rubric.get("dimensions") or []
    if len(dimensions) < 2:
        raise HTTPException(status_code=400, detail="发布前至少需要 2 个评价维度")


_CN_GRADE_MAP = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def _extract_document_text(document: Document) -> str:
    if not document.file_path:
        return ""
    source = Path(document.file_path)
    if not source.exists():
        return ""
    content = source.read_bytes()
    pages = parse_document(content, document.filename or source.name)
    return "\n".join((page.get("text") or "").strip() for page in pages if isinstance(page, dict))


def _clean_filename_stem(filename: str) -> str:
    stem = Path(filename).stem.strip()
    stem = re.sub(r"[_-]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem)
    return stem


def _infer_grade_from_text(text: str) -> Optional[int]:
    match = re.search(r"([1-9])\s*年级", text)
    if match:
        return int(match.group(1))
    cn_match = re.search(r"([一二三四五六七八九])\s*年级", text)
    if cn_match:
        return _CN_GRADE_MAP.get(cn_match.group(1))
    return None


def _infer_school_stage(text: str, grade: Optional[int]) -> SchoolStage:
    if "小学" in text:
        return SchoolStage.PRIMARY
    if "初中" in text or "七年级" in text or "八年级" in text or "九年级" in text:
        return SchoolStage.MIDDLE
    if grade is not None and grade <= 6:
        return SchoolStage.PRIMARY
    return SchoolStage.MIDDLE


def _infer_assignment_type(text: str) -> AssignmentType:
    lowered = text.lower()
    if any(keyword in text for keyword in ("项目化", "项目式", "项目任务", "项目学习")):
        return AssignmentType.PROJECT
    if any(keyword in text for keyword in ("实验", "调查", "探究", "访谈", "问卷")):
        return AssignmentType.INQUIRY
    if any(keyword in text for keyword in ("参观", "体验", "实践活动", "劳动实践")):
        return AssignmentType.PRACTICAL
    if "project" in lowered:
        return AssignmentType.PROJECT
    if any(keyword in lowered for keyword in ("inquiry", "survey", "experiment")):
        return AssignmentType.INQUIRY
    return AssignmentType.PRACTICAL


def _infer_subtypes(
    assignment_type: AssignmentType,
    text: str,
) -> tuple[Optional[PracticalSubType], Optional[InquirySubType]]:
    if assignment_type == AssignmentType.PRACTICAL:
        if "模拟" in text or "角色扮演" in text:
            return PracticalSubType.SIMULATION, None
        if "观察" in text:
            return PracticalSubType.OBSERVATION, None
        return PracticalSubType.VISIT, None

    if assignment_type == AssignmentType.INQUIRY:
        lowered = text.lower()
        if any(keyword in text for keyword in ("问卷", "访谈", "调查")):
            return None, InquirySubType.SURVEY
        if "实验" in text or "experiment" in lowered:
            return None, InquirySubType.EXPERIMENT
        return None, InquirySubType.LITERATURE

    return None, None


def _infer_subject_ids(
    db: Session,
    text: str,
    stage: SchoolStage,
    requested_main_subject_id: Optional[int],
    requested_related_subject_ids: List[int],
    fallback_subject_id: Optional[int],
) -> tuple[int, List[int]]:
    stage_subjects = [
        subject
        for subject in db.query(Subject).all()
        if (stage == SchoolStage.PRIMARY and subject.primary_available)
        or (stage == SchoolStage.MIDDLE and subject.middle_available)
    ]
    if not stage_subjects:
        stage_subjects = db.query(Subject).all()

    by_id = {subject.id: subject for subject in stage_subjects}

    if requested_main_subject_id and requested_main_subject_id in by_id:
        main_subject_id = requested_main_subject_id
    elif fallback_subject_id and fallback_subject_id in by_id:
        main_subject_id = fallback_subject_id
    else:
        matched_ids: List[int] = []
        lowered = text.lower()
        for subject in stage_subjects:
            subject_name = (subject.name or "").strip()
            if subject_name and subject_name in text:
                matched_ids.append(subject.id)
                continue
            subject_code = (subject.code or "").strip().lower()
            if subject_code and subject_code in lowered:
                matched_ids.append(subject.id)
        if matched_ids:
            main_subject_id = matched_ids[0]
        else:
            main_subject_id = stage_subjects[0].id

    related_subject_ids: List[int] = []
    seen: set[int] = {main_subject_id}
    for subject_id in requested_related_subject_ids:
        if subject_id in by_id and subject_id not in seen:
            seen.add(subject_id)
            related_subject_ids.append(subject_id)

    if not related_subject_ids:
        lowered = text.lower()
        for subject in stage_subjects:
            if subject.id in seen:
                continue
            subject_name = (subject.name or "").strip()
            subject_code = (subject.code or "").strip().lower()
            if (subject_name and subject_name in text) or (subject_code and subject_code in lowered):
                seen.add(subject.id)
                related_subject_ids.append(subject.id)
            if len(related_subject_ids) >= 2:
                break

    return main_subject_id, related_subject_ids


def _normalize_subject_token(value: str) -> str:
    normalized = re.sub(r"\s+", "", (value or "").strip().lower())
    normalized = normalized.replace("学科", "")
    return normalized


def _resolve_subject_ids_from_names(
    db: Session,
    stage: SchoolStage,
    main_subject_name: Optional[str],
    related_subject_names: List[str],
) -> tuple[Optional[int], List[int]]:
    stage_subjects = [
        subject
        for subject in db.query(Subject).all()
        if (stage == SchoolStage.PRIMARY and subject.primary_available)
        or (stage == SchoolStage.MIDDLE and subject.middle_available)
    ]
    if not stage_subjects:
        stage_subjects = db.query(Subject).all()

    by_token: Dict[str, int] = {}
    for subject in stage_subjects:
        for token in [subject.name or "", subject.code or ""]:
            normalized = _normalize_subject_token(token)
            if normalized:
                by_token[normalized] = subject.id

    def match_subject_id(raw_name: Optional[str]) -> Optional[int]:
        token = _normalize_subject_token(raw_name or "")
        if not token:
            return None
        if token in by_token:
            return by_token[token]
        for key, subject_id in by_token.items():
            if token in key or key in token:
                return subject_id
        return None

    main_subject_id = match_subject_id(main_subject_name)
    related_subject_ids: List[int] = []
    seen = {main_subject_id} if main_subject_id else set()
    for name in related_subject_names:
        subject_id = match_subject_id(name)
        if subject_id and subject_id not in seen:
            seen.add(subject_id)
            related_subject_ids.append(subject_id)
    return main_subject_id, related_subject_ids


def _normalize_school_stage(value: Optional[str]) -> Optional[SchoolStage]:
    token = (value or "").strip().lower()
    if token in {"primary", "小学"}:
        return SchoolStage.PRIMARY
    if token in {"middle", "初中"}:
        return SchoolStage.MIDDLE
    return None


def _normalize_assignment_type(value: Optional[str]) -> Optional[AssignmentType]:
    token = (value or "").strip().lower()
    mapping = {
        "practical": AssignmentType.PRACTICAL,
        "实践": AssignmentType.PRACTICAL,
        "实践性作业": AssignmentType.PRACTICAL,
        "inquiry": AssignmentType.INQUIRY,
        "探究": AssignmentType.INQUIRY,
        "探究性作业": AssignmentType.INQUIRY,
        "project": AssignmentType.PROJECT,
        "项目": AssignmentType.PROJECT,
        "项目式作业": AssignmentType.PROJECT,
    }
    return mapping.get(token)


def _normalize_inquiry_depth(value: Optional[str]) -> Optional[InquiryDepth]:
    token = (value or "").strip().lower()
    mapping = {
        "basic": InquiryDepth.BASIC,
        "基础": InquiryDepth.BASIC,
        "intermediate": InquiryDepth.INTERMEDIATE,
        "中等": InquiryDepth.INTERMEDIATE,
        "deep": InquiryDepth.DEEP,
        "深度": InquiryDepth.DEEP,
    }
    return mapping.get(token)


def _normalize_submission_mode(value: Optional[str]) -> Optional[SubmissionMode]:
    token = (value or "").strip().lower()
    mapping = {
        "phased": SubmissionMode.PHASED,
        "过程性提交": SubmissionMode.PHASED,
        "once": SubmissionMode.ONCE,
        "一次性提交": SubmissionMode.ONCE,
        "mixed": SubmissionMode.MIXED,
        "混合提交": SubmissionMode.MIXED,
    }
    return mapping.get(token)


def _normalize_practical_subtype(value: Optional[str]) -> Optional[PracticalSubType]:
    token = (value or "").strip().lower()
    mapping = {
        "visit": PracticalSubType.VISIT,
        "参观考察": PracticalSubType.VISIT,
        "simulation": PracticalSubType.SIMULATION,
        "模拟表演": PracticalSubType.SIMULATION,
        "observation": PracticalSubType.OBSERVATION,
        "观察体验": PracticalSubType.OBSERVATION,
    }
    return mapping.get(token)


def _normalize_inquiry_subtype(value: Optional[str]) -> Optional[InquirySubType]:
    token = (value or "").strip().lower()
    mapping = {
        "literature": InquirySubType.LITERATURE,
        "文献探究": InquirySubType.LITERATURE,
        "survey": InquirySubType.SURVEY,
        "调查探究": InquirySubType.SURVEY,
        "experiment": InquirySubType.EXPERIMENT,
        "实验探究": InquirySubType.EXPERIMENT,
    }
    return mapping.get(token)


def _extract_lesson_plan_basics_with_ai(
    text: str,
    db: Session,
    request_data: LessonPlanDraftRequest,
) -> Dict[str, Any]:
    settings = get_settings()
    client = DeepSeekJSONClient(settings, temperature=0.0, max_output_tokens=600, request_timeout=45)
    if not client.is_available:
        return {}

    excerpt = _summarize_text(text, max_length=3200)
    system_prompt = (
        "你是K12教案结构化提取助手。"
        "只输出JSON对象，不要解释。"
        "仅提取基础表单字段，不要生成标题，不要生成步骤正文。"
    )
    user_prompt = (
        "请从教案文本中提取字段：school_stage, grade, assignment_type, practical_subtype, "
        "inquiry_subtype, inquiry_depth, submission_mode, duration_weeks, main_subject, related_subjects。\n"
        "school_stage仅可为 primary/middle；assignment_type仅可为 practical/inquiry/project；"
        "inquiry_depth仅可为 basic/intermediate/deep；submission_mode仅可为 phased/once/mixed。\n"
        "related_subjects必须是字符串数组。若无法判断字段则返回 null 或空数组。\n"
        f"教案文本：\n{excerpt}"
    )

    try:
        payload = client.predict_json(system_prompt, user_prompt)
        extracted = LessonPlanBasicsExtraction.model_validate(payload)
    except Exception as exc:
        _log_ai_generation_error(exc)
        return {}

    stage = _normalize_school_stage(extracted.school_stage)
    if stage is None:
        fallback_grade = extracted.grade if isinstance(extracted.grade, int) else request_data.grade
        stage = _infer_school_stage(text, fallback_grade)

    main_subject_id, related_subject_ids = _resolve_subject_ids_from_names(
        db,
        stage,
        extracted.main_subject,
        extracted.related_subjects or [],
    )

    return {
        "school_stage": stage,
        "grade": extracted.grade,
        "assignment_type": _normalize_assignment_type(extracted.assignment_type),
        "practical_subtype": _normalize_practical_subtype(extracted.practical_subtype),
        "inquiry_subtype": _normalize_inquiry_subtype(extracted.inquiry_subtype),
        "inquiry_depth": _normalize_inquiry_depth(extracted.inquiry_depth),
        "submission_mode": _normalize_submission_mode(extracted.submission_mode),
        "duration_weeks": extracted.duration_weeks,
        "main_subject_id": main_subject_id,
        "related_subject_ids": related_subject_ids,
    }


def _build_lesson_plan_seed(
    request_data: LessonPlanDraftRequest,
    document: Document,
    text: str,
    db: Session,
) -> AssignmentCreate:
    doc_meta = document.metadata_json or {}
    fallback_subject_id = doc_meta.get("subject_id") if isinstance(doc_meta, dict) else None
    extracted = _extract_lesson_plan_basics_with_ai(text, db, request_data)

    inferred_grade = request_data.grade or extracted.get("grade") or _infer_grade_from_text(text) or 8
    inferred_stage = request_data.school_stage or extracted.get("school_stage") or _infer_school_stage(text, inferred_grade)
    if inferred_stage == SchoolStage.PRIMARY and inferred_grade > 6:
        inferred_grade = 6
    if inferred_stage == SchoolStage.MIDDLE and inferred_grade < 7:
        inferred_grade = 7

    inferred_type = request_data.assignment_type or extracted.get("assignment_type") or _infer_assignment_type(text)
    practical_subtype, inquiry_subtype = _infer_subtypes(inferred_type, text)
    practical_subtype = extracted.get("practical_subtype") or practical_subtype
    inquiry_subtype = extracted.get("inquiry_subtype") or inquiry_subtype

    main_subject_id, related_subject_ids = _infer_subject_ids(
        db,
        text,
        inferred_stage,
        request_data.main_subject_id or extracted.get("main_subject_id"),
        request_data.related_subject_ids or extracted.get("related_subject_ids") or [],
        int(fallback_subject_id) if isinstance(fallback_subject_id, int) else None,
    )

    title_match = re.search(r"(?:教案名称|课题|主题)[:：]\s*([^\n\r]{2,80})", text)
    heading_title = ""
    for raw_line in text.splitlines()[:8]:
        line = re.sub(r"^[\s\-\d.()（）一二三四五六七八九十]+", "", raw_line.strip())
        if 4 <= len(line) <= 80:
            heading_title = line
            break
    title = (
        title_match.group(1).strip()
        if title_match
        else (heading_title or _clean_filename_stem(document.filename))
    )
    topic = re.sub(r"^(教案|教学设计|课程设计)\s*", "", title).strip() or title
    description = _summarize_text(text, max_length=900)

    duration_weeks = request_data.duration_weeks or extracted.get("duration_weeks") or 2
    week_match = re.search(r"(\d{1,2})\s*周", text)
    if week_match:
        duration_weeks = max(1, min(16, int(week_match.group(1))))

    return AssignmentCreate(
        title=title,
        topic=topic,
        description=description,
        school_stage=inferred_stage,
        grade=inferred_grade,
        main_subject_id=main_subject_id,
        related_subject_ids=related_subject_ids,
        document_id=document.id,
        assignment_type=inferred_type,
        practical_subtype=practical_subtype,
        inquiry_subtype=inquiry_subtype,
        inquiry_depth=request_data.inquiry_depth or extracted.get("inquiry_depth") or InquiryDepth.INTERMEDIATE,
        submission_mode=request_data.submission_mode or extracted.get("submission_mode") or SubmissionMode.PHASED,
        duration_weeks=duration_weeks,
        deadline=None,
        objectives_json=None,
        phases_json=None,
        rubric_json=None,
    )


# === API 端点 ===

@router.post("/preview", response_model=AssignmentPreviewResponse)
async def preview_assignment(
    data: AssignmentCreate,
    force_generate: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    """生成作业的 AI 预览内容，不入库。"""
    document = _validate_reference_document(db, data.document_id)
    _validate_stage_grade_match(data.school_stage, data.grade)
    data.related_subject_ids = _normalize_related_subject_ids(db, data.main_subject_id, data.related_subject_ids)
    objectives = data.objectives_payload()
    phases = data.phases_payload()
    rubric = data.rubric_payload()
    original_objectives_empty = _is_empty_json(objectives)
    original_phases_empty = _is_empty_json(phases)
    original_rubric_empty = _is_empty_json(rubric)
    meta = _build_generation_meta(ASSIGNMENT_PREVIEW_PROMPT, source="manual_merge")

    if force_generate:
        lesson_plan_text = _extract_document_text(document) if document else ""
        if lesson_plan_text.strip():
            objectives, phases, rubric, meta = _generate_ai_content_from_lesson_plan_with_meta(data, lesson_plan_text)
        else:
            objectives, phases, rubric, meta = _generate_ai_content_with_meta(data)
    elif _is_empty_json(objectives) or _is_empty_json(phases) or _is_empty_json(rubric):
        gen_objectives, gen_phases, gen_rubric, gen_meta = _generate_ai_content_with_meta(data)
        if _is_empty_json(objectives):
            objectives = gen_objectives
        if _is_empty_json(phases):
            phases = gen_phases
        if _is_empty_json(rubric):
            rubric = gen_rubric
        if original_objectives_empty and original_phases_empty and original_rubric_empty:
            meta = gen_meta
        else:
            meta = _build_generation_meta(
                ASSIGNMENT_PREVIEW_PROMPT,
                source="manual_merge",
                used_rag=bool(gen_meta.get("used_rag")),
                fallback_reason=gen_meta.get("fallback_reason", "none") if gen_meta.get("source") == "fallback" else "none",
            )

    objectives, phases, rubric = _ensure_ai_defaults(data, objectives, phases, rubric)
    return {
        "objectives_json": objectives,
        "phases_json": phases,
        "rubric_json": rubric,
        "meta": meta,
    }


@router.post("/from-lesson-plan", response_model=LessonPlanDraftResponse)
async def generate_assignment_from_lesson_plan(
    data: LessonPlanDraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    """根据已上传教案生成可编辑作业草稿，不直接入库。"""
    document = _validate_reference_document(db, data.document_id)
    if not document:
        raise HTTPException(status_code=400, detail="教案不存在或尚未完成入库")

    lesson_plan_text = _extract_document_text(document)
    if not lesson_plan_text.strip():
        raise HTTPException(status_code=400, detail="教案内容为空，无法生成草稿")

    seed = _build_lesson_plan_seed(data, document, lesson_plan_text, db)
    objectives, phases, rubric, meta = _generate_ai_content_from_lesson_plan_with_meta(seed, lesson_plan_text)
    objectives, phases, rubric = _ensure_ai_defaults(seed, objectives, phases, rubric)

    return {
        "title": seed.title,
        "topic": seed.topic,
        "description": seed.description or "",
        "school_stage": seed.school_stage,
        "grade": seed.grade,
        "main_subject_id": seed.main_subject_id,
        "related_subject_ids": seed.related_subject_ids,
        "document_id": document.id,
        "assignment_type": seed.assignment_type,
        "practical_subtype": seed.practical_subtype,
        "inquiry_subtype": seed.inquiry_subtype,
        "inquiry_depth": seed.inquiry_depth,
        "submission_mode": seed.submission_mode,
        "duration_weeks": seed.duration_weeks,
        "objectives_json": objectives,
        "phases_json": phases,
        "rubric_json": rubric,
        "source_summary": _summarize_text(lesson_plan_text, max_length=280),
        "meta": meta,
    }


@router.get("/ai-status")
async def ai_status(
    current_user: User = Depends(require_teacher),
):
    settings = get_settings()
    return {"available": bool(settings.deepseek_api_key), "model": settings.deepseek_model}


@router.post("/", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    data: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher)
):
    """创建新作业（教师权限）。"""
    _validate_reference_document(db, data.document_id)
    _validate_stage_grade_match(data.school_stage, data.grade)
    data.related_subject_ids = _normalize_related_subject_ids(db, data.main_subject_id, data.related_subject_ids)
    objectives = data.objectives_payload()
    phases = data.phases_payload()
    rubric = data.rubric_payload()
    objectives, phases, rubric = _ensure_ai_defaults(data, objectives, phases, rubric)
    assignment_payload = data.model_dump(
        exclude={"objectives_json", "phases_json", "rubric_json"}
    )
    assignment = Assignment(
        **assignment_payload,
        objectives_json=objectives,
        phases_json=phases,
        rubric_json=rubric,
        created_by=current_user.id,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    db.execute(
        update(Assignment)
        .where(Assignment.id == assignment.id)
        .values(
            objectives_json=objectives,
            phases_json=phases,
            rubric_json=rubric,
        )
    )
    db.commit()
    db.refresh(assignment)
    return assignment


@router.get("/", response_model=AssignmentListResponse)
async def list_assignments(
    page: int = 1,
    page_size: int = 20,
    published_only: bool = False,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取作业列表。教师看自己创建的，学生看已发布的。"""
    from app.models.user import UserRole

    query = db.query(Assignment)

    if current_user.role == UserRole.TEACHER:
        query = query.filter(Assignment.created_by == current_user.id)
        if not include_archived:
            query = query.filter(Assignment.is_archived == False)
    else:
        query = query.filter(Assignment.is_published == True)
        query = query.filter(Assignment.is_archived == False)
        if current_user.grade is not None:
            query = query.filter(Assignment.grade == current_user.grade)

    if published_only:
        query = query.filter(Assignment.is_published == True)

    total = query.count()
    assignments = query.offset((page - 1) * page_size).limit(page_size).all()

    return {"assignments": assignments, "total": total}


@router.get("/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取作业详情。"""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    return assignment


@router.put("/{assignment_id}", response_model=AssignmentResponse)
async def update_assignment(
    assignment_id: int,
    data: AssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher)
):
    """更新作业（教师权限）。"""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    if assignment.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="只能编辑自己创建的作业")
    
    update_data = data.model_dump(exclude_unset=True)
    if "document_id" in update_data and update_data.get("document_id") is not None:
        raw_document_id = update_data.get("document_id")
        if isinstance(raw_document_id, int):
            _validate_reference_document(db, raw_document_id)
        else:
            try:
                _validate_reference_document(db, int(str(raw_document_id)))
            except Exception:
                raise HTTPException(status_code=400, detail="参考资料参数无效")
    if "title" in update_data and isinstance(update_data["title"], str) and not update_data["title"].strip():
        raise HTTPException(status_code=400, detail="标题不能为空")
    if "topic" in update_data and isinstance(update_data["topic"], str) and not update_data["topic"].strip():
        raise HTTPException(status_code=400, detail="主题不能为空")
    for key, value in update_data.items():
        setattr(assignment, key, value)
    
    db.commit()
    db.refresh(assignment)
    return assignment


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher)
):
    """删除作业（教师权限）。"""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    if assignment.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="只能删除自己创建的作业")
    
    db.delete(assignment)
    db.commit()


@router.post("/{assignment_id}/publish", response_model=AssignmentResponse)
async def publish_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher)
):
    """发布作业。"""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    if assignment.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="只能发布自己创建的作业")
    _validate_stage_grade_match(assignment.school_stage, assignment.grade)
    assignment.related_subject_ids = _normalize_related_subject_ids(
        db,
        assignment.main_subject_id,
        assignment.related_subject_ids or [],
    )
    _validate_assignment_completeness(
        title=assignment.title,
        topic=assignment.topic,
        objectives=assignment.objectives_json or {},
        phases=assignment.phases_json or [],
        rubric=assignment.rubric_json or {},
    )
    
    assignment.is_published = True
    assignment.is_archived = False
    assignment.archived_at = None
    assignment.published_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.post("/{assignment_id}/archive", response_model=AssignmentResponse)
async def archive_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    """归档作业。"""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    if assignment.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="只能归档自己创建的作业")

    assignment.is_archived = True
    assignment.archived_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.post("/{assignment_id}/unarchive", response_model=AssignmentResponse)
async def unarchive_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    """取消归档作业。"""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    if assignment.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="只能操作自己创建的作业")

    assignment.is_archived = False
    assignment.archived_at = None
    db.commit()
    db.refresh(assignment)
    return assignment


@router.post("/{assignment_id}/generate-steps")
async def generate_steps(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher)
):
    """AI生成分步骤任务引导（待实现）。"""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    
    data = AssignmentCreate(
        title=assignment.title,
        topic=assignment.topic,
        description=assignment.description,
        school_stage=assignment.school_stage,
        grade=assignment.grade,
        main_subject_id=assignment.main_subject_id,
        related_subject_ids=assignment.related_subject_ids or [],
        document_id=assignment.document_id,
        assignment_type=assignment.assignment_type,
        practical_subtype=assignment.practical_subtype,
        inquiry_subtype=assignment.inquiry_subtype,
        inquiry_depth=assignment.inquiry_depth,
        submission_mode=assignment.submission_mode,
        duration_weeks=assignment.duration_weeks,
        deadline=assignment.deadline,
    )
    objectives, phases, rubric = _generate_ai_content(data)
    objectives, phases, rubric = _ensure_ai_defaults(data, objectives, phases, rubric)
    assignment.objectives_json = objectives
    assignment.phases_json = phases
    assignment.rubric_json = rubric
    db.commit()
    db.execute(
        update(Assignment)
        .where(Assignment.id == assignment.id)
        .values(
            objectives_json=objectives,
            phases_json=phases,
            rubric_json=rubric,
        )
    )
    db.commit()
    
    return {"message": "任务引导生成成功", "phases": phases}


# === 小组管理 ===

@router.post("/{assignment_id}/groups", response_model=GroupResponse)
async def create_group(
    assignment_id: int,
    data: GroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher)
):
    """为作业创建小组。"""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")

    if assignment.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="只能为自己创建的作业管理小组")

    group_name = data.name.strip()
    if not group_name:
        raise HTTPException(status_code=400, detail="小组名称不能为空")

    duplicate = (
        db.query(ProjectGroup)
        .filter(
            ProjectGroup.assignment_id == assignment_id,
            ProjectGroup.name == group_name,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="该作业内小组名称已存在")

    normalized_members = _normalize_group_members_input(db, data.members_json or [])
    
    group = ProjectGroup(
        assignment_id=assignment_id,
        name=group_name,
        members_json=normalized_members,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.get("/{assignment_id}/groups", response_model=List[GroupResponse])
async def list_groups(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取作业的所有小组。"""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")

    if not _can_view_assignment_groups(assignment, current_user):
        raise HTTPException(status_code=403, detail="无权查看该作业小组")

    groups = (
        db.query(ProjectGroup)
        .filter(ProjectGroup.assignment_id == assignment_id)
        .order_by(ProjectGroup.created_at.asc())
        .all()
    )
    return groups


@router.put("/{assignment_id}/groups/{group_id}/members", response_model=GroupResponse)
async def update_group_members(
    assignment_id: int,
    group_id: int,
    data: GroupMembersUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    """更新作业小组成员。"""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    if assignment.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="只能管理自己创建的作业小组")

    group = (
        db.query(ProjectGroup)
        .filter(
            ProjectGroup.id == group_id,
            ProjectGroup.assignment_id == assignment_id,
        )
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="小组不存在")

    linked_submission_count = (
        db.query(Submission)
        .filter(Submission.group_id == group.id)
        .count()
    )
    if linked_submission_count > 0:
        raise HTTPException(status_code=400, detail="该小组已有提交记录，不能再调整成员")

    normalized_members = _normalize_group_members_input(db, data.members_json or [])
    if not normalized_members:
        raise HTTPException(status_code=400, detail="小组至少需要 1 名成员")

    group.members_json = normalized_members
    db.commit()
    db.refresh(group)
    return group


@router.delete("/{assignment_id}/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    assignment_id: int,
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    """删除作业小组。"""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    if assignment.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="只能管理自己创建的作业小组")

    group = (
        db.query(ProjectGroup)
        .filter(
            ProjectGroup.id == group_id,
            ProjectGroup.assignment_id == assignment_id,
        )
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="小组不存在")

    linked_submission_count = (
        db.query(Submission)
        .filter(Submission.group_id == group.id)
        .count()
    )
    if linked_submission_count > 0:
        raise HTTPException(status_code=400, detail="该小组已有提交记录，不能删除")

    db.delete(group)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# === 辅助函数 ===

def _cp(content: str, evidence_type: str) -> Dict[str, Any]:
    return {"content": content, "evidence_type": evidence_type}


def _get_template_phases(data: AssignmentCreate) -> List[Dict[str, Any]]:
    """根据作业类型与子类型返回模板阶段（来源：产品设计文档 5.2.3）。"""
    if data.assignment_type == AssignmentType.PRACTICAL:
        phases = [
            {"name": "任务理解", "order": 1, "steps": [
                {"name": "阅读任务单", "description": "明确实践主题、目标、具体要求", "checkpoints": [_cp("确认已阅读任务单", "confirm")]},
                {"name": "了解评价标准", "description": "知道作业如何被评价", "checkpoints": [_cp("能复述评价要点", "text")]},
            ]},
            {"name": "实践准备", "order": 2, "steps": [
                {"name": "制定计划", "description": "确定时间、地点、所需材料", "checkpoints": [_cp("有书面准备清单", "document")]},
                {"name": "分工协作", "description": "明确小组成员分工", "checkpoints": [_cp("有分工表", "document")]},
            ]},
            {"name": "实践体验", "order": 3, "steps": [
                {"name": "参与实践活动", "description": "按计划完成参观/观察/体验", "checkpoints": [_cp("时间线记录", "text")]},
                {"name": "过程记录", "description": "用文字、照片、视频等记录过程", "checkpoints": [_cp("照片/视频/笔记", "image")]},
            ]},
            {"name": "跨学科解释", "order": 4, "steps": [
                {"name": "知识联结", "description": "用多学科知识解释观察到的现象", "checkpoints": [_cp("跨学科概念对应表", "document")]},
                {"name": "深度思考", "description": "分析现象背后的原因和规律", "checkpoints": [_cp("分析文字（至少200字）", "text")]},
            ]},
            {"name": "成果展示", "order": 5, "steps": [
                {"name": "制作成果", "description": "制作海报/PPT/视频/表演稿", "checkpoints": [_cp("成果材料", "document")]},
                {"name": "汇报展示", "description": "向全班或小组汇报", "checkpoints": [_cp("汇报记录", "document")]},
            ]},
            {"name": "反思总结", "order": 6, "steps": [
                {"name": "个人反思", "description": "写出收获、困难、改进点", "checkpoints": [_cp("反思文字（至少150字）", "text")]},
                {"name": "互评", "description": "对同学的成果给出评价", "checkpoints": [_cp("互评表", "document")]},
            ]},
        ]
        return _apply_depth_scaffold(phases, data.inquiry_depth)

    if data.assignment_type == AssignmentType.INQUIRY:
        subtype = data.inquiry_subtype or InquirySubType.LITERATURE
        if subtype == InquirySubType.SURVEY:
            phases = [
                {"name": "确定问题", "order": 1, "steps": [
                    {"name": "明确调查目的", "description": "确定要调查什么、为什么调查", "checkpoints": [_cp("调查目的描述", "text")]},
                    {"name": "确定调查对象", "description": "明确调查谁、多少人", "checkpoints": [_cp("调查对象说明", "text")]},
                ]},
                {"name": "设计方案", "order": 2, "steps": [
                    {"name": "选择调查方法", "description": "问卷/访谈/观察", "checkpoints": [_cp("方法选择说明", "text")]},
                    {"name": "设计调查工具", "description": "设计问卷/访谈提纲", "checkpoints": [_cp("调查工具（问卷/提纲）", "document")]},
                ]},
                {"name": "实施调查", "order": 3, "steps": [
                    {"name": "开展调查", "description": "按计划实施调查", "checkpoints": [_cp("调查过程记录", "document")]},
                    {"name": "收集数据", "description": "整理收回的数据", "checkpoints": [_cp("原始数据", "document")]},
                ]},
                {"name": "数据分析", "order": 4, "steps": [
                    {"name": "数据整理", "description": "清洗、分类、统计数据", "checkpoints": [_cp("数据统计表", "document")]},
                    {"name": "数据可视化", "description": "用图表呈现数据", "checkpoints": [_cp("图表（至少2个）", "image")]},
                ]},
                {"name": "得出结论", "order": 5, "steps": [
                    {"name": "分析发现", "description": "基于数据分析得出结论", "checkpoints": [_cp("分析结论", "text")]},
                    {"name": "提出建议", "description": "基于结论提出建议或对策", "checkpoints": [_cp("建议部分", "text")]},
                ]},
                {"name": "撰写报告", "order": 6, "steps": [
                    {"name": "撰写调查报告", "description": "按规范格式撰写", "checkpoints": [_cp("调查报告", "document")]},
                ]},
            ]
        elif subtype == InquirySubType.EXPERIMENT:
            phases = [
                {"name": "提出问题与假设", "order": 1, "steps": [
                    {"name": "观察现象", "description": "观察并描述要研究的现象", "checkpoints": [_cp("现象描述", "text")]},
                    {"name": "提出问题", "description": "基于观察提出探究问题", "checkpoints": [_cp("探究问题", "text")]},
                    {"name": "作出假设", "description": "对问题给出可验证的假设", "checkpoints": [_cp("假设陈述", "text")]},
                ]},
                {"name": "设计实验", "order": 2, "steps": [
                    {"name": "确定变量", "description": "明确自变量、因变量、控制变量", "checkpoints": [_cp("变量确认表", "document")]},
                    {"name": "设计步骤", "description": "写出实验操作步骤", "checkpoints": [_cp("实验方案", "document")]},
                    {"name": "准备材料", "description": "列出所需器材和材料", "checkpoints": [_cp("材料清单", "document")]},
                ]},
                {"name": "实施实验", "order": 3, "steps": [
                    {"name": "按步骤操作", "description": "规范操作，注意安全", "checkpoints": [_cp("操作过程照片/视频", "image")]},
                    {"name": "记录数据", "description": "如实记录实验数据", "checkpoints": [_cp("原始数据记录表", "document")]},
                    {"name": "重复实验", "description": "至少重复2次以确保可靠性", "checkpoints": [_cp("多次实验数据", "document")]},
                ]},
                {"name": "分析与结论", "order": 4, "steps": [
                    {"name": "数据处理", "description": "计算平均值、绘制图表", "checkpoints": [_cp("数据分析图表", "image")]},
                    {"name": "得出结论", "description": "判断假设是否成立", "checkpoints": [_cp("结论陈述", "text")]},
                ]},
                {"name": "交流与反思", "order": 5, "steps": [
                    {"name": "撰写报告", "description": "按实验报告格式撰写", "checkpoints": [_cp("实验报告", "document")]},
                    {"name": "反思改进", "description": "分析误差来源和改进方向", "checkpoints": [_cp("反思部分", "text")]},
                ]},
            ]
        else:
            phases = [
                {"name": "确定问题", "order": 1, "steps": [
                    {"name": "提出探究问题", "description": "基于主题确定要探究的核心问题", "checkpoints": [_cp("探究问题描述", "text")]},
                    {"name": "形成假设", "description": "对问题的初步回答或猜想", "checkpoints": [_cp("假设陈述", "text")]},
                ]},
                {"name": "检索资料", "order": 2, "steps": [
                    {"name": "确定检索策略", "description": "明确关键词、资料来源类型", "checkpoints": [_cp("检索计划", "document")]},
                    {"name": "收集资料", "description": "从课本、图书、网络等收集资料", "checkpoints": [_cp("资料清单（含来源）", "document")]},
                ]},
                {"name": "阅读分析", "order": 3, "steps": [
                    {"name": "精读资料", "description": "提取关键信息，做标注笔记", "checkpoints": [_cp("阅读笔记", "document")]},
                    {"name": "信息整合", "description": "整理归纳不同来源的信息", "checkpoints": [_cp("信息整合表/思维导图", "document")]},
                ]},
                {"name": "形成结论", "order": 4, "steps": [
                    {"name": "论证分析", "description": "基于证据论证假设是否成立", "checkpoints": [_cp("论证过程记录", "text")]},
                    {"name": "得出结论", "description": "形成对探究问题的回答", "checkpoints": [_cp("结论陈述", "text")]},
                ]},
                {"name": "撰写报告", "order": 5, "steps": [
                    {"name": "撰写探究报告", "description": "按规范格式撰写报告", "checkpoints": [_cp("探究报告", "document")]},
                    {"name": "反思局限", "description": "分析探究的局限性和改进方向", "checkpoints": [_cp("反思部分", "text")]},
                ]},
            ]
        return _apply_depth_scaffold(phases, data.inquiry_depth)

    phases = [
        {"name": "立项启动", "order": 1, "steps": [
            {"name": "理解真实问题", "description": "深入理解要解决的问题及其背景", "checkpoints": [_cp("问题分析文档", "document")]},
            {"name": "明确项目目标", "description": "确定成果形式、受众、成功标准", "checkpoints": [_cp("项目立项卡", "document")]},
            {"name": "组建团队", "description": "确定成员、角色分工", "checkpoints": [_cp("团队分工表", "document")]},
        ]},
        {"name": "规划设计", "order": 2, "steps": [
            {"name": "调研分析", "description": "收集相关信息，分析已有方案", "checkpoints": [_cp("调研报告", "document")]},
            {"name": "制定计划", "description": "确定时间节点、里程碑", "checkpoints": [_cp("项目计划表（甘特图）", "document")]},
            {"name": "方案设计", "description": "设计解决方案", "checkpoints": [_cp("设计方案", "document")]},
        ]},
        {"name": "第一轮迭代", "order": 3, "steps": [
            {"name": "实施制作", "description": "按设计方案制作初版成果", "checkpoints": [_cp("初版成果（原型）", "image")]},
            {"name": "测试验证", "description": "测试初版成果是否达成目标", "checkpoints": [_cp("测试记录", "document")]},
            {"name": "收集反馈", "description": "向同学、老师或用户收集反馈", "checkpoints": [_cp("反馈汇总", "document")]},
        ]},
        {"name": "第二轮迭代", "order": 4, "steps": [
            {"name": "分析问题", "description": "基于反馈分析需要改进的问题", "checkpoints": [_cp("问题清单", "document")]},
            {"name": "改进优化", "description": "针对问题进行改进", "checkpoints": [_cp("改进记录+终版成果", "document")]},
        ]},
        {"name": "展示汇报", "order": 5, "steps": [
            {"name": "准备汇报材料", "description": "制作PPT/海报/视频等", "checkpoints": [_cp("汇报材料", "document")]},
            {"name": "进行展示", "description": "向全班/评审进行汇报", "checkpoints": [_cp("展示照片/视频", "image")]},
            {"name": "答辩交流", "description": "回答提问，交流心得", "checkpoints": [_cp("答辩记录", "document")]},
        ]},
        {"name": "复盘总结", "order": 6, "steps": [
            {"name": "团队复盘", "description": "回顾过程，分析成功与不足", "checkpoints": [_cp("复盘报告", "document")]},
            {"name": "个人反思", "description": "每位成员写个人反思", "checkpoints": [_cp("个人反思文字", "text")]},
            {"name": "归档存档", "description": "整理所有过程材料", "checkpoints": [_cp("项目档案袋", "document")]},
        ]},
    ]
    return _apply_depth_scaffold(phases, data.inquiry_depth)


def _apply_depth_scaffold(
    phases: List[Dict[str, Any]],
    depth: InquiryDepth,
) -> List[Dict[str, Any]]:
    if depth == InquiryDepth.BASIC:
        suffix = "提示：可参考示例或模板，按步骤完成。"
    elif depth == InquiryDepth.DEEP:
        suffix = "提示：说明你的选择依据，体现独立思考。"
    else:
        suffix = "提示：注意记录来源与过程。"

    for phase in phases:
        for step in phase.get("steps", []):
            description = step.get("description", "")
            if suffix and suffix not in description:
                step["description"] = f"{description} {suffix}".strip()
    return phases


def _summarize_text(text: str, max_length: int = 360) -> str:
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""
    return cleaned[:max_length] + ("..." if len(cleaned) > max_length else "")


def _resolve_subject_names(subject_ids: List[int]) -> List[str]:
    if not subject_ids:
        return []
    with SessionLocal() as db:
        subjects = db.query(Subject).filter(Subject.id.in_(subject_ids)).all()
    id_to_name = {subject.id: subject.name for subject in subjects}
    return [id_to_name.get(subject_id, f"id={subject_id}") for subject_id in subject_ids]


def _resolve_document_name(document_id: Optional[int]) -> str:
    if not document_id:
        return ""
    with SessionLocal() as db:
        document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        return f"id={document_id}"
    return document.filename


def _collect_weighted_rag_chunks(
    inventory: InventoryService,
    query: str,
    main_subject_id: int,
    related_subject_ids: List[int],
    document_id: Optional[int],
) -> List[Dict[str, Any]]:
    weighted: List[tuple[int, Dict[str, Any]]] = []

    main_chunks = inventory.query_chunks(
        query,
        subject_ids=[main_subject_id],
        document_ids=None,
        limit=6,
    )
    for chunk in main_chunks:
        weighted.append((100, chunk))

    for subject_id in related_subject_ids[:3]:
        related_chunks = inventory.query_chunks(
            query,
            subject_ids=[subject_id],
            document_ids=None,
            limit=3,
        )
        for chunk in related_chunks:
            weighted.append((70, chunk))

    if document_id:
        document_chunks = inventory.query_chunks(
            query,
            subject_ids=None,
            document_ids=[document_id],
            limit=4,
        )
        for chunk in document_chunks:
            weighted.append((60, chunk))

    weighted.sort(key=lambda item: item[0], reverse=True)
    deduped: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    for _weight, chunk in weighted:
        key = str(chunk.get("id") or "")
        if not key or key in seen_ids:
            continue
        seen_ids.add(key)
        deduped.append(chunk)
        if len(deduped) >= 8:
            break
    return deduped


def _build_rag_context(data: AssignmentCreate) -> str:
    query = " ".join(
        [part for part in [data.title, data.topic, data.description or ""] if part]
    ).strip()
    if not query:
        return ""
    main_subject_id = data.main_subject_id
    related_subject_ids = [sid for sid in (data.related_subject_ids or []) if sid != main_subject_id]
    inventory = InventoryService(get_settings())
    chunks = _collect_weighted_rag_chunks(
        inventory,
        query,
        main_subject_id=main_subject_id,
        related_subject_ids=related_subject_ids,
        document_id=data.document_id,
    )
    if not chunks:
        return ""
    lines: List[str] = []
    for chunk in chunks[:6]:
        snippet = _summarize_text(chunk.get("text", ""))
        meta_parts: List[str] = []
        if chunk.get("subject_name"):
            meta_parts.append(f"subject={chunk['subject_name']}")
        elif chunk.get("subject_id") is not None:
            meta_parts.append(f"subject_id={chunk['subject_id']}")
        if chunk.get("page") is not None:
            meta_parts.append(f"page={chunk['page']}")
        meta = " ".join(meta_parts)
        meta = f" {meta}" if meta else ""
        lines.append(f"[chunk_id={chunk.get('id','')}{meta}] {snippet}")
    return "\n".join(lines)


def _default_objectives(data: AssignmentCreate) -> Dict[str, str]:
    if data.assignment_type == AssignmentType.PRACTICAL:
        return {
            "knowledge": f"理解与{data.topic}相关的核心概念与实践知识。",
            "process": "通过实践体验、过程记录与成果表达完成任务。",
            "emotion": "培养参与意识、责任感与服务社会的态度。",
        }
    if data.assignment_type == AssignmentType.PROJECT:
        return {
            "knowledge": f"掌握与{data.topic}相关的跨学科知识与应用方法。",
            "process": "经历项目规划、协作实施与迭代改进的完整过程。",
            "emotion": "培养合作意识、创新精神与社会责任感。",
        }
    return {
        "knowledge": f"理解与{data.topic}相关的核心概念与学科知识。",
        "process": "通过资料检索、调查分析与合作探究完成任务。",
        "emotion": "培养科学探究精神与协作意识。",
    }


def _default_rubric(assignment_type: AssignmentType) -> Dict[str, Any]:
    level_template = {
        "excellent": "表现突出，达到并超出要求。",
        "good": "达到要求，表现良好。",
        "pass": "基本达到要求。",
        "improve": "未达要求，需要改进。",
    }
    if assignment_type == AssignmentType.PRACTICAL:
        return {
            "dimensions": [
                {"name": "实践准备", "levels": level_template},
                {"name": "实践参与", "levels": level_template},
                {"name": "过程记录", "levels": level_template},
                {"name": "跨学科运用", "levels": level_template},
                {"name": "成果表达", "levels": level_template},
                {"name": "反思能力", "levels": level_template},
            ]
        }
    if assignment_type == AssignmentType.PROJECT:
        return {
            "dimensions": [
                {"name": "问题分析", "levels": level_template},
                {"name": "规划协作", "levels": level_template},
                {"name": "迭代改进", "levels": level_template},
                {"name": "成果质量", "levels": level_template},
                {"name": "展示汇报", "levels": level_template},
                {"name": "复盘反思", "levels": level_template},
            ]
        }
    return {
        "dimensions": [
            {"name": "问题意识", "levels": level_template},
            {"name": "方案设计", "levels": level_template},
            {"name": "探究过程", "levels": level_template},
            {"name": "结论质量", "levels": level_template},
            {"name": "反思能力", "levels": level_template},
        ]
    }


def _build_generation_meta(
    prompt_spec: Any,
    source: Literal["ai", "fallback", "manual_merge"],
    used_rag: bool = False,
    fallback_reason: str = "none",
) -> Dict[str, Any]:
    return {
        "source": source,
        "prompt_id": getattr(prompt_spec, "prompt_id", "unknown"),
        "prompt_version": getattr(prompt_spec, "version", "unknown"),
        "used_rag": used_rag,
        "fallback_reason": fallback_reason,
    }


def _classify_fallback_reason(error: Exception) -> str:
    lowered = f"{type(error).__name__}: {error}".lower()
    if "timeout" in lowered or "timed out" in lowered:
        return "timeout"
    if "json" in lowered or "parse" in lowered or "decode" in lowered:
        return "parse_error"
    return "request_error"


_FORMULAIC_PROCESS_PATTERNS = (
    "你将作为",
    "本次任务不是纸面练习",
    "请把自己代入任务角色",
)


def _looks_formulaic_objectives(objectives: Dict[str, Any]) -> bool:
    process_text = str((objectives or {}).get("process") or "")
    if not process_text:
        return False
    return any(pattern in process_text for pattern in _FORMULAIC_PROCESS_PATTERNS)


def _generate_ai_content_with_meta(
    data: AssignmentCreate,
) -> tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    settings = get_settings()
    client = DeepSeekJSONClient(settings)
    _log_ai_debug(
        "generate_called "
        f"prompt={ASSIGNMENT_PREVIEW_PROMPT.log_label()} "
        f"target={ASSIGNMENT_PREVIEW_PROMPT.target_api}"
    )
    template_phases = _get_template_phases(data)
    default_objectives = _default_objectives(data)
    default_rubric = _default_rubric(data.assignment_type)

    if not client.is_available:
        return (
            default_objectives,
            template_phases,
            default_rubric,
            _build_generation_meta(
                ASSIGNMENT_PREVIEW_PROMPT,
                source="fallback",
                fallback_reason="provider_unavailable",
            ),
        )

    type_map = {
        AssignmentType.PRACTICAL: "实践性作业",
        AssignmentType.INQUIRY: "探究性作业",
        AssignmentType.PROJECT: "项目式作业",
    }
    stage_map = {
        SchoolStage.PRIMARY: "小学",
        SchoolStage.MIDDLE: "初中",
    }
    depth_map = {
        InquiryDepth.BASIC: "基础",
        InquiryDepth.INTERMEDIATE: "中等",
        InquiryDepth.DEEP: "深度",
    }
    submission_map = {
        SubmissionMode.PHASED: "过程性提交",
        SubmissionMode.ONCE: "一次性提交",
        SubmissionMode.MIXED: "混合提交",
    }

    subtype_label = "无"
    if data.assignment_type == AssignmentType.PRACTICAL and data.practical_subtype:
        subtype_label = {
            PracticalSubType.VISIT: "参观考察",
            PracticalSubType.SIMULATION: "模拟表演",
            PracticalSubType.OBSERVATION: "观察体验",
        }.get(data.practical_subtype, data.practical_subtype.value)
    if data.assignment_type == AssignmentType.INQUIRY and data.inquiry_subtype:
        subtype_label = {
            InquirySubType.LITERATURE: "文献探究",
            InquirySubType.SURVEY: "调查探究",
            InquirySubType.EXPERIMENT: "实验探究",
        }.get(data.inquiry_subtype, data.inquiry_subtype.value)

    subject_ids = [data.main_subject_id] + [
        subject_id for subject_id in (data.related_subject_ids or []) if subject_id != data.main_subject_id
    ]
    subject_labels = _resolve_subject_names(subject_ids)
    main_subject_label = subject_labels[0] if subject_labels else f"id={data.main_subject_id}"
    related_subjects_label = ", ".join(subject_labels[1:]) if len(subject_labels) > 1 else "none"
    reference_document_label = _resolve_document_name(data.document_id)
    rag_context = _build_rag_context(data)
    used_rag = bool((rag_context or "").strip())

    type_guidance = {
        AssignmentType.PRACTICAL: "Emphasize authentic practice, process evidence, output artifacts, and reflection.",
        AssignmentType.INQUIRY: "Emphasize question-evidence-conclusion reasoning and reproducible inquiry process.",
        AssignmentType.PROJECT: "Emphasize real-world problem solving, collaboration, and iterative improvement.",
    }.get(data.assignment_type, "")

    subtype_guidance = ""
    if data.assignment_type == AssignmentType.PRACTICAL and data.practical_subtype:
        subtype_guidance = {
            PracticalSubType.VISIT: "Visit fieldwork: focus on observation targets and factual recording.",
            PracticalSubType.SIMULATION: "Simulation performance: focus on roles, scenario replay, and reflection notes.",
            PracticalSubType.OBSERVATION: "Observation experience: focus on continuous records and pattern analysis.",
        }.get(data.practical_subtype, "")
    elif data.assignment_type == AssignmentType.INQUIRY and data.inquiry_subtype:
        subtype_guidance = {
            InquirySubType.LITERATURE: "Literature inquiry: focus on search strategy, annotation, synthesis, and citations.",
            InquirySubType.SURVEY: "Survey inquiry: focus on instrument design, sampling notes, and statistics.",
            InquirySubType.EXPERIMENT: "Experiment inquiry: focus on variable control, repeated trials, and error analysis.",
        }.get(data.inquiry_subtype, "")

    depth_guidance = {
        InquiryDepth.BASIC: "Basic depth: provide explicit scaffolding and concrete checkpoints.",
        InquiryDepth.INTERMEDIATE: "Intermediate depth: provide framework plus key prompts with moderate openness.",
        InquiryDepth.DEEP: "Deep depth: provide goal-level guidance and emphasize quality criteria.",
    }.get(data.inquiry_depth, "Intermediate depth: provide framework plus key prompts.")

    template_json = json.dumps(template_phases, ensure_ascii=False, indent=2)
    prompt_context = AssignmentPreviewPromptContext(
        title=data.title,
        topic=data.topic,
        description=data.description or "none",
        school_stage=stage_map.get(data.school_stage, data.school_stage),
        grade=data.grade,
        assignment_type=type_map.get(data.assignment_type, data.assignment_type),
        subtype=subtype_label,
        main_subject=main_subject_label,
        related_subjects=related_subjects_label,
        reference_document=reference_document_label or "none",
        type_guidance=type_guidance or "none",
        subtype_guidance=subtype_guidance or "none",
        inquiry_depth=depth_map.get(data.inquiry_depth, data.inquiry_depth),
        submission_mode=submission_map.get(data.submission_mode, data.submission_mode),
        duration_weeks=data.duration_weeks,
        depth_guidance=depth_guidance,
        template_json=template_json,
        rag_context=rag_context,
    )
    system_prompt, user_prompt = build_assignment_preview_prompt(prompt_context)

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            raw_payload = client.predict_json(system_prompt, user_prompt)
            normalized = _normalize_ai_assignment_output(raw_payload)
            objectives = normalized.get("objectives") or default_objectives

            if _looks_formulaic_objectives(objectives):
                if attempt == 0:
                    _log_ai_debug("preview_formulaic_guard_hit retry=1")
                    continue
                raise ValueError("formulaic_guard_hit")

            ai_phases = normalized.get("phases") or []
            if _is_compact_story_phases(ai_phases):
                phases = _normalize_compact_story_phases(ai_phases)
            else:
                phases = _merge_phases(copy.deepcopy(template_phases), ai_phases)
            rubric = normalized.get("rubric") or {}
            if not rubric.get("dimensions"):
                rubric = default_rubric
            return (
                objectives,
                phases,
                rubric,
                _build_generation_meta(ASSIGNMENT_PREVIEW_PROMPT, source="ai", used_rag=used_rag),
            )
        except Exception as exc:
            last_error = exc
            _log_ai_generation_error(exc)
            if attempt == 0:
                _log_ai_debug(f"preview_retry_on_error reason={_classify_fallback_reason(exc)}")
                continue
            break

    fallback_reason = _classify_fallback_reason(last_error) if last_error else "request_error"
    if isinstance(last_error, ValueError) and str(last_error) == "formulaic_guard_hit":
        fallback_reason = "formulaic_guard_hit"
    return (
        default_objectives,
        template_phases,
        default_rubric,
        _build_generation_meta(
            ASSIGNMENT_PREVIEW_PROMPT,
            source="fallback",
            used_rag=used_rag,
            fallback_reason=fallback_reason,
        ),
    )


def _generate_ai_content(data: AssignmentCreate) -> tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    objectives, phases, rubric, _meta = _generate_ai_content_with_meta(data)
    return objectives, phases, rubric


def _generate_ai_content_from_lesson_plan_with_meta(
    data: AssignmentCreate,
    lesson_plan_text: str,
) -> tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    settings = get_settings()
    client = DeepSeekJSONClient(settings, temperature=0.1, max_output_tokens=2200, request_timeout=75)
    _log_ai_debug(
        "generate_from_lesson_plan_called "
        f"prompt={ASSIGNMENT_LESSON_PLAN_PROMPT.log_label()} "
        f"target={ASSIGNMENT_LESSON_PLAN_PROMPT.target_api}"
    )

    template_phases = _get_template_phases(data)
    default_objectives = _default_objectives(data)
    default_rubric = _default_rubric(data.assignment_type)
    if not client.is_available:
        return (
            default_objectives,
            template_phases,
            default_rubric,
            _build_generation_meta(
                ASSIGNMENT_LESSON_PLAN_PROMPT,
                source="fallback",
                fallback_reason="provider_unavailable",
            ),
        )

    subject_ids = [data.main_subject_id] + [
        subject_id for subject_id in (data.related_subject_ids or []) if subject_id != data.main_subject_id
    ]
    subject_labels = _resolve_subject_names(subject_ids)
    main_subject_label = subject_labels[0] if subject_labels else f"id={data.main_subject_id}"
    related_subjects_label = ", ".join(subject_labels[1:]) if len(subject_labels) > 1 else "none"

    lesson_plan_excerpt = _summarize_text(lesson_plan_text, max_length=2800)
    template_json = json.dumps(template_phases, ensure_ascii=False, indent=2)
    rag_context = _build_rag_context(data)
    used_rag = bool((rag_context or "").strip())

    prompt_context = LessonPlanPromptContext(
        title=data.title,
        topic=data.topic,
        school_stage=str(data.school_stage),
        grade=data.grade,
        assignment_type=str(data.assignment_type),
        inquiry_depth=str(data.inquiry_depth),
        submission_mode=str(data.submission_mode),
        duration_weeks=data.duration_weeks,
        main_subject=main_subject_label,
        related_subjects=related_subjects_label,
        lesson_plan_excerpt=lesson_plan_excerpt,
        template_json=template_json,
        rag_context=rag_context,
    )
    system_prompt, user_prompt = build_lesson_plan_prompt(prompt_context)

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            raw_payload = client.predict_json(system_prompt, user_prompt)
            normalized = _normalize_ai_assignment_output(raw_payload)
            objectives = normalized.get("objectives") or default_objectives

            if _looks_formulaic_objectives(objectives):
                if attempt == 0:
                    _log_ai_debug("lesson_plan_formulaic_guard_hit retry=1")
                    continue
                raise ValueError("formulaic_guard_hit")

            ai_phases = normalized.get("phases") or []
            if _is_compact_story_phases(ai_phases):
                phases = _normalize_compact_story_phases(ai_phases)
            else:
                phases = _merge_phases(copy.deepcopy(template_phases), ai_phases)
            rubric = normalized.get("rubric") or {}
            if not rubric.get("dimensions"):
                rubric = default_rubric
            return (
                objectives,
                phases,
                rubric,
                _build_generation_meta(ASSIGNMENT_LESSON_PLAN_PROMPT, source="ai", used_rag=used_rag),
            )
        except Exception as exc:
            last_error = exc
            _log_ai_generation_error(exc)
            if attempt == 0:
                _log_ai_debug(f"lesson_plan_retry_on_error reason={_classify_fallback_reason(exc)}")
                continue
            break

    fallback_reason = _classify_fallback_reason(last_error) if last_error else "request_error"
    if isinstance(last_error, ValueError) and str(last_error) == "formulaic_guard_hit":
        fallback_reason = "formulaic_guard_hit"
    return (
        default_objectives,
        template_phases,
        default_rubric,
        _build_generation_meta(
            ASSIGNMENT_LESSON_PLAN_PROMPT,
            source="fallback",
            used_rag=used_rag,
            fallback_reason=fallback_reason,
        ),
    )


def _generate_ai_content_from_lesson_plan(
    data: AssignmentCreate,
    lesson_plan_text: str,
) -> tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    objectives, phases, rubric, _meta = _generate_ai_content_from_lesson_plan_with_meta(data, lesson_plan_text)
    return objectives, phases, rubric


_ALLOWED_EVIDENCE_TYPES = {"text", "document", "image", "video", "confirm", "link"}


def _normalize_text_for_compare(text: str) -> str:
    if not text:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return re.sub(r"[\\s\\W_]+", "", text, flags=re.UNICODE)


def _clean_checkpoints(description: str, checkpoints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not checkpoints:
        return []
    norm_desc = _normalize_text_for_compare(description)
    seen: set[str] = set()
    cleaned: List[Dict[str, Any]] = []
    for cp in checkpoints:
        content = (cp.get("content") or "").strip()
        if not content:
            continue
        norm_content = _normalize_text_for_compare(content)
        if not norm_content:
            continue
        if norm_desc and (norm_content == norm_desc or norm_desc in norm_content or norm_content in norm_desc):
            continue
        if norm_content in seen:
            continue
        seen.add(norm_content)
        cleaned.append(cp)
    return cleaned


def _infer_evidence_type(text: str) -> str:
    if not text:
        return "text"
    if not isinstance(text, str):
        text = str(text)
    lowered = text.lower()
    if "http" in lowered or "www." in lowered or "链接" in text or "网址" in text:
        return "link"
    if any(keyword in text for keyword in ("视频", "录像", "录屏", "音频", "录音")):
        return "video"
    if any(keyword in text for keyword in ("图片", "照片", "图表", "截图", "海报", "插图", "流程图", "折线图", "柱状图")):
        return "image"
    if any(keyword in text for keyword in ("确认", "勾选", "完成", "已读", "签字")):
        return "confirm"
    if any(keyword in text for keyword in ("报告", "文档", "表格", "清单", "记录", "方案", "计划", "汇报", "笔记", "问卷", "档案", "日志", "摘要", "论文")):
        return "document"
    if any(keyword in lowered for keyword in ("ppt", "pdf", "doc", "docx", "xls", "xlsx")):
        return "document"
    return "text"


def _is_compact_story_phases(phases: List[Dict[str, Any]]) -> bool:
    if not isinstance(phases, list):
        return False
    if len(phases) < 3 or len(phases) > 4:
        return False
    for phase in phases:
        if not isinstance(phase, dict):
            return False
        steps = phase.get("steps")
        if not isinstance(steps, list) or not steps:
            return False
        if len(steps) > 2:
            return False
        for step in steps:
            if not isinstance(step, dict):
                return False
            if not (step.get("name") and step.get("description")):
                return False
            checkpoints = step.get("checkpoints")
            if not isinstance(checkpoints, list) or not checkpoints:
                return False
    return True


def _normalize_compact_story_phases(phases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for phase_index, phase in enumerate(phases, start=1):
        phase_name = str(phase.get("name") or phase.get("title") or f"阶段{phase_index}").strip()
        phase_title = str(phase.get("title") or phase_name).strip()

        raw_steps = phase.get("steps") or []
        if isinstance(raw_steps, dict):
            raw_steps = [raw_steps]
        step_list = [step for step in raw_steps if isinstance(step, dict)][:2]
        if not step_list:
            step_list = [{"name": "核心任务", "description": "请完成本阶段核心任务并提交证据。", "checkpoints": []}]

        steps: List[Dict[str, Any]] = []
        for step in step_list:
            step_name = str(step.get("name") or step.get("title") or "步骤").strip()
            description = str(step.get("description") or "").strip()
            content = str(step.get("content") or "").strip()

            checkpoints = step.get("checkpoints") or []
            if isinstance(checkpoints, dict):
                checkpoints = [checkpoints]
            if isinstance(checkpoints, str):
                checkpoints = [checkpoints]
            normalized_checkpoints: List[Dict[str, Any]] = []
            if isinstance(checkpoints, list):
                for cp in checkpoints[:2]:
                    if isinstance(cp, str):
                        cp_content = cp
                        cp_type = _infer_evidence_type(cp_content)
                    elif isinstance(cp, dict):
                        cp_content = (cp.get("content") or cp.get("text") or cp.get("description") or "").strip()
                        cp_type = cp.get("evidence_type")
                        if cp_type not in _ALLOWED_EVIDENCE_TYPES:
                            cp_type = _infer_evidence_type(cp_content)
                    else:
                        cp_content = str(cp)
                        cp_type = _infer_evidence_type(cp_content)
                    if cp_content:
                        normalized_checkpoints.append({"content": cp_content, "evidence_type": cp_type})

            if normalized_checkpoints:
                normalized_checkpoints = _clean_checkpoints(description, normalized_checkpoints)

            steps.append(
                {
                    "name": step_name,
                    "description": description,
                    "checkpoints": normalized_checkpoints,
                    **({"content": content} if content else {}),
                }
            )

        normalized.append(
            {
                "name": phase_name,
                "title": phase_title,
                "order": phase_index,
                "steps": steps,
            }
        )

    return normalized


def _merge_phases(
    template_phases: List[Dict[str, Any]],
    ai_phases: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not isinstance(template_phases, list):
        return template_phases
    if not ai_phases:
        return template_phases

    ai_phase_list = [phase for phase in ai_phases if isinstance(phase, dict)]
    if not ai_phase_list:
        return template_phases

    ai_by_order: Dict[int, Dict[str, Any]] = {}
    ai_by_name: Dict[str, Dict[str, Any]] = {}
    for phase in ai_phase_list:
        order_value = phase.get("order")
        if isinstance(order_value, int):
            ai_by_order[order_value] = phase
        name_value = phase.get("name")
        if isinstance(name_value, str) and name_value:
            ai_by_name[name_value] = phase

    for index, phase in enumerate(template_phases):
        if not isinstance(phase, dict):
            continue
        match = None
        order_value = phase.get("order")
        if isinstance(order_value, int) and order_value in ai_by_order:
            match = ai_by_order[order_value]
        else:
            name_value = phase.get("name")
            if isinstance(name_value, str) and name_value in ai_by_name:
                match = ai_by_name[name_value]
            elif index < len(ai_phase_list):
                match = ai_phase_list[index]
        if not match:
            continue

        phase_title = match.get("title")
        if phase_title:
            phase["title"] = phase_title

        template_steps = phase.get("steps") or []
        ai_steps = match.get("steps") or []
        if isinstance(ai_steps, dict):
            ai_steps = [ai_steps]
        ai_steps = [step for step in ai_steps if isinstance(step, dict)]
        ai_steps_by_name = {step.get("name"): step for step in ai_steps if step.get("name")}

        for step_index, step in enumerate(template_steps):
            if not isinstance(step, dict):
                continue
            ai_step = None
            step_name = step.get("name")
            if step_name and step_name in ai_steps_by_name:
                ai_step = ai_steps_by_name[step_name]
            elif step_index < len(ai_steps):
                ai_step = ai_steps[step_index]
            if not ai_step:
                continue

            description = ai_step.get("description")
            if description:
                step["description"] = description

            content = ai_step.get("content")
            if content:
                step["content"] = content

            ai_checkpoints = ai_step.get("checkpoints") or []
            if isinstance(ai_checkpoints, dict):
                ai_checkpoints = [ai_checkpoints]
            normalized_checkpoints: List[Dict[str, Any]] = []
            if isinstance(ai_checkpoints, list):
                for cp in ai_checkpoints:
                    if isinstance(cp, str):
                        content = cp
                        evidence_type = _infer_evidence_type(content or description)
                    elif isinstance(cp, dict):
                        content = cp.get("content") or cp.get("text") or cp.get("description") or ""
                        evidence_type = cp.get("evidence_type")
                        if evidence_type not in _ALLOWED_EVIDENCE_TYPES:
                            evidence_type = _infer_evidence_type(content or description)
                    else:
                        content = str(cp)
                        evidence_type = _infer_evidence_type(content or description)
                    normalized_checkpoints.append({"content": content, "evidence_type": evidence_type})
            if normalized_checkpoints:
                step["checkpoints"] = _clean_checkpoints(description or "", normalized_checkpoints)

        phase["steps"] = template_steps

    return template_phases


def _normalize_ai_assignment_output(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    objectives = payload.get("objectives") or {}
    if isinstance(objectives, list):
        objectives = {
            "knowledge": objectives[0] if len(objectives) > 0 else "",
            "process": objectives[1] if len(objectives) > 1 else "",
            "emotion": objectives[2] if len(objectives) > 2 else "",
        }
    elif isinstance(objectives, str):
        objectives = {"knowledge": objectives, "process": "", "emotion": ""}
    if not isinstance(objectives, dict):
        objectives = {}
    for key in ("knowledge", "process", "emotion"):
        objectives.setdefault(key, "")
    payload["objectives"] = objectives

    phases = payload.get("phases") or payload.get("phase") or []
    if isinstance(phases, dict):
        phases = [phases]
    if isinstance(phases, str):
        phases = [{"title": phases}]
    normalized_phases: List[Dict[str, Any]] = []
    for idx, phase in enumerate(phases, start=1):
        if isinstance(phase, str):
            phase = {"title": phase}
        if not isinstance(phase, dict):
            continue
        order_value = phase.get("order")
        try:
            order_value = int(order_value)
        except Exception:
            order_value = idx
        phase_title = phase.get("title")
        phase_name = phase.get("name") or phase_title or phase.get("phase") or f"阶段{idx}"
        steps = phase.get("steps") or phase.get("step") or phase.get("items") or []
        if isinstance(steps, dict):
            steps = [steps]
        if isinstance(steps, str):
            steps = [{"content": steps}]
        normalized_steps: List[Dict[str, Any]] = []
        for step in steps if isinstance(steps, list) else []:
            if isinstance(step, str):
                step = {"content": step}
            if not isinstance(step, dict):
                continue
            raw_content = step.get("content")
            description = step.get("description") or raw_content or step.get("detail") or ""
            step_name = step.get("name") or step.get("title") or step.get("label") or ""
            checkpoints = step.get("checkpoints")
            if checkpoints is None and "checkpoint" in step:
                checkpoints = step.get("checkpoint")
            if checkpoints is None and "outputs" in step:
                checkpoints = step.get("outputs")
            if isinstance(checkpoints, dict):
                checkpoints = [checkpoints]
            if isinstance(checkpoints, str):
                checkpoints = [checkpoints]
            normalized_checkpoints: List[Dict[str, Any]] = []
            if isinstance(checkpoints, list):
                for cp in checkpoints:
                    if isinstance(cp, str):
                        content = cp
                        evidence_type = _infer_evidence_type(content or description)
                    elif isinstance(cp, dict):
                        content = cp.get("content") or cp.get("text") or cp.get("description") or ""
                        evidence_type = cp.get("evidence_type")
                        if evidence_type not in _ALLOWED_EVIDENCE_TYPES:
                            evidence_type = _infer_evidence_type(content or description)
                    else:
                        content = str(cp)
                        evidence_type = _infer_evidence_type(content or description)
                    normalized_checkpoints.append({"content": content, "evidence_type": evidence_type})
            if not step_name:
                if description:
                    step_name = description[:12]
                elif normalized_checkpoints:
                    step_name = normalized_checkpoints[0]["content"][:12]
                else:
                    step_name = "步骤"
            if not description and normalized_checkpoints:
                description = normalized_checkpoints[0]["content"]
            normalized_step = {
                "name": step_name,
                "description": description,
                "checkpoints": normalized_checkpoints,
            }
            if raw_content:
                normalized_step["content"] = raw_content
            normalized_steps.append(normalized_step)
        normalized_phase = {
            "name": phase_name,
            "order": order_value,
            "steps": normalized_steps,
        }
        if phase_title:
            normalized_phase["title"] = phase_title
        normalized_phases.append(normalized_phase)
    payload["phases"] = normalized_phases

    rubric = payload.get("rubric") or {}
    if isinstance(rubric, list):
        rubric = {"dimensions": rubric}
    if not isinstance(rubric, dict):
        rubric = {}
    dimensions = rubric.get("dimensions") or rubric.get("criteria") or []
    if isinstance(dimensions, dict):
        dimensions = [{"name": name} for name in dimensions.keys()]
    normalized_dims: List[Dict[str, Any]] = []
    for dim in dimensions if isinstance(dimensions, list) else []:
        if isinstance(dim, str):
            normalized_dims.append({
                "name": dim,
                "levels": {
                    "excellent": "表现突出，达到并超出要求。",
                    "good": "达到要求，表现良好。",
                    "pass": "基本达到要求。",
                    "improve": "未达要求，需要改进。",
                },
            })
        elif isinstance(dim, dict):
            name = dim.get("name") or dim.get("criterion") or dim.get("dimension") or "维度"
            levels = dim.get("levels")
            if not isinstance(levels, dict):
                levels = {
                    "excellent": "表现突出，达到并超出要求。",
                    "good": "达到要求，表现良好。",
                    "pass": "基本达到要求。",
                    "improve": "未达要求，需要改进。",
                }
            normalized_dims.append({"name": name, "levels": levels})
    payload["rubric"] = {"dimensions": normalized_dims}
    return payload


def _log_ai_generation_error(error: Exception, payload: Dict[str, Any] | None = None) -> None:
    try:
        settings = get_settings()
        log_path = settings.ai_logs_dir / "ai_debug.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[assignments] {type(error).__name__}: {error}\n---\n")
            if payload is not None:
                handle.write(f"{payload}\n---\n")
    except Exception:
        pass


def _log_ai_debug(message: str) -> None:
    try:
        settings = get_settings()
        log_path = settings.ai_logs_dir / "ai_debug.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[debug] {message}\n---\n")
    except Exception:
        pass


def _build_background_setting(data: AssignmentCreate) -> str:
    stage_label = "小学" if data.school_stage == SchoolStage.PRIMARY else "初中"
    role_map = {
        AssignmentType.PRACTICAL: "校园实践小队",
        AssignmentType.INQUIRY: "校园研究小队",
        AssignmentType.PROJECT: "校园项目小队",
    }
    role = role_map.get(data.assignment_type, "学习小队")
    return (
        f"你将作为{stage_label}{data.grade}年级的{role}成员，"
        f"围绕“{data.topic}”进入真实学习情境。"
        f"本次任务不是纸面练习，而是一次面向真实对象的行动挑战："
        f"你需要在调查、分析与创作中逐步推进方案，让你的成果真正能被同学或老师看见并使用。"
    )


def _build_process_mainline(data: AssignmentCreate) -> str:
    if data.assignment_type == AssignmentType.PRACTICAL:
        return "行动主线：先完成真实场景观察与记录，再提炼关键发现并形成可展示成果，最后进行复盘反思。"
    if data.assignment_type == AssignmentType.INQUIRY:
        return "行动主线：围绕核心问题收集证据、进行分析论证并形成结论，再把发现转化为清晰表达与改进建议。"
    return "行动主线：围绕真实问题完成方案设计、阶段实施与迭代优化，最终提交可验证的成果并复盘经验。"


def _split_background_and_process(process_text: str) -> tuple[str, str]:
    raw = (process_text or "").strip()
    if not raw:
        return "", ""
    if not raw.startswith("背景设定：") and not raw.startswith("背景设定:"):
        return "", raw

    body = re.sub(r"^背景设定[:：]\s*", "", raw)
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if len(lines) >= 2:
        return lines[0], "\n".join(lines[1:]).strip()

    marker = "行动主线："
    if marker in body:
        prefix, suffix = body.split(marker, 1)
        return prefix.strip(), f"{marker}{suffix.strip()}"

    if len(body) > 160:
        split_idx = max(body.rfind("。", 0, 160), body.rfind("！", 0, 160), body.rfind("？", 0, 160))
        if split_idx >= 40:
            return body[: split_idx + 1].strip(), body[split_idx + 1 :].strip()

    return body.strip(), ""


def _ensure_background_setting(data: AssignmentCreate, objectives: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(objectives or {})
    for key in ("knowledge", "process", "emotion"):
        value = normalized.get(key)
        normalized[key] = value if isinstance(value, str) else ("" if value is None else str(value))

    process_text = (normalized.get("process") or "").strip()
    background, process_core = _split_background_and_process(process_text)

    if not background:
        background = _build_background_setting(data)
    elif len(background) < 90:
        extra_map = {
            AssignmentType.PRACTICAL: "你们将走进真实场地，与同伴协作完成观察、记录与表达，让学习成果真正贴近校园生活。",
            AssignmentType.INQUIRY: "你们将带着问题走进真实语境，通过证据收集与推理验证，形成有说服力的解释与结论。",
            AssignmentType.PROJECT: "你们将以团队方式推进阶段任务，把想法逐步落地为可展示、可验证、可改进的项目成果。",
        }
        extra = extra_map.get(data.assignment_type, "你们将通过真实任务推进，最终形成可展示的学习成果。")
        background = f"{background.rstrip('。') if background else background}。{extra}" if background else extra

    if len(background) < 120:
        background = (
            f"{background.rstrip('。')}。"
            "请把自己代入任务角色，在每个阶段都明确“为什么做、怎么做、做成什么样”，"
            "并让你的证据能真实反映行动过程与思考变化。"
        )

    if not process_core:
        process_core = _build_process_mainline(data)
    elif len(process_core) < 38:
        process_core = f"{process_core.rstrip('。')}。{_build_process_mainline(data)}"

    normalized["process"] = f"背景设定：{background}\n{process_core}".strip()
    return normalized


def _pick_story_phase_indices(total: int, target: int) -> List[int]:
    if target >= total:
        return list(range(total))
    if target <= 1:
        return [0]
    points: List[int] = []
    for i in range(target):
        idx = round(i * (total - 1) / (target - 1))
        points.append(int(idx))
    unique = sorted(set(points))
    while len(unique) < target:
        for idx in range(total):
            if idx not in unique:
                unique.append(idx)
            if len(unique) >= target:
                break
    return sorted(unique[:target])


def _normalize_storyline_phases(phases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    valid_phases = [phase for phase in phases if isinstance(phase, dict)]
    if not valid_phases:
        return phases

    target_phase_count = len(valid_phases)
    if target_phase_count > 4:
        target_phase_count = 4
    if target_phase_count < 3 and len(valid_phases) >= 3:
        target_phase_count = 3

    if len(valid_phases) > target_phase_count:
        picked_indices = _pick_story_phase_indices(len(valid_phases), target_phase_count)
        selected_phases = [valid_phases[idx] for idx in picked_indices]
    else:
        selected_phases = valid_phases

    normalized_phases: List[Dict[str, Any]] = []
    core_step_budget = 6
    core_step_count = 0

    for phase_index, phase in enumerate(selected_phases, start=1):
        phase_name = str(phase.get("name") or phase.get("title") or f"阶段{phase_index}").strip()
        phase_title = str(phase.get("title") or phase_name).strip()

        raw_steps = phase.get("steps")
        if isinstance(raw_steps, dict):
            raw_steps = [raw_steps]
        elif isinstance(raw_steps, str):
            raw_steps = [{"name": raw_steps, "description": raw_steps}]
        elif not isinstance(raw_steps, list):
            raw_steps = []

        step_list = [step for step in raw_steps if isinstance(step, dict)]
        if not step_list:
            step_list = [{"name": "核心任务", "description": "请完成本阶段核心任务并提交证据。", "checkpoints": []}]
        step_list = step_list[:2]

        normalized_steps: List[Dict[str, Any]] = []
        for step_index, step in enumerate(step_list, start=1):
            step_name = str(step.get("name") or step.get("title") or f"步骤{step_index}").strip()
            description = str(step.get("description") or step.get("content") or "").strip()
            if not description:
                description = f"请围绕“{phase_title}”完成“{step_name}”，并记录关键证据。"
            if not description.startswith("在这个情境中") and not description.startswith("（可选）在这个情境中"):
                description = f"在这个情境中，{description}"
            if len(description) < 88:
                description = (
                    f"{description} 先明确你要解决的具体问题，再根据阶段目标选择合适的方法推进；"
                    f"过程中请记录关键证据、同伴分工与判断依据，并在阶段结束时总结“本步发现了什么、下一步将如何调整”。"
                )

            is_core = step_index == 1 and core_step_count < core_step_budget
            if is_core:
                core_step_count += 1
            elif not description.startswith("（可选）"):
                description = f"（可选）{description}"

            content = str(step.get("content") or "").strip()
            if not content:
                content = f"情境推进：围绕“{phase_title}”，推进“{step_name}”。"
            elif len(content) < 42:
                content = f"情境推进：{content} 请把这一阶段的观察、判断与证据自然衔接到下一步行动，并说明你们为何这样选择。"

            checkpoints = step.get("checkpoints") or []
            if isinstance(checkpoints, dict):
                checkpoints = [checkpoints]
            if isinstance(checkpoints, str):
                checkpoints = [checkpoints]
            normalized_checkpoints: List[Dict[str, Any]] = []
            if isinstance(checkpoints, list):
                for cp in checkpoints[:2]:
                    if isinstance(cp, str):
                        cp_content = cp
                        cp_type = _infer_evidence_type(cp_content)
                    elif isinstance(cp, dict):
                        cp_content = (cp.get("content") or cp.get("text") or cp.get("description") or "").strip()
                        cp_type = cp.get("evidence_type")
                        if cp_type not in _ALLOWED_EVIDENCE_TYPES:
                            cp_type = _infer_evidence_type(cp_content)
                    else:
                        cp_content = str(cp)
                        cp_type = _infer_evidence_type(cp_content)
                    if cp_content:
                        normalized_checkpoints.append({"content": cp_content, "evidence_type": cp_type})
            if not normalized_checkpoints:
                normalized_checkpoints = [
                    {"content": "提交本阶段关键证据（文本或文档）", "evidence_type": "text"}
                ]

            normalized_steps.append(
                {
                    "name": step_name,
                    "description": description,
                    "content": content,
                    "checkpoints": _clean_checkpoints(description, normalized_checkpoints),
                }
            )

        normalized_phases.append(
            {
                "name": phase_name,
                "title": phase_title,
                "order": phase_index,
                "steps": normalized_steps,
            }
        )

    return normalized_phases


def _ensure_ai_defaults(
    data: AssignmentCreate,
    objectives: Dict[str, Any],
    phases: List[Dict[str, Any]],
    rubric: Dict[str, Any],
    enforce_storyline: bool = False,
) -> tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    if not objectives or not objectives.get("knowledge"):
        objectives = _default_objectives(data)
    if not phases:
        phases = _get_template_phases(data)
    if not rubric or not rubric.get("dimensions"):
        rubric = _default_rubric(data.assignment_type)

    if enforce_storyline:
        objectives = _ensure_background_setting(data, objectives)
        phases = _normalize_storyline_phases(phases)

    return objectives, phases, rubric


def _is_empty_json(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (dict, list)):
        return not value
    if isinstance(value, str):
        return value.strip() in ("{}", "[]", "")
    return False
