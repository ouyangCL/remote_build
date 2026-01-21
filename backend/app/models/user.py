"""User model."""
import enum
from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.deployment import Deployment


class UserRole(str, enum.Enum):
    """User roles."""

    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class User(Base, TimestampMixin):
    """User model."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(String(20), default=UserRole.VIEWER, nullable=False)
    email: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    deployments: Mapped[list["Deployment"]] = relationship(
        "Deployment", back_populates="created_by_user", lazy="selectin"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="user", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"

    @property
    def is_admin(self) -> bool:
        """Check if user is admin."""
        return self.role == UserRole.ADMIN

    @property
    def can_deploy(self) -> bool:
        """Check if user can deploy."""
        return self.role in {UserRole.ADMIN, UserRole.OPERATOR}
