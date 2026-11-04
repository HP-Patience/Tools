from datetime import date
from uuid import uuid4
import pytest


@pytest.mark.parametrize(
    "start,n,unit,expected",
    [
        ("2027-01-31", 1, "month", "2027-02-28"),
        ("2028-02-29", 1, "year", "2029-02-28"),
        ("2026-10-16", 2, "week", "2026-10-30"),
        ("2026-10-16", 7, "day", "2026-10-23"),
    ],
)
def test_dates(start, n, unit, expected):
    from app.calendar import add_term

    assert add_term(date.fromisoformat(start), n, unit).isoformat() == expected


def create_records(owner):
    def post(path, data):
        r = owner.post("/api/" + path + "/", json=data)
        assert r.status_code == 201, r.text
        return r.json()

    customer = post(
        "customers",
        {
            "name": "客户甲",
            "contacts": [
                {"kind": "wechat", "value": "wx-demo"},
                {"kind": "qq", "value": "123456"},
            ],
        },
    )
    supplier = post("suppliers", {"name": "供应商A", "url": "https://example.com"})
    product = post(
        "products",
        {
            "name": "ChatGPT Plus",
            "supplier_id": supplier["id"],
            "platform": "OpenAI",
            "plan": "Plus",
            "delivery": "代充",
            "cost_fen": 6000,
            "price_fen": 10000,
            "term_count": 1,
            "term_unit": "month",
        },
    )
    return customer, supplier, product


def buy(owner, customer, product, **kwargs):
    data = {
        "customer_id": customer["id"],
        "product_id": product["id"],
        "sold_on": "2026-10-17",
        "started_on": "2026-10-17",
        "cost_fen": 6000,
        "price_fen": 10000,
        "submission_id": str(uuid4()),
        "term_count": 1,
        "term_unit": "month",
    } | kwargs
    response = owner.post("/api/sales/", json=data)
    assert response.status_code == 201, response.text
    return response.json(), data


def test_multiple_services_and_snapshots(owner):
    c, s, p = create_records(owner)
    first, _ = buy(owner, c, p)
    second, _ = buy(owner, c, p)
    assert first["service_id"] != second["service_id"]
    owner.patch(f"/api/products/{p['id']}/", json={"cost_fen": 9000})
    old = owner.get(f"/api/sales/{first['id']}/").json()
    assert old["cost_fen"] == 6000
    assert old["snapshot"]["supplier_name"] == "供应商A"
    assert owner.get("/api/customers/?q=wx-demo").json()["count"] == 1


def test_repeat_purchase_and_conflict(owner):
    c, s, p = create_records(owner)
    sale, data = buy(owner, c, p)
    assert owner.post("/api/sales/", json=data).json()["id"] == sale["id"]
    data["price_fen"] = 12345
    assert owner.post("/api/sales/", json=data).status_code == 409
    assert owner.get("/api/sales/").json()["count"] == 1


def test_renewal_stale_version_and_duplicate(owner):
    c, s, p = create_records(owner)
    sale, data = buy(owner, c, p)
    service = owner.get(f"/api/services/{sale['service_id']}/").json()
    renewal = {
        **data,
        "sold_on": "2026-10-20",
        "submission_id": str(uuid4()),
        "expected_revision": service["revision"],
        "started_on": None,
    }
    path = f"/api/services/{service['id']}/renew/"
    r = owner.post(path, json=renewal)
    assert r.status_code == 201, r.text
    updated = owner.get(f"/api/services/{service['id']}/").json()
    assert updated["expires_on"] == "2026-12-17"
    assert owner.post(path, json=renewal).json()["id"] == r.json()["id"]
    renewal["submission_id"] = str(uuid4())
    assert owner.post(path, json=renewal).status_code == 409


def test_void_and_negative_profit(owner):
    c, s, p = create_records(owner)
    sale, _ = buy(owner, c, p, price_fen=5000)
    totals = owner.get("/api/dashboard/?month=2026-10").json()["totals"]
    assert totals["profit_fen"] == -1000
    service = owner.get(f"/api/services/{sale['service_id']}/").json()
    r = owner.post(
        f"/api/sales/{sale['id']}/void/",
        json={
            "reason": "录入错误",
            "expected_revision": service["revision"],
            "service_state": {
                "expires_on": None,
                "ended": True,
                "purchased_quota": "0",
            },
        },
    )
    assert r.status_code == 200, r.text
    assert owner.get("/api/dashboard/?month=2026-10").json()["totals"]["profit_fen"] == 0


def test_validation_and_archive(owner):
    c, s, p = create_records(owner)
    assert (
        owner.post(
            "/api/suppliers/", json={"name": "Bad", "url": "javascript:alert(1)"}
        ).status_code
        == 422
    )
    assert owner.post("/api/products/", json={**p, "price_fen": -1}).status_code == 422
    sale, _ = buy(owner, c, p)
    assert owner.delete(f"/api/products/{p['id']}/").status_code == 409
    assert owner.patch(f"/api/products/{p['id']}/", json={"is_active": False}).status_code == 200


def test_no_expiry_quota(owner):
    c, s, p = create_records(owner)
    sale, _ = buy(
        owner,
        c,
        p,
        term_count=None,
        term_unit=None,
        quota_amount="1.125",
        quota_unit="百万Token",
    )
    service = owner.get(f"/api/services/{sale['service_id']}/").json()
    assert service["expires_on"] is None
    assert service["purchased_quota"] == "1.125"


def test_expired_renewal_and_topup_decimal(owner):
    c, s, p = create_records(owner)
    sale, data = buy(owner, c, p, started_on="2026-08-01", expires_on="2026-09-01")
    service = owner.get(f"/api/services/{sale['service_id']}/").json()
    r = owner.post(
        f"/api/services/{service['id']}/renew/",
        json={
            **data,
            "sold_on": "2026-10-17",
            "started_on": None,
            "expires_on": None,
            "expected_revision": service["revision"],
            "submission_id": str(uuid4()),
        },
    )
    assert r.status_code == 201, r.text
    assert owner.get(f"/api/services/{service['id']}/").json()["expires_on"] == "2026-11-17"
    sale, data = buy(
        owner,
        c,
        p,
        term_count=None,
        term_unit=None,
        quota_amount="0.1",
        quota_unit="额度",
    )
    service = owner.get(f"/api/services/{sale['service_id']}/").json()
    r = owner.post(
        f"/api/services/{service['id']}/topup/",
        json={
            **data,
            "quota_amount": "0.2",
            "expected_revision": service["revision"],
            "submission_id": str(uuid4()),
        },
    )
    assert r.status_code == 201, r.text
    assert owner.get(f"/api/services/{service['id']}/").json()["purchased_quota"] == "0.3"


def test_correct_sale_preserves_history(owner):
    c, s, p = create_records(owner)
    sale, data = buy(owner, c, p)
    service = owner.get(f"/api/services/{sale['service_id']}/").json()
    r = owner.post(
        f"/api/sales/{sale['id']}/correct/",
        json={
            "reason": "成本录错",
            "cost_fen": 7000,
            "price_fen": 10000,
            "sold_on": "2026-10-17",
            "expected_revision": service["revision"],
            "service_state": {
                "expires_on": service["expires_on"],
                "ended": False,
                "purchased_quota": "0",
            },
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["snapshot"]["correction_history"][0]["cost_fen"] == 6000
    assert owner.get("/api/dashboard/?month=2026-10").json()["totals"]["profit_fen"] == 3000
