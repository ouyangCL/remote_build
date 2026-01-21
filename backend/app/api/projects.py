"""Project management API routes."""
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

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
from app.services.git_service import GitError, get_remote_branches

router = APIRouter(prefix="/api/projects", tags=["Projects"])


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Project]:
    """List all projects."""
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return cast(list[Project], projects)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
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

    return cast(Project, project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
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

    db.delete(project)
    db.commit()


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
        branches = get_remote_branches(project.git_url)
        return BranchListResponse(branches=branches)
    except GitError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch branches: {e}",
        ) from e
