"""Dashboard, Widget, DashboardFilter, and APIKey models.

Dashboards are projections of workflows. Widgets point to workflow output
nodes — they do NOT store their own queries.
"""

import uuid
import enum

from sqlalchemy import ForeignKey, Integer, String, Text, DateTime
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Dashboard(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "dashboards"

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    # Relationships
    created_by_user: Mapped["User"] = relationship(back_populates="dashboards")  # noqa: F821
    widgets: Mapped[list["Widget"]] = relationship(
        back_populates="dashboard", cascade="all, delete-orphan"
    )
    filters: Mapped[list["DashboardFilter"]] = relationship(
        back_populates="dashboard", cascade="all, delete-orphan"
    )


class Widget(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A widget is a pointer to a workflow output node.

    It does NOT store its own query. Changing the source workflow
    changes the widget output. Deleting the workflow orphans the widget.
    """

    __tablename__ = "widgets"

    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dashboards.id")
    )
    source_workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id")
    )
    source_node_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(255))
    layout: Mapped[dict] = mapped_column(JSONB, default=dict)
    config_overrides: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    dashboard: Mapped["Dashboard"] = relationship(back_populates="widgets")
    source_workflow: Mapped["Workflow"] = relationship(back_populates="widgets")  # noqa: F821


class FilterType(str, enum.Enum):
    DATE_RANGE = "date_range"
    DROPDOWN = "dropdown"
    TEXT = "text"


class DashboardFilter(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "dashboard_filters"

    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dashboards.id")
    )
    filter_type: Mapped[FilterType]
    target_column: Mapped[str] = mapped_column(String(255))
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    position: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    dashboard: Mapped["Dashboard"] = relationship(back_populates="filters")


class APIKey(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    """API keys for embed mode. Scoped to specific widgets and tenant."""

    __tablename__ = "api_keys"

    key_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    label: Mapped[str | None] = mapped_column(String(255))
    scoped_widget_ids: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    revoked_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    rate_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="api_keys")  # noqa: F821
