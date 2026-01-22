"""User management schemas."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserBase(BaseModel):
    """Base user schema."""

    username: str = Field(..., min_length=1, max_length=50)
    email: EmailStr | None = None
    role: str = Field(..., pattern="^(admin|operator|viewer)$")
    is_active: bool = True

    @field_validator('email')
    @classmethod
    def empty_email_to_none(cls, v: str | None) -> str | None:
        """Convert empty string to None."""
        if v is None or v.strip() == '':
            return None
        return v


class UserCreate(UserBase):
    """User creation schema."""

    password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    """User update schema."""

    username: str | None = Field(None, min_length=1, max_length=50)
    email: EmailStr | None = None
    role: str | None = Field(None, pattern="^(admin|operator|viewer)$")
    password: str | None = Field(None, min_length=6)
    is_active: bool | None = None


class UserResponse(BaseModel):
    """User response schema."""

    id: int
    username: str
    role: str
    email: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Audit Log Schemas
class AuditLogResponse(BaseModel):
    """Audit log response schema."""

    id: int
    user_id: int
    action: str
    resource_type: str | None = None
    resource_id: int | None = None
    details: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime
    updated_at: datetime

    # Include nested user info
    user: UserResponse | None = None

    model_config = {"from_attributes": True}


class AuditLogResponseWithUser(BaseModel):
    """Audit log response with user info."""

    id: int
    user_id: int
    action: str
    resource_type: str | None = None
    resource_id: int | None = None
    details: Any | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime
    updated_at: datetime

    user: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class PaginatedAuditLogs(BaseModel):
    """Paginated audit logs response schema."""

    items: list[AuditLogResponseWithUser]
    total: int
    page: int
    page_size: int
    total_pages: int
