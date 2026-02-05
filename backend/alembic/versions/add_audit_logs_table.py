"""add audit_logs table

Revision ID: a5f8d2c3e4b1
Revises: 92284ff9b280
Create Date: 2026-02-03 12:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a5f8d2c3e4b1"
down_revision: str | None = "92284ff9b280"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create enum types
    audit_action = postgresql.ENUM(
        "CREATED",
        "UPDATED",
        "DELETED",
        "EXECUTED",
        "REVOKED",
        name="audit_action",
        create_type=False,
    )
    audit_action.create(op.get_bind(), checkfirst=True)

    audit_resource_type = postgresql.ENUM(
        "WORKFLOW",
        "DASHBOARD",
        "WIDGET",
        "API_KEY",
        name="audit_resource_type",
        create_type=False,
    )
    audit_resource_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "audit_logs",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "CREATED",
                "UPDATED",
                "DELETED",
                "EXECUTED",
                "REVOKED",
                name="audit_action",
            ),
            nullable=False,
        ),
        sa.Column(
            "resource_type",
            sa.Enum(
                "WORKFLOW", "DASHBOARD", "WIDGET", "API_KEY", name="audit_resource_type"
            ),
            nullable=False,
        ),
        sa.Column("resource_id", sa.UUID(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_logs_tenant_created",
        "audit_logs",
        ["tenant_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_logs_tenant_id"), "audit_logs", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_tenant_id"), table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_created", table_name="audit_logs")
    op.drop_table("audit_logs")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS audit_action")
    op.execute("DROP TYPE IF EXISTS audit_resource_type")
