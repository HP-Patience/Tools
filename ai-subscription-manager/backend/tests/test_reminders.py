from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select
from test_business import create_records, buy

TZ = ZoneInfo("Asia/Hong_Kong")
NOW = datetime(2026, 10, 17, 9, tzinfo=TZ)


def setup_service(owner, app, expires="2026-10-20"):
    from app.models import Service, ReminderSettings

    c, s, p = create_records(owner)
    sale, _ = buy(owner, c, p, expires_on=expires)
    with app.state.db.write() as db:
        service = db.get(Service, sale["service_id"])
        service.created_at = datetime(2026, 10, 1)
        db.add(ReminderSettings(id=1, recipient="owner@example.com"))
    return sale


def test_plan_unique_and_cancel(owner, app):
    from app.reminders import plan_due
    from app.models import Reminder

    sale = setup_service(owner, app)
    assert plan_due(app.state.db, NOW) == 1
    assert plan_due(app.state.db, NOW) == 0
    service = owner.get(f"/api/services/{sale['service_id']}/").json()
    owner.post(
        f"/api/services/{service['id']}/end/",
        json={"expected_revision": service["revision"]},
    )
    with app.state.db.read() as db:
        assert db.scalar(select(Reminder)).status == "cancelled"


def test_late_import_no_historical_reminders(owner, app):
    from app.reminders import plan_due
    from app.models import Service

    sale = setup_service(owner, app, expires="2026-10-17")
    with app.state.db.write() as db:
        db.get(Service, sale["service_id"]).created_at = datetime(2026, 10, 18)
    assert plan_due(app.state.db, NOW + timedelta(days=2)) == 0


def test_successful_digest_once(owner, app):
    from app.reminders import plan_due, send_due

    setup_service(owner, app)
    plan_due(app.state.db, NOW)
    sent = []

    def capture(settings, batch):
        sent.append(batch)
        return "test-message-id"

    assert send_due(app.state.db, app.state.settings, NOW, send=capture)["sent"] == 1
    assert send_due(app.state.db, app.state.settings, NOW, send=capture)["sent"] == 0
    assert len(sent) == 1
    assert "cost_fen" not in str(sent)


def test_failure_and_recovery(owner, app):
    from app.reminders import plan_due, send_due

    setup_service(owner, app)
    plan_due(app.state.db, NOW)

    def fail(settings, batch):
        raise ConnectionRefusedError()

    assert send_due(app.state.db, app.state.settings, NOW, send=fail)["failed"] == 1
    assert (
        send_due(
            app.state.db,
            app.state.settings,
            NOW + timedelta(minutes=1),
            send=lambda s, b: "ok",
        )["sent"]
        == 0
    )
    assert (
        send_due(
            app.state.db,
            app.state.settings,
            NOW + timedelta(minutes=16),
            send=lambda s, b: "ok",
        )["sent"]
        == 1
    )


def test_timeout_uncertain(owner, app):
    from app.reminders import plan_due, send_due

    setup_service(owner, app)
    plan_due(app.state.db, NOW)

    def timeout(settings, batch):
        raise TimeoutError()

    assert send_due(app.state.db, app.state.settings, NOW, send=timeout)["uncertain"] == 1


def test_reminder_settings_validation(owner):
    assert (
        owner.patch("/api/reminders/settings/", json={"recipient": "not-email"}).status_code == 422
    )
    assert (
        owner.patch("/api/reminders/settings/", json={"recipient": "me@example.com"}).status_code
        == 200
    )


def test_before_nine_and_day_zero_recovery(owner, app):
    from app.reminders import plan_due
    from app.models import Reminder

    setup_service(owner, app, expires="2026-10-20")
    assert plan_due(app.state.db, NOW.replace(hour=8)) == 0
    assert plan_due(app.state.db, NOW + timedelta(days=4)) == 2
    with app.state.db.read() as db:
        assert {r.kind for r in db.scalars(select(Reminder))} == {"before3", "day0"}


def test_renew_cancels_old_pending_and_keeps_sent(owner, app):
    from app.reminders import plan_due, send_due
    from app.models import Reminder
    from uuid import uuid4

    sale = setup_service(owner, app)
    plan_due(app.state.db, NOW)
    send_due(app.state.db, app.state.settings, NOW, send=lambda s, b: "delivered")
    service = owner.get(f"/api/services/{sale['service_id']}/").json()
    payload = {
        "customer_id": sale["customer_id"],
        "product_id": sale["product_id"],
        "sold_on": "2026-10-17",
        "cost_fen": 6000,
        "price_fen": 10000,
        "submission_id": str(uuid4()),
        "term_count": 1,
        "term_unit": "month",
        "expected_revision": service["revision"],
    }
    assert owner.post(f"/api/services/{service['id']}/renew/", json=payload).status_code == 201
    assert plan_due(app.state.db, NOW + timedelta(days=3)) == 0
    with app.state.db.read() as db:
        assert db.scalar(select(Reminder)).status == "sent"


def test_concurrent_sender_one_delivery(owner, app):
    from app.reminders import plan_due, send_due
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    setup_service(owner, app)
    plan_due(app.state.db, NOW)
    started = Event()
    finish = Event()
    sent = []

    def slow(s, b):
        started.set()
        finish.wait(3)
        sent.append(b["id"])
        return "delivered"

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(send_due, app.state.db, app.state.settings, NOW, slow)
        assert started.wait(3)
        second = pool.submit(send_due, app.state.db, app.state.settings, NOW, slow)
        assert second.result()["sent"] == 0
        finish.set()
        assert first.result()["sent"] == 1
    assert len(sent) == 1


def test_reverting_expiry_reactivates_unsent_reminder(owner, app):
    from datetime import date
    from app.reminders import plan_due
    from app.models import Service, Reminder

    sale = setup_service(owner, app)
    assert plan_due(app.state.db, NOW) == 1
    with app.state.db.write() as db:
        db.get(Service, sale["service_id"]).expires_on = date(2026, 11, 20)
    plan_due(app.state.db, NOW)
    with app.state.db.read() as db:
        assert db.scalar(select(Reminder)).status == "cancelled"
    with app.state.db.write() as db:
        db.get(Service, sale["service_id"]).expires_on = date(2026, 10, 20)
    plan_due(app.state.db, NOW)
    with app.state.db.read() as db:
        assert db.scalar(select(Reminder)).status == "pending"
