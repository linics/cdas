from fastapi.testclient import TestClient

from app.models.assignment import Assignment
from app.models.enums import AssignmentType, SchoolStage, SubmissionMode, SubmissionStatus
from app.models.subject import Subject
from app.models.submission import Submission


def _register_and_login(client: TestClient, username: str = "student1"):
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
    user_id = register_resp.json()["id"]

    login_resp = client.post(
        "/api/v2/auth/login",
        data={"username": username, "password": "password123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return user_id, token


def test_submit_returns_next_submission_id(client: TestClient, session):
    user_id, token = _register_and_login(client)

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
        phases_json=[{"name": "P1"}, {"name": "P2"}],
        created_by=user_id,
        is_published=True,
    )
    session.add(assignment)
    session.commit()

    submission = Submission(
        assignment_id=assignment.id,
        student_id=user_id,
        phase_index=0,
        content_json={"text": "draft"},
        attachments_json=[],
        checkpoints_json={},
        status=SubmissionStatus.DRAFT,
    )
    session.add(submission)
    session.commit()

    resp = client.post(
        f"/api/v2/submissions/{submission.id}/submit",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["next_submission_id"] is not None

    resp2 = client.post(
        f"/api/v2/submissions/{submission.id}/submit",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["next_submission_id"] == data["next_submission_id"]
