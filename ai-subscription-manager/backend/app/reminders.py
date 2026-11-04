import smtplib
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from .auth import authenticated
from .models import (
    Service,
    Customer,
    Product,
    Reminder,
    MailBatch,
    ReminderRun,
    ReminderSettings,
    utcnow,
)
from .catalog import encode, paged
from .calendar import TZ
from .mail import send_digest, MailNotConfigured
from .errors import ApiError

router = APIRouter(prefix="/api/reminders", dependencies=[Depends(authenticated)])


def normalized(now):
    if now.tzinfo is None:
        raise ValueError("任务时间必须有时区")
    return now.astimezone(TZ)


def utc_naive(now):
    return now.astimezone(timezone.utc).replace(tzinfo=None)


def valid(reminder, service):
    return service and not service.ended_at and service.expires_on == reminder.target_expiry


def plan_due(database, now):
    local = normalized(now)
    count = 0
    with database.write() as db:
        for item in db.scalars(select(Reminder).where(Reminder.status == "pending")):
            if not valid(item, db.get(Service, item.service_id)):
                item.status = "cancelled"
        services = db.scalars(
            select(Service).where(Service.ended_at.is_(None), Service.expires_on.is_not(None))
        )
        for service in services:
            created = service.created_at.replace(tzinfo=timezone.utc).astimezone(TZ).date()
            for kind, delta in [("before3", 3), ("day0", 0)]:
                planned = service.expires_on - timedelta(days=delta)
                if (
                    planned < created
                    or planned > local.date()
                    or (planned == local.date() and local.hour < 9)
                ):
                    continue
                existing = db.scalar(
                    select(Reminder).where(
                        Reminder.service_id == service.id,
                        Reminder.target_expiry == service.expires_on,
                        Reminder.kind == kind,
                    )
                )
                if existing is not None and existing.status == "cancelled":
                    existing.status = "pending"
                    existing.batch_id = None
                if existing is None:
                    db.add(
                        Reminder(
                            service_id=service.id,
                            target_expiry=service.expires_on,
                            kind=kind,
                            planned_on=planned,
                            status="pending",
                        )
                    )
                    count += 1
    return count


def send_due(database, settings, now, send=send_digest):
    local = normalized(now)
    at = utc_naive(now)
    counts = {"sent": 0, "failed": 0, "uncertain": 0, "cancelled": 0}
    payload = None
    with database.write() as db:
        config = db.get(ReminderSettings, 1)
        if not config or not config.recipient:
            return counts
        batches = list(db.scalars(select(MailBatch).where(MailBatch.status != "sent")))
        for b in batches:
            if b.status == "claimed" and b.claimed_at < at - timedelta(minutes=5):
                b.status = "uncertain"
                b.error_code = "worker_interrupted"
        pending = list(
            db.scalars(
                select(Reminder).where(
                    Reminder.status == "pending", Reminder.planned_on <= local.date()
                )
            )
        )
        chosen = []
        old_ids = set()
        for item in pending:
            service = db.get(Service, item.service_id)
            if not valid(item, service):
                item.status = "cancelled"
                counts["cancelled"] += 1
                continue
            old = db.get(MailBatch, item.batch_id) if item.batch_id else None
            if old:
                if old.status == "claimed":
                    continue
                if at < old.claimed_at + timedelta(minutes=15):
                    continue
                if old.attempt_day == local.date() and old.attempts_today >= 4:
                    continue
            chosen.append(item)
            if old:
                old_ids.add(old.id)
        if not chosen:
            return counts
        batch_id = str(uuid4())
        # Each attempt owns a separate immutable snapshot; per-item retry budget derives from its previous batch.
        prior = [db.get(MailBatch, i) for i in old_ids]
        attempts = (
            max([b.attempts_today if b.attempt_day == local.date() else 0 for b in prior] or [0])
            + 1
        )
        total = max([b.attempts_total for b in prior] or [0]) + 1
        batch = MailBatch(
            id=batch_id,
            recipient=config.recipient,
            status="claimed",
            claimed_at=at,
            attempt_day=local.date(),
            attempts_today=attempts,
            attempts_total=total,
            payload=[],
        )
        db.add(batch)
        db.flush()
        rows = []
        for item in chosen:
            service = db.get(Service, item.service_id)
            customer = db.get(Customer, service.customer_id)
            product = db.get(Product, service.product_id)
            rows.append(
                {
                    "reminder_id": item.id,
                    "service_id": service.id,
                    "revision": service.revision,
                    "customer_name": customer.name,
                    "contacts": customer.contacts,
                    "product_name": product.name,
                    "identifier": service.identifier,
                    "expires_on": service.expires_on.isoformat(),
                    "kind": "到期前 3 天" if item.kind == "before3" else "到期当天",
                    "planned_on": item.planned_on.isoformat(),
                }
            )
            item.batch_id = batch_id
        batch.payload = rows
        payload = {
            "id": batch_id,
            "recipient": batch.recipient,
            "items": rows,
            "as_of": local.isoformat(),
        }
    # Recheck in a separate short transaction immediately before the network operation.
    with database.write() as db:
        rows = []
        for row in payload["items"]:
            item = db.get(Reminder, row["reminder_id"])
            service = db.get(Service, row["service_id"])
            if (
                item.status == "pending"
                and valid(item, service)
                and service.revision == row["revision"]
            ):
                rows.append(row)
            else:
                item.status = "cancelled"
                counts["cancelled"] += 1
        db.get(MailBatch, payload["id"]).payload = rows
        payload["items"] = rows
    result = "sent"
    message_id = ""
    code = ""
    try:
        if payload["items"]:
            message_id = send(settings, payload)
    except MailNotConfigured:
        result = "failed"
        code = "mail_not_configured"
    except (TimeoutError, ConnectionResetError, smtplib.SMTPServerDisconnected):
        result = "uncertain"
        code = "delivery_uncertain"
    except Exception as error:
        result = "failed"
        code = type(error).__name__[:80]
    with database.write() as db:
        batch = db.get(MailBatch, payload["id"])
        batch.status = result
        batch.error_code = code
        batch.provider_message_id = message_id
        if result == "sent":
            batch.sent_at = at
            for row in payload["items"]:
                item = db.get(Reminder, row["reminder_id"])
                # A renewal during send cannot retract delivery; preserve its cancellation if already made.
                if item.status == "pending":
                    item.status = "sent"
        counts[result] = len(payload["items"])
    return counts


def run_cycle(database, settings, now=None):
    now = now or datetime.now(TZ)
    with database.write() as db:
        row = ReminderRun(started_at=utc_naive(now))
        db.add(row)
        db.flush()
        identifier = row.id
    try:
        generated = plan_due(database, now)
        counts = send_due(database, settings, now)
        result = {"generated": generated, **counts}
        status = "success" if not counts["failed"] and not counts["uncertain"] else "attention"
        with database.write() as db:
            row = db.get(ReminderRun, identifier)
            row.finished_at = utcnow()
            row.status = status
            row.counts = result
        return result
    except Exception as error:
        with database.write() as db:
            row = db.get(ReminderRun, identifier)
            row.finished_at = utcnow()
            row.status = "failed"
            row.error_code = type(error).__name__
        raise


class SettingsInput(BaseModel):
    recipient: EmailStr


@router.get("/settings/")
def reminder_settings(request: Request):
    with request.app.state.db.read() as db:
        config = db.get(ReminderSettings, 1)
        last = db.scalar(select(ReminderRun).order_by(ReminderRun.id.desc()).limit(1))
        return {
            "recipient": config.recipient if config else "",
            "mail_ready": request.app.state.settings.mail_ready,
            "schedule": "每天 09:00 汇总，每 15 分钟检查补发",
            "timezone": "Asia/Hong_Kong",
            "last_run": encode(last) if last else None,
        }


@router.patch("/settings/")
def save_settings(request: Request, data: SettingsInput):
    with request.app.state.db.write() as db:
        config = db.get(ReminderSettings, 1)
        if not config:
            config = ReminderSettings(id=1)
            db.add(config)
        config.recipient = str(data.recipient)
    return reminder_settings(request)


@router.get("/runs/")
def runs(request: Request):
    with request.app.state.db.read() as db:
        return {
            "runs": paged(
                [
                    encode(r)
                    for r in db.scalars(select(ReminderRun).order_by(ReminderRun.id.desc()))
                ],
                request,
            ),
            "batches": paged(
                [
                    encode(r)
                    for r in db.scalars(select(MailBatch).order_by(MailBatch.created_at.desc()))
                ],
                request,
            ),
        }


@router.post("/retry/")
def retry(request: Request):
    return run_cycle(request.app.state.db, request.app.state.settings)


@router.post("/test/")
def test_mail(request: Request):
    with request.app.state.db.read() as db:
        config = db.get(ReminderSettings, 1)
        if not config or not config.recipient:
            raise ApiError("recipient", "请先保存接收邮箱")
        recipient = config.recipient
    try:
        result = send_digest(
            request.app.state.settings,
            {
                "id": str(uuid4()),
                "recipient": recipient,
                "items": [],
                "as_of": datetime.now(TZ).isoformat(),
            },
        )
    except MailNotConfigured:
        raise ApiError("mail_not_configured", "服务器尚未配置 SMTP，请按部署说明设置")
    except Exception:
        raise ApiError("mail_failed", "测试发送失败，请检查服务器邮件配置", 502)
    return {"message": "测试邮件已提交发送", "message_id": result}
