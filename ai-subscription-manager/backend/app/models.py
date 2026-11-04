from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Date,
    DateTime,
    Boolean,
    ForeignKey,
    JSON,
    CheckConstraint,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import DeclarativeBase


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Owner(Base):
    __tablename__ = "owners"
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    __table_args__ = (CheckConstraint("id = 1"),)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash = Column(String(64), primary_key=True)
    csrf_hash = Column(String(64), nullable=False)
    owner_id = Column(Integer, ForeignKey("owners.id"))
    expires_at = Column(DateTime, nullable=False)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    key = Column(String(64), primary_key=True)
    failures = Column(Integer, default=0, nullable=False)
    window_at = Column(DateTime, nullable=False)


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    contacts = Column(JSON, nullable=False, default=list)
    notes = Column(Text, nullable=False, default="")
    archived_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    url = Column(Text, nullable=False, default="")
    contact_name = Column(String(200), nullable=False, default="")
    contact_details = Column(Text, nullable=False, default="")
    notes = Column(Text, nullable=False, default="")
    is_active = Column(Boolean, nullable=False, default=True)


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False)
    name = Column(String(200), nullable=False)
    platform = Column(String(100), nullable=False, default="")
    plan = Column(String(100), nullable=False, default="")
    delivery = Column(String(100), nullable=False, default="")
    source_name = Column(Text, nullable=False, default="")
    source_url = Column(Text, nullable=False, default="")
    tags = Column(JSON, nullable=False, default=list)
    cost_fen = Column(Integer, nullable=False, default=0)
    price_fen = Column(Integer, nullable=False, default=0)
    quoted_on = Column(Date)
    term_count = Column(Integer)
    term_unit = Column(String(10))
    quota_amount = Column(String(40))
    quota_unit = Column(String(80))
    warranty_notes = Column(Text, nullable=False, default="")
    is_active = Column(Boolean, nullable=False, default=True)
    __table_args__ = (CheckConstraint("cost_fen >= 0 AND price_fen >= 0"),)


class Service(Base):
    __tablename__ = "services"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    identifier = Column(String(200), nullable=False, default="")
    started_on = Column(Date, nullable=False)
    expires_on = Column(Date, index=True)
    quota_unit = Column(String(80))
    purchased_quota = Column(String(40), nullable=False, default="0")
    notes = Column(Text, nullable=False, default="")
    ended_at = Column(DateTime)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class Sale(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="RESTRICT"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    kind = Column(String(20), nullable=False)
    sold_on = Column(Date, nullable=False, index=True)
    cost_fen = Column(Integer, nullable=False)
    price_fen = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=False)
    before_state = Column(JSON, nullable=False, default=dict)
    after_state = Column(JSON, nullable=False, default=dict)
    submission_id = Column(String(36), unique=True, nullable=False)
    payload_hash = Column(String(64), nullable=False)
    voided_at = Column(DateTime)
    void_reason = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    __table_args__ = (CheckConstraint("cost_fen >= 0 AND price_fen >= 0"),)


class ReminderSettings(Base):
    __tablename__ = "reminder_settings"
    id = Column(Integer, primary_key=True, default=1)
    recipient = Column(String(254), nullable=False, default="")
    __table_args__ = (CheckConstraint("id = 1"),)


class MailBatch(Base):
    __tablename__ = "mail_batches"
    id = Column(String(36), primary_key=True)
    recipient = Column(String(254), nullable=False)
    status = Column(String(20), nullable=False, default="claimed")
    claimed_at = Column(DateTime, nullable=False)
    attempt_day = Column(Date, nullable=False)
    attempts_today = Column(Integer, nullable=False, default=1)
    attempts_total = Column(Integer, nullable=False, default=1)
    provider_message_id = Column(String(200), nullable=False, default="")
    error_code = Column(String(80), nullable=False, default="")
    payload = Column(JSON, nullable=False, default=list)
    sent_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class Reminder(Base):
    __tablename__ = "reminders"
    id = Column(Integer, primary_key=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    target_expiry = Column(Date, nullable=False)
    kind = Column(String(10), nullable=False)
    planned_on = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    batch_id = Column(String(36), ForeignKey("mail_batches.id"))
    __table_args__ = (
        UniqueConstraint("service_id", "target_expiry", "kind"),
        Index("ix_reminder_pending", "status", "planned_on"),
    )


class ReminderRun(Base):
    __tablename__ = "reminder_runs"
    id = Column(Integer, primary_key=True)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime)
    status = Column(String(30), nullable=False, default="running")
    counts = Column(JSON, nullable=False, default=dict)
    error_code = Column(String(80), nullable=False, default="")
