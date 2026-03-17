"""Shared test fixtures — in-memory SQLite DB and FastAPI test client."""

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from crossfit_coach.database import Base
from crossfit_coach.api import app, get_db


@pytest.fixture()
def db_engine():
    """Single in-memory engine shared across the test (StaticPool keeps it alive)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    """FastAPI test client with overridden DB dependency."""

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
