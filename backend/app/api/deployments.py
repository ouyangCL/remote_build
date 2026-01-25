"""Deployment management API routes."""
import asyncio
import logging
from typing import cast

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

# Global task registry to prevent garbage collection
_background_tasks: dict[int, asyncio.Task] = {}
logger = logging.getLogger(__name__)

from app.models.audit_log import AuditAction
from app.core.permissions import Permission
from app.db.session import get_db
from app.dependencies import get_current_user, get_current_user_from_token
from app.models.deployment import Deployment, DeploymentLog, DeploymentStatus, DeploymentType
from app.models.project import Project
from app.models.server import ServerGroup
from app.models.user import User, UserRole
from app.schemas.deployment import (
    DeploymentCreate,
    DeploymentResponse,
)
from app.services.audit_service import create_audit_log
from app.services.deploy_service import execute_deployment
from app.services.environment_service import EnvironmentService
from app.services.log_service import stream_deployment_logs
from app.services.rollback_service import execute_rollback

router = APIRouter(prefix="/api/deployments", tags=["Deployments"])


def get_current_operator(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current user and verify they are an operator or admin."""
    if current_user.role not in {UserRole.ADMIN, UserRole.OPERATOR}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Deploy permission required (admin or operator role)",
        )
    return current_user


@router.get("", response_model=list[DeploymentResponse])
async def list_deployments(
    project_id: int | None = None,
    environment: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Deployment]:
    """List deployments, optionally filtered by project and environment."""
    query = db.query(Deployment)

    if project_id:
        query = query.filter(Deployment.project_id == project_id)

    if environment:
        query = query.filter(Deployment.environment == environment)

    deployments = query.order_by(Deployment.created_at.desc()).limit(100).all()
    return cast(list[Deployment], deployments)


@router.post("", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    deployment_data: DeploymentCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_operator),
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

    # Validate environment consistency
    EnvironmentService.validate_deployment_environment(project, server_groups)

    # Handle branch for restart_only mode: use placeholder if empty
    branch = deployment_data.branch
    if not branch and deployment_data.deployment_type == DeploymentType.RESTART_ONLY:
        branch = "-"  # Placeholder for restart-only deployments

    # Create deployment - inherit environment from project
    deployment = Deployment(
        project_id=deployment_data.project_id,
        branch=branch,
        status=DeploymentStatus.PENDING,
        created_by=current_user.id,
        server_groups=server_groups,
        environment=project.environment,
        deployment_type=deployment_data.deployment_type,
    )
    db.add(deployment)
    db.commit()
    db.refresh(deployment)

    # Log audit with environment info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    create_audit_log(
        db=db,
        user_id=current_user.id,
        action=AuditAction.DEPLOYMENT_CREATE,
        resource_type="deployment",
        resource_id=deployment.id,
        details={
            "project": project.name,
            "branch": deployment_data.branch,
            "environment": project.environment
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Check deployment concurrency limit
    from app.services.deploy_service import get_concurrency_manager
    concurrency_manager = get_concurrency_manager()

    if not await concurrency_manager.acquire(deployment.id):
        # Max concurrent deployments reached, update deployment status
        deployment.status = DeploymentStatus.QUEUED
        deployment.error_message = "Deployment queued: maximum concurrent deployments reached"
        db.commit()

        # Still return deployment but note it's queued
        return cast(Deployment, deployment)

    # Execute deployment in background with a new database session
    # The background task will create its own session to avoid issues with
    # the parent request's session being closed
    def run_deployment_sync():
        """Wrapper to run async deployment in background."""
        # Create a new event loop for the background task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _run():
            try:
                await execute_deployment(deployment.id)
            except Exception as e:
                logger.error(f"Background deployment task failed for deployment {deployment.id}: {e}")
            finally:
                # Clean up task reference when done
                _background_tasks.pop(deployment.id, None)
                # Also release concurrency slot
                await get_concurrency_manager().release(deployment.id)

        loop.run_until_complete(_run())
        loop.close()

    # Use FastAPI's BackgroundTasks - executes after response is sent
    background_tasks.add_task(run_deployment_sync)

    # Manually construct the response to avoid Pydantic from_attributes serialization
    # This prevents loading of relationships like logs, server_groups, etc.
    from app.schemas.deployment import DeploymentResponse
    return DeploymentResponse(
        id=deployment.id,
        project_id=deployment.project_id,
        branch=deployment.branch,
        status=str(deployment.status),
        deployment_type=deployment.deployment_type,
        progress=deployment.progress,
        current_step=deployment.current_step,
        total_steps=deployment.total_steps,
        commit_hash=deployment.commit_hash,
        commit_message=deployment.commit_message,
        error_message=deployment.error_message,
        created_at=deployment.created_at,
        created_by=deployment.created_by,
        rollback_from=deployment.rollback_from,
        environment=str(deployment.environment),
    )


@router.get("/{deployment_id}")
async def get_deployment(
    deployment_id: int,
    since_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get deployment details.

    Args:
        deployment_id: Deployment ID
        since_id: Optional log ID to fetch incremental logs. If provided,
                  only returns logs with ID > since_id. If not provided,
                  returns the most recent 500 logs.
    """
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment not found",
        )

    # Build base query for logs - 优化查询性能
    # 使用子查询获取最新的500条日志，避免desc+reversed的性能问题
    from sqlalchemy import select, func

    logs_query = db.query(DeploymentLog).filter(
        DeploymentLog.deployment_id == deployment_id
    )

    # Apply incremental filter if since_id is provided
    if since_id is not None:
        # 增量查询：获取since_id之后的日志，限制100条
        logs_query = logs_query.filter(DeploymentLog.id > since_id)
        logs_query = logs_query.order_by(DeploymentLog.id.asc()).limit(100)
    else:
        # 初始查询：使用子查询获取最新的500条日志（按时间顺序）
        # 这避免了desc+reversed的性能问题
        subquery = (
            db.query(DeploymentLog.id)
            .filter(DeploymentLog.deployment_id == deployment_id)
            .order_by(DeploymentLog.id.desc())
            .limit(500)
            .subquery()
        )
        logs_query = logs_query.filter(DeploymentLog.id.in_(select(subquery.c.id)))
        logs_query = logs_query.order_by(DeploymentLog.id.asc())

    logs = logs_query.all()

    # Calculate max_log_id for next incremental query
    max_log_id = max((log.id for log in logs), default=0)

    return {
        "id": deployment.id,
        "project_id": deployment.project_id,
        "branch": deployment.branch,
        "status": deployment.status.value if hasattr(deployment.status, "value") else deployment.status,
        "deployment_type": deployment.deployment_type.value if hasattr(deployment.deployment_type, "value") else deployment.deployment_type,
        "commit_hash": deployment.commit_hash,
        "commit_message": deployment.commit_message,
        "error_message": deployment.error_message,
        "created_at": deployment.created_at.isoformat(),
        "created_by": deployment.created_by,
        "rollback_from": deployment.rollback_from,
        "project": {
            "id": deployment.project.id,
            "name": deployment.project.name,
            "project_type": deployment.project.project_type.value if hasattr(deployment.project.project_type, "value") else deployment.project.project_type,
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
                "timestamp": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "max_log_id": max_log_id,
    }


@router.get("/{deployment_id}/logs")
async def get_deployment_logs(
    deployment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
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
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_operator),
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

    # Get project for environment validation
    project = db.query(Project).filter(Project.id == source_deployment.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
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

    # Validate environment consistency
    EnvironmentService.validate_deployment_environment(project, server_groups)

    # Create rollback deployment - inherit environment from project
    rollback_deployment = Deployment(
        project_id=source_deployment.project_id,
        branch=source_deployment.branch,
        status=DeploymentStatus.PENDING,
        created_by=current_user.id,
        rollback_from=deployment_id,
        server_groups=server_groups,
        environment=project.environment,
    )
    db.add(rollback_deployment)
    db.commit()
    db.refresh(rollback_deployment)

    # Log audit with environment info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    create_audit_log(
        db=db,
        user_id=current_user.id,
        action=AuditAction.DEPLOYMENT_ROLLBACK,
        resource_type="deployment",
        resource_id=rollback_deployment.id,
        details={
            "source_deployment_id": deployment_id,
            "environment": project.environment
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Execute rollback in background with a new database session
    # The background task will create its own session to avoid issues with
    # the parent request's session being closed
    async def run_rollback():
        try:
            await execute_rollback(rollback_deployment.id, deployment_id)
        except Exception as e:
            logger.error(f"Background rollback task failed for deployment {rollback_deployment.id}: {e}")
        finally:
            _background_tasks.pop(rollback_deployment.id, None)

    task = asyncio.ensure_future(run_rollback())
    _background_tasks[rollback_deployment.id] = task

    return cast(Deployment, rollback_deployment)


@router.delete("/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_deployment(
    deployment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_operator),
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

    # Log audit
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    create_audit_log(
        db=db,
        user_id=current_user.id,
        action=AuditAction.DEPLOYMENT_CANCEL,
        resource_type="deployment",
        resource_id=deployment_id,
        details={"branch": deployment.branch},
        ip_address=ip_address,
        user_agent=user_agent,
    )
