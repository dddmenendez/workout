"""Database configuration and session management."""

import os
from pathlib import Path

import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)

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


def run_migrations(engine):
    """Add missing columns to existing tables."""
    insp = inspect(engine)
    if insp.has_table("users"):
        columns = [c["name"] for c in insp.get_columns("users")]
        with engine.begin() as conn:
            if "telegram_chat_id" not in columns:
                logger.info("Adding telegram_chat_id column to users table")
                conn.execute(text("ALTER TABLE users ADD COLUMN telegram_chat_id INTEGER UNIQUE"))


def init_db(engine):
    """Create tables and run migrations safely."""
    run_migrations(engine)
    try:
        Base.metadata.create_all(engine)
    except Exception:
        logger.warning("create_all failed (tables may already exist), continuing")


def get_session() -> Session:
    engine = get_engine()
    init_db(engine)
    return sessionmaker(bind=engine)()
