"""Deployment schemas."""
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.deployment import DeploymentType


class DeploymentCreate(BaseModel):
    """Deployment creation schema."""

    project_id: int = Field(..., ge=1)
    branch: str = Field(..., min_length=1, max_length=100)
    server_group_ids: list[int] = Field(..., min_length=1)
    deployment_type: DeploymentType = Field(default=DeploymentType.FULL)


class DeploymentResponse(BaseModel):
    """Deployment response schema."""

    id: int
    project_id: int
    branch: str
    status: str
    deployment_type: DeploymentType
    commit_hash: str | None = None
    commit_message: str | None = None
    error_message: str | None = None
    created_at: datetime
    created_by: int | None = None
    rollback_from: int | None = None
    environment: str = "development"

    model_config = {"from_attributes": True}


class DeploymentDetailResponse(DeploymentResponse):
    """Deployment detail response schema."""

    project: dict | None = None
    server_groups: list[dict] = []
    logs: list[dict] = []


class RollbackCreate(BaseModel):
    """Rollback creation schema."""

    server_group_ids: list[int] = Field(..., min_length=1)
