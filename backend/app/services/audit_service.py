"""Audit log service for recording user actions."""
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditAction, AuditLog


def create_audit_log(
    db: Session,
    user_id: int,
    action: AuditAction,
    resource_type: str | None = None,
    resource_id: int | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    """Create an audit log entry.

    Args:
        db: Database session
        user_id: ID of the user performing the action
        action: Type of action performed
        resource_type: Type of resource affected (e.g., 'project', 'server')
        resource_id: ID of the resource affected
        details: Additional details about the action (will be JSON serialized)
        ip_address: IP address of the request
        user_agent: User agent string of the request

    Returns:
        Created audit log entry
    """
    details_json = json.dumps(details) if details else None

    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details_json,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)

    return audit_log


def log_login(
    db: Session,
    user_id: int,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    """Record a user login.

    Args:
        db: Database session
        user_id: ID of the user logging in
        ip_address: IP address of the request
        user_agent: User agent string of the request

    Returns:
        Created audit log entry
    """
    return create_audit_log(
        db=db,
        user_id=user_id,
        action=AuditAction.LOGIN,
        details={"event": "user_login"},
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_logout(
    db: Session,
    user_id: int,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    """Record a user logout.

    Args:
        db: Database session
        user_id: ID of the user logging out
        ip_address: IP address of the request
        user_agent: User agent string of the request

    Returns:
        Created audit log entry
    """
    return create_audit_log(
        db=db,
        user_id=user_id,
        action=AuditAction.LOGOUT,
        details={"event": "user_logout"},
        ip_address=ip_address,
        user_agent=user_agent,
    )
