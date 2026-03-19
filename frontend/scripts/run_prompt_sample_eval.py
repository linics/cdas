import json
import os
import random
import statistics
import string
import time
from pathlib import Path

import requests


def resolve_base_url() -> str:
    raw = (
        os.getenv("CDAS_API_BASE_URL")
        or os.getenv("VITE_API_BASE_URL")
        or "http://127.0.0.1:8000"
    ).strip()
    return raw.rstrip("/")


BASE = resolve_base_url()


def wait_for_health(session: requests.Session, timeout_sec: int = 60) -> None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            resp = session.get(f"{BASE}/health", timeout=8)
            if resp.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1.5)
    raise RuntimeError("backend health check timeout")


def expect(resp: requests.Response, status_codes, label: str) -> requests.Response:
    if isinstance(status_codes, int):
        status_codes = {status_codes}
    else:
        status_codes = set(status_codes)
    if resp.status_code not in status_codes:
        raise RuntimeError(
            f"{label} failed: status={resp.status_code}, body={resp.text[:500]}"
        )
    return resp


def make_suffix() -> str:
    return f"{int(time.time())}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=4))}"


def register_teacher(session: requests.Session, suffix: str) -> str:
    username = f"prompt_eval_teacher_{suffix}"
    password = "Passw0rd!"
    expect(
        session.post(
            f"{BASE}/api/v2/auth/register",
            json={
                "username": username,
                "password": password,
                "role": "teacher",
                "name": f"PromptEval-{suffix[-4:]}",
            },
            timeout=20,
        ),
        200,
        "register teacher",
    )
    login = expect(
        session.post(
            f"{BASE}/api/v2/auth/login",
            data={"username": username, "password": password, "role": "teacher"},
            timeout=20,
        ),
        200,
        "login teacher",
    )
    token = login.json().get("access_token")
    if not token:
        raise RuntimeError("missing teacher token")
    return token


def list_subjects(session: requests.Session) -> list[dict]:
    resp = expect(session.get(f"{BASE}/api/v2/subjects/", timeout=15), 200, "list subjects")
    data = resp.json()
    subjects = data.get("subjects") or []
    if not subjects:
        raise RuntimeError("subjects are empty")
    return subjects


def choose_subjects(subjects: list[dict], school_stage: str) -> tuple[int, list[int]]:
    if school_stage == "primary":
        candidates = [s for s in subjects if s.get("primary_available")]
    else:
        candidates = [s for s in subjects if s.get("middle_available")]
    if not candidates:
        candidates = subjects
    main = candidates[0]["id"]
    related = [candidates[1]["id"]] if len(candidates) > 1 else []
    return main, related


def score_generated_payload(phases: list, rubric: dict) -> dict:
    phase_titles = []
    steps = []
    checkpoints = []
    for phase in phases or []:
        if not isinstance(phase, dict):
            continue
        phase_titles.append((phase.get("title") or phase.get("name") or "").strip())
        for step in phase.get("steps") or []:
            if not isinstance(step, dict):
                continue
            steps.append(step)
            for cp in step.get("checkpoints") or []:
                if isinstance(cp, dict):
                    checkpoints.append(cp)

    continuity = 1
    titled = [t for t in phase_titles if t]
    if len(titled) >= 3:
        continuity = 4
    if len(set(titled)) >= 4 and all(len(t) >= 4 for t in titled[:4]):
        continuity = 5

    actionable = 1
    rich_steps = [s for s in steps if (s.get("name") and s.get("description"))]
    if len(rich_steps) >= 4:
        actionable = 4
    if rich_steps and all(len((s.get("description") or "")) >= 12 for s in rich_steps[:4]):
        actionable = 5

    evidence = 1
    valid_types = {"text", "document", "image", "video", "confirm", "link"}
    valid_cps = [cp for cp in checkpoints if cp.get("content") and cp.get("evidence_type") in valid_types]
    if len(valid_cps) >= 4:
        evidence = 4
    if valid_cps and all(len((cp.get("content") or "")) >= 6 for cp in valid_cps[:4]):
        evidence = 5

    non_template = 3
    descs = [((s.get("description") or "").strip()) for s in steps if s.get("description")]
    if descs:
        uniq_ratio = len(set(descs)) / max(1, len(descs))
        if uniq_ratio >= 0.9:
            non_template = 5
        elif uniq_ratio >= 0.75:
            non_template = 4
        elif uniq_ratio < 0.5:
            non_template = 2

    rubric_dims = (rubric or {}).get("dimensions") or []
    edit_cost = 3
    if len(steps) >= 4 and len(rubric_dims) >= 5:
        edit_cost = 4
    if continuity >= 4 and actionable >= 4 and evidence >= 4 and len(rubric_dims) >= 5:
        edit_cost = 5

    return {
        "continuity": continuity,
        "actionability": actionable,
        "evidence": evidence,
        "non_template": non_template,
        "edit_cost": edit_cost,
    }


def build_preview_payload(case: dict, subjects: list[dict]) -> dict:
    main_subject_id, related_subject_ids = choose_subjects(subjects, case["school_stage"])
    return {
        "title": case["theme"],
        "topic": case["theme"],
        "description": case.get("description") or f"{case['theme']} classroom assignment generation",
        "school_stage": case["school_stage"],
        "grade": case["grade"],
        "main_subject_id": main_subject_id,
        "related_subject_ids": related_subject_ids,
        "document_id": None,
        "assignment_type": case["assignment_type"],
        "practical_subtype": "observation" if case["assignment_type"] == "practical" else None,
        "inquiry_subtype": "survey" if case["assignment_type"] == "inquiry" else None,
        "inquiry_depth": "intermediate",
        "submission_mode": "phased",
        "duration_weeks": 2,
        "deadline": None,
        "objectives_json": {},
        "phases_json": [],
        "rubric_json": {},
    }


def upload_lesson_plan(session: requests.Session, headers: dict) -> int:
    candidate = Path("docs/integration/reference-upload-task-guide-sample.docx")
    if not candidate.exists():
        raise RuntimeError(f"lesson plan sample not found: {candidate}")
    with candidate.open("rb") as file_obj:
        resp = expect(
            session.post(
                f"{BASE}/api/documents/upload",
                headers=headers,
                files={
                    "file": (
                        candidate.name,
                        file_obj.read(),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
                timeout=60,
            ),
            200,
            "upload lesson plan",
        )
    return resp.json()["document_id"]


def run() -> int:
    cases = [
        {"id": "C01", "path": "from-lesson-plan", "theme": "校园垃圾分类改进", "grade": 7, "school_stage": "middle", "assignment_type": "project"},
        {"id": "C02", "path": "from-lesson-plan", "theme": "社区老年人数字关怀", "grade": 8, "school_stage": "middle", "assignment_type": "inquiry"},
        {"id": "C03", "path": "from-lesson-plan", "theme": "本地水质微调查", "grade": 8, "school_stage": "middle", "assignment_type": "inquiry"},
        {"id": "C04", "path": "from-lesson-plan", "theme": "校园植物观察日记", "grade": 7, "school_stage": "middle", "assignment_type": "practical"},
        {"id": "C05", "path": "from-lesson-plan", "theme": "传统节日文化传播", "grade": 7, "school_stage": "middle", "assignment_type": "project"},
        {"id": "C06", "path": "preview", "theme": "厨余堆肥实验", "grade": 8, "school_stage": "middle", "assignment_type": "inquiry"},
        {"id": "C07", "path": "preview", "theme": "校园导览短视频", "grade": 7, "school_stage": "middle", "assignment_type": "practical"},
        {"id": "C08", "path": "preview", "theme": "绿色出行倡议", "grade": 8, "school_stage": "middle", "assignment_type": "project"},
        {"id": "C09", "path": "preview", "theme": "校园噪声治理建议", "grade": 9, "school_stage": "middle", "assignment_type": "inquiry"},
        {"id": "C10", "path": "preview", "theme": "班级阅读推广计划", "grade": 7, "school_stage": "middle", "assignment_type": "project"},
    ]

    summary = {
        "base": BASE,
        "run_id": make_suffix(),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cases": [],
    }

    with requests.Session() as session:
        wait_for_health(session)
        token = register_teacher(session, summary["run_id"])
        headers = {"Authorization": f"Bearer {token}"}
        subjects = list_subjects(session)
        lesson_plan_doc_id = upload_lesson_plan(session, headers)

        for case in cases:
            started = time.time()
            try:
                if case["path"] == "preview":
                    payload = build_preview_payload(case, subjects)
                    resp = expect(
                        session.post(
                            f"{BASE}/api/v2/assignments/preview",
                            headers=headers,
                            json=payload,
                            timeout=120,
                        ),
                        200,
                        f"preview {case['id']}",
                    )
                    data = resp.json()
                    objectives = data.get("objectives_json") or {}
                    phases = data.get("phases_json") or []
                    rubric = data.get("rubric_json") or {}
                else:
                    main_subject_id, related_subject_ids = choose_subjects(subjects, case["school_stage"])
                    resp = expect(
                        session.post(
                            f"{BASE}/api/v2/assignments/from-lesson-plan",
                            headers=headers,
                            json={
                                "document_id": lesson_plan_doc_id,
                                "school_stage": case["school_stage"],
                                "grade": case["grade"],
                                "main_subject_id": main_subject_id,
                                "related_subject_ids": related_subject_ids,
                                "assignment_type": case["assignment_type"],
                                "inquiry_depth": "intermediate",
                                "submission_mode": "phased",
                                "duration_weeks": 2,
                            },
                            timeout=150,
                        ),
                        200,
                        f"from-lesson-plan {case['id']}",
                    )
                    data = resp.json()
                    objectives = data.get("objectives_json") or {}
                    phases = data.get("phases_json") or []
                    rubric = data.get("rubric_json") or {}
            except Exception as exc:
                elapsed = round(time.time() - started, 2)
                summary["cases"].append(
                    {
                        "case_id": case["id"],
                        "path": case["path"],
                        "theme": case["theme"],
                        "elapsed_sec": elapsed,
                        "phase_count": 0,
                        "step_count": 0,
                        "rubric_dims": 0,
                        "objectives_keys": [],
                        "scores": {
                            "continuity": 1,
                            "actionability": 1,
                            "evidence": 1,
                            "non_template": 1,
                            "edit_cost": 1,
                        },
                        "error": str(exc),
                    }
                )
                continue

            elapsed = round(time.time() - started, 2)
            scores = score_generated_payload(phases, rubric)
            case_result = {
                "case_id": case["id"],
                "path": case["path"],
                "theme": case["theme"],
                "elapsed_sec": elapsed,
                "phase_count": len(phases),
                "step_count": sum(len((phase or {}).get("steps") or []) for phase in phases if isinstance(phase, dict)),
                "rubric_dims": len((rubric or {}).get("dimensions") or []),
                "objectives_keys": sorted((objectives or {}).keys()),
                "scores": scores,
            }
            summary["cases"].append(case_result)

    for metric in ("continuity", "actionability", "evidence", "non_template", "edit_cost"):
        values = [c["scores"][metric] for c in summary["cases"] if metric in c["scores"]]
        summary[f"avg_{metric}"] = round(statistics.mean(values), 2) if values else 0
    summary["avg_elapsed_sec"] = round(
        statistics.mean([c["elapsed_sec"] for c in summary["cases"]]),
        2,
    )

    out_dir = Path("docs/integration")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "issue-009-prompt-evaluation-results.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = out_dir / "issue-009-prompt-evaluation-results.md"
    lines = [
        "# ISSUE-009 Prompt Evaluation Results",
        "",
        f"- Run ID: `{summary['run_id']}`",
        f"- API Base: `{summary['base']}`",
        f"- Generated At: `{summary['generated_at']}`",
        f"- Avg Latency: `{summary['avg_elapsed_sec']}s`",
        f"- Avg Continuity: `{summary['avg_continuity']}`",
        f"- Avg Actionability: `{summary['avg_actionability']}`",
        f"- Avg Evidence: `{summary['avg_evidence']}`",
        f"- Avg Non-template: `{summary['avg_non_template']}`",
        f"- Avg Edit Cost: `{summary['avg_edit_cost']}`",
        "",
        "## Case Results",
        "",
        "| Case | Path | Theme | Latency(s) | Continuity | Actionability | Evidence | Non-template | Edit Cost |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for c in summary["cases"]:
        s = c["scores"]
        lines.append(
            f"| {c['case_id']} | {c['path']} | {c['theme']} | {c['elapsed_sec']} | {s['continuity']} | {s['actionability']} | {s['evidence']} | {s['non_template']} | {s['edit_cost']} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "json_report": str(json_path),
        "md_report": str(md_path),
        "avg_elapsed_sec": summary["avg_elapsed_sec"],
        "avg_continuity": summary["avg_continuity"],
        "avg_actionability": summary["avg_actionability"],
        "avg_evidence": summary["avg_evidence"],
        "avg_non_template": summary["avg_non_template"],
        "avg_edit_cost": summary["avg_edit_cost"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
