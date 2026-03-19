from fastapi.testclient import TestClient

def test_register_student(client: TestClient):
    response = client.post(
        "/api/v2/auth/register",
        json={
            "username": "student1",
            "password": "password123",
            "name": "Test Student",
            "role": "student",
            "grade": 7,
            "class_name": "1"
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "student1"
    assert "id" in data
    assert data["role"] == "student"

def test_register_teacher(client: TestClient):
    response = client.post(
        "/api/v2/auth/register",
        json={
            "username": "teacher1",
            "password": "password123",
            "name": "Test Teacher",
            "role": "teacher"
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "teacher1"
    assert data["role"] == "teacher"

def test_login(client: TestClient):
    # First register
    client.post(
        "/api/v2/auth/register",
        json={
            "username": "user1",
            "password": "password123",
            "name": "User One",
            "role": "student",
            "grade": 7,
            "class_name": "1"
        },
    )
    
    # Then login
    response = client.post(
        "/api/v2/auth/login",
        data={
            "username": "user1",
            "password": "password123"
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_invalid_password(client: TestClient):
    # First register
    client.post(
        "/api/v2/auth/register",
        json={
            "username": "user2",
            "password": "password123",
            "name": "User Two",
            "role": "student",
            "grade": 7,
            "class_name": "1"
        },
    )
    
    # Then login with wrong password
    response = client.post(
        "/api/v2/auth/login",
        data={
            "username": "user2",
            "password": "wrongpassword"
        },
    )
    assert response.status_code == 401
