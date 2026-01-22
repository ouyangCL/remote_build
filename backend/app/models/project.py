"""Project model."""
import enum
from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.environment import EnvironmentType

if TYPE_CHECKING:
    from app.models.deployment import Deployment


class ProjectType(str, enum.Enum):
    """Project types."""

    FRONTEND = "frontend"
    BACKEND = "backend"
    JAVA = "java"


class Project(Base, TimestampMixin):
    """Project model."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    git_url: Mapped[str] = mapped_column(String(500), nullable=False)
    git_ssh_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_type: Mapped[ProjectType] = mapped_column(String(20), nullable=False)
    build_script: Mapped[str] = mapped_column(Text, nullable=False)
    deploy_script_path: Mapped[str] = mapped_column(
        String(255), nullable=False, default="/opt/restart.sh"
    )
    output_dir: Mapped[str] = mapped_column(
        String(255), nullable=False, default="dist"
    )
    environment: Mapped[EnvironmentType] = mapped_column(
        String(20), default=EnvironmentType.DEVELOPMENT, nullable=False, index=True
    )

    # Relationships
    deployments: Mapped[list["Deployment"]] = relationship(
        "Deployment", back_populates="project", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name='{self.name}', type='{self.project_type}')>"

    @property
    def has_git_credentials(self) -> bool:
        """Check if project has Git credentials configured (SSH key)."""
        return bool(self.git_ssh_key)
