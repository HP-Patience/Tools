from contextlib import contextmanager
import sqlite3, time
from sqlalchemy.exc import OperationalError
from pathlib import Path
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker


class Database:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with sqlite3.connect(path, timeout=5) as init:
            init.execute("PRAGMA journal_mode=WAL")
        self.engine = create_engine(
            "sqlite:///" + Path(path).resolve().as_posix(),
            connect_args={"check_same_thread": False, "timeout": 5},
        )

        @event.listens_for(self.engine, "connect")
        def configure(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")

        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def read(self):
        with self.sessions() as session:
            yield session

    @contextmanager
    def write(self):
        with self.sessions() as session:
            for attempt in range(3):
                try:
                    session.execute(text("BEGIN IMMEDIATE"))
                    break
                except OperationalError as error:
                    session.rollback()
                    if "locked" not in str(error).lower() or attempt == 2:
                        raise
                    time.sleep(0.05 * (attempt + 1))
            try:
                yield session
                session.commit()
            except BaseException:
                session.rollback()
                raise
