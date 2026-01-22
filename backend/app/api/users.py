"""User management API routes."""
import json
from datetime import datetime
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.session import get_db
from app.dependencies import get_current_admin
from app.models.audit_log import AuditAction, AuditLog
from app.models.user import User, UserRole
from app.schemas.user import (
    AuditLogResponseWithUser,
    PaginatedAuditLogs,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/api/users", tags=["User Management"])

audit_router = APIRouter(prefix="/api/audit-logs", tags=["Audit Logs"])


@router.get("", response_model=list[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> list[User]:
    """List all users (admin only)."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return cast(list[User], users)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> User:
    """Create a new user (admin only)."""
    # Check if username already exists
    existing = db.query(User).filter(User.username == user_data.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    # Check if email already exists
    if user_data.email:
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists",
            )

    # Create new user
    new_user = User(
        username=user_data.username,
        hashed_password=get_password_hash(user_data.password),
        role=user_data.role,
        email=user_data.email,
        is_active=user_data.is_active,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Log the action
    create_audit_log(
        db=db,
        user_id=current_admin.id,
        action=AuditAction.USER_CREATE,
        resource_type="user",
        resource_id=new_user.id,
        details={"target_username": user_data.username, "role": user_data.role},
    )

    return cast(User, new_user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> User:
    """Get user by ID (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return cast(User, user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> User:
    """Update a user (admin only).

    Users cannot modify their own role.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent user from modifying their own role
    if user_id == current_admin.id and user_data.role is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify your own role",
        )

    # Check username uniqueness if being updated
    if user_data.username and user_data.username != user.username:
        existing = db.query(User).filter(User.username == user_data.username).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )

    # Check email uniqueness if being updated
    if user_data.email and user_data.email != user.email:
        existing = db.query(User).filter(User.email == user_data.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists",
            )

    # Update fields
    update_data = user_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "password" and value is not None:
            user.hashed_password = get_password_hash(value)
        elif field != "password":
            setattr(user, field, value)

    db.commit()
    db.refresh(user)

    # Log the action
    create_audit_log(
        db=db,
        user_id=current_admin.id,
        action=AuditAction.USER_UPDATE,
        resource_type="user",
        resource_id=user.id,
        details={"target_username": user.username, "updates": list(update_data.keys())},
    )

    return cast(User, user)


@router.patch("/{user_id}/toggle", response_model=UserResponse)
async def toggle_user_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> User:
    """Toggle user active status (admin only).

    Users cannot disable themselves.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent user from disabling themselves
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot disable your own account",
        )

    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)

    # Log the action
    create_audit_log(
        db=db,
        user_id=current_admin.id,
        action=AuditAction.USER_TOGGLE,
        resource_type="user",
        resource_id=user.id,
        details={"target_username": user.username, "new_status": user.is_active},
    )

    return cast(User, user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> None:
    """Delete a user (admin only).

    Users cannot delete themselves.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent user from deleting themselves
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete your own account",
        )

    username = user.username

    db.delete(user)
    db.commit()

    # Log the action
    create_audit_log(
        db=db,
        user_id=current_admin.id,
        action=AuditAction.USER_DELETE,
        resource_type="user",
        resource_id=user_id,
        details={"target_username": username},
    )


@audit_router.get("", response_model=PaginatedAuditLogs)
async def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int | None = Query(None),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> PaginatedAuditLogs:
    """Get audit logs with filtering and pagination (admin only)."""
    # Build query
    query = db.query(AuditLog)

    # Apply filters
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)

    if action is not None:
        query = query.filter(AuditLog.action == action)

    if resource_type is not None:
        query = query.filter(AuditLog.resource_type == resource_type)

    if start_date is not None:
        query = query.filter(AuditLog.created_at >= start_date)

    if end_date is not None:
        query = query.filter(AuditLog.created_at <= end_date)

    # Get total count
    total = query.count()

    # Calculate pagination
    total_pages = (total + page_size - 1) // page_size
    offset = (page - 1) * page_size

    # Get paginated results
    logs = (
        query.order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    # Build response with user info
    items = []
    for log in logs:
        user_dict = None
        if log.user:
            user_dict = {
                "id": log.user.id,
                "username": log.user.username,
                "role": log.user.role,
            }

        # Parse details JSON if present
        details_dict = None
        if log.details:
            try:
                # details might already be a dict (SQLAlchemy auto-parsed) or a string
                if isinstance(log.details, dict):
                    details_dict = log.details
                else:
                    details_dict = json.loads(log.details)
            except Exception:
                details_dict = log.details

        items.append(
            AuditLogResponseWithUser(
                id=log.id,
                user_id=log.user_id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                details=details_dict,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                created_at=log.created_at,
                updated_at=log.updated_at,
                user=user_dict,
            )
        )

    return PaginatedAuditLogs(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
