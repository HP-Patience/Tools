from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete, select


@pytest.fixture
def fresh_app(app):
    from app.models import Owner

    with app.state.db.write() as db:
        db.execute(delete(Owner))
    return app


def csrf(client):
    return {"X-CSRFToken": client.get("/api/auth/csrf/").json()["csrfToken"]}


def payload(username="my-admin"):
    return {
        "username": username,
        "password": "my-private-password-123",
        "confirm_password": "my-private-password-123",
    }


def test_first_setup_logs_in_and_cannot_be_repeated(fresh_app):
    with TestClient(fresh_app) as c:
        assert c.get("/api/auth/status/").json() == {"needs_setup": True}
        old = c.cookies.get("session")
        response = c.post("/api/auth/setup/", json=payload(), headers=csrf(c))
        assert response.status_code == 201, response.text
        assert response.json()["user"]["username"] == "my-admin"
        assert c.cookies.get("session") != old
        assert c.get("/api/auth/me/").status_code == 200
        assert c.get("/api/auth/status/").json() == {"needs_setup": False}
        assert (
            c.post("/api/auth/setup/", json=payload("attacker"), headers=csrf(c)).status_code == 409
        )
        token = csrf(c)
        assert c.post("/api/auth/logout/", headers=token).status_code == 204
        response = c.post(
            "/api/auth/login/",
            json={"username": "my-admin", "password": "my-private-password-123"},
            headers=csrf(c),
        )
        assert response.status_code == 200


def test_existing_owner_cannot_be_overwritten(client, app):
    from app.models import Owner

    assert client.get("/api/auth/status/").json() == {"needs_setup": False}
    assert client.post("/api/auth/setup/", json=payload(), headers=csrf(client)).status_code == 409
    with app.state.db.read() as db:
        assert db.get(Owner, 1).username == "owner"


def test_setup_requires_csrf_and_password_confirmation(fresh_app):
    with TestClient(fresh_app) as c:
        assert c.post("/api/auth/setup/", json=payload()).status_code == 403
        token = csrf(c)
        assert (
            c.post(
                "/api/auth/setup/",
                json={**payload(), "confirm_password": "different-password-123"},
                headers=token,
            ).status_code
            == 422
        )
        assert (
            c.post(
                "/api/auth/setup/",
                json={"username": "admin", "password": "123", "confirm_password": "123"},
                headers=token,
            ).status_code
            == 422
        )
        assert c.get("/api/auth/status/").json()["needs_setup"]


def test_concurrent_setup_creates_only_one_owner(fresh_app):
    from app.models import Owner

    def attempt(name):
        with TestClient(fresh_app) as c:
            return c.post("/api/auth/setup/", json=payload(name), headers=csrf(c)).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(attempt, ["admin-first", "admin-second"]))
    assert sorted(codes) == [201, 409]
    with fresh_app.state.db.read() as db:
        assert len(list(db.scalars(select(Owner)))) == 1
