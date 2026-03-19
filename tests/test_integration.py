from fastapi.testclient import TestClient
import pytest

def get_auth_headers(client: TestClient, username: str, password: str):
    response = client.post(
        "/api/v2/auth/login",
        data={"username": username, "password": password},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_assignment_workflow(client: TestClient):
    # 1. Register Teacher
    client.post(
        "/api/v2/auth/register",
        json={
            "username": "teacher_main",
            "password": "password",
            "name": "Teacher Main",
            "role": "teacher"
        },
    )
    teacher_headers = get_auth_headers(client, "teacher_main", "password")

    # Initialize subjects
    client.post("/api/v2/subjects/init")

    # 2. Register Student
    client.post(
        "/api/v2/auth/register",
        json={
            "username": "student_main",
            "password": "password",
            "name": "Student Main",
            "role": "student",
            "grade": 7,
            "class_name": "1"
        },
    )
    student_headers = get_auth_headers(client, "student_main", "password")

    # 3. Teacher creates Main Subject (if needed) and Assignment
    # Check if subjects exist or create one. Assuming subjects are pre-seeded or we create one.
    # The API for creating subjects might be protected or not exist in v2 public API easily?
    # Let's check api/v2/subjects.py. 
    # If no subjects, assignment creation might fail unless we use existing ID (seeded 1-9).
    # We'll try using subject_id=1.
    
    assignment_payload = {
        "title": "Integration Test Assignment",
        "topic": "Testing",
        "school_stage": "middle",
        "grade": 7,
        "main_subject_id": 1,
        "assignment_type": "inquiry",
        "inquiry_depth": "basic",
        "submission_mode": "once",
        "duration_weeks": 1
    }
    
    response = client.post(
        "/api/v2/assignments/",
        json=assignment_payload,
        headers=teacher_headers
    )
    if response.status_code == 404: 
        # Subject not found? We might need to seed subjects.
        # But let's assume valid response for now or Assertion Error will tell us.
        pass
    
    assert response.status_code == 201, f"Create assignment failed: {response.text}"
    assignment_id = response.json()["id"]

    # 4. publish
    response = client.post(
        f"/api/v2/assignments/{assignment_id}/publish",
        headers=teacher_headers
    )
    assert response.status_code == 200

    # 5. Student lists assignments
    response = client.get(
        "/api/v2/assignments/",
        headers=student_headers
    )
    assert response.status_code == 200
    assignments = response.json()["assignments"]  # PaginatedResponse usually
    assert any(a["id"] == assignment_id for a in assignments)

    # 6. Student creates submission
    submission_payload = {
        "assignment_id": assignment_id,
        "content_json": {"text": "My submission content"},
        "phase_index": 0
    }
    response = client.post(
        "/api/v2/submissions/",
        json=submission_payload,
        headers=student_headers
    )
    assert response.status_code == 201
    submission_id = response.json()["id"]

    # 7. Student submits (finalizes)
    response = client.post(
        f"/api/v2/submissions/{submission_id}/submit",
        headers=student_headers
    )
    assert response.status_code == 200

    # 8. Teacher lists submissions
    response = client.get(
        f"/api/v2/submissions/assignment/{assignment_id}",
        headers=teacher_headers
    )
    assert response.status_code == 200
    submissions = response.json()["submissions"]
    assert any(s["id"] == submission_id for s in submissions)

    # 9. Teacher grades submission
    evaluation_payload = {
        "submission_id": submission_id,
        "score_numeric": 4,
        "score_level": "excellent",
        "dimension_scores_json": {"Creativity": 4},
        "feedback": "Good job",
        "evaluation_type": "teacher"
    }
    response = client.post(
        "/api/v2/evaluations/teacher",
        json=evaluation_payload,
        headers=teacher_headers
    )
    assert response.status_code == 200
    assert response.json()["score_numeric"] == 4
