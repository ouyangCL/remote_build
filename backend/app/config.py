"""Application configuration."""
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "DevOps Deployment Platform"
    app_version: str = "1.0.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 9090

    # Database
    database_url: str = "sqlite:///./devops.db"
    # For PostgreSQL: postgresql://user:password@host:port/database

    # JWT
    secret_key: str = Field(
        default="your-secret-key-change-in-production",
        description="Secret key for JWT token signing"
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Encryption
    encryption_key: str = Field(
        default="your-encryption-key-change-in-production",
        description="Key for encrypting sensitive data like SSH keys"
    )

    # File Storage
    work_dir: str = "./work"
    artifacts_dir: str = "./artifacts"
    logs_dir: str = "./logs"
    max_artifacts_size_mb: int = 1024  # 1GB

    # Deployment
    max_concurrent_deployments: int = 5
    build_timeout_seconds: int = 3600  # 1 hour
    ssh_timeout_seconds: int = 300  # 5 minutes

    # CORS
    cors_origins: list[str] = ["http://localhost:5050", "http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from comma-separated string or list.

        Args:
            v: Comma-separated string or list of origins

        Returns:
            List of origins
        """
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # Environment
    environment: Literal["development", "production"] = "development"


settings = Settings()
