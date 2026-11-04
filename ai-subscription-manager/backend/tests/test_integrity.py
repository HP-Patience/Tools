from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select
from uuid import uuid4
import sqlite3
from test_business import create_records, buy


def test_concurrent_same_submission(app, owner):
    from app.billing import transact
    from app.schemas import SaleInput
    from app.models import Sale, Service

    c, s, p = create_records(owner)
    data = SaleInput(
        customer_id=c["id"],
        product_id=p["id"],
        sold_on="2026-10-17",
        cost_fen=6000,
        price_fen=10000,
        submission_id=uuid4(),
        term_count=1,
        term_unit="month",
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: transact(app.state.db, data), range(2)))
    assert results[0]["id"] == results[1]["id"]
    with app.state.db.read() as db:
        assert len(list(db.scalars(select(Sale)))) == 1
        assert len(list(db.scalars(select(Service)))) == 1


def test_backup_restore_integrity(app, owner, tmp_path):
    from app.cli import backup

    c, s, p = create_records(owner)
    buy(owner, c, p)
    target = tmp_path / "backup.db"
    backup(app.state.db.path, target)
    with sqlite3.connect(target) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 1


def test_csrf_write_required(owner):
    token = owner.headers.pop("X-CSRFToken")
    assert owner.post("/api/customers/", json={"name": "unauthorized"}).status_code == 403
    owner.headers["X-CSRFToken"] = token
    assert owner.get("/api/customers/").json()["count"] == 0


def test_inactive_and_customer_mismatch(owner):
    c, s, p = create_records(owner)
    sale, data = buy(owner, c, p)
    other = owner.post("/api/customers/", json={"name": "其他客户"}).json()
    service = owner.get(f"/api/services/{sale['service_id']}/").json()
    wrong = {
        **data,
        "customer_id": other["id"],
        "expected_revision": service["revision"],
        "submission_id": str(uuid4()),
    }
    assert owner.post(f"/api/services/{service['id']}/renew/", json=wrong).status_code == 422
    owner.patch(f"/api/products/{p['id']}/", json={"is_active": False})
    data["submission_id"] = str(uuid4())
    assert owner.post("/api/sales/", json=data).status_code == 422


def test_login_limits_persist(client):
    csrf = client.get("/api/auth/csrf/").json()["csrfToken"]
    for _ in range(10):
        assert (
            client.post(
                "/api/auth/login/",
                json={"username": "owner", "password": "incorrect"},
                headers={"X-CSRFToken": csrf},
            ).status_code
            == 400
        )
    assert (
        client.post(
            "/api/auth/login/",
            json={"username": "owner", "password": "password12345"},
            headers={"X-CSRFToken": csrf},
        ).status_code
        == 429
    )


def test_invalid_date_filter_returns_validation(owner):
    assert owner.get("/api/sales/?sold_from=invalid").status_code == 422


def test_ops_backup_and_isolated_restore(app, owner, tmp_path):
    import subprocess, sys
    from pathlib import Path

    c, s, p = create_records(owner)
    buy(owner, c, p)
    root = Path(__file__).resolve().parents[2]
    folder = tmp_path / "snapshots"
    subprocess.run(
        [sys.executable, str(root / "ops/backup.py"), app.state.db.path, str(folder)],
        check=True,
        capture_output=True,
    )
    snapshot = next(folder.glob("*.sqlite3"))
    restored = tmp_path / "restored.db"
    subprocess.run(
        [sys.executable, str(root / "ops/restore.py"), str(snapshot), str(restored)],
        check=True,
        capture_output=True,
    )
    with sqlite3.connect(restored) as db:
        assert db.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 1
    rejected = subprocess.run(
        [sys.executable, str(root / "ops/restore.py"), str(snapshot), str(restored)],
        capture_output=True,
    )
    assert rejected.returncode != 0


def test_production_config_requires_https_and_tls():
    import pytest
    from pydantic import ValidationError
    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(production=True, app_url="http://example.com")
    with pytest.raises(ValidationError):
        Settings(
            production=True,
            app_url="https://example.com",
            mail_backend="smtp",
            smtp_starttls=False,
            smtp_ssl=False,
        )
