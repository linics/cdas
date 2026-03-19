from fastapi.testclient import TestClient

from app.models.assignment import Assignment
from app.models.enums import AssignmentType, SchoolStage, SubmissionMode, SubmissionStatus
from app.models.subject import Subject
from app.models.submission import Submission


def _register_and_login_teacher(client: TestClient, username: str = "teacher1"):
    register_resp = client.post(
        "/api/v2/auth/register",
        json={
            "username": username,
            "password": "password123",
            "name": "Test Teacher",
            "role": "teacher",
        },
    )
    assert register_resp.status_code == 200
    teacher_id = register_resp.json()["id"]

    login_resp = client.post(
        "/api/v2/auth/login",
        data={"username": username, "password": "password123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return teacher_id, token


def _register_student(client: TestClient, username: str = "student1") -> int:
    register_resp = client.post(
        "/api/v2/auth/register",
        json={
            "username": username,
            "password": "password123",
            "name": "Test Student",
            "role": "student",
            "grade": 7,
            "class_name": "1",
        },
    )
    assert register_resp.status_code == 200
    return register_resp.json()["id"]


def test_teacher_evaluation_uses_numeric_only(client: TestClient, session):
    teacher_id, token = _register_and_login_teacher(client)
    student_id = _register_student(client, "student2")

    subject = Subject(code="test", name="Test", category="test")
    session.add(subject)
    session.commit()

    assignment = Assignment(
        title="Phase Assignment",
        topic="Topic",
        description="desc",
        school_stage=SchoolStage.PRIMARY,
        grade=1,
        main_subject_id=subject.id,
        assignment_type=AssignmentType.PROJECT,
        submission_mode=SubmissionMode.PHASED,
        phases_json=[{"name": "P1"}],
        created_by=teacher_id,
        is_published=True,
    )
    session.add(assignment)
    session.commit()

    submission = Submission(
        assignment_id=assignment.id,
        student_id=student_id,
        phase_index=0,
        content_json={"text": "draft"},
        attachments_json=[],
        checkpoints_json={},
        status=SubmissionStatus.SUBMITTED,
    )
    session.add(submission)
    session.commit()

    resp = client.post(
        "/api/v2/evaluations/teacher",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "submission_id": submission.id,
            "score_numeric": 4,
            "dimension_scores_json": {"问题与假设": 4},
            "feedback": "ok",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["score_numeric"] == 4
    assert data["score_level"] == "excellent"


def test_teacher_evaluation_rejects_invalid_score(client: TestClient, session):
    teacher_id, token = _register_and_login_teacher(client, "teacher2")
    student_id = _register_student(client, "student3")

    subject = Subject(code="test2", name="Test2", category="test")
    session.add(subject)
    session.commit()

    assignment = Assignment(
        title="Phase Assignment",
        topic="Topic",
        description="desc",
        school_stage=SchoolStage.PRIMARY,
        grade=1,
        main_subject_id=subject.id,
        assignment_type=AssignmentType.PROJECT,
        submission_mode=SubmissionMode.PHASED,
        phases_json=[{"name": "P1"}],
        created_by=teacher_id,
        is_published=True,
    )
    session.add(assignment)
    session.commit()

    submission = Submission(
        assignment_id=assignment.id,
        student_id=student_id,
        phase_index=0,
        content_json={"text": "draft"},
        attachments_json=[],
        checkpoints_json={},
        status=SubmissionStatus.SUBMITTED,
    )
    session.add(submission)
    session.commit()

    resp = client.post(
        "/api/v2/evaluations/teacher",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "submission_id": submission.id,
            "score_numeric": 9,
            "dimension_scores_json": {"问题与假设": 4},
            "feedback": "bad",
        },
    )
    assert resp.status_code == 400
