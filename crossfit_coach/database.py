"""Database configuration and session management."""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DB_PATH = Path.home() / ".crossfit_coach" / "coach.db"


class Base(DeclarativeBase):
    pass


def get_database_url() -> str:
    """Return DATABASE_URL from env (PostgreSQL for production) or SQLite fallback."""
    url = os.environ.get("DATABASE_URL")
    if url:
        # Render uses postgres:// but SQLAlchemy needs postgresql://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DB_PATH}"


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(get_database_url(), echo=False)
    return _engine


def get_session() -> Session:
    engine = get_engine()
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()
