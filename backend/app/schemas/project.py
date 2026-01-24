"""Project schemas."""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ProjectBase(BaseModel):
    """Base project schema."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    git_url: str = Field(..., min_length=1, max_length=500)
    git_token: str | None = Field(None, description="Git access token for HTTPS private repositories")
    project_type: str = Field(..., pattern="^(frontend|backend|java)$")
    build_script: str = Field(..., min_length=1)
    upload_path: str = Field(default="", max_length=255, description="Server-side path for uploading deployment packages")
    restart_script_path: str = Field(default="/opt/restart.sh", max_length=255, description="Server-side script to restart the application")
    restart_only_script_path: str | None = Field(
        default=None,
        description="仅重启部署模式专用的重启脚本路径"
    )
    output_dir: str = Field(default="dist", max_length=255)
    # Dependency installation
    install_script: str | None = Field(
        default=None,
        max_length=500,
        description="Custom dependency installation command (e.g., 'npm ci', 'yarn install', 'pip install -r requirements.txt')"
    )
    auto_install: bool = Field(
        default=True,
        description="Automatically install dependencies before build"
    )
    environment: str = Field(default="development", pattern="^(development|production)$")

    # Health Check Configuration
    health_check_enabled: bool = Field(default=False, description="Enable health check after deployment")
    health_check_type: str = Field(default="http", pattern="^(http|tcp|command)$", description="Type of health check")
    health_check_url: str | None = Field(None, max_length=500, description="URL for HTTP health check (e.g., http://localhost:8080/health)")
    health_check_port: int | None = Field(None, ge=1, le=65535, description="Port number for TCP health check")
    health_check_command: str | None = Field(None, description="Custom command for health check")
    health_check_timeout: int = Field(default=30, ge=1, le=300, description="Health check timeout in seconds")
    health_check_retries: int = Field(default=3, ge=1, le=10, description="Number of retries before marking as failed")
    health_check_interval: int = Field(default=5, ge=1, le=60, description="Interval between retries in seconds")


class ProjectCreate(ProjectBase):
    """Project creation schema."""

    git_ssh_key: str | None = Field(None, description="SSH private key for private repositories (e.g., GitLab/GitHub deploy key)")


class ProjectUpdate(BaseModel):
    """Project update schema."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    git_url: str | None = Field(None, min_length=1, max_length=500)
    git_token: str | None = Field(None, description="Git access token for HTTPS private repositories")
    git_ssh_key: str | None = Field(None, description="SSH private key for private repositories")
    project_type: str | None = Field(None, pattern="^(frontend|backend|java)$")
    build_script: str | None = None
    upload_path: str | None = Field(None, max_length=255, description="Server-side path for uploading deployment packages")
    restart_script_path: str | None = Field(None, max_length=255, description="Server-side script to restart the application")
    restart_only_script_path: str | None = Field(
        default=None,
        description="仅重启部署模式专用的重启脚本路径"
    )
    output_dir: str | None = Field(None, max_length=255)
    # Dependency installation
    install_script: str | None = Field(
        default=None,
        max_length=500,
        description="Custom dependency installation command"
    )
    auto_install: bool | None = Field(
        default=None,
        description="Automatically install dependencies before build"
    )
    environment: str | None = Field(None, pattern="^(development|production)$")

    # Health Check Configuration
    health_check_enabled: bool | None = Field(None, description="Enable health check after deployment")
    health_check_type: str | None = Field(None, pattern="^(http|tcp|command)$", description="Type of health check")
    health_check_url: str | None = Field(None, max_length=500, description="URL for HTTP health check")
    health_check_port: int | None = Field(None, ge=1, le=65535, description="Port number for TCP health check")
    health_check_command: str | None = Field(None, description="Custom command for health check")
    health_check_timeout: int | None = Field(None, ge=1, le=300, description="Health check timeout in seconds")
    health_check_retries: int | None = Field(None, ge=1, le=10, description="Number of retries before marking as failed")
    health_check_interval: int | None = Field(None, ge=1, le=60, description="Interval between retries in seconds")


class ProjectResponse(ProjectBase):
    """Project response schema."""

    id: int
    created_at: datetime
    updated_at: datetime
    has_git_credentials: bool = Field(default=False, description="Whether the project has Git credentials configured")

    model_config = {"from_attributes": True}


class BranchListResponse(BaseModel):
    """Branch list response schema."""

    branches: list[str]
