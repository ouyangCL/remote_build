"""Authentication schemas."""
from datetime import datetime
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Login request schema."""

    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Token response schema."""

    access_token: str
    token_type: str = "bearer"


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
