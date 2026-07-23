"""Initialize DB + seed on startup."""

from __future__ import annotations

import os

from pos.db import DATABASE_URL, db_backend, init_db, run_alembic_upgrade
from pos.seed import seed


def bootstrap_pos() -> dict:
    """
    Schema strategy:
      - USE_ALEMBIC=1 → always alembic upgrade head
      - postgres URL → alembic by default (set USE_ALEMBIC=0 to force create_all)
      - sqlite → create_all (tests/dev) unless USE_ALEMBIC=1
    """
    use_alembic = os.getenv("USE_ALEMBIC")
    if use_alembic is None:
        use_alembic = "1" if db_backend() == "postgresql" else "0"

    if use_alembic == "1":
        try:
            run_alembic_upgrade()
            print(f"[pos] Alembic upgrade head ({db_backend()})")
        except Exception as exc:  # noqa: BLE001
            print(f"[pos] Alembic failed ({exc}); falling back to create_all")
            init_db()
    else:
        init_db()
        print(f"[pos] create_all ({db_backend()}) url={DATABASE_URL[:48]}...")

    return seed()
