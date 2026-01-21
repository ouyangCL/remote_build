"""Deployment management API routes."""
import asyncio
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.permissions import require_operator
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.deployment import Deployment, DeploymentStatus
from app.models.project import Project
from app.models.server import ServerGroup
from app.models.user import User
from app.schemas.deployment import (
    DeploymentCreate,
    DeploymentResponse,
)
from app.services.deploy_service import execute_deployment
from app.services.log_service import stream_deployment_logs
from app.services.rollback_service import execute_rollback

router = APIRouter(prefix="/api/deployments", tags=["Deployments"])


@router.get("", response_model=list[DeploymentResponse])
async def list_deployments(
    project_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Deployment]:
    """List deployments, optionally filtered by project."""
    query = db.query(Deployment)

    if project_id:
        query = query.filter(Deployment.project_id == project_id)

    deployments = query.order_by(Deployment.created_at.desc()).limit(100).all()
    return cast(list[Deployment], deployments)


@router.post("", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    deployment_data: DeploymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Deployment:
    """Create a new deployment."""
    # Validate project
    project = db.query(Project).filter(Project.id == deployment_data.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Validate server groups
    server_groups = []
    for group_id in deployment_data.server_group_ids:
        group = db.query(ServerGroup).filter(ServerGroup.id == group_id).first()
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Server group {group_id} not found",
            )
        server_groups.append(group)

    # Create deployment
    deployment = Deployment(
        project_id=deployment_data.project_id,
        branch=deployment_data.branch,
        status=DeploymentStatus.PENDING,
        created_by=current_user.id,
        server_groups=server_groups,
    )
    db.add(deployment)
    db.commit()
    db.refresh(deployment)

    # Execute deployment in background
    asyncio.create_task(execute_deployment(deployment.id, db))

    return cast(Deployment, deployment)


@router.get("/{deployment_id}")
async def get_deployment(
    deployment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get deployment details."""
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment not found",
        )

    return {
        "id": deployment.id,
        "project_id": deployment.project_id,
        "branch": deployment.branch,
        "status": deployment.status.value,
        "commit_hash": deployment.commit_hash,
        "commit_message": deployment.commit_message,
        "error_message": deployment.error_message,
        "created_at": deployment.created_at.isoformat(),
        "created_by": deployment.created_by,
        "rollback_from": deployment.rollback_from,
        "project": {
            "id": deployment.project.id,
            "name": deployment.project.name,
            "project_type": deployment.project.project_type.value,
        } if deployment.project else None,
        "server_groups": [
            {"id": sg.id, "name": sg.name}
            for sg in deployment.server_groups
        ],
        "logs": [
            {
                "id": log.id,
                "level": log.level,
                "content": log.content,
                "timestamp": log.timestamp.isoformat(),
            }
            for log in deployment.logs[:500]
        ],
    }


@router.get("/{deployment_id}/logs")
async def get_deployment_logs(
    deployment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Stream deployment logs via Server-Sent Events."""
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment not found",
        )

    return StreamingResponse(
        stream_deployment_logs(deployment_id),
        media_type="text/event-stream",
    )


@router.post("/{deployment_id}/rollback", response_model=DeploymentResponse)
async def rollback_deployment(
    deployment_id: int,
    rollback_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Deployment:
    """Rollback to a previous deployment."""
    # Get source deployment
    source_deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not source_deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment not found",
        )

    # Check if source deployment has artifacts
    if not source_deployment.artifacts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source deployment has no artifacts to rollback to",
        )

    # Validate server groups
    server_groups = []
    for group_id in rollback_data.get("server_group_ids", []):
        group = db.query(ServerGroup).filter(ServerGroup.id == group_id).first()
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Server group {group_id} not found",
            )
        server_groups.append(group)

    # Create rollback deployment
    rollback_deployment = Deployment(
        project_id=source_deployment.project_id,
        branch=source_deployment.branch,
        status=DeploymentStatus.PENDING,
        created_by=current_user.id,
        rollback_from=deployment_id,
        server_groups=server_groups,
    )
    db.add(rollback_deployment)
    db.commit()
    db.refresh(rollback_deployment)

    # Execute rollback in background
    asyncio.create_task(execute_rollback(rollback_deployment.id, deployment_id, db))

    return cast(Deployment, rollback_deployment)


@router.delete("/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_deployment(
    deployment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Cancel an active deployment."""
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment not found",
        )

    # Only allow cancelling pending/running deployments
    if deployment.status in {
        DeploymentStatus.SUCCESS,
        DeploymentStatus.FAILED,
        DeploymentStatus.CANCELLED,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel a completed deployment",
        )

    deployment.status = DeploymentStatus.CANCELLED
    db.commit()
