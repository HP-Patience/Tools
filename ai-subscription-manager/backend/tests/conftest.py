import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app(tmp_path):
    from app.main import create_app
    from app.config import Settings
    from app.models import Base, Owner
    from app.auth import hash_password

    instance = create_app(
        Settings(database_path=str(tmp_path / "test.db"), app_url="http://testserver")
    )
    Base.metadata.create_all(instance.state.db.engine)
    with instance.state.db.write() as db:
        db.add(Owner(id=1, username="owner", password_hash=hash_password("password12345")))
    yield instance
    instance.state.db.engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def owner(client):
    token = client.get("/api/auth/csrf/").json()["csrfToken"]
    result = client.post(
        "/api/auth/login/",
        json={"username": "owner", "password": "password12345"},
        headers={"X-CSRFToken": token},
    )
    assert result.status_code == 200
    token = client.get("/api/auth/csrf/").json()["csrfToken"]
    client.headers["X-CSRFToken"] = token
    return client
