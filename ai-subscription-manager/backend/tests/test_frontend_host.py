from fastapi.testclient import TestClient


def test_built_frontend_and_spa_routes(tmp_path):
    from app.main import create_app
    from app.config import Settings

    frontend = tmp_path / "dist"
    frontend.mkdir()
    (frontend / "assets").mkdir()
    (frontend / "index.html").write_text("<html>subscription-workspace</html>")
    (frontend / "assets/app.js").write_text('console.log("test")')
    app = create_app(
        Settings(database_path=str(tmp_path / "db.sqlite"), frontend_dir=str(frontend))
    )
    with TestClient(app) as client:
        assert "subscription-workspace" in client.get("/").text
        response = client.get("/customers/42", headers={"Accept": "text/html"})
        assert response.status_code == 200 and "subscription-workspace" in response.text
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/assets/missing.js", headers={"Accept": "text/html"}).status_code == 404
        response = client.get("/api/missing", headers={"Accept": "text/html"})
        assert response.status_code == 404
        assert "application/json" in response.headers["content-type"]
