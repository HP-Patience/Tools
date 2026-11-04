def test_private_api_is_json_401(client):
    response = client.get("/api/customers/")
    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


def test_login_requires_csrf(client):
    assert (
        client.post(
            "/api/auth/login/", json={"username": "owner", "password": "password12345"}
        ).status_code
        == 403
    )


def test_login_rotation_and_logout(client):
    token = client.get("/api/auth/csrf/").json()["csrfToken"]
    old = client.cookies.get("session")
    response = client.post(
        "/api/auth/login/",
        json={"username": "owner", "password": "password12345"},
        headers={"X-CSRFToken": token},
    )
    assert response.status_code == 200
    assert client.cookies.get("session") != old
    assert client.get("/api/auth/me/").json()["user"]["username"] == "owner"
    token = client.get("/api/auth/csrf/").json()["csrfToken"]
    assert client.post("/api/auth/logout/", headers={"X-CSRFToken": token}).status_code == 204
    assert client.get("/api/auth/me/").status_code == 401


def test_foreign_origin_rejected(client):
    token = client.get("/api/auth/csrf/").json()["csrfToken"]
    response = client.post(
        "/api/auth/login/",
        json={"username": "owner", "password": "password12345"},
        headers={"X-CSRFToken": token, "Origin": "https://evil.example"},
    )
    assert response.status_code == 403


def test_no_public_registration(client):
    assert client.post("/api/auth/register/", json={}).status_code == 401
