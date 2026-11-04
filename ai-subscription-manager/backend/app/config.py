from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")
    database_path: str = "data/subscriptions.db"
    app_url: str = "http://localhost:5173"
    production: bool = False
    release_sha: str = "development"
    frontend_dir: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_ssl: bool = False
    smtp_starttls: bool = True
    mail_backend: str = "disabled"

    @model_validator(mode="after")
    def production_requirements(self):
        from urllib.parse import urlparse

        url = urlparse(self.app_url)
        if url.scheme not in ("http", "https") or not url.netloc or url.path not in ("", "/"):
            raise ValueError("APP_APP_URL 必须是完整的站点来源，不带路径")
        if self.production and url.scheme != "https":
            raise ValueError("生产环境需要 HTTPS")
        if (
            self.production
            and self.mail_backend == "smtp"
            and not (self.smtp_ssl or self.smtp_starttls)
        ):
            raise ValueError("生产 SMTP 需要 TLS 或 SSL")
        return self

    @property
    def mail_ready(self):
        return self.mail_backend == "smtp" and bool(self.smtp_host and self.smtp_from)
