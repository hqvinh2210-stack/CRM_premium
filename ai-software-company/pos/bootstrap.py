"""Initialize DB + seed on startup."""

from pos.db import init_db
from pos.seed import seed


def bootstrap_pos() -> dict:
    init_db()
    return seed()
