"""Prepare stable demo data for the teacher-review recording flow."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from typing import Any

import requests


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_PASSWORD = "Passw0rd!"
DEFAULT_THEME = "校园节水行动"
DEFAULT_CLASS_NAME = "初一（3）班 Demo"
DEFAULT_GROUP_NAME = "节水调研组"
TIMEOUT_SECONDS = 20


@dataclass
class DemoUser:
    username: str
    password: str
    role: str
    name: str
    grade: int | None = None
    class_name: str | None = None


def resolve_base_url(raw: str | None) -> str:
    value = (
        raw
        or os.getenv("CDAS_API_BASE_URL")
        or os.getenv("VITE_API_BASE_URL")
        or DEFAULT_BASE_URL
    ).strip()
    return value.rstrip("/")


def expect(response: requests.Response, allowed: int | set[int], label: str) -> requests.Response:
    allowed_codes = {allowed} if isinstance(allowed, int) else set(allowed)
    if response.status_code not in allowed_codes:
        body = response.text[:500]
        raise RuntimeError(f"{label} failed: status={response.status_code}, body={body}")
    return response


def json_request(
    session: requests.Session,
    method: str,
    url: str,
    label: str,
    expected: int | set[int] = 200,
    **kwargs: Any,
) -> Any:
    response = session.request(method, url, timeout=TIMEOUT_SECONDS, **kwargs)
    expect(response, expected, label)
    if response.status_code == 204:
        return None
    return response.json()


def login(
    session: requests.Session,
    base_url: str,
    user: DemoUser,
) -> tuple[dict[str, str], dict[str, Any]]:
    response = session.post(
        f"{base_url}/api/v2/auth/login",
        data={
            "username": user.username,
            "password": user.password,
            "role": user.role,
        },
        timeout=TIMEOUT_SECONDS,
    )
    expect(response, 200, f"login {user.username}")
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = json_request(
        session,
        "GET",
        f"{base_url}/api/v2/auth/me",
        f"fetch current user {user.username}",
        headers=headers,
    )
    return headers, me


def ensure_user(
    session: requests.Session,
    base_url: str,
    user: DemoUser,
) -> tuple[dict[str, str], dict[str, Any]]:
    login_response = session.post(
        f"{base_url}/api/v2/auth/login",
        data={
            "username": user.username,
            "password": user.password,
            "role": user.role,
        },
        timeout=TIMEOUT_SECONDS,
    )
    if login_response.status_code == 200:
        return login(session, base_url, user)

    payload: dict[str, Any] = {
        "username": user.username,
        "password": user.password,
        "role": user.role,
        "name": user.name,
    }
    if user.grade is not None:
        payload["grade"] = user.grade
    if user.class_name:
        payload["class_name"] = user.class_name

    register_response = session.post(
        f"{base_url}/api/v2/auth/register",
        json=payload,
        timeout=TIMEOUT_SECONDS,
    )
    if register_response.status_code not in {200, 400}:
        expect(register_response, 200, f"register {user.username}")

    if register_response.status_code == 400 and "用户名已存在" not in register_response.text:
        expect(register_response, 200, f"register {user.username}")

    try:
        return login(session, base_url, user)
    except RuntimeError as exc:
        raise RuntimeError(
            f"Unable to reuse account {user.username}. "
            f"Use a new username or update the password. Detail: {exc}"
        ) from exc


def choose_subjects(session: requests.Session, base_url: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json_request(
        session,
        "GET",
        f"{base_url}/api/v2/subjects/",
        "list subjects",
        params={"stage": "middle"},
    )
    subjects = payload.get("subjects", [])
    if not subjects:
        raise RuntimeError("No subjects available. Seed subjects before preparing demo data.")

    middle_subjects = [item for item in subjects if item.get("middle_available")]
    if not middle_subjects:
        middle_subjects = subjects

    by_name = {item.get("name"): item for item in middle_subjects}

    def pick_one(preferred: list[str]) -> dict[str, Any]:
        for name in preferred:
            item = by_name.get(name)
            if item:
                return item
        return middle_subjects[0]

    main_subject = pick_one(["科学", "语文", "数学"])
    related: list[dict[str, Any]] = []
    for name in ["数学", "语文", "科学"]:
        item = by_name.get(name)
        if item and item["id"] != main_subject["id"]:
            related.append(item)
        if len(related) >= 2:
            break

    if not related:
        related = [item for item in middle_subjects if item["id"] != main_subject["id"]][:2]

    return main_subject, related


def ensure_classroom(
    session: requests.Session,
    base_url: str,
    teacher_headers: dict[str, str],
    class_name: str,
    class_grade: int,
) -> dict[str, Any]:
    payload = json_request(
        session,
        "GET",
        f"{base_url}/api/v2/classes/my",
        "list teacher classrooms",
        headers=teacher_headers,
    )
    classes = payload.get("classes", [])
    for item in classes:
        if item.get("name") == class_name and item.get("grade") == class_grade:
            return item

    return json_request(
        session,
        "POST",
        f"{base_url}/api/v2/classes/",
        "create classroom",
        expected=201,
        headers=teacher_headers,
        json={"name": class_name, "grade": class_grade},
    )


def ensure_student_joined(
    session: requests.Session,
    base_url: str,
    student_headers: dict[str, str],
    invite_code: str,
) -> None:
    json_request(
        session,
        "POST",
        f"{base_url}/api/v2/classes/join",
        "join classroom",
        headers=student_headers,
        json={"invite_code": invite_code},
    )


def ensure_group(
    session: requests.Session,
    base_url: str,
    teacher_headers: dict[str, str],
    class_id: int,
    group_name: str,
) -> dict[str, Any]:
    payload = json_request(
        session,
        "GET",
        f"{base_url}/api/v2/classes/{class_id}/groups",
        "list class groups",
        headers=teacher_headers,
    )
    groups = payload.get("groups", [])
    for group in groups:
        if group.get("name") == group_name:
            return group

    return json_request(
        session,
        "POST",
        f"{base_url}/api/v2/classes/{class_id}/groups",
        "create class group",
        expected=201,
        headers=teacher_headers,
        json={"name": group_name},
    )


def assign_student_to_group(
    session: requests.Session,
    base_url: str,
    teacher_headers: dict[str, str],
    class_id: int,
    group_id: int,
    student_id: int,
) -> None:
    json_request(
        session,
        "POST",
        f"{base_url}/api/v2/classes/{class_id}/groups/{group_id}/members",
        "assign class group member",
        headers=teacher_headers,
        json={"student_id": student_id},
    )


def build_assignment_payload(
    title: str,
    theme: str,
    main_subject: dict[str, Any],
    related_subjects: list[dict[str, Any]],
) -> dict[str, Any]:
    deadline = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    return {
        "title": title,
        "topic": "围绕校园节水提出跨学科改进方案",
        "description": "学生围绕校园真实用水场景开展观察、调查和表达，形成可执行的节水行动建议。",
        "school_stage": "middle",
        "grade": 7,
        "main_subject_id": main_subject["id"],
        "related_subject_ids": [item["id"] for item in related_subjects],
        "assignment_type": "inquiry",
        "inquiry_subtype": "survey",
        "inquiry_depth": "intermediate",
        "submission_mode": "phased",
        "duration_weeks": 2,
        "deadline": deadline,
        "objectives_json": {
            "knowledge": "理解校园日常用水场景，识别节水相关的科学与数据问题。",
            "process": f"背景设定：{theme}。通过观察、问卷和数据整理完成问题分析，并形成改进建议。",
            "emotion": "建立公共资源意识与校园改进行动责任感。",
        },
        "phases_json": [
            {
                "name": "问题界定",
                "order": 1,
                "title": "从校园真实现象发现可探究问题",
                "steps": [
                    {
                        "name": "观察校园用水场景",
                        "description": "记录容易出现浪费或高频用水的点位，并说明观察依据。",
                        "content": "从真实校园情境切入，先明确问题，再进入调查。",
                        "checkpoints": [
                            {
                                "content": "完成校园用水点位观察记录",
                                "evidence_type": "text",
                            }
                        ],
                    }
                ],
            },
            {
                "name": "数据采集与分析",
                "order": 2,
                "title": "用调查与统计支持判断",
                "steps": [
                    {
                        "name": "收集问卷与观察数据",
                        "description": "用简单统计方法整理学生或教师的用水反馈。",
                        "content": "把零散现象转化为可分析的数据。",
                        "checkpoints": [
                            {
                                "content": "提交一份问卷或统计表",
                                "evidence_type": "document",
                            }
                        ],
                    }
                ],
            },
            {
                "name": "方案表达",
                "order": 3,
                "title": "形成可执行的校园节水提案",
                "steps": [
                    {
                        "name": "输出节水行动建议",
                        "description": "结合观察和数据提出两条以上可执行改进方案。",
                        "content": "方案需要和问题、证据形成对应。",
                        "checkpoints": [
                            {
                                "content": "提交节水提案与理由说明",
                                "evidence_type": "document",
                            }
                        ],
                    }
                ],
            },
        ],
        "rubric_json": {
            "dimensions": [
                {
                    "name": "问题意识",
                    "levels": {
                        "excellent": "问题聚焦清晰，能准确界定校园用水情境。",
                        "good": "问题较明确，能说明观察依据。",
                        "pass": "问题基本成立，但边界不够清楚。",
                        "improve": "问题表述模糊，缺少具体情境。",
                    },
                },
                {
                    "name": "证据质量",
                    "levels": {
                        "excellent": "证据完整且来源清晰，能够支撑分析。",
                        "good": "证据较充分，基本能支撑结论。",
                        "pass": "证据有限，支撑作用一般。",
                        "improve": "证据不足或与问题关联弱。",
                    },
                },
                {
                    "name": "跨学科连接",
                    "levels": {
                        "excellent": "能把科学理解、数据整理与表达清晰结合。",
                        "good": "体现了基本的跨学科整合。",
                        "pass": "学科联系较弱但可以识别。",
                        "improve": "缺少跨学科关联。",
                    },
                },
                {
                    "name": "方案表达",
                    "levels": {
                        "excellent": "建议具体、可执行、表达清晰。",
                        "good": "建议基本完整，表达较清楚。",
                        "pass": "建议可理解，但可执行性一般。",
                        "improve": "建议笼统，表达不清楚。",
                    },
                },
            ]
        },
    }


def create_assignment(
    session: requests.Session,
    base_url: str,
    teacher_headers: dict[str, str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    assignment = json_request(
        session,
        "POST",
        f"{base_url}/api/v2/assignments/",
        "create assignment",
        expected=201,
        headers=teacher_headers,
        json=payload,
    )
    return json_request(
        session,
        "POST",
        f"{base_url}/api/v2/assignments/{assignment['id']}/publish",
        "publish assignment",
        headers=teacher_headers,
    )


def create_submitted_submission(
    session: requests.Session,
    base_url: str,
    student_headers: dict[str, str],
    assignment_id: int,
) -> dict[str, Any]:
    submission = json_request(
        session,
        "POST",
        f"{base_url}/api/v2/submissions/",
        "create submission",
        expected=201,
        headers=student_headers,
        json={
            "assignment_id": assignment_id,
            "phase_index": 0,
            "content_json": {
                "text": (
                    "我们先观察了教学楼饮水点、卫生间和食堂周边的用水情况，"
                    "发现中午和课间是高频用水时段。根据观察记录，我们计划继续通过问卷和"
                    "简单统计确认浪费现象出现的时间段和原因。"
                )
            },
            "attachments_json": [
                {
                    "filename": "节水观察记录.pdf",
                    "url": "https://example.com/cdas-demo-water-observation",
                    "type": "link",
                }
            ],
            "checkpoints_json": {
                "完成校园用水点位观察记录": True,
            },
        },
    )
    return json_request(
        session,
        "POST",
        f"{base_url}/api/v2/submissions/{submission['id']}/submit",
        "submit submission",
        headers=student_headers,
    )


def create_teacher_evaluation(
    session: requests.Session,
    base_url: str,
    teacher_headers: dict[str, str],
    submission_id: int,
) -> dict[str, Any]:
    return json_request(
        session,
        "POST",
        f"{base_url}/api/v2/evaluations/teacher",
        "create teacher evaluation",
        headers=teacher_headers,
        json={
            "submission_id": submission_id,
            "score_numeric": 3,
            "dimension_scores_json": {
                "问题意识": 3,
                "证据质量": 3,
                "跨学科连接": 3,
                "方案表达": 4,
            },
            "feedback": (
                "证据收集方向明确，已经形成问题意识和基本分析框架。"
                "下一步建议补充更具体的数据来源，并把节水建议和统计结果建立更清晰的对应关系。"
            ),
        },
    )


def build_backup_title(theme: str, run_id: str, stage_label: str) -> str:
    return f"{theme} · {stage_label} · {run_id}"


def print_summary(
    base_url: str,
    teacher: DemoUser,
    student: DemoUser,
    classroom: dict[str, Any],
    group: dict[str, Any],
    live_subjects: tuple[str, list[str]],
    backup_a: dict[str, Any],
    backup_b: dict[str, Any],
    backup_b_submission: dict[str, Any],
    backup_c: dict[str, Any],
    backup_c_submission: dict[str, Any],
) -> None:
    related_subjects = "、".join(live_subjects[1]) if live_subjects[1] else "无"
    print("=" * 72)
    print("CDAS demo data is ready")
    print("=" * 72)
    print(f"Base URL: {base_url}")
    print("")
    print("Teacher account")
    print(f"  username: {teacher.username}")
    print(f"  password: {teacher.password}")
    print("")
    print("Student account")
    print(f"  username: {student.username}")
    print(f"  password: {student.password}")
    print("")
    print("Classroom setup")
    print(f"  class name : {classroom['name']}")
    print(f"  invite code: {classroom['invite_code']}")
    print(f"  group name : {group['name']}")
    print("")
    print("Recommended live recording fields")
    print(f"  title           : {DEFAULT_THEME}")
    print("  topic           : 围绕校园节水提出跨学科改进方案")
    print("  school stage    : 初中")
    print("  grade           : 7 年级")
    print(f"  main subject    : {live_subjects[0]}")
    print(f"  related subjects: {related_subjects}")
    print("  assignment type : inquiry")
    print("  submission mode : phased")
    print("  duration        : 2 weeks")
    print("")
    print("Backup scenarios")
    print(f"  Backup A (published only) : /assignment/{backup_a['id']}  -> {backup_a['title']}")
    print(
        f"  Backup B (submitted)      : /assignment/{backup_b['id']}  -> {backup_b['title']}"
    )
    print(
        f"                               grading: /grading/{backup_b_submission['id']}"
    )
    print(f"  Backup C (graded)         : /assignment/{backup_c['id']}  -> {backup_c['title']}")
    print(
        f"                               grading: /grading/{backup_c_submission['id']}"
    )
    print("")
    print("Fallback guide")
    print("  if live creation/publish fails -> switch to Backup A")
    print("  if student submit fails        -> switch to Backup B")
    print("  if teacher grading fails       -> switch to Backup C")
    print("=" * 72)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare stable demo data for CDAS recording")
    parser.add_argument("--base-url", default=None, help="API base URL, defaults to local backend")
    parser.add_argument(
        "--teacher-username",
        default="demo_teacher",
        help="Teacher username used for the demo account",
    )
    parser.add_argument(
        "--student-username",
        default="demo_student",
        help="Student username used for the demo account",
    )
    parser.add_argument(
        "--password",
        default=DEFAULT_PASSWORD,
        help="Shared password for both demo accounts",
    )
    parser.add_argument(
        "--theme",
        default=DEFAULT_THEME,
        help="Theme used for backup assignments and live script suggestions",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_url = resolve_base_url(args.base_url)
    session = requests.Session()

    json_request(session, "GET", f"{base_url}/health", "health check")

    teacher_user = DemoUser(
        username=args.teacher_username,
        password=args.password,
        role="teacher",
        name="Demo Teacher",
    )
    student_user = DemoUser(
        username=args.student_username,
        password=args.password,
        role="student",
        name="Demo Student",
        grade=7,
        class_name="1班",
    )

    teacher_headers, _teacher_profile = ensure_user(session, base_url, teacher_user)
    student_headers, student_profile = ensure_user(session, base_url, student_user)

    main_subject, related_subjects = choose_subjects(session, base_url)
    classroom = ensure_classroom(
        session,
        base_url,
        teacher_headers,
        DEFAULT_CLASS_NAME,
        7,
    )
    ensure_student_joined(session, base_url, student_headers, classroom["invite_code"])
    group = ensure_group(
        session,
        base_url,
        teacher_headers,
        classroom["id"],
        DEFAULT_GROUP_NAME,
    )
    assign_student_to_group(
        session,
        base_url,
        teacher_headers,
        classroom["id"],
        group["id"],
        student_profile["id"],
    )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    backup_a = create_assignment(
        session,
        base_url,
        teacher_headers,
        build_assignment_payload(
            build_backup_title(args.theme, run_id, "备份A-已发布"),
            args.theme,
            main_subject,
            related_subjects,
        ),
    )

    backup_b = create_assignment(
        session,
        base_url,
        teacher_headers,
        build_assignment_payload(
            build_backup_title(args.theme, run_id, "备份B-已提交"),
            args.theme,
            main_subject,
            related_subjects,
        ),
    )
    backup_b_submission = create_submitted_submission(
        session,
        base_url,
        student_headers,
        backup_b["id"],
    )

    backup_c = create_assignment(
        session,
        base_url,
        teacher_headers,
        build_assignment_payload(
            build_backup_title(args.theme, run_id, "备份C-已评分"),
            args.theme,
            main_subject,
            related_subjects,
        ),
    )
    backup_c_submission = create_submitted_submission(
        session,
        base_url,
        student_headers,
        backup_c["id"],
    )
    create_teacher_evaluation(
        session,
        base_url,
        teacher_headers,
        backup_c_submission["id"],
    )

    print_summary(
        base_url=base_url,
        teacher=teacher_user,
        student=student_user,
        classroom=classroom,
        group=group,
        live_subjects=(
            main_subject["name"],
            [item["name"] for item in related_subjects],
        ),
        backup_a=backup_a,
        backup_b=backup_b,
        backup_b_submission=backup_b_submission,
        backup_c=backup_c,
        backup_c_submission=backup_c_submission,
    )


if __name__ == "__main__":
    main()
