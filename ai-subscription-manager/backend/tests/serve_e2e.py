"""Start a disposable E2E instance. Never reads the local preview database."""

import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.chdir(Path(__file__).resolve().parents[1])
from app.config import Settings
from alembic.config import Config
from alembic import command
import uvicorn

settings = Settings()
path = Path(settings.database_path).resolve()
if ".local" not in path.parts or "e2e-" not in path.name:
    raise RuntimeError("E2E database must use an isolated e2e file inside .local")
command.upgrade(Config("alembic.ini"), "head")
uvicorn.run("app.main:app", host="127.0.0.1", port=18761)
