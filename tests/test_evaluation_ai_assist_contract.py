from __future__ import annotations

import json
from datetime import datetime, timezone

import app.api.v2.evaluations as evaluations_api
from app.api.v2.auth import create_token, hash_password
from app.config import get_settings
from app.models import (
    Assignment,
    AssignmentType,
    EvaluationType,
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


def _disable_ai_services(monkeypatch) -> None:
    monkeypatch.setenv("CDAS_DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("CDAS_SILICONFLOW_API_KEY", "")
    get_settings.cache_clear()


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


def _long_text(label: str, repeat: int = 40) -> str:
    return " ".join([f"{label}{idx}" for idx in range(repeat)])


def test_serialize_json_for_prompt_caps_large_dict_payload():
    warnings: list[str] = []

    payload = {
        _long_text(f"检查点标题{index}", repeat=8): _long_text(f"检查点值{index}", repeat=24)
        for index in range(1, 101)
    }

    serialized = evaluations_api._serialize_json_for_prompt(
        payload,
        limit=1200,
        warning_key="checkpoints_truncated",
        warnings=warnings,
    )

    parsed = json.loads(serialized)
    assert len(serialized) <= 1200
    assert isinstance(parsed, dict) and parsed
    assert "checkpoints_truncated" in warnings


def test_serialize_rubric_json_for_prompt_caps_large_dimension_set():
    warnings: list[str] = []
    dimensions = [
        {
            "name": f"维度{index} " + ("超长维度名称 " * 12),
            "levels": {
                "excellent": _long_text(f"维度{index}优秀", repeat=40),
                "good": _long_text(f"维度{index}良好", repeat=40),
            },
        }
        for index in range(1, 46)
    ]

    serialized = evaluations_api._serialize_rubric_json_for_prompt(
        dimensions,
        limit=1800,
        warning_key="rubric_text_truncated",
        warnings=warnings,
    )

    parsed = json.loads(serialized)
    assert len(serialized) <= 1800
    assert isinstance(parsed, dict)
    assert isinstance(parsed.get("dimensions"), list)
    assert len(parsed["dimensions"]) >= 1
    assert "rubric_text_truncated" in warnings


def test_ai_assist_returns_stable_suggestion_contract(client, session, monkeypatch):
    _disable_ai_services(monkeypatch)
    try:
        teacher = _create_user(session, "evaluation_teacher", UserRole.TEACHER)
        student = _create_user(session, "evaluation_student", UserRole.STUDENT, grade=7)
        subject = Subject(code="science", name="科学", category="test", primary_available=True, middle_available=True)
        session.add(subject)
        session.commit()

        assignment = Assignment(
            title="校园节水行动",
            topic="校园节水行动",
            description="测试评价合同",
            school_stage=SchoolStage.MIDDLE,
            grade=7,
            main_subject_id=subject.id,
            related_subject_ids=[],
            assignment_type=AssignmentType.INQUIRY,
            inquiry_depth="intermediate",
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
                            "checkpoints": [{"content": "提交调查记录", "evidence_type": "document"}],
                        }
                    ],
                }
            ],
            rubric_json={"dimensions": [{"name": "问题意识"}, {"name": "证据质量"}]},
            created_by=teacher.id,
            is_published=True,
            published_at=datetime.now(timezone.utc),
        )
        session.add(assignment)
        session.commit()

        submission = Submission(
            assignment_id=assignment.id,
            student_id=student.id,
            phase_index=0,
            status=SubmissionStatus.SUBMITTED,
            content_json={"text": "已提交文字证据"},
            attachments_json=[],
            checkpoints_json={"提交调查记录": True},
            submitted_at=datetime.now(timezone.utc),
        )
        session.add(submission)
        session.commit()
        session.refresh(submission)

        response = client.post(
            f"/api/v2/evaluations/ai-assist?submission_id={submission.id}",
            headers=_headers(teacher.id, teacher.role.value),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"]

        suggestion = data["suggestion"]
        assert suggestion["suggested_level"] in {"excellent", "good", "pass", "improve"}
        assert 1 <= suggestion["suggested_score"] <= 4
        assert set(suggestion["dimension_scores"]) == {"问题意识", "证据质量"}
        assert all(1 <= score <= 4 for score in suggestion["dimension_scores"].values())
        assert suggestion["feedback"]
        assert isinstance(suggestion["evidence"], list)
        assert isinstance(suggestion["action_items"], list)

        meta = data.get("meta")
        if meta is not None:
            assert meta["source"] in {"ai", "fallback"}
            assert isinstance(meta["prompt_id"], str) and meta["prompt_id"]
            assert isinstance(meta["prompt_version"], str) and meta["prompt_version"]
            assert isinstance(meta["fallback_reason"], str)
    finally:
        get_settings.cache_clear()


def test_ai_assist_keeps_structured_prompt_json_valid_when_compacted(client, session, monkeypatch):
    teacher = _create_user(session, "evaluation_teacher_compact", UserRole.TEACHER)
    student = _create_user(session, "evaluation_student_compact", UserRole.STUDENT, grade=7)
    subject = Subject(code="science_compact", name="科学", category="test", primary_available=True, middle_available=True)
    session.add(subject)
    session.commit()
    captured: dict[str, str] = {}

    rubric_dimensions = []
    for index in range(1, 8):
        rubric_dimensions.append(
            {
                "name": f"维度{index}",
                "description": _long_text(f"维度{index}说明", repeat=45),
                "levels": {
                    "excellent": _long_text(f"维度{index}优秀", repeat=32),
                    "good": _long_text(f"维度{index}良好", repeat=32),
                    "pass": _long_text(f"维度{index}合格", repeat=32),
                    "improve": _long_text(f"维度{index}改进", repeat=32),
                },
            }
        )

    assignment = Assignment(
        title="校园节水行动",
        topic="校园节水行动",
        description="测试评价合同",
        school_stage=SchoolStage.MIDDLE,
        grade=7,
        main_subject_id=subject.id,
        related_subject_ids=[],
        assignment_type=AssignmentType.INQUIRY,
        inquiry_depth="intermediate",
        submission_mode=SubmissionMode.PHASED,
        duration_weeks=2,
        objectives_json={
            "knowledge": _long_text("知识目标", repeat=80),
            "process": _long_text("过程目标", repeat=120),
            "emotion": _long_text("情感目标", repeat=80),
        },
        phases_json=[
            {
                "name": "阶段一",
                "order": 1,
                "steps": [
                    {
                        "name": "步骤一",
                        "description": _long_text("场景说明", repeat=120),
                        "content": _long_text("情境承接", repeat=90),
                        "checkpoints": [
                            {"content": _long_text("提交调查记录", repeat=50), "evidence_type": "document"},
                            {"content": _long_text("补充分析", repeat=50), "evidence_type": "text"},
                        ],
                    }
                ],
            }
        ],
        rubric_json={"dimensions": rubric_dimensions},
        created_by=teacher.id,
        is_published=True,
        published_at=datetime.now(timezone.utc),
    )
    session.add(assignment)
    session.commit()

    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        phase_index=0,
        status=SubmissionStatus.SUBMITTED,
        content_json={"text": _long_text("学生提交文本", repeat=220)},
        attachments_json=[
            {
                "filename": f"evidence_{index}.pdf",
                "url": f"https://example.com/{index}/" + ("attachment-path-" * 30),
                "type": "document",
            }
            for index in range(1, 6)
        ],
        checkpoints_json={
            _long_text(f"检查点标题{index}", repeat=8): _long_text(f"值{index}", repeat=50)
            for index in range(1, 101)
        },
        submitted_at=datetime.now(timezone.utc),
    )
    session.add(submission)
    session.commit()
    session.refresh(submission)

    class FakeEvaluationClient:
        def __init__(self, *_args, **_kwargs):
            self.is_available = True

        def structured_predict(self, _schema, _system_prompt: str, _user_prompt: str):
            return _schema(
                suggested_level="good",
                suggested_score=3,
                dimension_scores={dimension["name"]: 3 for dimension in rubric_dimensions},
                feedback="优势：证据较充分；不足：还需进一步细化；下一步：补充关键对照。",
                evidence=[],
                action_items=["补充关键证据", "逐项对照量规优化表达"],
            )

    def fake_build_prompt(ctx):
        captured["rubric_text"] = ctx.rubric_text
        captured["attachments"] = ctx.attachments
        captured["checkpoints"] = ctx.checkpoints
        captured["objectives_json"] = ctx.objectives_json
        return "system", "user"

    monkeypatch.setattr(evaluations_api, "DeepSeekJSONClient", FakeEvaluationClient)
    monkeypatch.setattr(evaluations_api, "build_evaluation_prompt", fake_build_prompt)

    response = client.post(
        f"/api/v2/evaluations/ai-assist?submission_id={submission.id}",
        headers=_headers(teacher.id, teacher.role.value),
    )

    assert response.status_code == 200
    rubric_payload = json.loads(captured["rubric_text"])
    assert [item["name"] for item in rubric_payload["dimensions"]] == [item["name"] for item in rubric_dimensions]
    assert json.loads(captured["attachments"])
    assert json.loads(captured["checkpoints"])
    assert len(captured["checkpoints"]) <= 1200
    assert json.loads(captured["objectives_json"])
    warnings = set(response.json()["meta"]["warnings"])
    assert "rubric_text_truncated" in warnings
    assert "attachments_truncated" in warnings
    assert "checkpoints_truncated" in warnings
    assert "objectives_text_truncated" in warnings


def test_ai_assist_caps_rubric_text_when_rubric_has_many_dimensions(client, session, monkeypatch):
    teacher = _create_user(session, "evaluation_teacher_large_rubric", UserRole.TEACHER)
    student = _create_user(session, "evaluation_student_large_rubric", UserRole.STUDENT, grade=7)
    subject = Subject(code="science_large_rubric", name="科学", category="test", primary_available=True, middle_available=True)
    session.add(subject)
    session.commit()
    captured: dict[str, str] = {}

    rubric_dimensions = [
        {
            "name": f"维度{index} " + ("超长维度名称 " * 12),
            "levels": {
                "excellent": _long_text(f"维度{index}优秀", repeat=40),
                "good": _long_text(f"维度{index}良好", repeat=40),
            },
        }
        for index in range(1, 46)
    ]

    assignment = Assignment(
        title="校园节水行动",
        topic="校园节水行动",
        description="测试大 rubric 压缩",
        school_stage=SchoolStage.MIDDLE,
        grade=7,
        main_subject_id=subject.id,
        related_subject_ids=[],
        assignment_type=AssignmentType.INQUIRY,
        inquiry_depth="intermediate",
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
                        "checkpoints": [{"content": "提交调查记录", "evidence_type": "document"}],
                    }
                ],
            }
        ],
        rubric_json={"dimensions": rubric_dimensions},
        created_by=teacher.id,
        is_published=True,
        published_at=datetime.now(timezone.utc),
    )
    session.add(assignment)
    session.commit()

    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        phase_index=0,
        status=SubmissionStatus.SUBMITTED,
        content_json={"text": "已提交文字证据"},
        attachments_json=[],
        checkpoints_json={"提交调查记录": True},
        submitted_at=datetime.now(timezone.utc),
    )
    session.add(submission)
    session.commit()
    session.refresh(submission)

    class FakeEvaluationClient:
        def __init__(self, *_args, **_kwargs):
            self.is_available = True

        def structured_predict(self, _schema, _system_prompt: str, _user_prompt: str):
            return _schema(
                suggested_level="good",
                suggested_score=3,
                dimension_scores={dimension["name"]: 3 for dimension in rubric_dimensions[:1]},
                feedback="请继续补充说明。",
                evidence=[],
                action_items=["补充关键证据"],
            )

    def fake_build_prompt(ctx):
        captured["rubric_text"] = ctx.rubric_text
        return "system", "user"

    monkeypatch.setattr(evaluations_api, "DeepSeekJSONClient", FakeEvaluationClient)
    monkeypatch.setattr(evaluations_api, "build_evaluation_prompt", fake_build_prompt)

    response = client.post(
        f"/api/v2/evaluations/ai-assist?submission_id={submission.id}",
        headers=_headers(teacher.id, teacher.role.value),
    )

    assert response.status_code == 200
    assert len(captured["rubric_text"]) <= 1800
    rubric_payload = json.loads(captured["rubric_text"])
    assert isinstance(rubric_payload.get("dimensions"), list)
    assert len(rubric_payload["dimensions"]) >= 1
    assert "rubric_text_truncated" in set(response.json()["meta"]["warnings"])
