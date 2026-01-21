"""Role-based access control (RBAC) permissions."""
from functools import wraps
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models.user import User, UserRole

security = HTTPBearer()


class Permission:
    """Permission checker."""

    @staticmethod
    def require_role(*roles: UserRole) -> Callable[[User], None]:
        """Create a dependency that requires specific role(s).

        Args:
            *roles: Allowed roles

        Returns:
            Dependency function
        """

        def check_role(current_user: User) -> None:
            """Check if user has required role."""
            if current_user.role not in roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required role: {[r.value for r in roles]}",
                )

        return check_role

    @staticmethod
    def require_admin(current_user: User = Depends(lambda: None)) -> None:
        """Require admin role.

        Args:
            current_user: Current authenticated user

        Raises:
            HTTPException: If user is not admin
        """
        if not current_user or not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required",
            )

    @staticmethod
    def require_deploy_permission(current_user: User) -> None:
        """Require permission to deploy (admin or operator).

        Args:
            current_user: Current authenticated user

        Raises:
            HTTPException: If user cannot deploy
        """
        if not current_user.can_deploy:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Deploy permission required (admin or operator role)",
            )


# Common permission dependencies
require_admin = Permission.require_role(UserRole.ADMIN)
require_operator = Permission.require_role(UserRole.ADMIN, UserRole.OPERATOR)
require_viewer = Permission.require_role(UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER)
