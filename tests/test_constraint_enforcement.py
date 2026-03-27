from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest
from sqlalchemy.orm import Session

from app.api.v2.auth import create_token, hash_password
from app.config import Settings
from app.models import (
    Assignment,
    AssignmentType,
    InquiryDepth,
    InquirySubType,
    SchoolStage,
    Submission,
    SubmissionMode,
    SubmissionStatus,
    Subject,
    User,
    UserRole,
)


def _headers(user_id: int, role: str) -> dict[str, str]:
    token = create_token(user_id, role)
    return {"Authorization": f"Bearer {token}"}


def _create_subject(session: Session, *, code: str, name: str) -> Subject:
    subject = Subject(
        code=code,
        name=name,
        category="test",
        primary_available=True,
        middle_available=True,
        core_competencies=[],
        cross_disciplinary_concepts=[],
    )
    session.add(subject)
    session.commit()
    session.refresh(subject)
    return subject


def _create_user(session: Session, *, username: str, role: UserRole, grade: int | None = None) -> User:
    user = User(
        username=username,
        password_hash=hash_password("Passw0rd123"),
        role=role,
        name=username,
        grade=grade,
        class_name="1班" if role == UserRole.STUDENT else None,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _create_assignment(
    session: Session,
    *,
    teacher_id: int,
    main_subject_id: int,
    published: bool = True,
) -> Assignment:
    assignment = Assignment(
        title="校园节水行动",
        topic="校园节水行动",
        description="测试作业",
        school_stage=SchoolStage.MIDDLE,
        grade=7,
        main_subject_id=main_subject_id,
        related_subject_ids=[],
        assignment_type=AssignmentType.INQUIRY,
        inquiry_subtype=InquirySubType.SURVEY,
        inquiry_depth=InquiryDepth.INTERMEDIATE,
        submission_mode=SubmissionMode.PHASED,
        duration_weeks=2,
        objectives_json={"knowledge": "目标", "process": "过程", "emotion": "情感"},
        phases_json=[
            {
                "name": "阶段一",
                "order": 1,
                "steps": [
                    {
                        "name": "问题提出",
                        "description": "明确问题",
                        "checkpoints": [{"content": "问题陈述", "evidence_type": "text"}],
                    },
                    {
                        "name": "证据收集",
                        "description": "收集证据",
                        "checkpoints": [{"content": "证据记录", "evidence_type": "document"}],
                    },
                ],
            }
        ],
        rubric_json={"dimensions": [{"name": "问题意识"}, {"name": "证据质量"}]},
        created_by=teacher_id,
        is_published=published,
        published_at=datetime.now(timezone.utc) if published else None,
    )
    session.add(assignment)
    session.commit()
    session.refresh(assignment)
    return assignment


def test_register_student_requires_grade(client: TestClient):
    response = client.post(
        "/api/v2/auth/register",
        json={
            "username": "student_a",
            "password": "Passw0rd123",
            "name": "Student A",
            "role": "student",
        },
    )
    assert response.status_code == 422


def test_settings_require_auth_secret(monkeypatch):
    monkeypatch.delenv("CDAS_AUTH_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_assignment_create_rejects_stage_grade_mismatch(client: TestClient, session: Session):
    teacher = _create_user(session, username="teacher_a", role=UserRole.TEACHER)
    chinese = _create_subject(session, code="chinese", name="语文")

    response = client.post(
        "/api/v2/assignments/",
        headers=_headers(teacher.id, teacher.role.value),
        json={
            "title": "小学错误年级",
            "topic": "小学错误年级",
            "school_stage": "primary",
            "grade": 7,
            "main_subject_id": chinese.id,
            "related_subject_ids": [],
            "assignment_type": "inquiry",
            "inquiry_subtype": "survey",
            "inquiry_depth": "intermediate",
            "submission_mode": "phased",
            "duration_weeks": 2,
        },
    )
    assert response.status_code == 400
    assert "年级" in response.json()["detail"]


def test_publish_requires_at_least_two_rubric_dimensions(client: TestClient, session: Session):
    teacher = _create_user(session, username="teacher_b", role=UserRole.TEACHER)
    chinese = _create_subject(session, code="chinese", name="语文")
    assignment = _create_assignment(session, teacher_id=teacher.id, main_subject_id=chinese.id, published=False)
    assignment.rubric_json = {"dimensions": [{"name": "单一维度"}]}
    session.commit()

    response = client.post(
        f"/api/v2/assignments/{assignment.id}/publish",
        headers=_headers(teacher.id, teacher.role.value),
    )
    assert response.status_code == 400
    assert "评价维度" in response.json()["detail"]


def test_assignment_create_dedupes_related_subject_ids(client: TestClient, session: Session):
    teacher = _create_user(session, username="teacher_subject", role=UserRole.TEACHER)
    main_subject = _create_subject(session, code="science_main", name="科学")
    related_subject = _create_subject(session, code="math_related", name="数学")

    response = client.post(
        "/api/v2/assignments/",
        headers=_headers(teacher.id, teacher.role.value),
        json={
            "title": "学科融合任务",
            "topic": "学科融合任务",
            "school_stage": "middle",
            "grade": 7,
            "main_subject_id": main_subject.id,
            "related_subject_ids": [main_subject.id, related_subject.id, related_subject.id],
            "assignment_type": "inquiry",
            "inquiry_subtype": "survey",
            "inquiry_depth": "intermediate",
            "submission_mode": "phased",
            "duration_weeks": 2,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["related_subject_ids"] == [related_subject.id]


def test_assignment_create_rejects_conflicting_subtypes(client: TestClient, session: Session):
    teacher = _create_user(session, username="teacher_conflict", role=UserRole.TEACHER)
    main_subject = _create_subject(session, code="science_conflict", name="科学")

    response = client.post(
        "/api/v2/assignments/",
        headers=_headers(teacher.id, teacher.role.value),
        json={
            "title": "冲突子类型",
            "topic": "冲突子类型",
            "school_stage": "middle",
            "grade": 7,
            "main_subject_id": main_subject.id,
            "related_subject_ids": [],
            "assignment_type": "practical",
            "practical_subtype": "visit",
            "inquiry_subtype": "survey",
            "inquiry_depth": "intermediate",
            "submission_mode": "phased",
            "duration_weeks": 2,
        },
    )

    assert response.status_code == 422


def test_submit_requires_evidence(client: TestClient, session: Session):
    teacher = _create_user(session, username="teacher_c", role=UserRole.TEACHER)
    student = _create_user(session, username="student_c", role=UserRole.STUDENT, grade=7)
    chinese = _create_subject(session, code="chinese", name="语文")
    assignment = _create_assignment(session, teacher_id=teacher.id, main_subject_id=chinese.id, published=True)
    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        phase_index=0,
        status=SubmissionStatus.DRAFT,
        content_json={"text": ""},
        attachments_json=[],
        checkpoints_json={},
    )
    session.add(submission)
    session.commit()
    session.refresh(submission)

    response = client.post(
        f"/api/v2/submissions/{submission.id}/submit",
        headers=_headers(student.id, student.role.value),
    )
    assert response.status_code == 400
    assert "证据" in response.json()["detail"]


def test_teacher_evaluation_requires_exact_rubric_dimensions(client: TestClient, session: Session):
    teacher = _create_user(session, username="teacher_d", role=UserRole.TEACHER)
    student = _create_user(session, username="student_d", role=UserRole.STUDENT, grade=7)
    chinese = _create_subject(session, code="chinese", name="语文")
    assignment = _create_assignment(session, teacher_id=teacher.id, main_subject_id=chinese.id, published=True)
    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        phase_index=0,
        status=SubmissionStatus.SUBMITTED,
        content_json={"text": "已提交文本"},
        attachments_json=[],
        checkpoints_json={},
        submitted_at=datetime.now(timezone.utc),
    )
    session.add(submission)
    session.commit()
    session.refresh(submission)

    response = client.post(
        "/api/v2/evaluations/teacher",
        headers=_headers(teacher.id, teacher.role.value),
        json={
            "submission_id": submission.id,
            "score_numeric": 3,
            "dimension_scores_json": {"问题意识": 3, "不存在的维度": 2},
            "feedback": "整体不错。",
        },
    )
    assert response.status_code == 400
    assert "rubric" in response.json()["detail"]
