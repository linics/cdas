import json
import os
import random
import string
import time

import requests


def _resolve_base_url() -> str:
    raw = (
        os.getenv("CDAS_API_BASE_URL")
        or os.getenv("VITE_API_BASE_URL")
        or "http://127.0.0.1:8000"
    ).strip()
    return raw.rstrip("/")


BASE = _resolve_base_url()


def expect(resp, status_codes, label):
    if isinstance(status_codes, int):
        status_codes = {status_codes}
    else:
        status_codes = set(status_codes)
    if resp.status_code not in status_codes:
        raise RuntimeError(
            f"{label} failed: status={resp.status_code}, body={resp.text[:500]}"
        )
    return resp


def _assert_preview_meta(meta: dict[str, object], expected_source: str) -> None:
    required = {"source", "prompt_id", "prompt_version", "used_rag", "fallback_reason"}
    missing = sorted(required - set(meta))
    if missing:
        raise RuntimeError(f"preview meta missing keys: {missing}")
    if meta.get("source") != expected_source:
        raise RuntimeError(
            f"preview meta source mismatch: {meta.get('source')} != {expected_source}"
        )
    if not isinstance(meta.get("prompt_id"), str) or not meta.get("prompt_id"):
        raise RuntimeError("preview meta prompt_id missing")
    if not isinstance(meta.get("prompt_version"), str) or not meta.get("prompt_version"):
        raise RuntimeError("preview meta prompt_version missing")


def _assert_evaluation_readback(resp_json: dict[str, object], expected_score: int) -> None:
    evaluations = resp_json.get("evaluations") or []
    if not evaluations:
        raise RuntimeError("no evaluations returned for submission")
    first = evaluations[0]
    if not isinstance(first, dict):
        raise RuntimeError("evaluation payload malformed")
    if first.get("score_numeric") != expected_score:
        raise RuntimeError(
            f"teacher evaluation score mismatch: {first.get('score_numeric')} != {expected_score}"
        )


def main():
    suffix = f"{int(time.time())}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=4))}"
    teacher_username = f"teacher_{suffix}"
    student_username = f"student_{suffix}"
    password = "Passw0rd!"

    summary: dict[str, object] = {
        "base": BASE,
        "run_id": suffix,
        "teacher_username": teacher_username,
        "student_username": student_username,
    }

    resp = requests.get(f"{BASE}/health", timeout=10)
    expect(resp, 200, "health")
    summary["health"] = resp.json()

    teacher_register_payload = {
        "username": teacher_username,
        "password": password,
        "role": "teacher",
        "name": f"Teacher-{suffix[-4:]}",
    }
    student_register_payload = {
        "username": student_username,
        "password": password,
        "role": "student",
        "name": f"Student-{suffix[-4:]}",
        "grade": 7,
        "class_name": "1A",
    }

    resp = requests.post(f"{BASE}/api/v2/auth/register", json=teacher_register_payload, timeout=15)
    expect(resp, 200, "register teacher")
    summary["teacher_register"] = resp.json()

    resp = requests.post(f"{BASE}/api/v2/auth/register", json=student_register_payload, timeout=15)
    expect(resp, 200, "register student")
    summary["student_register"] = resp.json()

    resp = requests.post(
        f"{BASE}/api/v2/auth/login",
        data={"username": teacher_username, "password": password},
        timeout=15,
    )
    expect(resp, 200, "login teacher")
    teacher_token = resp.json().get("access_token")
    if not teacher_token:
        raise RuntimeError("teacher token missing")

    resp = requests.post(
        f"{BASE}/api/v2/auth/login",
        data={"username": student_username, "password": password},
        timeout=15,
    )
    expect(resp, 200, "login student")
    student_token = resp.json().get("access_token")
    if not student_token:
        raise RuntimeError("student token missing")

    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
    student_headers = {"Authorization": f"Bearer {student_token}"}

    resp = requests.get(f"{BASE}/api/v2/auth/me", headers=teacher_headers, timeout=10)
    expect(resp, 200, "teacher /me")
    summary["teacher_me"] = resp.json()

    resp = requests.get(f"{BASE}/api/v2/auth/me", headers=student_headers, timeout=10)
    expect(resp, 200, "student /me")
    summary["student_me"] = resp.json()

    resp = requests.get(f"{BASE}/api/v2/assignments/ai-status", headers=teacher_headers, timeout=10)
    expect(resp, 200, "ai status")
    ai_status = resp.json()
    if "available" not in ai_status or "model" not in ai_status:
        raise RuntimeError(f"ai-status payload missing fields: {ai_status}")
    summary["ai_status"] = ai_status

    resp = requests.get(f"{BASE}/api/v2/subjects/", timeout=10)
    expect(resp, 200, "list subjects")
    subjects_data = resp.json()
    subjects = subjects_data.get("subjects", [])
    if not subjects:
        raise RuntimeError("subjects empty")

    middle_subjects = [s for s in subjects if s.get("middle_available")]
    selected_subjects = middle_subjects or subjects
    main_subject = selected_subjects[0]
    related_subject = selected_subjects[1] if len(selected_subjects) > 1 else None

    summary["subject_selection"] = {
        "main_subject": {
            "id": main_subject.get("id"),
            "code": main_subject.get("code"),
            "name": main_subject.get("name"),
        },
        "related_subject": {
            "id": related_subject.get("id"),
            "code": related_subject.get("code"),
            "name": related_subject.get("name"),
        }
        if related_subject
        else None,
        "subject_total": subjects_data.get("total"),
    }

    resp = requests.get(f"{BASE}/api/documents", timeout=15)
    expect(resp, 200, "list documents before")
    docs_before = resp.json()

    lesson_plan_filename = f"lesson-plan-{suffix}.txt"
    lesson_plan_content = (
        "教案名称：校园节水行动\n"
        "学段：初中\n"
        "年级：7年级\n"
        "主学科：科学\n"
        "融合学科：数学\n"
        "作业类型：项目式\n"
        "提交模式：一次性提交\n"
        "周期：3周\n"
        "教学过程：先调查校园用水数据，再完成分析与改进方案。\n"
    ).encode("utf-8")

    resp = requests.post(
        f"{BASE}/api/documents/upload",
        files={"file": (lesson_plan_filename, lesson_plan_content, "text/plain")},
        timeout=60,
    )
    expect(resp, 200, "upload lesson plan document")
    lesson_plan_upload = resp.json()
    lesson_plan_doc_id = lesson_plan_upload.get("document_id") or lesson_plan_upload.get("id")
    if not lesson_plan_doc_id:
        raise RuntimeError(f"lesson plan document id missing: {lesson_plan_upload}")

    resp = requests.post(
        f"{BASE}/api/v2/assignments/from-lesson-plan",
        headers=teacher_headers,
        json={"document_id": lesson_plan_doc_id},
        timeout=90,
    )
    expect(resp, 200, "from lesson plan")
    lesson_plan_generated = resp.json()
    if not lesson_plan_generated.get("title"):
        raise RuntimeError("lesson plan generation missing title")
    summary["lesson_plan_generation"] = {
        "document_id": lesson_plan_doc_id,
        "title": lesson_plan_generated.get("title"),
        "school_stage": lesson_plan_generated.get("school_stage"),
        "grade": lesson_plan_generated.get("grade"),
        "assignment_type": lesson_plan_generated.get("assignment_type"),
    }

    rubric_names = [
        "Problem Framing",
        "Evidence Quality",
        "Cross-Discipline Link",
        "Outcome Expression",
        "Reflection",
    ]

    assignment_payload = {
        "title": f"Integration Assignment-{suffix}",
        "topic": "Campus Water Saving Plan",
        "description": "Workflow integration verification",
        "school_stage": "middle",
        "grade": 7,
        "main_subject_id": main_subject["id"],
        "related_subject_ids": [related_subject["id"]] if related_subject else [],
        "assignment_type": "inquiry",
        "inquiry_subtype": "survey",
        "inquiry_depth": "intermediate",
        "submission_mode": "phased",
        "duration_weeks": 2,
        "deadline": None,
        "objectives_json": {
            "knowledge": "Understand campus water usage patterns",
            "process": "Collect evidence and draft actionable proposals",
            "emotion": "Build sustainability responsibility",
        },
        "phases_json": [
            {
                "name": "Problem Definition",
                "order": 1,
                "steps": [
                    {
                        "name": "Define Questions",
                        "description": "Identify researchable water-saving questions",
                        "checkpoints": [
                            {"content": "Question list submitted", "evidence_type": "document"}
                        ],
                    }
                ],
            },
            {
                "name": "Solution Design",
                "order": 2,
                "steps": [
                    {
                        "name": "Draft Solution",
                        "description": "Use data to propose feasible interventions",
                        "checkpoints": [
                            {"content": "Solution file submitted", "evidence_type": "document"}
                        ],
                    }
                ],
            },
        ],
        "rubric_json": {
            "dimensions": [
                {
                    "name": name,
                    "levels": {
                        "excellent": "Excellent",
                        "good": "Good",
                        "pass": "Pass",
                        "improve": "Needs improvement",
                    },
                }
                for name in rubric_names
            ]
        },
    }

    resp = requests.post(
        f"{BASE}/api/v2/assignments/preview",
        headers=teacher_headers,
        params={"force_generate": "false"},
        json=assignment_payload,
        timeout=20,
    )
    expect(resp, 200, "assignment preview")
    preview = resp.json()
    preview_meta = preview.get("meta")
    if not isinstance(preview_meta, dict):
        raise RuntimeError(f"preview meta missing: {preview}")
    _assert_preview_meta(preview_meta, expected_source="manual_merge")
    if len(preview.get("phases_json") or []) < 2:
        raise RuntimeError("preview phases too short")
    if len((preview.get("rubric_json") or {}).get("dimensions") or []) < 2:
        raise RuntimeError("preview rubric too short")
    summary["assignment_preview"] = {
        "meta": preview_meta,
        "phase_count": len(preview.get("phases_json") or []),
        "rubric_dimension_count": len((preview.get("rubric_json") or {}).get("dimensions") or []),
    }

    resp = requests.post(
        f"{BASE}/api/v2/assignments/",
        headers=teacher_headers,
        json=assignment_payload,
        timeout=20,
    )
    expect(resp, 201, "create assignment")
    assignment = resp.json()
    assignment_id = assignment["id"]
    summary["assignment_created"] = {
        "id": assignment_id,
        "title": assignment.get("title"),
        "is_published": assignment.get("is_published"),
        "phase_count": len(assignment.get("phases_json") or []),
    }

    resp = requests.post(
        f"{BASE}/api/v2/assignments/{assignment_id}/publish",
        headers=teacher_headers,
        timeout=15,
    )
    expect(resp, 200, "publish assignment")
    published_assignment = resp.json()
    summary["assignment_published"] = {
        "id": published_assignment.get("id"),
        "is_published": published_assignment.get("is_published"),
    }

    resp = requests.get(
        f"{BASE}/api/v2/assignments/",
        headers=student_headers,
        params={"published_only": "true", "page": 1, "page_size": 100},
        timeout=15,
    )
    expect(resp, 200, "student list assignments")
    student_assignments = resp.json().get("assignments", [])
    visible = any(item.get("id") == assignment_id for item in student_assignments)
    if not visible:
        raise RuntimeError("published assignment not visible to student")
    summary["student_assignment_visibility"] = {
        "visible": visible,
        "student_assignment_total": len(student_assignments),
    }

    resp = requests.post(
        f"{BASE}/api/v2/submissions/",
        headers=student_headers,
        json={
            "assignment_id": assignment_id,
            "phase_index": 0,
            "content_json": {"text": "Draft submission content"},
            "checkpoints_json": {"Question list submitted": True},
        },
        timeout=15,
    )
    expect(resp, 201, "create submission")
    submission = resp.json()
    submission_id = submission["id"]
    summary["submission_created"] = {
        "id": submission_id,
        "status": submission.get("status"),
        "phase_index": submission.get("phase_index"),
    }

    resp = requests.put(
        f"{BASE}/api/v2/submissions/{submission_id}",
        headers=student_headers,
        json={
            "content_json": {"text": "Updated submission with evidence"},
            "attachments_json": [
                {
                    "filename": "research-sheet",
                    "url": "https://example.com/research",
                    "type": "link",
                }
            ],
            "checkpoints_json": {"Question list submitted": True},
        },
        timeout=15,
    )
    expect(resp, 200, "update submission")
    updated_submission = resp.json()
    summary["submission_updated"] = {
        "id": updated_submission.get("id"),
        "status": updated_submission.get("status"),
        "attachment_count": len(updated_submission.get("attachments_json") or []),
    }

    attachment_filename = f"submission-note-{suffix}.txt"
    attachment_content = (
        "附件证据：记录了校园洗手池用水高峰时段，并附上了改进建议。\n"
        "关键发现：午间高峰有明显浪费。\n"
    ).encode("utf-8")
    resp = requests.post(
        f"{BASE}/api/v2/submissions/{submission_id}/attachments/upload",
        headers=student_headers,
        files={"file": (attachment_filename, attachment_content, "text/plain")},
        timeout=60,
    )
    expect(resp, 200, "upload submission attachment")
    attachment_data = resp.json()
    if attachment_data.get("parsing_status") != "ready":
        raise RuntimeError(f"submission attachment not ready: {attachment_data}")
    summary["submission_attachment_upload"] = {
        "attachment_id": attachment_data.get("attachment_id"),
        "filename": attachment_data.get("filename"),
        "parsing_status": attachment_data.get("parsing_status"),
    }

    resp = requests.post(
        f"{BASE}/api/v2/submissions/{submission_id}/submit",
        headers=student_headers,
        timeout=15,
    )
    expect(resp, 200, "submit submission")
    submitted = resp.json()
    next_submission_id = submitted.get("next_submission_id")
    summary["submission_submitted"] = {
        "id": submitted.get("id"),
        "status": submitted.get("status"),
        "next_submission_id": next_submission_id,
    }
    if not next_submission_id:
        raise RuntimeError("next_submission_id missing for phased assignment")

    resp = requests.get(
        f"{BASE}/api/v2/submissions/{next_submission_id}",
        headers=student_headers,
        timeout=15,
    )
    expect(resp, 200, "get next phase submission")
    next_sub = resp.json()
    summary["next_phase_submission"] = {
        "id": next_sub.get("id"),
        "phase_index": next_sub.get("phase_index"),
        "status": next_sub.get("status"),
    }

    resp = requests.get(
        f"{BASE}/api/v2/submissions/assignment/{assignment_id}",
        headers=teacher_headers,
        timeout=15,
    )
    expect(resp, 200, "teacher list assignment submissions")
    teacher_submissions = resp.json().get("submissions", [])
    submitted_items = [s for s in teacher_submissions if s.get("status") == "submitted"]
    if not submitted_items:
        raise RuntimeError("teacher cannot find submitted submission")
    submission_for_grade = submitted_items[0]
    summary["teacher_submission_list"] = {
        "total": len(teacher_submissions),
        "submitted_count": len(submitted_items),
    }

    teacher_eval_payload = {
        "submission_id": submission_for_grade["id"],
        "score_numeric": 3,
        "dimension_scores_json": {name: 3 for name in rubric_names},
        "feedback": "Good evidence and feasible proposal. Add cost estimation.",
    }
    resp = requests.post(
        f"{BASE}/api/v2/evaluations/teacher",
        headers=teacher_headers,
        json=teacher_eval_payload,
        timeout=15,
    )
    expect(resp, 200, "teacher evaluation")
    teacher_eval = resp.json()
    summary["teacher_evaluation"] = {
        "id": teacher_eval.get("id"),
        "score_numeric": teacher_eval.get("score_numeric"),
        "score_level": teacher_eval.get("score_level"),
    }

    resp = requests.get(
        f"{BASE}/api/v2/evaluations/submission/{submission_for_grade['id']}",
        headers=teacher_headers,
        timeout=15,
    )
    expect(resp, 200, "teacher evaluation readback")
    eval_readback = resp.json()
    _assert_evaluation_readback(eval_readback, expected_score=3)
    summary["teacher_evaluation_readback"] = {
        "total": eval_readback.get("total"),
        "evaluations": len(eval_readback.get("evaluations") or []),
    }

    resp = requests.get(
        f"{BASE}/api/v2/evaluations/my-received",
        headers=student_headers,
        timeout=15,
    )
    expect(resp, 200, "student received evaluations")
    received = resp.json().get("evaluations", [])
    received_match = [ev for ev in received if ev.get("submission_id") == submission_for_grade["id"]]
    if not received_match:
        raise RuntimeError("student cannot view teacher evaluation")
    summary["student_feedback"] = {
        "total_received": len(received),
        "matched_submission_feedback": len(received_match),
    }

    for _ in range(5):
        resp = requests.get(f"{BASE}/api/documents/{lesson_plan_doc_id}", timeout=15)
        if resp.status_code == 200:
            break
        time.sleep(1)
    expect(resp, 200, "get uploaded document")
    doc_detail = resp.json()
    detail_status = (doc_detail.get("status") or doc_detail.get("parsing_status") or "").lower()
    if detail_status == "failed":
        raise RuntimeError(
            f"uploaded document indexing failed: {doc_detail.get('error_msg', 'unknown error')}"
        )

    resp = requests.get(f"{BASE}/api/documents", timeout=15)
    expect(resp, 200, "list documents after upload")
    docs_after_upload = resp.json()
    if not any(d.get("id") == lesson_plan_doc_id for d in docs_after_upload):
        raise RuntimeError("uploaded document not found in list")

    resp = requests.delete(f"{BASE}/api/documents/{lesson_plan_doc_id}", timeout=15)
    expect(resp, 200, "delete document")

    resp = requests.get(f"{BASE}/api/documents", timeout=15)
    expect(resp, 200, "list documents after delete")
    docs_after_delete = resp.json()
    if any(d.get("id") == doc_id for d in docs_after_delete):
        raise RuntimeError("document still exists after delete")

    summary["knowledge_base"] = {
        "docs_before": len(docs_before),
        "uploaded_document_id": lesson_plan_doc_id,
        "upload_status": lesson_plan_upload.get("status") or lesson_plan_upload.get("parsing_status"),
        "detail_status": detail_status,
        "docs_after_upload": len(docs_after_upload),
        "docs_after_delete": len(docs_after_delete),
    }

    summary["result"] = "PASS"
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
