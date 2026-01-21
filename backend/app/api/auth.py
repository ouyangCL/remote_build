"""Authentication API routes."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.db.session import get_db
from app.dependencies import get_current_user, get_current_admin
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.services.audit_service import log_login, log_logout

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """User login endpoint.

    Args:
        credentials: Login credentials
        request: FastAPI request
        db: Database session

    Returns:
        Access token

    Raises:
        HTTPException: If credentials are invalid
    """
    user = db.query(User).filter(User.username == credentials.username).first()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )

    # Log login
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    log_login(db=db, user_id=user.id, ip_address=ip_address, user_agent=user_agent)

    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current authenticated user.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user data
    """
    return current_user


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """User logout endpoint.

    Args:
        request: FastAPI request
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success message
    """
    # Log logout
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    log_logout(db=db, user_id=current_user.id, ip_address=ip_address, user_agent=user_agent)

    return {"message": "Successfully logged out"}


@router.post("/init", response_model=UserResponse)
async def initialize_admin(
    db: Session = Depends(get_db),
) -> User:
    """Initialize admin user (only if no users exist).

    Args:
        db: Database session

    Returns:
        Created admin user
    """
    # Check if any users exist
    existing = db.query(User).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin user already exists",
        )

    # Create default admin
    admin = User(
        username="admin",
        hashed_password=get_password_hash("admin123"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    return admin
