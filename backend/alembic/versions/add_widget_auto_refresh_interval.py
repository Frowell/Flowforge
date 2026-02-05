"""add auto_refresh_interval to widgets

Revision ID: b6e9f3d4a5c2
Revises: a5f8d2c3e4b1
Create Date: 2026-02-05 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b6e9f3d4a5c2"
down_revision: str | None = "a5f8d2c3e4b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "widgets",
        sa.Column("auto_refresh_interval", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("widgets", "auto_refresh_interval")
