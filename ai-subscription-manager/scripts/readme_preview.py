"""Disposable screenshot instance containing synthetic data only."""
import os,sys
from pathlib import Path
from datetime import timedelta
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'));os.chdir(root/'backend')
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from app.config import Settings
from app.db import Database
from app.models import Sale
from app.cli import seed_demo
from app.calendar import today
import uvicorn
settings=Settings();target=Path(settings.database_path).resolve()
if target.parent != (root/'.local').resolve() or not target.name.startswith('readme-'): raise RuntimeError('Disposable README database required')
if target.exists(): raise RuntimeError('Refusing to reuse a database')
command.upgrade(Config('alembic.ini'),'head')
database=Database(str(target));seed_demo(database)
with database.write() as session:
    for sale in session.scalars(select(Sale)): sale.sold_on=today()-timedelta(days=3)
uvicorn.run('app.main:app',host='127.0.0.1',port=18771)
