from __future__ import annotations

import io
import json
from datetime import datetime, timezone

import app.api.v2.evaluations as evaluations_api
from app.api.v2.auth import create_token, hash_password
from app.config import get_settings
from app.models import (
    Assignment,
    AssignmentType,
    InquiryDepth,
    InquirySubType,
    ProjectGroup,
    SchoolStage,
    Submission,
    SubmissionAttachmentAsset,
    SubmissionMode,
    SubmissionStatus,
    Subject,
    User,
    UserRole,
)


def _headers(user_id: int, role: str) -> dict[str, str]:
    token = create_token(user_id, role)
    return {"Authorization": f"Bearer {token}"}


def _create_user(session, username: str, role: UserRole, grade: int | None = None) -> User:
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
    session,
    teacher_id: int,
    subject_id: int,
    *,
    deadline: datetime | None = None,
) -> Assignment:
    assignment = Assignment(
        title="校园水质分析",
        topic="校园水质分析",
        description="测试上传附件",
        school_stage=SchoolStage.MIDDLE,
        grade=7,
        main_subject_id=subject_id,
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
                        "name": "步骤一",
                        "description": "收集证据",
                        "checkpoints": [{"content": "提交记录", "evidence_type": "document"}],
                    }
                ],
            }
        ],
        rubric_json={"dimensions": [{"name": "证据质量"}, {"name": "分析表达"}]},
        created_by=teacher_id,
        is_published=True,
        published_at=datetime.now(timezone.utc),
        deadline=deadline,
    )
    session.add(assignment)
    session.commit()
    session.refresh(assignment)
    return assignment


def _create_submission(session, assignment_id: int, student_id: int) -> Submission:
    submission = Submission(
        assignment_id=assignment_id,
        student_id=student_id,
        phase_index=0,
        status=SubmissionStatus.DRAFT,
        content_json={"text": ""},
        attachments_json=[],
        checkpoints_json={},
    )
    session.add(submission)
    session.commit()
    session.refresh(submission)
    return submission


def _create_group(session, assignment_id: int, members_json: list[dict[str, object]]) -> ProjectGroup:
    group = ProjectGroup(
        assignment_id=assignment_id,
        name="实验小组",
        members_json=members_json,
    )
    session.add(group)
    session.commit()
    session.refresh(group)
    return group


def test_upload_attachment_projects_back_into_submission_response(client, session, monkeypatch, tmp_path):
    monkeypatch.setenv("CDAS_DOCUMENTS_DIR", str(tmp_path / "documents"))
    get_settings.cache_clear()
    try:
        teacher = _create_user(session, "teacher_upload", UserRole.TEACHER)
        student = _create_user(session, "student_upload", UserRole.STUDENT, grade=7)
        subject = Subject(code="science_upload", name="科学", category="test", primary_available=True, middle_available=True)
        session.add(subject)
        session.commit()
        assignment = _create_assignment(session, teacher.id, subject.id)
        submission = _create_submission(session, assignment.id, student.id)

        response = client.post(
            f"/api/v2/submissions/{submission.id}/attachments/upload",
            headers=_headers(student.id, student.role.value),
            files={"file": ("notes.txt", io.BytesIO("第一段证据\n第二段分析".encode("utf-8")), "text/plain")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["source"] == "upload"
        assert payload["parsing_status"] == "ready"
        assert payload["summary_text"]
        assert payload["url"].endswith("/download")

        submission_response = client.get(
            f"/api/v2/submissions/{submission.id}",
            headers=_headers(student.id, student.role.value),
        )
        assert submission_response.status_code == 200
        attachments = submission_response.json()["attachments_json"]
        assert len(attachments) == 1
        assert attachments[0]["source"] == "upload"
        assert attachments[0]["parsing_status"] == "ready"
    finally:
        get_settings.cache_clear()


def test_reused_group_submission_includes_uploaded_attachments(client, session, monkeypatch, tmp_path):
    monkeypatch.setenv("CDAS_DOCUMENTS_DIR", str(tmp_path / "documents"))
    get_settings.cache_clear()
    try:
        teacher = _create_user(session, "teacher_group_upload", UserRole.TEACHER)
        student_one = _create_user(session, "student_group_upload_one", UserRole.STUDENT, grade=7)
        student_two = _create_user(session, "student_group_upload_two", UserRole.STUDENT, grade=7)
        subject = Subject(code="science_group_upload", name="科学", category="test", primary_available=True, middle_available=True)
        session.add(subject)
        session.commit()
        assignment = _create_assignment(session, teacher.id, subject.id)
        group = _create_group(
            session,
            assignment.id,
            [
                {"user_id": student_one.id, "name": student_one.name, "username": student_one.username},
                {"user_id": student_two.id, "name": student_two.name, "username": student_two.username},
            ],
        )

        create_response = client.post(
            "/api/v2/submissions/",
            headers=_headers(student_one.id, student_one.role.value),
            json={
                "assignment_id": assignment.id,
                "phase_index": 0,
                "group_id": group.id,
            },
        )
        assert create_response.status_code == 201
        submission_id = create_response.json()["id"]

        upload_response = client.post(
            f"/api/v2/submissions/{submission_id}/attachments/upload",
            headers=_headers(student_one.id, student_one.role.value),
            files={"file": ("notes.txt", io.BytesIO("小组共享证据".encode("utf-8")), "text/plain")},
        )
        assert upload_response.status_code == 200
        assert upload_response.json()["source"] == "upload"

        reused_response = client.post(
            "/api/v2/submissions/",
            headers=_headers(student_two.id, student_two.role.value),
            json={
                "assignment_id": assignment.id,
                "phase_index": 0,
                "group_id": group.id,
            },
        )

        assert reused_response.status_code == 201
        attachments = reused_response.json()["attachments_json"]
        assert len(attachments) == 1
        assert attachments[0]["source"] == "upload"
        assert attachments[0]["filename"] == "notes.txt"
    finally:
        get_settings.cache_clear()


def test_submit_rejects_when_uploaded_attachment_not_ready(client, session, monkeypatch, tmp_path):
    monkeypatch.setenv("CDAS_DOCUMENTS_DIR", str(tmp_path / "documents"))
    get_settings.cache_clear()
    try:
        teacher = _create_user(session, "teacher_submit_attachment", UserRole.TEACHER)
        student = _create_user(session, "student_submit_attachment", UserRole.STUDENT, grade=7)
        subject = Subject(code="science_submit_attachment", name="科学", category="test", primary_available=True, middle_available=True)
        session.add(subject)
        session.commit()
        assignment = _create_assignment(session, teacher.id, subject.id)
        submission = _create_submission(session, assignment.id, student.id)

        async def fail_save_upload_file(*_args, **_kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("app.services.submission_attachments.save_upload_file", fail_save_upload_file)

        upload_response = client.post(
            f"/api/v2/submissions/{submission.id}/attachments/upload",
            headers=_headers(student.id, student.role.value),
            files={"file": ("notes.txt", io.BytesIO("已有附件".encode("utf-8")), "text/plain")},
        )
        assert upload_response.status_code == 200
        assert upload_response.json()["parsing_status"] == "failed"

        update_response = client.put(
            f"/api/v2/submissions/{submission.id}",
            headers=_headers(student.id, student.role.value),
            json={"content_json": {"text": "已有文字说明"}},
        )
        assert update_response.status_code == 200

        submit_response = client.post(
            f"/api/v2/submissions/{submission.id}/submit",
            headers=_headers(student.id, student.role.value),
        )

        assert submit_response.status_code == 400
        assert "附件" in submit_response.json()["detail"]
        assert "READY" not in submit_response.json()["detail"]
    finally:
        get_settings.cache_clear()


def test_upload_attachment_rejects_unsupported_file_before_persisting(client, session, monkeypatch, tmp_path):
    monkeypatch.setenv("CDAS_DOCUMENTS_DIR", str(tmp_path / "documents"))
    get_settings.cache_clear()
    try:
        teacher = _create_user(session, "teacher_upload_bad_type", UserRole.TEACHER)
        student = _create_user(session, "student_upload_bad_type", UserRole.STUDENT, grade=7)
        subject = Subject(code="science_upload_bad_type", name="科学", category="test", primary_available=True, middle_available=True)
        session.add(subject)
        session.commit()
        assignment = _create_assignment(session, teacher.id, subject.id)
        submission = _create_submission(session, assignment.id, student.id)

        response = client.post(
            f"/api/v2/submissions/{submission.id}/attachments/upload",
            headers=_headers(student.id, student.role.value),
            files={"file": ("bad.md", io.BytesIO(b"# unsupported"), "text/markdown")},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "仅支持上传 PDF、DOCX 或 TXT 附件"
        assert session.query(SubmissionAttachmentAsset).filter_by(submission_id=submission.id).count() == 0

        list_response = client.get(
            f"/api/v2/submissions/{submission.id}/attachments",
            headers=_headers(student.id, student.role.value),
        )
        assert list_response.status_code == 200
        assert list_response.json()["attachments"] == []
        storage_root = tmp_path / "submission_attachments"
        assert not storage_root.exists() or list(storage_root.iterdir()) == []
    finally:
        get_settings.cache_clear()


def test_upload_attachment_rejects_oversized_file_before_persisting(client, session, monkeypatch, tmp_path):
    monkeypatch.setenv("CDAS_DOCUMENTS_DIR", str(tmp_path / "documents"))
    get_settings.cache_clear()
    try:
        teacher = _create_user(session, "teacher_upload_too_large", UserRole.TEACHER)
        student = _create_user(session, "student_upload_too_large", UserRole.STUDENT, grade=7)
        subject = Subject(code="science_upload_too_large", name="科学", category="test", primary_available=True, middle_available=True)
        session.add(subject)
        session.commit()
        assignment = _create_assignment(session, teacher.id, subject.id)
        submission = _create_submission(session, assignment.id, student.id)

        response = client.post(
            f"/api/v2/submissions/{submission.id}/attachments/upload",
            headers=_headers(student.id, student.role.value),
            files={"file": ("large.txt", io.BytesIO(b"x" * (10 * 1024 * 1024 + 1)), "text/plain")},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "上传附件不能超过 10MB"
        assert session.query(SubmissionAttachmentAsset).filter_by(submission_id=submission.id).count() == 0

        list_response = client.get(
            f"/api/v2/submissions/{submission.id}/attachments",
            headers=_headers(student.id, student.role.value),
        )
        assert list_response.status_code == 200
        assert list_response.json()["attachments"] == []
        storage_root = tmp_path / "submission_attachments"
        assert not storage_root.exists() or list(storage_root.iterdir()) == []
    finally:
        get_settings.cache_clear()


def test_delete_uploaded_attachment_removes_it_from_attachment_list(client, session, monkeypatch, tmp_path):
    monkeypatch.setenv("CDAS_DOCUMENTS_DIR", str(tmp_path / "documents"))
    get_settings.cache_clear()
    try:
        teacher = _create_user(session, "teacher_delete_attachment", UserRole.TEACHER)
        student = _create_user(session, "student_delete_attachment", UserRole.STUDENT, grade=7)
        subject = Subject(code="science_delete_attachment", name="科学", category="test", primary_available=True, middle_available=True)
        session.add(subject)
        session.commit()
        assignment = _create_assignment(session, teacher.id, subject.id)
        submission = _create_submission(session, assignment.id, student.id)

        upload_response = client.post(
            f"/api/v2/submissions/{submission.id}/attachments/upload",
            headers=_headers(student.id, student.role.value),
            files={"file": ("notes.txt", io.BytesIO("删除测试".encode("utf-8")), "text/plain")},
        )
        attachment_id = upload_response.json()["attachment_id"]

        delete_response = client.delete(
            f"/api/v2/submissions/{submission.id}/attachments/{attachment_id}",
            headers=_headers(student.id, student.role.value),
        )
        assert delete_response.status_code == 204

        list_response = client.get(
            f"/api/v2/submissions/{submission.id}/attachments",
            headers=_headers(student.id, student.role.value),
        )
        assert list_response.status_code == 200
        assert list_response.json()["attachments"] == []
    finally:
        get_settings.cache_clear()


def test_upload_attachment_rejects_after_deadline(client, session, monkeypatch, tmp_path):
    monkeypatch.setenv("CDAS_DOCUMENTS_DIR", str(tmp_path / "documents"))
    get_settings.cache_clear()
    try:
        teacher = _create_user(session, "teacher_upload_deadline", UserRole.TEACHER)
        student = _create_user(session, "student_upload_deadline", UserRole.STUDENT, grade=7)
        subject = Subject(code="science_upload_deadline", name="科学", category="test", primary_available=True, middle_available=True)
        session.add(subject)
        session.commit()
        assignment = _create_assignment(
            session,
            teacher.id,
            subject.id,
            deadline=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        submission = _create_submission(session, assignment.id, student.id)

        response = client.post(
            f"/api/v2/submissions/{submission.id}/attachments/upload",
            headers=_headers(student.id, student.role.value),
            files={"file": ("notes.txt", io.BytesIO("截止后上传".encode("utf-8")), "text/plain")},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "已过截止时间，不能修改"
    finally:
        get_settings.cache_clear()


def test_upload_attachment_write_failure_marks_asset_failed(client, session, monkeypatch, tmp_path):
    monkeypatch.setenv("CDAS_DOCUMENTS_DIR", str(tmp_path / "documents"))
    get_settings.cache_clear()
    try:
        teacher = _create_user(session, "teacher_upload_io_failure", UserRole.TEACHER)
        student = _create_user(session, "student_upload_io_failure", UserRole.STUDENT, grade=7)
        subject = Subject(code="science_upload_io_failure", name="科学", category="test", primary_available=True, middle_available=True)
        session.add(subject)
        session.commit()
        assignment = _create_assignment(session, teacher.id, subject.id)
        submission = _create_submission(session, assignment.id, student.id)

        async def fail_save_upload_file(*_args, **_kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("app.services.submission_attachments.save_upload_file", fail_save_upload_file)

        response = client.post(
            f"/api/v2/submissions/{submission.id}/attachments/upload",
            headers=_headers(student.id, student.role.value),
            files={"file": ("notes.txt", io.BytesIO("写盘失败".encode("utf-8")), "text/plain")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["parsing_status"] == "failed"
        assert payload["error_msg"] == "disk full"

        list_response = client.get(
            f"/api/v2/submissions/{submission.id}/attachments",
            headers=_headers(student.id, student.role.value),
        )
        assert list_response.status_code == 200
        attachments = list_response.json()["attachments"]
        assert len(attachments) == 1
        assert attachments[0]["parsing_status"] == "failed"
        assert attachments[0]["error_msg"] == "disk full"
    finally:
        get_settings.cache_clear()


def test_delete_uploaded_attachment_rejects_after_deadline(client, session, monkeypatch, tmp_path):
    monkeypatch.setenv("CDAS_DOCUMENTS_DIR", str(tmp_path / "documents"))
    get_settings.cache_clear()
    try:
        teacher = _create_user(session, "teacher_delete_deadline", UserRole.TEACHER)
        student = _create_user(session, "student_delete_deadline", UserRole.STUDENT, grade=7)
        subject = Subject(code="science_delete_deadline", name="科学", category="test", primary_available=True, middle_available=True)
        session.add(subject)
        session.commit()
        assignment = _create_assignment(
            session,
            teacher.id,
            subject.id,
            deadline=datetime(2027, 1, 1, tzinfo=timezone.utc),
        )
        submission = _create_submission(session, assignment.id, student.id)

        upload_response = client.post(
            f"/api/v2/submissions/{submission.id}/attachments/upload",
            headers=_headers(student.id, student.role.value),
            files={"file": ("notes.txt", io.BytesIO("先上传再改 deadline".encode("utf-8")), "text/plain")},
        )
        assert upload_response.status_code == 200
        attachment_id = upload_response.json()["attachment_id"]

        assignment.deadline = datetime(2025, 1, 1, tzinfo=timezone.utc)
        session.commit()

        response = client.delete(
            f"/api/v2/submissions/{submission.id}/attachments/{attachment_id}",
            headers=_headers(student.id, student.role.value),
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "已过截止时间，不能修改"
    finally:
        get_settings.cache_clear()


def test_delete_failed_uploaded_attachment_allows_cleanup_after_deadline(client, session, monkeypatch, tmp_path):
    monkeypatch.setenv("CDAS_DOCUMENTS_DIR", str(tmp_path / "documents"))
    get_settings.cache_clear()
    try:
        teacher = _create_user(session, "teacher_delete_failed_after_deadline", UserRole.TEACHER)
        student = _create_user(session, "student_delete_failed_after_deadline", UserRole.STUDENT, grade=7)
        subject = Subject(
            code="science_delete_failed_after_deadline",
            name="科学",
            category="test",
            primary_available=True,
            middle_available=True,
        )
        session.add(subject)
        session.commit()
        assignment = _create_assignment(
            session,
            teacher.id,
            subject.id,
            deadline=datetime(2027, 1, 1, tzinfo=timezone.utc),
        )
        submission = _create_submission(session, assignment.id, student.id)

        async def fail_save_upload_file(*_args, **_kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("app.services.submission_attachments.save_upload_file", fail_save_upload_file)

        upload_response = client.post(
            f"/api/v2/submissions/{submission.id}/attachments/upload",
            headers=_headers(student.id, student.role.value),
            files={"file": ("notes.txt", io.BytesIO("先失败后删除".encode("utf-8")), "text/plain")},
        )
        assert upload_response.status_code == 200
        assert upload_response.json()["parsing_status"] == "failed"
        attachment_id = upload_response.json()["attachment_id"]

        assignment.deadline = datetime(2025, 1, 1, tzinfo=timezone.utc)
        session.commit()

        response = client.delete(
            f"/api/v2/submissions/{submission.id}/attachments/{attachment_id}",
            headers=_headers(student.id, student.role.value),
        )

        assert response.status_code == 204

        list_response = client.get(
            f"/api/v2/submissions/{submission.id}/attachments",
            headers=_headers(student.id, student.role.value),
        )
        assert list_response.status_code == 200
        assert list_response.json()["attachments"] == []
    finally:
        get_settings.cache_clear()


def test_delete_draft_submission_removes_uploaded_attachment_files(client, session, monkeypatch, tmp_path):
    monkeypatch.setenv("CDAS_DOCUMENTS_DIR", str(tmp_path / "documents"))
    get_settings.cache_clear()
    try:
        teacher = _create_user(session, "teacher_delete_submission", UserRole.TEACHER)
        student = _create_user(session, "student_delete_submission", UserRole.STUDENT, grade=7)
        subject = Subject(code="science_delete_submission", name="科学", category="test", primary_available=True, middle_available=True)
        session.add(subject)
        session.commit()
        assignment = _create_assignment(session, teacher.id, subject.id)
        submission = _create_submission(session, assignment.id, student.id)

        upload_response = client.post(
            f"/api/v2/submissions/{submission.id}/attachments/upload",
            headers=_headers(student.id, student.role.value),
            files={"file": ("notes.txt", io.BytesIO("删除整份提交".encode("utf-8")), "text/plain")},
        )
        assert upload_response.status_code == 200
        attachment_path = upload_response.json()["url"]

        attachment_dir = tmp_path / "submission_attachments" / str(upload_response.json()["attachment_id"])
        assert attachment_dir.exists()

        delete_response = client.delete(
            f"/api/v2/submissions/{submission.id}",
            headers=_headers(student.id, student.role.value),
        )
        assert delete_response.status_code == 204
        assert not attachment_dir.exists(), attachment_path
    finally:
        get_settings.cache_clear()


def test_ai_assist_prefers_uploaded_attachment_summary(client, session, monkeypatch, tmp_path):
    monkeypatch.setenv("CDAS_DOCUMENTS_DIR", str(tmp_path / "documents"))
    get_settings.cache_clear()
    captured: dict[str, str] = {}
    try:
        teacher = _create_user(session, "teacher_ai_attachment", UserRole.TEACHER)
        student = _create_user(session, "student_ai_attachment", UserRole.STUDENT, grade=7)
        subject = Subject(code="science_ai_attachment", name="科学", category="test", primary_available=True, middle_available=True)
        session.add(subject)
        session.commit()
        assignment = _create_assignment(session, teacher.id, subject.id)
        submission = Submission(
            assignment_id=assignment.id,
            student_id=student.id,
            phase_index=0,
            status=SubmissionStatus.DRAFT,
            content_json={"text": "学生正文"},
            attachments_json=[],
            checkpoints_json={},
        )
        session.add(submission)
        session.commit()
        session.refresh(submission)

        upload_response = client.post(
            f"/api/v2/submissions/{submission.id}/attachments/upload",
            headers=_headers(student.id, student.role.value),
            files={"file": ("analysis.txt", io.BytesIO("关键证据A。关键证据B。".encode("utf-8")), "text/plain")},
        )
        assert upload_response.status_code == 200
        submission.status = SubmissionStatus.SUBMITTED
        submission.submitted_at = datetime.now(timezone.utc)
        session.commit()

        class FakeEvaluationClient:
            def __init__(self, *_args, **_kwargs):
                self.is_available = True

            def structured_predict(self, schema, _system_prompt: str, _user_prompt: str):
                return schema(
                    suggested_level="good",
                    suggested_score=3,
                    dimension_scores={"证据质量": 3, "分析表达": 3},
                    feedback="反馈",
                    evidence=[],
                    action_items=[],
                )

        def fake_build_prompt(ctx):
            captured["attachments"] = ctx.attachments
            return "system", "user"

        monkeypatch.setattr(evaluations_api, "DeepSeekJSONClient", FakeEvaluationClient)
        monkeypatch.setattr(evaluations_api, "build_evaluation_prompt", fake_build_prompt)

        response = client.post(
            f"/api/v2/evaluations/ai-assist?submission_id={submission.id}",
            headers=_headers(teacher.id, teacher.role.value),
        )
        assert response.status_code == 200

        attachments_payload = json.loads(captured["attachments"])
        assert attachments_payload[0]["source"] == "upload"
        assert attachments_payload[0]["summary_text"]
        assert "关键证据A" in attachments_payload[0]["summary_text"]
    finally:
        get_settings.cache_clear()
