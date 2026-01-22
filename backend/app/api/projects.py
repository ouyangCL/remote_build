"""Project management API routes."""
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.audit_decorator import audit_log
from app.models.audit_log import AuditAction
from app.core.permissions import require_admin
from app.core.security import encrypt_data
from app.db.session import get_db
from app.dependencies import get_current_user, get_current_admin
from app.models.project import Project
from app.models.user import User
from app.schemas.project import (
    BranchListResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.audit_service import create_audit_log
from app.services.git_service import GitError, get_remote_branches

router = APIRouter(prefix="/api/projects", tags=["Projects"])


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    environment: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Project]:
    """List all projects, optionally filtered by environment."""
    query = db.query(Project)

    if environment:
        query = query.filter(Project.environment == environment)

    projects = query.order_by(Project.created_at.desc()).all()
    return cast(list[Project], projects)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> Project:
    """Create a new project."""
    existing = db.query(Project).filter(Project.name == project_data.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project name already exists",
        )

    project = Project(**project_data.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)

    # Log audit
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    create_audit_log(
        db=db,
        user_id=current_admin.id,
        action=AuditAction.PROJECT_CREATE,
        resource_type="project",
        resource_id=project.id,
        details={"project_name": project.name},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return cast(Project, project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Project:
    """Get a project by ID."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return cast(Project, project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> Project:
    """Update a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    for field, value in project_data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)

    # Log audit
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    create_audit_log(
        db=db,
        user_id=current_admin.id,
        action=AuditAction.PROJECT_UPDATE,
        resource_type="project",
        resource_id=project.id,
        details={"project_name": project.name},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return cast(Project, project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> None:
    """Delete a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    project_name = project.name
    db.delete(project)
    db.commit()

    # Log audit
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    create_audit_log(
        db=db,
        user_id=current_admin.id,
        action=AuditAction.PROJECT_DELETE,
        resource_type="project",
        resource_id=project_id,
        details={"project_name": project_name},
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.get("/{project_id}/branches", response_model=BranchListResponse)
async def get_project_branches(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BranchListResponse:
    """Get list of branches for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    try:
        branches = get_remote_branches(
            project.git_url,
            ssh_key=project.git_ssh_key,
        )
        return BranchListResponse(branches=branches)
    except GitError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch branches: {e}",
        ) from e
