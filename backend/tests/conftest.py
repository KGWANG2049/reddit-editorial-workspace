from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.bootstrap as bootstrap
import app.database as database
import app.db_worker as db_worker
import app.jobs as jobs
import app.main as main
from app.database import Base


@pytest.fixture
def db_session_factory(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_factory)
    monkeypatch.setattr(bootstrap, "engine", engine)
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)
    monkeypatch.setattr(db_worker, "SessionLocal", session_factory)
    return session_factory


@pytest.fixture
def client(db_session_factory) -> Iterator[TestClient]:
    def override_get_session():
        session = db_session_factory()
        try:
            yield session
        finally:
            session.close()

    main.app.dependency_overrides[main.get_session] = override_get_session
    main.app.dependency_overrides[database.get_session] = override_get_session
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()
