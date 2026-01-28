"""Project model."""
import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.environment import EnvironmentType

if TYPE_CHECKING:
    from app.models.deployment import Deployment


class ProjectType(str, enum.Enum):
    """Project types."""

    FRONTEND = "frontend"
    JAVA = "java"


class HealthCheckType(str, enum.Enum):
    """Health check types."""

    HTTP = "http"
    TCP = "tcp"
    COMMAND = "command"


class Project(Base, TimestampMixin):
    """Project model."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    git_url: Mapped[str] = mapped_column(String(500), nullable=False)
    # Git credentials - support three authentication methods:
    # 1. OAuth2 token (git_token): For GitHub, GitLab, etc.
    # 2. Basic auth (git_username + git_password): For private Git servers
    # 3. SSH key (git_ssh_key): For SSH-based authentication
    git_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    git_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    git_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    git_ssh_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_type: Mapped[ProjectType] = mapped_column(String(20), nullable=False)
    build_script: Mapped[str] = mapped_column(Text, nullable=False)
    # Upload path for deployment packages (server-side path)
    upload_path: Mapped[str] = mapped_column(
        String(255), nullable=False, default=""
    )
    # Restart script path to execute after deployment
    restart_script_path: Mapped[str] = mapped_column(
        String(255), nullable=False, default="/opt/restart.sh"
    )
    # Restart script path for restart-only deployment mode
    restart_only_script_path: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )
    output_dir: Mapped[str] = mapped_column(
        String(255), nullable=False, default="dist"
    )
    # Dependency installation configuration
    install_script: Mapped[str | None] = mapped_column(
        String(500), nullable=True, default=None
    )
    auto_install: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    environment: Mapped[EnvironmentType] = mapped_column(
        String(20), default=EnvironmentType.DEVELOPMENT, nullable=False, index=True
    )

    # Health Check Configuration
    health_check_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    health_check_type: Mapped[HealthCheckType] = mapped_column(
        String(20), default=HealthCheckType.HTTP, nullable=False
    )
    health_check_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    health_check_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    health_check_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    health_check_timeout: Mapped[int] = mapped_column(
        Integer, default=30, nullable=False
    )
    health_check_retries: Mapped[int] = mapped_column(
        Integer, default=3, nullable=False
    )
    health_check_interval: Mapped[int] = mapped_column(
        Integer, default=5, nullable=False
    )

    # Relationships
    deployments: Mapped[list["Deployment"]] = relationship(
        "Deployment", back_populates="project", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name='{self.name}', type='{self.project_type}')>"

    @property
    def has_git_credentials(self) -> bool:
        """Check if project has Git credentials configured (any method)."""
        return bool(self.git_token or self.git_username or self.git_ssh_key)
