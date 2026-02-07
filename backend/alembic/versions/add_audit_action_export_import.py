"""add exported and imported to audit_action enum

Revision ID: c7f0a4e5b6d3
Revises: b6e9f3d4a5c2
Create Date: 2026-02-07 10:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c7f0a4e5b6d3"
down_revision: str | None = "b6e9f3d4a5c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'exported'")
    op.execute("ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'imported'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from enums.
    # Downgrade would require recreating the type, which is complex.
    # In practice, unused enum values are harmless.
    pass
