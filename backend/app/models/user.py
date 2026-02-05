"""User model."""

import enum

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class UserRole(enum.StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class User(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(default=UserRole.ANALYST)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relationships
    workflows: Mapped[list["Workflow"]] = relationship(back_populates="created_by_user")  # noqa: F821
    dashboards: Mapped[list["Dashboard"]] = relationship(  # noqa: F821
        back_populates="created_by_user"
    )
    api_keys: Mapped[list["APIKey"]] = relationship(back_populates="user")  # noqa: F821
