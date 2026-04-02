from __future__ import annotations

import json
from pathlib import Path

import app.api.v2.assignments as assignments_api
from app.api.v2.assignments import _prepare_prompt_excerpt
from app.api.v2.auth import create_token, hash_password
from app.config import get_settings
from app.models import Document, ParsingStatus, Subject, User, UserRole


def _headers(user_id: int, role: str) -> dict[str, str]:
    token = create_token(user_id, role)
    return {"Authorization": f"Bearer {token}"}


def _disable_ai_services(monkeypatch) -> None:
    monkeypatch.setenv("CDAS_DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("CDAS_SILICONFLOW_API_KEY", "")
    get_settings.cache_clear()


def _create_teacher(session, username: str = "lesson_teacher") -> User:
    user = User(
        username=username,
        password_hash=hash_password("Passw0rd123"),
        role=UserRole.TEACHER,
        name="Lesson Teacher",
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
            steps.append(
                {
                    "name": f"步骤{phase_index}-{step_index} " + ("情境推进 " * 8),
                    "content": ("需要在场景中串联人物、地点与成果要求。 " * 12).strip(),
                    "description": ("这是详细的支架说明，需要保留关键约束与提交标准。 " * 18).strip(),
                    "checkpoints": [
                        {
                            "content": f"阶段{phase_index}步骤{step_index}证据1 " + ("详细格式要求 " * 18),
                            "evidence_type": "document",
                        },
                        {
                            "content": f"阶段{phase_index}步骤{step_index}证据2 " + ("详细格式要求 " * 18),
                            "evidence_type": "text",
                        },
                    ],
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


def test_from_lesson_plan_returns_fallback_meta(client, session, tmp_path, monkeypatch):
    _disable_ai_services(monkeypatch)
    try:
        teacher = _create_teacher(session)
        subject = _create_subject(session, code="science", name="科学")

        lesson_plan_path = tmp_path / "lesson-plan.txt"
        lesson_plan_path.write_text(
            "\n".join(
                [
                    "教案名称：校园节水项目",
                    "课题：校园节水项目",
                    "初中七年级科学",
                    "项目式作业",
                    "调查学生节水行为并提出改进建议。",
                ]
            ),
            encoding="utf-8",
        )

        document = Document(
            filename="lesson-plan.txt",
            file_path=str(lesson_plan_path),
            mime_type="text/plain",
            parsing_status=ParsingStatus.READY,
            metadata_json={"subject_id": subject.id, "subject_name": subject.name},
            source="user",
        )
        session.add(document)
        session.commit()
        session.refresh(document)

        response = client.post(
            "/api/v2/assignments/from-lesson-plan",
            headers=_headers(teacher.id, teacher.role.value),
            json={"document_id": document.id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == document.id
        assert data["main_subject_id"] == subject.id
        assert data["school_stage"] == "middle"
        assert data["grade"] == 7
        assert data["title"] == "校园节水项目"
        assert data["topic"] == "校园节水项目"
        assert data["source_summary"]
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


def test_prepare_prompt_excerpt_marks_compaction_from_raw_text():
    warnings: list[str] = []
    excerpt, input_truncated = _prepare_prompt_excerpt(
        "校园节水项目背景说明 " * 300,
        limit=120,
        warning_key="lesson_plan_extract_excerpt_truncated",
        warnings=warnings,
    )

    assert input_truncated is True
    assert excerpt.endswith("...")
    assert "lesson_plan_extract_excerpt_truncated" in warnings


def test_from_lesson_plan_marks_metadata_when_long_input_is_compacted(client, session, tmp_path, monkeypatch):
    try:
        teacher = _create_teacher(session, username="lesson_teacher_long")
        subject = _create_subject(session, code="science_long", name="科学")

        class FakeLessonPlanClient:
            def __init__(self, *_args, **_kwargs):
                self.is_available = True

            def predict_json(self, _system_prompt: str, user_prompt: str):
                if "提取字段" in user_prompt:
                    return {
                        "school_stage": "middle",
                        "grade": 7,
                        "assignment_type": "project",
                        "inquiry_depth": "intermediate",
                        "submission_mode": "phased",
                        "duration_weeks": 2,
                        "main_subject": "科学",
                        "related_subjects": [],
                    }
                return {
                    "objectives": {
                        "knowledge": "理解校园节水问题",
                        "process": "完成调查与方案设计",
                        "emotion": "建立节水责任感",
                    },
                    "phases": [
                        {
                            "name": "阶段一",
                            "order": 1,
                            "steps": [
                                {
                                    "name": "收集资料",
                                    "description": "记录校园用水现状",
                                    "checkpoints": ["提交调查记录"],
                                }
                            ],
                        },
                        {
                            "name": "阶段二",
                            "order": 2,
                            "steps": [
                                {
                                    "name": "形成方案",
                                    "description": "提交改进建议",
                                    "checkpoints": ["提交方案草稿"],
                                }
                            ],
                        },
                    ],
                    "rubric": {
                        "dimensions": [
                            {"name": "问题意识"},
                            {"name": "证据质量"},
                        ]
                    },
                }

        monkeypatch.setattr(assignments_api, "DeepSeekJSONClient", FakeLessonPlanClient)

        lesson_plan_path = tmp_path / "lesson-plan-long.txt"
        lesson_plan_path.write_text(
            "\n".join(
                [
                    "教案名称：校园节水项目",
                    "课题：校园节水项目",
                    "初中七年级科学",
                    "项目式作业",
                    "调查学生节水行为并提出改进建议。",
                    "背景说明：" + ("校园节水项目背景说明 " * 500),
                ]
            ),
            encoding="utf-8",
        )

        document = Document(
            filename="lesson-plan-long.txt",
            file_path=str(lesson_plan_path),
            mime_type="text/plain",
            parsing_status=ParsingStatus.READY,
            metadata_json={"subject_id": subject.id, "subject_name": subject.name},
            source="user",
        )
        session.add(document)
        session.commit()
        session.refresh(document)

        response = client.post(
            "/api/v2/assignments/from-lesson-plan",
            headers=_headers(teacher.id, teacher.role.value),
            json={"document_id": document.id},
        )

        assert response.status_code == 200
        meta = response.json()["meta"]
        assert meta["input_truncated"] is True
        assert "lesson_plan_excerpt_truncated" in meta["warnings"]
    finally:
        get_settings.cache_clear()


def test_from_lesson_plan_clears_incompatible_subtypes_in_seed(client, session, tmp_path, monkeypatch):
    try:
        teacher = _create_teacher(session, username="lesson_teacher_project_subtype")
        subject = _create_subject(session, code="science_project", name="科学")

        class FakeLessonPlanClient:
            def __init__(self, *_args, **_kwargs):
                self.is_available = True

            def predict_json(self, _system_prompt: str, user_prompt: str):
                if "提取字段" in user_prompt:
                    return {
                        "school_stage": "middle",
                        "grade": 7,
                        "assignment_type": "project",
                        "inquiry_subtype": "survey",
                        "inquiry_depth": "intermediate",
                        "submission_mode": "phased",
                        "duration_weeks": 2,
                        "main_subject": "科学",
                        "related_subjects": [],
                    }
                return {
                    "objectives": {
                        "knowledge": "理解校园节水问题",
                        "process": "完成调查与方案设计",
                        "emotion": "建立节水责任感",
                    },
                    "phases": [
                        {
                            "name": "阶段一",
                            "order": 1,
                            "steps": [
                                {
                                    "name": "收集资料",
                                    "description": "记录校园用水现状",
                                    "checkpoints": ["提交调查记录"],
                                }
                            ],
                        },
                        {
                            "name": "阶段二",
                            "order": 2,
                            "steps": [
                                {
                                    "name": "形成方案",
                                    "description": "提交改进建议",
                                    "checkpoints": ["提交方案草稿"],
                                }
                            ],
                        },
                    ],
                    "rubric": {
                        "dimensions": [
                            {"name": "问题意识"},
                            {"name": "证据质量"},
                        ]
                    },
                }

        monkeypatch.setattr(assignments_api, "DeepSeekJSONClient", FakeLessonPlanClient)

        lesson_plan_path = tmp_path / "lesson-plan-project-subtype.txt"
        lesson_plan_path.write_text(
            "\n".join(
                [
                    "教案名称：校园节水项目",
                    "课题：校园节水项目",
                    "初中七年级科学",
                    "项目式作业",
                    "调查学生节水行为并提出改进建议。",
                ]
            ),
            encoding="utf-8",
        )

        document = Document(
            filename="lesson-plan-project-subtype.txt",
            file_path=str(lesson_plan_path),
            mime_type="text/plain",
            parsing_status=ParsingStatus.READY,
            metadata_json={"subject_id": subject.id, "subject_name": subject.name},
            source="user",
        )
        session.add(document)
        session.commit()
        session.refresh(document)

        response = client.post(
            "/api/v2/assignments/from-lesson-plan",
            headers=_headers(teacher.id, teacher.role.value),
            json={"document_id": document.id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["assignment_type"] == "project"
        assert data["practical_subtype"] is None
        assert data["inquiry_subtype"] is None
    finally:
        get_settings.cache_clear()


def test_from_lesson_plan_uses_valid_compacted_template_json(client, session, tmp_path, monkeypatch):
    teacher = _create_teacher(session, username="lesson_teacher_compact_template")
    subject = _create_subject(session, code="science_compact_template", name="科学")
    captured: dict[str, str] = {}

    class FakeLessonPlanClient:
        def __init__(self, *_args, **_kwargs):
            self.is_available = True

        def predict_json(self, _system_prompt: str, user_prompt: str):
            if "提取字段" in user_prompt:
                return {
                    "school_stage": "middle",
                    "grade": 7,
                    "assignment_type": "project",
                    "inquiry_depth": "intermediate",
                    "submission_mode": "phased",
                    "duration_weeks": 2,
                    "main_subject": "科学",
                    "related_subjects": [],
                }
            return {
                "objectives": {
                    "knowledge": "理解校园节水问题",
                    "process": "背景设定：周三午休，图书馆一楼走廊的节水展示区需要重新布置，后勤老师请同学们在两周内完成调查并给出改进方案，要求保留可核验的证据与可展示成果。\n行动主线：先调查，再分析，再形成改进方案并公开汇报。",
                    "emotion": "建立节水责任感",
                },
                "phases": [
                    {
                        "name": "阶段一",
                        "order": 1,
                        "steps": [
                            {
                                "name": "收集资料",
                                "description": "记录校园用水现状",
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
                                "description": "提交改进建议",
                                "checkpoints": [{"content": "提交方案草稿", "evidence_type": "document"}],
                            }
                        ],
                    },
                ],
                "rubric": {"dimensions": [{"name": "问题意识"}, {"name": "证据质量"}]},
            }

    def fake_build_prompt(ctx):
        captured["template_json"] = ctx.template_json
        return "system", "user"

    monkeypatch.setattr(assignments_api, "DeepSeekJSONClient", FakeLessonPlanClient)
    monkeypatch.setattr(assignments_api, "build_lesson_plan_prompt", fake_build_prompt)
    monkeypatch.setattr(assignments_api, "_get_template_phases", lambda _data: _make_large_template_phases())

    lesson_plan_path = tmp_path / "lesson-plan-large-template.txt"
    lesson_plan_path.write_text(
        "\n".join(
            [
                "教案名称：校园节水项目",
                "课题：校园节水项目",
                "初中七年级科学",
                "项目式作业",
                "调查学生节水行为并提出改进建议。",
            ]
        ),
        encoding="utf-8",
    )

    document = Document(
        filename="lesson-plan-large-template.txt",
        file_path=str(lesson_plan_path),
        mime_type="text/plain",
        parsing_status=ParsingStatus.READY,
        metadata_json={"subject_id": subject.id, "subject_name": subject.name},
        source="user",
    )
    session.add(document)
    session.commit()
    session.refresh(document)

    response = client.post(
        "/api/v2/assignments/from-lesson-plan",
        headers=_headers(teacher.id, teacher.role.value),
        json={"document_id": document.id},
    )

    assert response.status_code == 200
    assert json.loads(captured["template_json"])
    assert "template_json_truncated" in response.json()["meta"]["warnings"]


def test_from_lesson_plan_respects_explicitly_cleared_text_constraints(client, session, tmp_path, monkeypatch):
    try:
        teacher = _create_teacher(session, username="lesson_teacher_clear_text")
        subject = _create_subject(session, code="science_clear_text", name="科学")

        class FakeLessonPlanClient:
            def __init__(self, *_args, **_kwargs):
                self.is_available = True

            def predict_json(self, _system_prompt: str, user_prompt: str):
                if "提取字段" in user_prompt:
                    return {
                        "school_stage": "middle",
                        "grade": 7,
                        "assignment_type": "project",
                        "inquiry_depth": "intermediate",
                        "submission_mode": "phased",
                        "duration_weeks": 2,
                        "main_subject": "科学",
                        "related_subjects": ["语文"],
                    }
                return {
                    "objectives": {
                        "knowledge": "理解校园节水问题",
                        "process": "背景设定：教案里的原始背景\n行动主线：完成调查与方案设计",
                        "emotion": "建立节水责任感",
                    },
                    "phases": [
                        {
                            "name": "阶段一",
                            "order": 1,
                            "steps": [
                                {
                                    "name": "收集资料",
                                    "description": "记录校园用水现状",
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
                                    "description": "提交改进建议",
                                    "checkpoints": [{"content": "提交方案草稿", "evidence_type": "document"}],
                                }
                            ],
                        },
                    ],
                    "rubric": {"dimensions": [{"name": "问题意识"}, {"name": "证据质量"}]},
                }

        monkeypatch.setattr(assignments_api, "DeepSeekJSONClient", FakeLessonPlanClient)

        lesson_plan_path = tmp_path / "lesson-plan-clear-text.txt"
        lesson_plan_path.write_text(
            "\n".join(
                [
                    "教案名称：校园节水项目",
                    "课题：校园节水项目",
                    "初中七年级科学",
                    "项目式作业",
                    "调查学生节水行为并提出改进建议。",
                ]
            ),
            encoding="utf-8",
        )

        document = Document(
            filename="lesson-plan-clear-text.txt",
            file_path=str(lesson_plan_path),
            mime_type="text/plain",
            parsing_status=ParsingStatus.READY,
            metadata_json={"subject_id": subject.id, "subject_name": subject.name},
            source="user",
        )
        session.add(document)
        session.commit()
        session.refresh(document)

        response = client.post(
            "/api/v2/assignments/from-lesson-plan",
            headers=_headers(teacher.id, teacher.role.value),
            json={
                "document_id": document.id,
                "title": "",
                "topic": "",
                "description": "",
                "background_setting": "",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == ""
        assert data["topic"] == ""
        assert data["description"] == ""
        assert data["objectives_json"]["process"] == "行动主线：完成调查与方案设计"
    finally:
        get_settings.cache_clear()


def test_from_lesson_plan_uses_cleared_title_topic_in_prompt_context(client, session, tmp_path, monkeypatch):
    try:
        teacher = _create_teacher(session, username="lesson_teacher_clear_prompt_context")
        subject = _create_subject(session, code="science_clear_prompt_context", name="科学")
        captured: dict[str, str] = {}

        class FakeLessonPlanClient:
            def __init__(self, *_args, **_kwargs):
                self.is_available = True

            def predict_json(self, _system_prompt: str, user_prompt: str):
                if "提取字段" in user_prompt:
                    return {
                        "school_stage": "middle",
                        "grade": 7,
                        "assignment_type": "project",
                        "inquiry_depth": "intermediate",
                        "submission_mode": "phased",
                        "duration_weeks": 2,
                        "main_subject": "科学",
                        "related_subjects": [],
                    }
                return {
                    "objectives": {
                        "knowledge": "理解校园节水问题",
                        "process": "行动主线：完成调查与方案设计",
                        "emotion": "建立节水责任感",
                    },
                    "phases": [
                        {
                            "name": "阶段一",
                            "order": 1,
                            "steps": [
                                {
                                    "name": "收集资料",
                                    "description": "记录校园用水现状",
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
                                    "description": "提交改进建议",
                                    "checkpoints": [{"content": "提交方案草稿", "evidence_type": "document"}],
                                }
                            ],
                        },
                    ],
                    "rubric": {"dimensions": [{"name": "问题意识"}, {"name": "证据质量"}]},
                }

        def fake_build_prompt(ctx):
            captured["title"] = ctx.title
            captured["topic"] = ctx.topic
            captured["description"] = ctx.description
            captured["background_setting"] = ctx.background_setting
            return "system", "user"

        monkeypatch.setattr(assignments_api, "DeepSeekJSONClient", FakeLessonPlanClient)
        monkeypatch.setattr(assignments_api, "build_lesson_plan_prompt", fake_build_prompt)

        lesson_plan_path = tmp_path / "lesson-plan-clear-prompt-context.txt"
        lesson_plan_path.write_text(
            "\n".join(
                [
                    "教案名称：校园节水项目",
                    "课题：校园节水项目",
                    "初中七年级科学",
                    "项目式作业",
                    "调查学生节水行为并提出改进建议。",
                ]
            ),
            encoding="utf-8",
        )

        document = Document(
            filename="lesson-plan-clear-prompt-context.txt",
            file_path=str(lesson_plan_path),
            mime_type="text/plain",
            parsing_status=ParsingStatus.READY,
            metadata_json={"subject_id": subject.id, "subject_name": subject.name},
            source="user",
        )
        session.add(document)
        session.commit()
        session.refresh(document)

        response = client.post(
            "/api/v2/assignments/from-lesson-plan",
            headers=_headers(teacher.id, teacher.role.value),
            json={
                "document_id": document.id,
                "title": "",
                "topic": "",
                "description": "",
                "background_setting": "",
            },
        )

        assert response.status_code == 200
        assert captured["title"] == ""
        assert captured["topic"] == ""
        assert captured["description"] == ""
        assert captured["background_setting"] == ""
    finally:
        get_settings.cache_clear()


def test_from_lesson_plan_treats_null_text_constraints_as_omitted(client, session, tmp_path, monkeypatch):
    try:
        teacher = _create_teacher(session, username="lesson_teacher_null_text")
        subject = _create_subject(session, code="science_null_text", name="科学")

        class FakeLessonPlanClient:
            def __init__(self, *_args, **_kwargs):
                self.is_available = True

            def predict_json(self, _system_prompt: str, user_prompt: str):
                if "提取字段" in user_prompt:
                    return {
                        "school_stage": "middle",
                        "grade": 7,
                        "assignment_type": "project",
                        "inquiry_depth": "intermediate",
                        "submission_mode": "phased",
                        "duration_weeks": 2,
                        "main_subject": "科学",
                        "related_subjects": [],
                    }
                return {
                    "objectives": {
                        "knowledge": "理解校园节水问题",
                        "process": "背景设定：教案里的原始背景\n行动主线：完成调查与方案设计",
                        "emotion": "建立节水责任感",
                    },
                    "phases": [
                        {
                            "name": "阶段一",
                            "order": 1,
                            "steps": [
                                {
                                    "name": "收集资料",
                                    "description": "记录校园用水现状",
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
                                    "description": "提交改进建议",
                                    "checkpoints": [{"content": "提交方案草稿", "evidence_type": "document"}],
                                }
                            ],
                        },
                    ],
                    "rubric": {"dimensions": [{"name": "问题意识"}, {"name": "证据质量"}]},
                }

        monkeypatch.setattr(assignments_api, "DeepSeekJSONClient", FakeLessonPlanClient)

        lesson_plan_path = tmp_path / "lesson-plan-null-text.txt"
        lesson_plan_path.write_text(
            "\n".join(
                [
                    "教案名称：校园节水项目",
                    "课题：校园节水项目",
                    "初中七年级科学",
                    "项目式作业",
                    "调查学生节水行为并提出改进建议。",
                ]
            ),
            encoding="utf-8",
        )

        document = Document(
            filename="lesson-plan-null-text.txt",
            file_path=str(lesson_plan_path),
            mime_type="text/plain",
            parsing_status=ParsingStatus.READY,
            metadata_json={"subject_id": subject.id, "subject_name": subject.name},
            source="user",
        )
        session.add(document)
        session.commit()
        session.refresh(document)

        baseline_response = client.post(
            "/api/v2/assignments/from-lesson-plan",
            headers=_headers(teacher.id, teacher.role.value),
            json={"document_id": document.id},
        )
        assert baseline_response.status_code == 200
        baseline_data = baseline_response.json()

        response = client.post(
            "/api/v2/assignments/from-lesson-plan",
            headers=_headers(teacher.id, teacher.role.value),
            json={
                "document_id": document.id,
                "title": None,
                "topic": None,
                "description": None,
                "background_setting": None,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == baseline_data["title"]
        assert data["topic"] == baseline_data["topic"]
        assert data["description"] == baseline_data["description"]
        assert data["objectives_json"]["process"] == baseline_data["objectives_json"]["process"]
    finally:
        get_settings.cache_clear()


def test_from_lesson_plan_omits_null_text_constraints_from_prompt_context(client, session, tmp_path, monkeypatch):
    try:
        teacher = _create_teacher(session, username="lesson_teacher_null_prompt_context")
        subject = _create_subject(session, code="science_null_prompt_context", name="科学")
        captured: dict[str, str] = {}
        baseline_captured: dict[str, str] = {}

        class FakeLessonPlanClient:
            def __init__(self, *_args, **_kwargs):
                self.is_available = True

            def predict_json(self, _system_prompt: str, user_prompt: str):
                if "提取字段" in user_prompt:
                    return {
                        "school_stage": "middle",
                        "grade": 7,
                        "assignment_type": "project",
                        "inquiry_depth": "intermediate",
                        "submission_mode": "phased",
                        "duration_weeks": 2,
                        "main_subject": "科学",
                        "related_subjects": [],
                    }
                return {
                    "objectives": {
                        "knowledge": "理解校园节水问题",
                        "process": "行动主线：完成调查与方案设计",
                        "emotion": "建立节水责任感",
                    },
                    "phases": [
                        {
                            "name": "阶段一",
                            "order": 1,
                            "steps": [
                                {
                                    "name": "收集资料",
                                    "description": "记录校园用水现状",
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
                                    "description": "提交改进建议",
                                    "checkpoints": [{"content": "提交方案草稿", "evidence_type": "document"}],
                                }
                            ],
                        },
                    ],
                    "rubric": {"dimensions": [{"name": "问题意识"}, {"name": "证据质量"}]},
                }

        def fake_build_prompt(ctx):
            target = baseline_captured if not baseline_captured else captured
            target["title"] = ctx.title
            target["topic"] = ctx.topic
            target["description"] = ctx.description
            target["background_setting"] = ctx.background_setting
            return "system", "user"

        monkeypatch.setattr(assignments_api, "DeepSeekJSONClient", FakeLessonPlanClient)
        monkeypatch.setattr(assignments_api, "build_lesson_plan_prompt", fake_build_prompt)

        lesson_plan_path = tmp_path / "lesson-plan-null-prompt-context.txt"
        lesson_plan_path.write_text(
            "\n".join(
                [
                    "教案名称：校园节水项目",
                    "课题：校园节水项目",
                    "初中七年级科学",
                    "项目式作业",
                    "调查学生节水行为并提出改进建议。",
                ]
            ),
            encoding="utf-8",
        )

        document = Document(
            filename="lesson-plan-null-prompt-context.txt",
            file_path=str(lesson_plan_path),
            mime_type="text/plain",
            parsing_status=ParsingStatus.READY,
            metadata_json={"subject_id": subject.id, "subject_name": subject.name},
            source="user",
        )
        session.add(document)
        session.commit()
        session.refresh(document)

        baseline_response = client.post(
            "/api/v2/assignments/from-lesson-plan",
            headers=_headers(teacher.id, teacher.role.value),
            json={"document_id": document.id},
        )
        assert baseline_response.status_code == 200

        response = client.post(
            "/api/v2/assignments/from-lesson-plan",
            headers=_headers(teacher.id, teacher.role.value),
            json={
                "document_id": document.id,
                "title": None,
                "topic": None,
                "description": None,
                "background_setting": None,
            },
        )

        assert response.status_code == 200
        assert captured["title"] == baseline_captured["title"]
        assert captured["topic"] == baseline_captured["topic"]
        assert captured["description"] == baseline_captured["description"]
        assert captured["background_setting"] == baseline_captured["background_setting"]
    finally:
        get_settings.cache_clear()


def test_from_lesson_plan_null_main_subject_reverts_to_inferred_subject(client, session, tmp_path, monkeypatch):
    try:
        teacher = _create_teacher(session, username="lesson_teacher_null_subject")
        subject = _create_subject(session, code="science_null_subject", name="科学")

        class FakeLessonPlanClient:
            def __init__(self, *_args, **_kwargs):
                self.is_available = True

            def predict_json(self, _system_prompt: str, user_prompt: str):
                if "提取字段" in user_prompt:
                    return {
                        "school_stage": "middle",
                        "grade": 7,
                        "assignment_type": "project",
                        "inquiry_depth": "intermediate",
                        "submission_mode": "phased",
                        "duration_weeks": 2,
                        "main_subject": "科学",
                        "related_subjects": [],
                    }
                return {
                    "objectives": {
                        "knowledge": "理解校园节水问题",
                        "process": "行动主线：完成调查与方案设计",
                        "emotion": "建立节水责任感",
                    },
                    "phases": [
                        {
                            "name": "阶段一",
                            "order": 1,
                            "steps": [
                                {
                                    "name": "收集资料",
                                    "description": "记录校园用水现状",
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
                                    "description": "提交改进建议",
                                    "checkpoints": [{"content": "提交方案草稿", "evidence_type": "document"}],
                                }
                            ],
                        },
                    ],
                    "rubric": {"dimensions": [{"name": "问题意识"}, {"name": "证据质量"}]},
                }

        monkeypatch.setattr(assignments_api, "DeepSeekJSONClient", FakeLessonPlanClient)

        lesson_plan_path = tmp_path / "lesson-plan-null-subject.txt"
        lesson_plan_path.write_text(
            "\n".join(
                [
                    "教案名称：校园节水项目",
                    "课题：校园节水项目",
                    "初中七年级科学",
                    "项目式作业",
                    "调查学生节水行为并提出改进建议。",
                ]
            ),
            encoding="utf-8",
        )

        document = Document(
            filename="lesson-plan-null-subject.txt",
            file_path=str(lesson_plan_path),
            mime_type="text/plain",
            parsing_status=ParsingStatus.READY,
            metadata_json={"subject_id": subject.id, "subject_name": subject.name},
            source="user",
        )
        session.add(document)
        session.commit()
        session.refresh(document)

        response = client.post(
            "/api/v2/assignments/from-lesson-plan",
            headers=_headers(teacher.id, teacher.role.value),
            json={
                "document_id": document.id,
                "main_subject_id": None,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["main_subject_id"] == subject.id
        assert data["title"] == "校园节水项目"
    finally:
        get_settings.cache_clear()


def test_from_lesson_plan_preserves_touched_duration_weeks(client, session, tmp_path, monkeypatch):
    try:
        teacher = _create_teacher(session, username="lesson_teacher_duration_weeks")
        subject = _create_subject(session, code="science_duration_weeks", name="科学")

        class FakeLessonPlanClient:
            def __init__(self, *_args, **_kwargs):
                self.is_available = True

            def predict_json(self, _system_prompt: str, user_prompt: str):
                if "提取字段" in user_prompt:
                    return {
                        "school_stage": "middle",
                        "grade": 7,
                        "assignment_type": "project",
                        "inquiry_depth": "intermediate",
                        "submission_mode": "phased",
                        "duration_weeks": 3,
                        "main_subject": "科学",
                        "related_subjects": [],
                    }
                return {
                    "objectives": {
                        "knowledge": "理解校园节水问题",
                        "process": "行动主线：完成调查与方案设计",
                        "emotion": "建立节水责任感",
                    },
                    "phases": [
                        {
                            "name": "阶段一",
                            "order": 1,
                            "steps": [
                                {
                                    "name": "收集资料",
                                    "description": "记录校园用水现状",
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
                                    "description": "提交改进建议",
                                    "checkpoints": [{"content": "提交方案草稿", "evidence_type": "document"}],
                                }
                            ],
                        },
                    ],
                    "rubric": {"dimensions": [{"name": "问题意识"}, {"name": "证据质量"}]},
                }

        monkeypatch.setattr(assignments_api, "DeepSeekJSONClient", FakeLessonPlanClient)

        lesson_plan_path = tmp_path / "lesson-plan-duration-weeks.txt"
        lesson_plan_path.write_text(
            "\n".join(
                [
                    "教案名称：校园节水项目",
                    "课题：校园节水项目",
                    "初中七年级科学",
                    "项目式作业",
                    "周期：3周",
                    "调查学生节水行为并提出改进建议。",
                ]
            ),
            encoding="utf-8",
        )

        document = Document(
            filename="lesson-plan-duration-weeks.txt",
            file_path=str(lesson_plan_path),
            mime_type="text/plain",
            parsing_status=ParsingStatus.READY,
            metadata_json={"subject_id": subject.id, "subject_name": subject.name},
            source="user",
        )
        session.add(document)
        session.commit()
        session.refresh(document)

        response = client.post(
            "/api/v2/assignments/from-lesson-plan",
            headers=_headers(teacher.id, teacher.role.value),
            json={
                "document_id": document.id,
                "duration_weeks": 5,
            },
        )

        assert response.status_code == 200
        assert response.json()["duration_weeks"] == 5
    finally:
        get_settings.cache_clear()


def test_from_lesson_plan_rejects_practical_subtype_without_assignment_type(client, session, tmp_path):
    teacher = _create_teacher(session, username="lesson_teacher_practical_subtype_only")
    subject = _create_subject(session, code="science_practical_subtype_only", name="科学")
    lesson_plan_path = tmp_path / "lesson-plan-practical-subtype-only.txt"
    lesson_plan_path.write_text("初中七年级科学教案", encoding="utf-8")

    document = Document(
        filename="lesson-plan-practical-subtype-only.txt",
        file_path=str(lesson_plan_path),
        mime_type="text/plain",
        parsing_status=ParsingStatus.READY,
        metadata_json={"subject_id": subject.id, "subject_name": subject.name},
        source="user",
    )
    session.add(document)
    session.commit()
    session.refresh(document)

    response = client.post(
        "/api/v2/assignments/from-lesson-plan",
        headers=_headers(teacher.id, teacher.role.value),
        json={
            "document_id": document.id,
            "practical_subtype": "visit",
        },
    )

    assert response.status_code == 422
    assert "作业类型" in response.text


def test_from_lesson_plan_rejects_inquiry_subtype_without_assignment_type(client, session, tmp_path):
    teacher = _create_teacher(session, username="lesson_teacher_inquiry_subtype_only")
    subject = _create_subject(session, code="science_inquiry_subtype_only", name="科学")
    lesson_plan_path = tmp_path / "lesson-plan-inquiry-subtype-only.txt"
    lesson_plan_path.write_text("初中七年级科学教案", encoding="utf-8")

    document = Document(
        filename="lesson-plan-inquiry-subtype-only.txt",
        file_path=str(lesson_plan_path),
        mime_type="text/plain",
        parsing_status=ParsingStatus.READY,
        metadata_json={"subject_id": subject.id, "subject_name": subject.name},
        source="user",
    )
    session.add(document)
    session.commit()
    session.refresh(document)

    response = client.post(
        "/api/v2/assignments/from-lesson-plan",
        headers=_headers(teacher.id, teacher.role.value),
        json={
            "document_id": document.id,
            "inquiry_subtype": "survey",
        },
    )

    assert response.status_code == 422
    assert "作业类型" in response.text
