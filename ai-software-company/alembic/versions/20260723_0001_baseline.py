"""baseline schema from SQLAlchemy models

Revision ID: 20260723_0001
Revises:
Create Date: 2026-07-23

Creates all current POS/CRM tables via metadata (safe for empty DBs).
For existing SQLite DBs that already used create_all, stamp:
  uv run alembic stamp head
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260723_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from pos import models  # noqa: F401
    from pos.db import Base

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from pos import models  # noqa: F401
    from pos.db import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
