"""schema cleanup: drop hashed_password, audit indexes, version tenant_id, GIN index

L2:  Drop users.hashed_password (dead column — Keycloak handles auth)
L5:  Add indexes on audit_logs.user_id and (resource_type, resource_id)
M12: Add tenant_id to workflow_versions (backfill from parent workflow)
M14: Add GIN index on api_keys.scoped_widget_ids

Revision ID: e9f2a3b4c5d6
Revises: d8a1b2c3d4e5
Create Date: 2026-02-24 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "e9f2a3b4c5d6"
down_revision: str | None = "d8a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # L2: Drop hashed_password from users
    op.drop_column("users", "hashed_password")

    # L5: Add indexes to audit_logs
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index(
        "ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"]
    )

    # M12: Add tenant_id to workflow_versions
    op.add_column(
        "workflow_versions",
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
    )
    # Backfill tenant_id from parent workflow
    op.execute(
        "UPDATE workflow_versions wv "
        "SET tenant_id = w.tenant_id "
        "FROM workflows w "
        "WHERE wv.workflow_id = w.id"
    )
    op.alter_column("workflow_versions", "tenant_id", nullable=False)
    op.create_index(
        "ix_workflow_versions_tenant_id", "workflow_versions", ["tenant_id"]
    )

    # M14: Add GIN index on api_keys.scoped_widget_ids
    op.create_index(
        "ix_api_keys_scoped_widgets",
        "api_keys",
        ["scoped_widget_ids"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    # M14: Drop GIN index
    op.drop_index("ix_api_keys_scoped_widgets", table_name="api_keys")

    # M12: Drop tenant_id from workflow_versions
    op.drop_index("ix_workflow_versions_tenant_id", table_name="workflow_versions")
    op.drop_column("workflow_versions", "tenant_id")

    # L5: Drop audit_logs indexes
    op.drop_index("ix_audit_logs_resource", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")

    # L2: Re-add hashed_password with a default for existing rows
    op.add_column(
        "users",
        sa.Column(
            "hashed_password",
            sa.String(length=255),
            nullable=False,
            server_default="removed",
        ),
    )
    op.alter_column("users", "hashed_password", server_default=None)
