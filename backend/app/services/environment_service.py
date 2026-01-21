"""Environment validation service."""
from typing import List

from app.models.environment import EnvironmentType
from app.models.project import Project
from app.models.server import ServerGroup
from fastapi import HTTPException


class EnvironmentService:
    """Service for environment validation and utilities."""

    @staticmethod
    def validate_deployment_environment(project: Project, server_groups: List[ServerGroup]) -> None:
        """
        Validate that project and all server groups have matching environments.

        Args:
            project: The project being deployed
            server_groups: List of server groups selected for deployment

        Raises:
            HTTPException: If environments don't match
        """
        if not server_groups:
            raise HTTPException(
                status_code=400,
                detail="至少需要选择一个服务器组"
            )

        mismatched_groups = [
            sg.name for sg in server_groups
            if sg.environment != project.environment
        ]

        if mismatched_groups:
            project_env = EnvironmentService.get_environment_display_name(project.environment)
            groups_str = ", ".join(mismatched_groups)
            raise HTTPException(
                status_code=400,
                detail=f"环境不匹配：项目属于 {project_env} 环境，但以下服务器组属于不同环境：{groups_str}"
            )

    @staticmethod
    def get_environment_display_name(environment: EnvironmentType | str) -> str:
        """
        Get human-readable display name for environment.

        Args:
            environment: The environment type (enum or string)

        Returns:
            Display name in Chinese
        """
        # Handle string values
        if isinstance(environment, str):
            env_value = environment
        else:
            env_value = environment.value

        display_names = {
            "development": "开发/测试",
            "production": "生产"
        }
        return display_names.get(env_value, env_value)

    @staticmethod
    def get_environment_color(environment: EnvironmentType | str) -> str:
        """
        Get color code for environment UI display.

        Args:
            environment: The environment type (enum or string)

        Returns:
            CSS color class or hex code
        """
        # Handle string values
        if isinstance(environment, str):
            env_value = environment
        else:
            env_value = environment.value

        colors = {
            "development": "success",  # Green
            "production": "danger"     # Red
        }
        return colors.get(env_value, "info")

    @staticmethod
    def get_environment_badge_style(environment: EnvironmentType | str) -> dict:
        """
        Get complete badge styling information for environment.

        Args:
            environment: The environment type (enum or string)

        Returns:
            Dictionary with color, icon, and label information
        """
        # Handle string values
        if isinstance(environment, str):
            env_value = environment
        else:
            env_value = environment.value

        styles = {
            "development": {
                "color": "success",
                "icon": "ri-code-s-slash-line",
                "label": "开发/测试"
            },
            "production": {
                "color": "danger",
                "icon": "ri-server-line",
                "label": "生产"
            }
        }
        return styles.get(env_value, {
            "color": "info",
            "icon": "ri-question-line",
            "label": env_value
        })
