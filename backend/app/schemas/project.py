"""Project schemas."""
from datetime import datetime

from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    """Base project schema."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    git_url: str = Field(..., min_length=1, max_length=500)
    project_type: str = Field(..., pattern="^(frontend|backend)$")
    build_script: str = Field(..., min_length=1)
    deploy_script_path: str = Field(default="/opt/restart.sh", max_length=255)
    output_dir: str = Field(default="dist", max_length=255)
    environment: str = Field(default="development", pattern="^(development|production)$")


class ProjectCreate(ProjectBase):
    """Project creation schema."""

    git_token: str | None = Field(None, max_length=255, description="Git access token for private repositories")


class ProjectUpdate(BaseModel):
    """Project update schema."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    git_url: str | None = Field(None, min_length=1, max_length=500)
    git_token: str | None = Field(None, max_length=255, description="Git access token for private repositories")
    project_type: str | None = Field(None, pattern="^(frontend|backend)$")
    build_script: str | None = None
    deploy_script_path: str | None = Field(None, max_length=255)
    output_dir: str | None = Field(None, max_length=255)
    environment: str | None = Field(None, pattern="^(development|production)$")


class ProjectResponse(ProjectBase):
    """Project response schema."""

    id: int
    created_at: datetime
    updated_at: datetime
    has_git_token: bool = Field(default=False, description="Whether the project has a Git token configured")

    model_config = {"from_attributes": True}


class BranchListResponse(BaseModel):
    """Branch list response schema."""

    branches: list[str]
