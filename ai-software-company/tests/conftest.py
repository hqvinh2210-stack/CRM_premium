"""Shared POS TestClient for the whole pytest session (one DB)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import pos.db as pos_db


@pytest.fixture(scope="session")
def pos_client():
    path = Path(__file__).resolve().parent / "_session_pos.db"
    if path.exists():
        try:
            path.unlink()
        except PermissionError:
            pass

    url = f"sqlite:///{path.as_posix()}"
    os.environ["DATABASE_URL"] = url
    pos_db.DATABASE_URL = url
    engine = create_engine(url, connect_args={"check_same_thread": False}, future=True)

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    pos_db.engine = engine
    pos_db.SessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True
    )

    from pos import models  # noqa: F401
    from pos.db import Base
    from pos.seed import seed

    Base.metadata.create_all(bind=engine)
    seed()

    # import app AFTER engine rebind
    from app.main import app

    with TestClient(app) as client:
        yield client

    try:
        engine.dispose()
        path.unlink(missing_ok=True)
    except Exception:
        pass
