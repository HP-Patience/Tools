import hashlib
import secrets
from datetime import timedelta
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select, delete
from .models import Owner, LoginSession, LoginAttempt, utcnow
from .errors import ApiError

passwords = PasswordHasher()


def hash_password(password):
    return passwords.hash(password)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def session_record(request, db):
    item = db.get(LoginSession, digest(request.cookies.get("session", "")))
    return item if item and item.expires_at > utcnow() else None


def check_csrf(request, item):
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != request.app.state.settings.app_url.rstrip("/"):
        raise ApiError("csrf", "请求来源不匹配，请刷新页面", 403)
    if not item or not secrets.compare_digest(
        item.csrf_hash, digest(request.headers.get("x-csrftoken", ""))
    ):
        raise ApiError("csrf", "安全验证过期，请刷新后重试", 403)


def authenticated(request: Request):
    with request.app.state.db.read() as db:
        item = session_record(request, db)
        if not item or not item.owner_id:
            raise ApiError("unauthenticated", "请先登录", 401)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            check_csrf(request, item)
        return item.owner_id


def issue(request, response, db, owner_id=None):
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    db.add(
        LoginSession(
            token_hash=digest(token),
            csrf_hash=digest(csrf),
            owner_id=owner_id,
            expires_at=utcnow() + timedelta(hours=12 if owner_id else 1),
        )
    )
    response.set_cookie(
        "session",
        token,
        httponly=True,
        secure=request.app.state.settings.production,
        samesite="lax",
        max_age=43200 if owner_id else 3600,
        path="/",
    )
    return csrf


router = APIRouter(prefix="/api/auth")


@router.get("/csrf/")
def csrf(request: Request, response: Response):
    with request.app.state.db.write() as db:
        item = session_record(request, db)
        if item:
            token = secrets.token_urlsafe(32)
            item.csrf_hash = digest(token)
        else:
            db.execute(delete(LoginSession).where(LoginSession.expires_at < utcnow()))
            token = issue(request, response, db)
    return {"csrfToken": token}


@router.post("/login/")
def login(request: Request, response: Response, data: dict):
    result = None
    error = None
    with request.app.state.db.write() as db:
        item = session_record(request, db)
        check_csrf(request, item)
        key = digest(request.client.host if request.client else "unknown")
        attempt = db.get(LoginAttempt, key)
        if attempt and attempt.window_at < utcnow() - timedelta(minutes=15):
            attempt.failures = 0
            attempt.window_at = utcnow()
        if attempt and attempt.failures >= 10:
            raise ApiError("rate_limited", "尝试次数过多，请 15 分钟后再试", 429)
        owner = db.scalar(select(Owner).where(Owner.username == str(data.get("username", ""))))
        valid = False
        try:
            valid = bool(owner) and passwords.verify(
                owner.password_hash, str(data.get("password", ""))
            )
        except (VerificationError, InvalidHashError):
            pass
        if not valid:
            if not attempt:
                attempt = LoginAttempt(key=key, failures=0, window_at=utcnow())
                db.add(attempt)
            attempt.failures += 1
            error = ApiError("invalid_credentials", "用户名或密码错误", 400)
        else:
            if attempt:
                db.delete(attempt)
            db.delete(item)
            token = issue(request, response, db, owner.id)
            result = {
                "user": {"id": owner.id, "username": owner.username},
                "csrfToken": token,
            }
    if error:
        raise error
    return result


@router.get("/me/")
def me(request: Request):
    identifier = authenticated(request)
    with request.app.state.db.read() as db:
        owner = db.get(Owner, identifier)
        return {"user": {"id": owner.id, "username": owner.username}}


@router.post("/logout/", status_code=204)
def logout(request: Request, response: Response):
    authenticated(request)
    with request.app.state.db.write() as db:
        item = session_record(request, db)
        if item:
            db.delete(item)
    response.delete_cookie("session", path="/")


class SetupInput(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=12, max_length=128)
    confirm_password: str = Field(min_length=12, max_length=128)

    @field_validator("username", mode="before")
    @classmethod
    def trim_username(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def confirm(self):
        if self.password != self.confirm_password:
            raise ValueError("两次输入的密码不一致")
        return self


@router.get("/status/")
def status(request: Request):
    with request.app.state.db.read() as db:
        return {"needs_setup": db.get(Owner, 1) is None}


@router.post("/setup/", status_code=201)
def setup(request: Request, response: Response, data: SetupInput):
    with request.app.state.db.write() as db:
        item = session_record(request, db)
        check_csrf(request, item)
        if db.get(Owner, 1) is not None:
            raise ApiError("already_initialized", "管理员已设置，请使用已有账号登录", 409)
        owner = Owner(id=1, username=data.username, password_hash=hash_password(data.password))
        db.add(owner)
        db.flush()
        db.delete(item)
        token = issue(request, response, db, owner.id)
        return {"user": {"id": owner.id, "username": owner.username}, "csrfToken": token}
