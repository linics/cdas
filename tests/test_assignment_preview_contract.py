from __future__ import annotations

import json

import app.api.v2.assignments as assignments_api
from app.api.v2.auth import create_token, hash_password
from app.api.v2.assignments import _serialize_template_phases_for_prompt
from app.config import get_settings
from app.models import AssignmentType, SchoolStage, Subject, User, UserRole


def _headers(user_id: int, role: str) -> dict[str, str]:
    token = create_token(user_id, role)
    return {"Authorization": f"Bearer {token}"}


def _disable_ai_services(monkeypatch) -> None:
    monkeypatch.setenv("CDAS_DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("CDAS_SILICONFLOW_API_KEY", "")
    get_settings.cache_clear()


def _create_teacher(session, username: str = "preview_teacher") -> User:
    user = User(
        username=username,
        password_hash=hash_password("Passw0rd123"),
        role=UserRole.TEACHER,
        name="Preview Teacher",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _create_subject(session, code: str, name: str) -> Subject:
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


def _make_large_template_phases() -> list[dict[str, object]]:
    phases: list[dict[str, object]] = []
    for phase_index in range(1, 7):
        steps: list[dict[str, object]] = []
        for step_index in range(1, 4):
            checkpoints = [
                {
                    "content": f"阶段{phase_index}步骤{step_index}检查点{checkpoint_index} " + ("详细证据要求与格式说明 " * 18),
                    "evidence_type": "document",
                }
                for checkpoint_index in range(1, 4)
            ]
            steps.append(
                {
                    "name": f"步骤{phase_index}-{step_index} " + ("情境推进 " * 8),
                    "content": " ".join(
                        [
                            f"这是阶段{phase_index}步骤{step_index}的情境承接内容，",
                            "需要保留任务对象、地点、时间线索以及成果约束。",
                        ]
                    )
                    * 8,
                    "description": " ".join(
                        [
                            f"这是阶段{phase_index}步骤{step_index}的学习支架说明，",
                            "包含场景钩子、操作建议、过程提示与提交标准。",
                        ]
                    )
                    * 14,
                    "checkpoints": checkpoints,
                }
            )
        phases.append(
            {
                "name": f"阶段{phase_index} " + ("章节标题 " * 8),
                "title": f"阶段标题{phase_index} " + ("叙事线索 " * 8),
                "order": phase_index,
                "steps": steps,
            }
        )
    return phases


def test_assignment_preview_returns_fallback_meta(client, session, monkeypatch):
    _disable_ai_services(monkeypatch)
    try:
        teacher = _create_teacher(session)
        subject = _create_subject(session, code="science", name="科学")
        related = _create_subject(session, code="math", name="数学")

        response = client.post(
            "/api/v2/assignments/preview",
            headers=_headers(teacher.id, teacher.role.value),
            json={
                "title": "校园节水行动",
                "topic": "校园节水行动",
                "description": "测试预览合同",
                "school_stage": SchoolStage.MIDDLE.value,
                "grade": 7,
                "main_subject_id": subject.id,
                "related_subject_ids": [related.id],
                "assignment_type": AssignmentType.INQUIRY.value,
                "inquiry_subtype": "survey",
                "inquiry_depth": "intermediate",
                "submission_mode": "phased",
                "duration_weeks": 2,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert set(data) >= {"objectives_json", "phases_json", "rubric_json", "meta"}
        assert len(data["phases_json"]) >= 2
        assert len(data["rubric_json"]["dimensions"]) >= 2

        meta = data["meta"]
        assert meta["source"] == "fallback"
        assert meta["fallback_reason"] == "provider_unavailable"
        assert isinstance(meta["prompt_id"], str) and meta["prompt_id"]
        assert isinstance(meta["prompt_version"], str) and meta["prompt_version"]
        assert meta["used_rag"] is False
    finally:
        get_settings.cache_clear()


def test_serialize_template_phases_for_prompt_keeps_json_valid_when_compacted():
    warnings: list[str] = []

    serialized = _serialize_template_phases_for_prompt(
        _make_large_template_phases(),
        limit=1200,
        warning_key="template_json_truncated",
        warnings=warnings,
    )

    parsed = json.loads(serialized)
    assert len(serialized) <= 1200
    assert isinstance(parsed, list) and len(parsed) == 6
    assert all(isinstance(phase.get("steps"), list) and phase["steps"] for phase in parsed)
    assert all(
        isinstance(step.get("checkpoints"), list) and step["checkpoints"]
        for phase in parsed
        for step in phase["steps"]
    )
    assert "template_json_truncated" in warnings


def test_assignment_preview_uses_valid_compacted_template_json(client, session, monkeypatch):
    teacher = _create_teacher(session, username="preview_compact_teacher")
    subject = _create_subject(session, code="science_compact", name="科学")
    related = _create_subject(session, code="math_compact", name="数学")
    captured: dict[str, str] = {}

    class FakePreviewClient:
        def __init__(self, *_args, **_kwargs):
            self.is_available = True

        def predict_json(self, _system_prompt: str, _user_prompt: str):
            return {
                "objectives": {
                    "knowledge": "理解任务目标",
                    "process": "背景设定：周三午休，图书馆一楼走廊的节水展示区需要重新布置，后勤老师请同学们在两周内完成调查并给出改进方案，要求保留可核验的证据与可展示成果。\n行动主线：先调查，再分析，再形成改进方案并公开汇报。",
                    "emotion": "建立责任感",
                },
                "phases": [
                    {
                        "name": "阶段一",
                        "order": 1,
                        "steps": [
                            {
                                "name": "收集资料",
                                "description": "先进入场景，再完成资料收集。",
                                "checkpoints": [{"content": "提交调查记录", "evidence_type": "document"}],
                            }
                        ],
                    },
                    {
                        "name": "阶段二",
                        "order": 2,
                        "steps": [
                            {
                                "name": "形成方案",
                                "description": "完成分析并提交方案。",
                                "checkpoints": [{"content": "提交方案草稿", "evidence_type": "document"}],
                            }
                        ],
                    },
                    {
                        "name": "阶段三",
                        "order": 3,
                        "steps": [
                            {
                                "name": "公开汇报",
                                "description": "整理成果并完成汇报。",
                                "checkpoints": [{"content": "提交汇报提纲", "evidence_type": "document"}],
                            }
                        ],
                    },
                ],
                "rubric": {"dimensions": [{"name": "问题意识"}, {"name": "证据质量"}]},
            }

    def fake_build_prompt(ctx):
        captured["template_json"] = ctx.template_json
        return "system", "user"

    monkeypatch.setattr(assignments_api, "DeepSeekJSONClient", FakePreviewClient)
    monkeypatch.setattr(assignments_api, "build_assignment_preview_prompt", fake_build_prompt)
    monkeypatch.setattr(assignments_api, "_get_template_phases", lambda _data: _make_large_template_phases())

    response = client.post(
        "/api/v2/assignments/preview",
        headers=_headers(teacher.id, teacher.role.value),
        json={
            "title": "校园节水行动",
            "topic": "校园节水行动",
            "description": "测试大模板压缩",
            "school_stage": SchoolStage.MIDDLE.value,
            "grade": 7,
            "main_subject_id": subject.id,
            "related_subject_ids": [related.id],
            "assignment_type": AssignmentType.INQUIRY.value,
            "inquiry_subtype": "survey",
            "inquiry_depth": "intermediate",
            "submission_mode": "phased",
            "duration_weeks": 2,
        },
    )

    assert response.status_code == 200
    assert json.loads(captured["template_json"])
    assert "template_json_truncated" in response.json()["meta"]["warnings"]
