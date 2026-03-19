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
        url = get_database_url()
        logger.info("Database URL: %s", url.split("@")[-1] if "@" in url else url)
        _engine = create_engine(url, echo=False)
    return _engine


def _add_column_if_missing(engine, table_name, column_name, column_def):
    """Add a column to a table if it doesn't exist."""
    insp = inspect(engine)
    if not insp.has_table(table_name):
        return
    columns = [c["name"] for c in insp.get_columns(table_name)]
    if column_name not in columns:
        logger.info("Adding %s column to %s table", column_name, table_name)
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"))


def run_migrations(engine):
    """Add missing columns to existing tables."""
    _add_column_if_missing(engine, "users", "telegram_chat_id", "INTEGER UNIQUE")


_db_initialized = False


def init_db(engine):
    """Create tables and run migrations safely. Only runs once."""
    global _db_initialized
    if _db_initialized:
        return
    run_migrations(engine)
    for table in Base.metadata.sorted_tables:
        try:
            table.create(engine, checkfirst=True)
        except Exception as e:
            logger.warning("Could not create table %s: %s", table.name, e)
    _db_initialized = True
    logger.info("Database initialized. Tables: %s",
                [t.name for t in Base.metadata.sorted_tables])


def get_session() -> Session:
    engine = get_engine()
    init_db(engine)
    return sessionmaker(bind=engine)()
