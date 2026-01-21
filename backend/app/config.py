"""Application configuration."""
import secrets
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

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str, info) -> str:
        """Validate that production environment uses a strong secret key.

        Args:
            v: The secret key value
            info: Field validation info

        Returns:
            The validated secret key

        Raises:
            ValueError: If production environment uses weak secret key
        """
        if hasattr(info, "data") and info.data.get("environment") == "production":
            weak_keys = [
                "your-secret-key-change-in-production",
                "your-secret-key",
                "secret",
                "dev-secret-key",
                "CHANGE_ME",
            ]
            if v in weak_keys or len(v) < 32:
                raise ValueError(
                    "生产环境必须使用强密钥！请使用至少32个字符的随机字符串作为 SECRET_KEY。"
                    "建议使用: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )
        return v

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, v: str, info) -> str:
        """Validate that production environment uses a strong encryption key.

        Args:
            v: The encryption key value
            info: Field validation info

        Returns:
            The validated encryption key

        Raises:
            ValueError: If production environment uses weak encryption key
        """
        if hasattr(info, "data") and info.data.get("environment") == "production":
            weak_keys = [
                "your-encryption-key-change-in-production",
                "your-encryption-key",
                "encryption",
                "dev-encryption-key",
                "CHANGE_ME",
            ]
            if v in weak_keys or len(v) < 32:
                raise ValueError(
                    "生产环境必须使用强加密密钥！请使用至少32字节的随机字符串作为 ENCRYPTION_KEY。"
                    "建议使用: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )
        return v

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str, info) -> str:
        """Validate and warn about database choice for production.

        Args:
            v: The database URL
            info: Field validation info

        Returns:
            The validated database URL
        """
        if hasattr(info, "data") and info.data.get("environment") == "production":
            if v.startswith("sqlite:///"):
                import warnings
                warnings.warn(
                    "生产环境推荐使用 PostgreSQL 而不是 SQLite。"
                    "SQLite 在生产环境中可能存在性能和并发限制。"
                )
        return v


settings = Settings()
