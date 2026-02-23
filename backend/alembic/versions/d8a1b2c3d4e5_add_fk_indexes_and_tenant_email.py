"""add FK indexes and per-tenant email uniqueness

Revision ID: d8a1b2c3d4e5
Revises: c7f0a4e5b6d3
Create Date: 2026-02-23 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d8a1b2c3d4e5"
down_revision: str | None = "c7f0a4e5b6d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # H4: Add missing FK indexes on Widget and DashboardFilter
    op.create_index(
        op.f("ix_widgets_dashboard_id"), "widgets", ["dashboard_id"]
    )
    op.create_index(
        op.f("ix_widgets_source_workflow_id"), "widgets", ["source_workflow_id"]
    )
    op.create_index(
        op.f("ix_dashboard_filters_dashboard_id"),
        "dashboard_filters",
        ["dashboard_id"],
    )

    # H5: Replace global email unique with per-tenant unique
    op.drop_index("ix_users_email", table_name="users")
    op.create_unique_constraint(
        "uq_users_tenant_email", "users", ["tenant_id", "email"]
    )


def downgrade() -> None:
    # H5: Restore global email unique index
    op.drop_constraint("uq_users_tenant_email", "users", type_="unique")
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # H4: Drop FK indexes
    op.drop_index(
        op.f("ix_dashboard_filters_dashboard_id"), table_name="dashboard_filters"
    )
    op.drop_index(op.f("ix_widgets_source_workflow_id"), table_name="widgets")
    op.drop_index(op.f("ix_widgets_dashboard_id"), table_name="widgets")
