"""作业提交API。"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.contracts.submission import (
    SubmissionCreate,
    SubmissionAttachmentListResponse,
    SubmissionListResponse,
    SubmissionResponse,
    SubmissionUpdate,
    normalize_submission_text,
)
from app.config import get_settings
from app.db import get_db
from app.models import (
    Assignment,
    Evaluation,
    EvaluationType,
    ParsingStatus,
    ProjectGroup,
    Submission,
    SubmissionAttachmentAsset,
    SubmissionMode,
    SubmissionStatus,
    User,
)
from app.api.v2.auth import get_current_user, require_student
from app.services.submission_attachments import SubmissionAttachmentService

router = APIRouter()


def _attachment_service() -> SubmissionAttachmentService:
    return SubmissionAttachmentService(get_settings())


# === Helpers ===

def _normalize_status(value: Any) -> str:
    if isinstance(value, SubmissionStatus):
        return value.value
    if isinstance(value, str):
        return value.lower()
    return str(value)


def _extract_member_ids(members_json: Any) -> set[int]:
    member_ids: set[int] = set()
    if not isinstance(members_json, list):
        return member_ids

    for item in members_json:
        raw_user_id: Any
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


def _group_ids_for_student(
    db: Session,
    student_id: int,
    assignment_id: Optional[int] = None,
) -> List[int]:
    query = db.query(ProjectGroup)
    if assignment_id is not None:
        query = query.filter(ProjectGroup.assignment_id == assignment_id)

    groups = query.all()
    matched: List[int] = []
    for group in groups:
        if student_id in _extract_member_ids(group.members_json or []):
            matched.append(group.id)
    return matched


def _student_has_submission_access(db: Session, submission: Submission, student_id: int) -> bool:
    if submission.student_id == student_id:
        return True
    if not submission.group_id:
        return False
    group = db.query(ProjectGroup).filter(ProjectGroup.id == submission.group_id).first()
    if not group:
        return False
    return student_id in _extract_member_ids(group.members_json or [])


def _teacher_has_submission_access(db: Session, submission: Submission, teacher_id: int) -> bool:
    assignment = db.query(Assignment).filter(Assignment.id == submission.assignment_id).first()
    if not assignment:
        return False
    return assignment.created_by == teacher_id


def _user_can_access_submission(db: Session, submission: Submission, current_user: User) -> bool:
    from app.models.user import UserRole

    if current_user.role == UserRole.STUDENT:
        return _student_has_submission_access(db, submission, current_user.id)
    if current_user.role == UserRole.TEACHER:
        return _teacher_has_submission_access(db, submission, current_user.id)
    return False


def _validate_group_submission_target(
    db: Session,
    assignment_id: int,
    group_id: int,
    student_id: int,
) -> ProjectGroup:
    group = (
        db.query(ProjectGroup)
        .filter(
            ProjectGroup.id == group_id,
            ProjectGroup.assignment_id == assignment_id,
        )
        .first()
    )
    if not group:
        raise HTTPException(status_code=400, detail="目标小组不存在或不属于当前作业")

    member_ids = _extract_member_ids(group.members_json or [])
    if student_id not in member_ids:
        raise HTTPException(status_code=403, detail="你不在该作业小组中，不能以小组模式提交")

    return group


def _build_group_context_map(
    db: Session,
    group_ids: List[int],
) -> Dict[int, Dict[str, Any]]:
    if not group_ids:
        return {}

    groups = db.query(ProjectGroup).filter(ProjectGroup.id.in_(group_ids)).all()

    all_member_ids: set[int] = set()
    for group in groups:
        all_member_ids.update(_extract_member_ids(group.members_json or []))

    user_name_by_id: Dict[int, str] = {}
    if all_member_ids:
        users = db.query(User).filter(User.id.in_(list(all_member_ids))).all()
        user_name_by_id = {user.id: user.name for user in users}

    context: Dict[int, Dict[str, Any]] = {}
    for group in groups:
        members: List[Dict[str, Any]] = []
        raw_members = group.members_json or []
        if isinstance(raw_members, list):
            for item in raw_members:
                if isinstance(item, dict):
                    raw_user_id = (
                        item.get("user_id")
                        or item.get("student_id")
                        or item.get("id")
                    )
                    try:
                        if raw_user_id is None:
                            continue
                        user_id = int(str(raw_user_id))
                    except Exception:
                        continue
                    if user_id <= 0:
                        continue
                    members.append(
                        {
                            "user_id": user_id,
                            "name": item.get("name") or user_name_by_id.get(user_id) or "",
                            "role": item.get("role") or "",
                        }
                    )
                else:
                    try:
                        user_id = int(item)
                    except Exception:
                        continue
                    if user_id <= 0:
                        continue
                    members.append(
                        {
                            "user_id": user_id,
                            "name": user_name_by_id.get(user_id) or "",
                            "role": "",
                        }
                    )

        context[group.id] = {
            "group_name": group.name,
            "group_members": members,
        }

    return context


def _build_teacher_evaluated_at_map(
    db: Session,
    submission_ids: List[int],
) -> Dict[int, datetime]:
    if not submission_ids:
        return {}

    evaluations = (
        db.query(Evaluation)
        .filter(
            Evaluation.submission_id.in_(submission_ids),
            Evaluation.evaluation_type == EvaluationType.TEACHER,
        )
        .order_by(Evaluation.submission_id.asc(), Evaluation.created_at.desc())
        .all()
    )

    latest_map: Dict[int, datetime] = {}
    for item in evaluations:
        if item.submission_id in latest_map:
            continue
        latest_map[item.submission_id] = item.created_at
    return latest_map


def _attachment_download_url(submission_id: int, attachment_id: int) -> str:
    return f"/api/v2/submissions/{submission_id}/attachments/{attachment_id}/download"


def _project_link_attachment(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "filename": item.get("filename") or "",
        "url": item.get("url") or "",
        "type": item.get("type") or "link",
        "size_bytes": item.get("size_bytes"),
        "source": "link",
        "parsing_status": ParsingStatus.READY.value,
        "mime_type": item.get("mime_type"),
        "error_msg": item.get("error_msg"),
        "summary_text": item.get("summary_text"),
    }


def _project_uploaded_attachment(asset: SubmissionAttachmentAsset) -> Dict[str, Any]:
    suffix = Path(asset.original_filename).suffix.lower().lstrip(".")
    analysis = asset.analysis
    return {
        "filename": asset.original_filename,
        "url": _attachment_download_url(asset.submission_id, asset.id),
        "type": suffix or "file",
        "size_bytes": asset.size_bytes,
        "attachment_id": asset.id,
        "source": "upload",
        "parsing_status": asset.parsing_status.value,
        "mime_type": asset.mime_type,
        "error_msg": analysis.error_msg if analysis else None,
        "summary_text": analysis.summary_text if analysis else None,
    }


def _build_attachment_context_map(
    db: Session,
    submission_ids: List[int],
) -> Dict[int, List[Dict[str, Any]]]:
    if not submission_ids:
        return {}

    assets = (
        db.query(SubmissionAttachmentAsset)
        .options(joinedload(SubmissionAttachmentAsset.analysis))
        .filter(SubmissionAttachmentAsset.submission_id.in_(submission_ids))
        .order_by(SubmissionAttachmentAsset.created_at.asc())
        .all()
    )
    context: Dict[int, List[Dict[str, Any]]] = {}
    for asset in assets:
        context.setdefault(asset.submission_id, []).append(_project_uploaded_attachment(asset))
    return context


def _validate_uploaded_attachments_ready(db: Session, submission_id: int) -> None:
    assets = (
        db.query(SubmissionAttachmentAsset)
        .filter(SubmissionAttachmentAsset.submission_id == submission_id)
        .all()
    )
    pending = [asset for asset in assets if asset.parsing_status != ParsingStatus.READY]
    if not pending:
        return

    failed = next((asset for asset in pending if asset.parsing_status == ParsingStatus.FAILED), pending[0])
    raise HTTPException(
        status_code=400,
        detail=f"附件「{failed.original_filename}」尚未就绪，请先处理为 ready 后再正式提交",
    )


def _has_uploaded_attachments(db: Session, submission_id: int) -> bool:
    return (
        db.query(SubmissionAttachmentAsset.id)
        .filter(SubmissionAttachmentAsset.submission_id == submission_id)
        .first()
        is not None
    )


def _serialize_submission(
    submission: Submission,
    group_context: Optional[Dict[str, Any]] = None,
    teacher_evaluated_at: Optional[datetime] = None,
    projected_attachments: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    link_attachments = [_project_link_attachment(item) for item in (submission.attachments_json or [])]
    payload = {
        "id": submission.id,
        "assignment_id": submission.assignment_id,
        "student_id": submission.student_id,
        "group_id": submission.group_id,
        "group_name": None,
        "group_members": [],
        "phase_index": submission.phase_index,
        "step_index": submission.step_index,
        "status": _normalize_status(submission.status),
        "content_json": submission.content_json or {},
        "attachments_json": link_attachments + (projected_attachments or []),
        "checkpoints_json": submission.checkpoints_json or {},
        "created_at": submission.created_at,
        "submitted_at": submission.submitted_at,
        "teacher_evaluated_at": teacher_evaluated_at,
    }
    if group_context:
        payload["group_name"] = group_context.get("group_name")
        payload["group_members"] = group_context.get("group_members") or []
    return payload


def _validate_submission_indices(
    assignment: Assignment,
    phase_index: int,
    step_index: Optional[int],
) -> None:
    phases = assignment.phases_json or []
    if phase_index < 0 or phase_index >= len(phases):
        raise HTTPException(status_code=400, detail="phase_index 超出作业阶段范围")

    if step_index is None:
        return

    current_phase = phases[phase_index] if phase_index < len(phases) else {}
    steps = current_phase.get("steps") if isinstance(current_phase, dict) else None
    steps = steps if isinstance(steps, list) else []
    if step_index < 0 or step_index >= len(steps):
        raise HTTPException(status_code=400, detail="step_index 超出当前阶段步骤范围")


def _allowed_checkpoint_keys(assignment: Assignment) -> set[str]:
    allowed: set[str] = set()
    for phase in assignment.phases_json or []:
        if not isinstance(phase, dict):
            continue
        steps = phase.get("steps") or []
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            checkpoints = step.get("checkpoints") or []
            if isinstance(checkpoints, dict):
                checkpoints = [checkpoints]
            if not isinstance(checkpoints, list):
                continue
            for checkpoint in checkpoints:
                if not isinstance(checkpoint, dict):
                    continue
                content = checkpoint.get("content")
                if isinstance(content, str) and content.strip():
                    allowed.add(content.strip())
    return allowed


def _validate_checkpoint_payload(assignment: Assignment, checkpoints_json: Dict[str, bool]) -> None:
    if not checkpoints_json:
        return
    allowed = _allowed_checkpoint_keys(assignment)
    unknown = [key for key in checkpoints_json.keys() if key not in allowed]
    if unknown:
        raise HTTPException(status_code=400, detail="checkpoints_json 包含未定义的 checkpoint")


def _has_submission_evidence(
    content_json: Dict[str, Any] | None,
    attachments_json: List[Dict[str, Any]] | None,
    checkpoints_json: Dict[str, bool] | None,
) -> bool:
    if normalize_submission_text(content_json):
        return True
    if attachments_json:
        return True
    if checkpoints_json and any(bool(value) for value in checkpoints_json.values()):
        return True
    return False


def _get_submission_or_404(db: Session, submission_id: int) -> Submission:
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="提交不存在")
    return submission


def _get_attachment_or_404(db: Session, submission_id: int, attachment_id: int) -> SubmissionAttachmentAsset:
    asset = _attachment_service().get_for_submission(db, submission_id, attachment_id)
    if not asset:
        raise HTTPException(status_code=404, detail="附件不存在")
    return asset


def _is_past_deadline(deadline: datetime | None) -> bool:
    if deadline is None:
        return False
    normalized_deadline = deadline if deadline.tzinfo is not None else deadline.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > normalized_deadline


def _get_editable_submission(
    db: Session,
    submission_id: int,
    student_id: int,
    *,
    draft_only_detail: str | None = None,
) -> tuple[Submission, Assignment | None]:
    submission = _get_submission_or_404(db, submission_id)
    if not _student_has_submission_access(db, submission, student_id):
        raise HTTPException(status_code=403, detail="只能修改自己或所在小组的提交")
    if draft_only_detail is not None:
        if submission.status != SubmissionStatus.DRAFT:
            raise HTTPException(status_code=400, detail=draft_only_detail)
    elif submission.status == SubmissionStatus.GRADED:
        raise HTTPException(status_code=400, detail="已评分的提交不能修改")

    assignment = db.query(Assignment).filter(Assignment.id == submission.assignment_id).first()
    if assignment is not None and _is_past_deadline(assignment.deadline):
        raise HTTPException(status_code=400, detail="已过截止时间，不能修改")

    return submission, assignment


# === API 端点 ===

@router.post("/{submission_id}/attachments/upload")
async def upload_submission_attachment(
    submission_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    submission, _assignment = _get_editable_submission(
        db,
        submission_id,
        current_user.id,
        draft_only_detail="只能在草稿状态上传附件",
    )

    asset = await _attachment_service().handle_upload(db, submission, file, current_user.id)
    asset = _get_attachment_or_404(db, submission.id, asset.id)
    return _project_uploaded_attachment(asset)


@router.get("/{submission_id}/attachments", response_model=SubmissionAttachmentListResponse)
async def list_submission_attachments(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submission = _get_submission_or_404(db, submission_id)
    if not _user_can_access_submission(db, submission, current_user):
        raise HTTPException(status_code=403, detail="无权查看该提交附件")

    assets = _attachment_service().list_for_submission(db, submission_id)
    projected = [_project_uploaded_attachment(asset) for asset in assets]
    return {"attachments": projected, "total": len(projected)}


@router.get("/{submission_id}/attachments/{attachment_id}/download")
async def download_submission_attachment(
    submission_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submission = _get_submission_or_404(db, submission_id)
    if not _user_can_access_submission(db, submission, current_user):
        raise HTTPException(status_code=403, detail="无权下载该附件")
    asset = _get_attachment_or_404(db, submission_id, attachment_id)
    path = Path(asset.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="附件文件不存在")
    return FileResponse(path, media_type=asset.mime_type or "application/octet-stream", filename=asset.original_filename)


@router.delete("/{submission_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_submission_attachment(
    submission_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    submission = _get_submission_or_404(db, submission_id)
    if not _student_has_submission_access(db, submission, current_user.id):
        raise HTTPException(status_code=403, detail="只能修改自己或所在小组的提交")
    if submission.status != SubmissionStatus.DRAFT:
        raise HTTPException(status_code=400, detail="只能删除草稿状态的附件")
    asset = _get_attachment_or_404(db, submission_id, attachment_id)
    assignment = db.query(Assignment).filter(Assignment.id == submission.assignment_id).first()
    if assignment is not None and _is_past_deadline(assignment.deadline):
        if asset.parsing_status == ParsingStatus.READY:
            raise HTTPException(status_code=400, detail="已过截止时间，不能修改")
    _attachment_service().delete(db, asset)

@router.post("/", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
async def create_submission(
    data: SubmissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student)
):
    """创建新提交（学生权限）。"""
    # 验证作业存在
    assignment = db.query(Assignment).filter(Assignment.id == data.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    if not assignment.is_published:
        raise HTTPException(status_code=400, detail="作业尚未发布")
    _validate_submission_indices(assignment, data.phase_index, data.step_index)
    _validate_checkpoint_payload(assignment, data.checkpoints_json or {})

    group_context: Optional[Dict[str, Any]] = None
    if data.group_id is not None:
        group = _validate_group_submission_target(
            db,
            assignment_id=data.assignment_id,
            group_id=data.group_id,
            student_id=current_user.id,
        )
        group_context = {
            "group_name": group.name,
            "group_members": _build_group_context_map(db, [group.id]).get(group.id, {}).get("group_members", []),
        }

        existing_group_submission = (
            db.query(Submission)
            .filter(
                Submission.assignment_id == data.assignment_id,
                Submission.group_id == data.group_id,
                Submission.phase_index == data.phase_index,
            )
            .order_by(Submission.created_at.desc())
            .first()
        )
        if existing_group_submission:
            evaluated_at_map = _build_teacher_evaluated_at_map(db, [existing_group_submission.id])
            attachment_context_map = _build_attachment_context_map(db, [existing_group_submission.id])
            return _serialize_submission(
                existing_group_submission,
                group_context,
                teacher_evaluated_at=evaluated_at_map.get(existing_group_submission.id),
                projected_attachments=attachment_context_map.get(existing_group_submission.id),
            )
    
    submission = Submission(
        assignment_id=data.assignment_id,
        student_id=current_user.id,
        group_id=data.group_id,
        phase_index=data.phase_index,
        step_index=data.step_index,
        content_json=data.content_json,
        attachments_json=data.attachments_payload(),
        checkpoints_json=data.checkpoints_json,
        status=SubmissionStatus.DRAFT,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    if submission.group_id and group_context is None:
        group_context = _build_group_context_map(db, [submission.group_id]).get(submission.group_id)
    evaluated_at_map = _build_teacher_evaluated_at_map(db, [submission.id])
    attachment_context_map = _build_attachment_context_map(db, [submission.id])
    return _serialize_submission(
        submission,
        group_context,
        teacher_evaluated_at=evaluated_at_map.get(submission.id),
        projected_attachments=attachment_context_map.get(submission.id),
    )


@router.get("/my", response_model=SubmissionListResponse)
async def list_my_submissions(
    assignment_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student)
):
    """学生查看自己的提交历史。"""
    query = db.query(Submission).options(joinedload(Submission.assignment))

    group_ids = _group_ids_for_student(db, current_user.id, assignment_id)
    if group_ids:
        query = query.filter(
            or_(
                Submission.student_id == current_user.id,
                Submission.group_id.in_(group_ids),
            )
        )
    else:
        query = query.filter(Submission.student_id == current_user.id)

    if assignment_id:
        query = query.filter(Submission.assignment_id == assignment_id)

    submissions = query.order_by(Submission.created_at.desc()).all()

    dedup_submissions: List[Submission] = []
    seen_ids: set[int] = set()
    for item in submissions:
        if item.id in seen_ids:
            continue
        seen_ids.add(item.id)
        dedup_submissions.append(item)

    group_context_map = _build_group_context_map(
        db,
        [item.group_id for item in dedup_submissions if item.group_id is not None],
    )
    evaluated_at_map = _build_teacher_evaluated_at_map(db, [item.id for item in dedup_submissions])
    attachment_context_map = _build_attachment_context_map(db, [item.id for item in dedup_submissions])

    # 手动构造响应以包含嵌套的 assignment 信息
    result = []
    for sub in dedup_submissions:
        group_context = group_context_map.get(sub.group_id) if sub.group_id else None
        sub_dict = {
            **_serialize_submission(
                sub,
                group_context,
                teacher_evaluated_at=evaluated_at_map.get(sub.id),
                projected_attachments=attachment_context_map.get(sub.id),
            ),
            "assignment": {
                "id": sub.assignment.id,
                "title": sub.assignment.title,
                "topic": sub.assignment.topic,
                "description": sub.assignment.description,
                "assignment_type": sub.assignment.assignment_type.value,
                "phases_json": sub.assignment.phases_json or [],
            } if sub.assignment else None
        }
        result.append(sub_dict)

    return {"submissions": result, "total": len(result)}


@router.get("/{submission_id}", response_model=SubmissionResponse)
async def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get submission detail."""
    submission = _get_submission_or_404(db, submission_id)
    if not _user_can_access_submission(db, submission, current_user):
        raise HTTPException(status_code=403, detail="无权查看该提交")

    assignment = db.query(Assignment).filter(Assignment.id == submission.assignment_id).first()
    group_context = None
    if submission.group_id:
        group_context = _build_group_context_map(db, [submission.group_id]).get(submission.group_id)
    evaluated_at_map = _build_teacher_evaluated_at_map(db, [submission.id])
    attachment_context_map = _build_attachment_context_map(db, [submission.id])

    return {
        **_serialize_submission(
            submission,
            group_context,
            teacher_evaluated_at=evaluated_at_map.get(submission.id),
            projected_attachments=attachment_context_map.get(submission.id),
        ),
        "assignment": {
            "id": assignment.id,
            "title": assignment.title,
            "topic": assignment.topic,
            "description": assignment.description,
            "assignment_type": assignment.assignment_type.value,
            "phases_json": assignment.phases_json or [],
        } if assignment else None,
    }

@router.put("/{submission_id}", response_model=SubmissionResponse)
async def update_submission(
    submission_id: int,
    data: SubmissionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student)
):
    """更新提交（截止前）。"""
    submission, assignment = _get_editable_submission(db, submission_id, current_user.id)

    if assignment is not None:
        _validate_submission_indices(assignment, submission.phase_index, submission.step_index)
    
    update_data = data.model_dump(exclude_unset=True)
    if "attachments_json" in update_data:
        update_data["attachments_json"] = data.attachments_payload()
    next_checkpoints = update_data.get("checkpoints_json")
    if assignment is not None and isinstance(next_checkpoints, dict):
        _validate_checkpoint_payload(assignment, next_checkpoints)
    for key, value in update_data.items():
        setattr(submission, key, value)
    
    db.commit()
    db.refresh(submission)
    group_context = None
    if submission.group_id:
        group_context = _build_group_context_map(db, [submission.group_id]).get(submission.group_id)
    evaluated_at_map = _build_teacher_evaluated_at_map(db, [submission.id])
    attachment_context_map = _build_attachment_context_map(db, [submission.id])
    return _serialize_submission(
        submission,
        group_context,
        teacher_evaluated_at=evaluated_at_map.get(submission.id),
        projected_attachments=attachment_context_map.get(submission.id),
    )


@router.post("/{submission_id}/submit", response_model=SubmissionResponse)
async def submit_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student)
):
    """正式提交（从草稿变为已提交）。"""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="提交不存在")
    if not _student_has_submission_access(db, submission, current_user.id):
        raise HTTPException(status_code=403, detail="只能提交自己或所在小组的草稿")

    assignment = db.query(Assignment).filter(Assignment.id == submission.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    _validate_submission_indices(assignment, submission.phase_index, submission.step_index)
    _validate_checkpoint_payload(assignment, submission.checkpoints_json or {})
    _validate_uploaded_attachments_ready(db, submission.id)
    has_evidence = _has_submission_evidence(
        submission.content_json or {},
        submission.attachments_json or [],
        submission.checkpoints_json or {},
    ) or _has_uploaded_attachments(db, submission.id)
    if not has_evidence:
        raise HTTPException(status_code=400, detail="正式提交前至少需要一项证据（文本、附件或检查点）")
    
    submission.status = SubmissionStatus.SUBMITTED
    submission.submitted_at = datetime.now(timezone.utc)
    next_submission_id: Optional[int] = None
    if assignment and assignment.submission_mode != SubmissionMode.ONCE:
        phases = assignment.phases_json or []
        next_phase_index = submission.phase_index + 1
        if next_phase_index < len(phases):
            if submission.group_id is not None:
                existing = (
                    db.query(Submission)
                    .filter(
                        Submission.assignment_id == submission.assignment_id,
                        Submission.group_id == submission.group_id,
                        Submission.phase_index == next_phase_index,
                    )
                    .first()
                )
            else:
                existing = (
                    db.query(Submission)
                    .filter(
                        Submission.assignment_id == submission.assignment_id,
                        Submission.student_id == submission.student_id,
                        Submission.phase_index == next_phase_index,
                    )
                    .first()
                )
            if existing:
                next_submission_id = existing.id
            else:
                next_submission = Submission(
                    assignment_id=submission.assignment_id,
                    student_id=submission.student_id,
                    group_id=submission.group_id,
                    phase_index=next_phase_index,
                    content_json={},
                    attachments_json=[],
                    checkpoints_json={},
                    status=SubmissionStatus.DRAFT,
                )
                db.add(next_submission)
                db.flush()
                next_submission_id = next_submission.id

    db.commit()
    db.refresh(submission)
    group_context = None
    if submission.group_id:
        group_context = _build_group_context_map(db, [submission.group_id]).get(submission.group_id)
    evaluated_at_map = _build_teacher_evaluated_at_map(db, [submission.id])
    attachment_context_map = _build_attachment_context_map(db, [submission.id])
    payload = _serialize_submission(
        submission,
        group_context,
        teacher_evaluated_at=evaluated_at_map.get(submission.id),
        projected_attachments=attachment_context_map.get(submission.id),
    )
    payload["next_submission_id"] = next_submission_id
    return payload


@router.delete("/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student)
):
    """删除草稿提交。"""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="提交不存在")
    if not _student_has_submission_access(db, submission, current_user.id):
        raise HTTPException(status_code=403, detail="只能删除自己或所在小组的提交")
    if submission.status != SubmissionStatus.DRAFT:
        raise HTTPException(status_code=400, detail="只能删除草稿状态的提交")

    _attachment_service().delete_for_submission(db, submission.id)
    db.delete(submission)
    db.commit()


# === 教师端 ===

@router.get("/assignment/{assignment_id}", response_model=SubmissionListResponse)
async def list_assignment_submissions(
    assignment_id: int,
    phase_index: Optional[int] = None,
    group_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """教师查看作业的所有提交。"""
    from app.models.user import UserRole
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="需要教师权限")

    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    if assignment.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="只能查看自己创建的作业提交")
    
    query = db.query(Submission).filter(Submission.assignment_id == assignment_id)
    
    if phase_index is not None:
        query = query.filter(Submission.phase_index == phase_index)

    if group_id is not None:
        query = query.filter(Submission.group_id == group_id)
    
    submissions = query.order_by(Submission.submitted_at.desc()).all()
    group_context_map = _build_group_context_map(
        db,
        [item.group_id for item in submissions if item.group_id is not None],
    )
    evaluated_at_map = _build_teacher_evaluated_at_map(db, [item.id for item in submissions])
    attachment_context_map = _build_attachment_context_map(db, [item.id for item in submissions])
    result = [
        _serialize_submission(
            item,
            group_context_map.get(item.group_id) if item.group_id else None,
            teacher_evaluated_at=evaluated_at_map.get(item.id),
            projected_attachments=attachment_context_map.get(item.id),
        )
        for item in submissions
    ]
    return {"submissions": result, "total": len(result)}
