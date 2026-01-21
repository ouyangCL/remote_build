"""Audit log decorator for automatic action logging."""
import functools
from typing import Any, Callable, ParamSpec

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit_log import AuditAction
from app.services.audit_service import create_audit_log

P = ParamSpec("P")


def audit_log(
    action: AuditAction,
    resource_type: str | None = None,
    resource_id_arg: str | None = None,
    details_builder: Callable[..., dict[str, Any]] | None = None,
) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
    """Decorator to automatically log API actions to audit log.

    Args:
        action: The type of action being performed
        resource_type: Type of resource (e.g., 'project', 'server')
        resource_id_arg: Name of the argument containing the resource ID
        details_builder: Optional function to build details dict from function arguments

    Returns:
        Decorator function

    Example:
        @audit_log(AuditAction.PROJECT_CREATE, resource_type="project")
        async def create_project(...):
            ...

        @audit_log(
            AuditAction.PROJECT_UPDATE,
            resource_type="project",
            resource_id_arg="project_id"
        )
        async def update_project(project_id: int, ...):
            ...
    """

    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            # Extract request and db from kwargs if available
            request: Request | None = kwargs.get("request")
            db: Session | None = kwargs.get("db")

            # Execute the function
            result = await func(*args, **kwargs)

            # Log after successful execution
            if db:
                # Get user from request or current_user dependency
                user_id = None
                if request and hasattr(request.state, "user"):
                    user_id = request.state.user.id
                elif "current_user" in kwargs:
                    user_id = kwargs["current_user"].id
                elif "current_admin" in kwargs:
                    user_id = kwargs["current_admin"].id

                # Get resource ID if specified
                resource_id = None
                if resource_id_arg and resource_id_arg in kwargs:
                    resource_id = kwargs[resource_id_arg]

                # Build details
                details = None
                if details_builder:
                    details = details_builder(*args, **kwargs)

                # Get IP and user agent from request
                ip_address = None
                user_agent = None
                if request:
                    ip_address = request.client.host if request.client else None
                    user_agent = request.headers.get("user-agent")

                # Create audit log
                if user_id:
                    try:
                        create_audit_log(
                            db=db,
                            user_id=user_id,
                            action=action,
                            resource_type=resource_type,
                            resource_id=resource_id,
                            details=details,
                            ip_address=ip_address,
                            user_agent=user_agent,
                        )
                    except Exception:
                        # Don't fail the request if audit logging fails
                        pass

            return result

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            # Extract request and db from kwargs if available
            request: Request | None = kwargs.get("request")
            db: Session | None = kwargs.get("db")

            # Execute the function
            result = func(*args, **kwargs)

            # Log after successful execution
            if db:
                # Get user from request or current_user dependency
                user_id = None
                if request and hasattr(request.state, "user"):
                    user_id = request.state.user.id
                elif "current_user" in kwargs:
                    user_id = kwargs["current_user"].id
                elif "current_admin" in kwargs:
                    user_id = kwargs["current_admin"].id

                # Get resource ID if specified
                resource_id = None
                if resource_id_arg and resource_id_arg in kwargs:
                    resource_id = kwargs[resource_id_arg]

                # Build details
                details = None
                if details_builder:
                    details = details_builder(*args, **kwargs)

                # Get IP and user agent from request
                ip_address = None
                user_agent = None
                if request:
                    ip_address = request.client.host if request.client else None
                    user_agent = request.headers.get("user-agent")

                # Create audit log
                if user_id:
                    try:
                        create_audit_log(
                            db=db,
                            user_id=user_id,
                            action=action,
                            resource_type=resource_type,
                            resource_id=resource_id,
                            details=details,
                            ip_address=ip_address,
                            user_agent=user_agent,
                        )
                    except Exception:
                        # Don't fail the request if audit logging fails
                        pass

            return result

        # Return appropriate wrapper based on whether function is async
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
