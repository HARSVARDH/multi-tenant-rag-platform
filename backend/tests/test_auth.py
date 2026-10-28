import uuid


def test_register_user_success(client):
    payload = {
        "email": "test@example.com",
        "password": "securepassword123",
        "full_name": "Test User",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    # Ensure ID is a valid UUID
    try:
        uuid.UUID(data["id"])
    except ValueError:
        pytest.fail("id is not a valid UUID")

    assert data["email"] == payload["email"]
    assert data["full_name"] == payload["full_name"]
    assert data["role"] == "user"
    assert "created_at" in data


def test_register_user_duplicate_email(client):
    payload = {
        "email": "duplicate@example.com",
        "password": "securepassword123",
        "full_name": "Test User",
    }
    # First registration
    response1 = client.post("/api/v1/auth/register", json=payload)
    assert response1.status_code == 201

    # Second registration with same email
    response2 = client.post("/api/v1/auth/register", json=payload)
    assert response2.status_code == 400
    assert response2.json()["detail"] == "Email already registered"


def test_login_user_success(client):
    register_payload = {
        "email": "login_test@example.com",
        "password": "securepassword123",
        "full_name": "Login Test User",
    }
    client.post("/api/v1/auth/register", json=register_payload)

    login_payload = {
        "email": register_payload["email"],
        "password": register_payload["password"],
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_form_success(client):
    register_payload = {
        "email": "form_test@example.com",
        "password": "securepassword123",
        "full_name": "Form Test User",
    }
    client.post("/api/v1/auth/register", json=register_payload)

    response = client.post(
        "/api/v1/auth/login/form",
        data={
            "username": register_payload["email"],
            "password": register_payload["password"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_user_incorrect_credentials(client):
    register_payload = {
        "email": "wrong_login@example.com",
        "password": "securepassword123",
        "full_name": "Wrong Login User",
    }
    client.post("/api/v1/auth/register", json=register_payload)

    login_payload = {
        "email": register_payload["email"],
        "password": "wrongpassword",
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_get_current_user_profile_success(client):
    register_payload = {
        "email": "me_test@example.com",
        "password": "securepassword123",
        "full_name": "Me Test User",
    }
    client.post("/api/v1/auth/register", json=register_payload)

    # Login to get token
    login_payload = {
        "email": register_payload["email"],
        "password": register_payload["password"],
    }
    login_response = client.post("/api/v1/auth/login", json=login_payload)
    token = login_response.json()["access_token"]

    # Access /me
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["email"] == register_payload["email"]
    assert data["full_name"] == register_payload["full_name"]


def test_get_current_user_profile_unauthorized(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401

    headers = {"Authorization": "Bearer invalidtoken123"}
    response2 = client.get("/api/v1/auth/me", headers=headers)
    assert response2.status_code == 401
