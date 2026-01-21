"""Audit log model for tracking user actions."""
import enum
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class AuditAction(str, enum.Enum):
    """Audit action types."""

    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"

    # User management
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    USER_TOGGLE = "user_toggle"

    # Project management
    PROJECT_CREATE = "project_create"
    PROJECT_UPDATE = "project_update"
    PROJECT_DELETE = "project_delete"

    # Server management
    SERVER_CREATE = "server_create"
    SERVER_UPDATE = "server_update"
    SERVER_DELETE = "server_delete"
    SERVER_GROUP_CREATE = "server_group_create"
    SERVER_GROUP_UPDATE = "server_group_update"
    SERVER_GROUP_DELETE = "server_group_delete"

    # Deployment operations
    DEPLOYMENT_CREATE = "deployment_create"
    DEPLOYMENT_CANCEL = "deployment_cancel"
    DEPLOYMENT_ROLLBACK = "deployment_rollback"


class AuditLog(Base, TimestampMixin):
    """Audit log model for tracking user actions."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(nullable=False, index=True)
    action: Mapped[AuditAction] = mapped_column(String(50), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    resource_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="audit_logs", lazy="selectin")

    __table_args__ = (
        Index("ix_audit_logs_user_action", "user_id", "action"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, user_id={self.user_id}, action='{self.action}')>"
