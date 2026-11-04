from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError, IntegrityError
from .config import Settings
from .db import Database
from .errors import ApiError
from .auth import router as auth_router
from .catalog import router as catalog_router
from .billing import router as billing_router
from .reminders import router as reminder_router


def create_app(settings=None):
    settings = settings or Settings()
    instance = FastAPI(
        title="续订 · 订阅管理",
        docs_url=None if settings.production else "/api/docs",
        redoc_url=None,
        openapi_url=None if settings.production else "/api/openapi.json",
    )
    instance.state.settings = settings
    instance.state.db = Database(settings.database_path)

    @instance.exception_handler(ApiError)
    async def api_error(request, error):
        return JSONResponse(
            {"code": error.code, "message": error.message, "fields": error.fields},
            status_code=error.status,
        )

    async def validation_error(request, error):
        fields = {".".join(str(v) for v in e["loc"]): e["msg"] for e in error.errors()}
        return JSONResponse(
            {"code": "validation", "message": "请检查填写内容", "fields": fields},
            status_code=422,
        )

    instance.add_exception_handler(RequestValidationError, validation_error)
    instance.add_exception_handler(ValidationError, validation_error)

    @instance.exception_handler(OperationalError)
    async def busy(request, error):
        if "locked" in str(error).lower():
            return JSONResponse(
                {
                    "code": "busy",
                    "message": "正在保存其他记录，请稍后重试",
                    "fields": {},
                },
                status_code=503,
            )
        return JSONResponse(
            {
                "code": "database_error",
                "message": "数据库暂不可用，请检查运行配置",
                "fields": {},
            },
            status_code=503,
        )

    @instance.exception_handler(IntegrityError)
    async def integrity(request, error):
        return JSONResponse(
            {
                "code": "conflict",
                "message": "记录存在关联或重复，请刷新核对",
                "fields": {},
            },
            status_code=409,
        )

    @instance.middleware("http")
    async def secure_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        return response

    @instance.get("/health/")
    def health():
        from sqlalchemy import text

        with instance.state.db.read() as db:
            db.execute(text("SELECT id FROM owners LIMIT 1"))
        return {"status": "ok", "release": settings.release_sha}

    instance.include_router(auth_router)
    instance.include_router(catalog_router)
    instance.include_router(billing_router)
    instance.include_router(reminder_router)

    @instance.api_route("/api/auth/register/", methods=["POST"])
    def unavailable(request: Request):
        from .auth import authenticated

        authenticated(request)
        raise ApiError("not_found", "不提供公开注册", 404)

    if settings.frontend_dir:
        from pathlib import Path
        from fastapi.staticfiles import StaticFiles

        instance.mount(
            "/assets",
            StaticFiles(directory=Path(settings.frontend_dir) / "assets"),
            name="frontend-assets",
        )

        @instance.api_route(
            "/api/{path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"]
        )
        def unknown_api(path: str):
            raise ApiError("not_found", "接口不存在", 404)

        instance.frontend("/", directory=settings.frontend_dir, fallback="index.html")
    return instance


app = create_app()
