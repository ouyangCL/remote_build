"""Server and ServerGroup models."""
import enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.deployment import Deployment

# Association table for server groups
server_group_members = Table(
    "server_group_members",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("group_id", Integer, ForeignKey("server_groups.id", ondelete="CASCADE")),
    Column("server_id", Integer, ForeignKey("servers.id", ondelete="CASCADE")),
    Column("is_active", Boolean, default=True, nullable=False),
)


class AuthType(str, enum.Enum):
    """SSH authentication types."""

    PASSWORD = "password"
    SSH_KEY = "ssh_key"


class Server(Base, TimestampMixin):
    """Server model."""

    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=22, nullable=False)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    auth_type: Mapped[AuthType] = mapped_column(String(20), default=AuthType.PASSWORD, nullable=False)
    auth_value: Mapped[str] = mapped_column(Text, nullable=False)  # Encrypted password or key
    deploy_path: Mapped[str] = mapped_column(
        String(255), nullable=False, default="/opt/app"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    server_groups: Mapped[list["ServerGroup"]] = relationship(
        "ServerGroup",
        secondary=server_group_members,
        back_populates="servers",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Server(id={self.id}, name='{self.name}', host='{self.host}')>"


class ServerGroup(Base, TimestampMixin):
    """Server group model."""

    __tablename__ = "server_groups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    servers: Mapped[list[Server]] = relationship(
        "Server",
        secondary=server_group_members,
        back_populates="server_groups",
        lazy="selectin",
    )
    deployments: Mapped[list["Deployment"]] = relationship(
        "Deployment",
        secondary="deployment_server_mappings",
        back_populates="server_groups",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<ServerGroup(id={self.id}, name='{self.name}')>"
