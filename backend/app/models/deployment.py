"""Deployment model."""
import enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.environment import EnvironmentType

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.server import ServerGroup
    from app.models.user import User


class DeploymentStatus(str, enum.Enum):
    """Deployment status."""

    PENDING = "pending"
    CLONING = "cloning"
    BUILDING = "building"
    UPLOADING = "uploading"
    DEPLOYING = "deploying"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLBACK = "rollback"


# Association table for deployment server groups
deployment_server_mappings = Table(
    "deployment_server_mappings",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("deployment_id", Integer, ForeignKey("deployments.id", ondelete="CASCADE")),
    Column("server_group_id", Integer, ForeignKey("server_groups.id", ondelete="CASCADE")),
)


class Deployment(Base, TimestampMixin):
    """Deployment model."""

    __tablename__ = "deployments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch: Mapped[str] = mapped_column(String(100), nullable=False)
    commit_hash: Mapped[str | None] = mapped_column(String(40), nullable=True)
    commit_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DeploymentStatus] = mapped_column(
        String(20), default=DeploymentStatus.PENDING, nullable=False, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    environment: Mapped[EnvironmentType] = mapped_column(
        String(20), default=EnvironmentType.DEVELOPMENT, nullable=False, index=True
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project", back_populates="deployments", lazy="selectin"
    )
    created_by_user: Mapped["User"] = relationship(
        "User", back_populates="deployments", lazy="selectin"
    )
    server_groups: Mapped[list["ServerGroup"]] = relationship(
        "ServerGroup",
        secondary=deployment_server_mappings,
        back_populates="deployments",
        lazy="selectin",
    )
    artifacts: Mapped[list["DeploymentArtifact"]] = relationship(
        "DeploymentArtifact",
        back_populates="deployment",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    logs: Mapped[list["DeploymentLog"]] = relationship(
        "DeploymentLog",
        back_populates="deployment",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="DeploymentLog.created_at",
    )
    rollback_from: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("deployments.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<Deployment(id={self.id}, project_id={self.project_id}, branch='{self.branch}', status='{self.status}')>"


class DeploymentArtifact(Base, TimestampMixin):
    """Deployment artifact model."""

    __tablename__ = "deployment_artifacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    deployment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # Size in bytes
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256

    # Relationships
    deployment: Mapped["Deployment"] = relationship(
        "Deployment", back_populates="artifacts", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<DeploymentArtifact(id={self.id}, deployment_id={self.deployment_id}, file_path='{self.file_path}')>"


class DeploymentLog(Base, TimestampMixin):
    """Deployment log model."""

    __tablename__ = "deployment_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    deployment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    level: Mapped[str] = mapped_column(String(20), default="INFO", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    deployment: Mapped["Deployment"] = relationship(
        "Deployment", back_populates="logs", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<DeploymentLog(id={self.id}, deployment_id={self.deployment_id}, level='{self.level}')>"
