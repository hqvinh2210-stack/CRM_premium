from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / ".data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DB = f"sqlite:///{(DATA_DIR / 'pos.db').as_posix()}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB)


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _is_postgres(url: str) -> bool:
    return url.startswith("postgresql") or url.startswith("postgres")


def make_engine(url: str | None = None):
    url = url or DATABASE_URL
    kwargs: dict = {"echo": False, "future": True}
    if _is_sqlite(url):
        kwargs["connect_args"] = {"check_same_thread": False}
    elif _is_postgres(url):
        # Pool suitable for FastAPI + Celery workers
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "5"))
        kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    return create_engine(url, **kwargs)


engine = make_engine()

if _is_sqlite(DATABASE_URL):

    @event.listens_for(engine, "connect")
    def _sqlite_fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Fallback schema create (dev/tests). Prefer Alembic in staging/prod."""
    from pos import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def run_alembic_upgrade() -> None:
    """Apply migrations to head (USE_ALEMBIC=1 or always when Postgres)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
    command.upgrade(cfg, "head")


def db_backend() -> str:
    if _is_postgres(DATABASE_URL):
        return "postgresql"
    if _is_sqlite(DATABASE_URL):
        return "sqlite"
    return "other"
