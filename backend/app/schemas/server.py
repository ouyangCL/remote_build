"""Server schemas."""
from pydantic import BaseModel, Field


class ServerBase(BaseModel):
    """Base server schema."""

    name: str = Field(..., min_length=1, max_length=100)
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(..., min_length=1, max_length=50)
    auth_type: str = Field(default="password", pattern="^(password|ssh_key)$")
    auth_value: str = Field(..., min_length=1)  # Will be encrypted
    deploy_path: str = Field(default="/opt/app", max_length=255)


class ServerCreate(ServerBase):
    """Server creation schema."""

    pass


class ServerUpdate(BaseModel):
    """Server update schema."""

    name: str | None = Field(None, min_length=1, max_length=100)
    host: str | None = Field(None, min_length=1, max_length=255)
    port: int | None = Field(None, ge=1, le=65535)
    username: str | None = Field(None, min_length=1, max_length=50)
    auth_type: str | None = Field(None, pattern="^(password|ssh_key)$")
    auth_value: str | None = None
    deploy_path: str | None = Field(None, max_length=255)


class ServerResponse(ServerBase):
    """Server response schema."""

    id: int
    is_active: bool
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class ServerGroupBase(BaseModel):
    """Base server group schema."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None


class ServerGroupCreate(ServerGroupBase):
    """Server group creation schema."""

    server_ids: list[int] = Field(default_factory=list)


class ServerGroupUpdate(BaseModel):
    """Server group update schema."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    server_ids: list[int] | None = None


class ServerGroupResponse(ServerGroupBase):
    """Server group response schema."""

    id: int
    created_at: str
    updated_at: str
    servers: list[ServerResponse] = []

    model_config = {"from_attributes": True}


class ConnectionTestResponse(BaseModel):
    """Connection test response schema."""

    success: bool
    message: str
