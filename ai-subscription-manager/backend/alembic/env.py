from alembic import context
from app.config import Settings
from app.db import Database
from app.models import Base

engine = Database(Settings().database_path).engine
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
