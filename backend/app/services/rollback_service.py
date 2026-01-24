"""Rollback service for reverting deployments."""
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

from app.core.ssh import SSHLogger, create_ssh_connection
from app.models.deployment import Deployment, DeploymentStatus, DeploymentStatus
from app.models.server import Server
from app.services.log_service import DeploymentLogger


class RollbackError(Exception):
    """Rollback error."""

    pass


class _RollbackSSHLoggerAdapter(SSHLogger):
    """Adapter to connect DeploymentLogger with SSHLogger interface."""

    def __init__(self, deployment_logger: DeploymentLogger):
        """Initialize adapter.

        Args:
            deployment_logger: Deployment logger instance
        """
        self._logger = deployment_logger

    async def info(self, message: str) -> None:
        """Log info message."""
        await self._logger.info(message)

    async def error(self, message: str) -> None:
        """Log error message."""
        await self._logger.error(message)


class RollbackService:
    """Service for rolling back deployments."""

    def __init__(
        self,
        target_deployment: Deployment,
        source_deployment: Deployment,
        db: Session,
        on_log: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize rollback service.

        Args:
            target_deployment: New deployment (rollback) record
            source_deployment: Original deployment to rollback to
            db: Database session
            on_log: Callback for log messages
        """
        self.target_deployment = target_deployment
        self.source_deployment = source_deployment
        self.db = db
        self.on_log = on_log or (lambda x: None)
        self.logger = DeploymentLogger(target_deployment.id, db)

    async def rollback(self) -> None:
        """Execute rollback process.

        Raises:
            RollbackError: If rollback fails
        """
        try:
            await self.logger.info(
                f"Starting rollback to deployment {self.source_deployment.id}"
            )

            # Get the artifact from source deployment
            artifact = self.source_deployment.artifacts[0] if self.source_deployment.artifacts else None

            if not artifact:
                raise RollbackError(
                    f"No artifact found for deployment {self.source_deployment.id}"
                )

            artifact_path = Path(artifact.file_path)
            if not artifact_path.exists():
                raise RollbackError(f"Artifact file not found: {artifact_path}")

            await self.logger.info(f"Using artifact: {artifact_path}")

            # Deploy to servers
            await self._deploy_to_servers(artifact_path)

            # Success
            self.target_deployment.status = DeploymentStatus.SUCCESS
            self.db.commit()
            await self.logger.info("Rollback completed successfully")

        except Exception as e:
            self.target_deployment.status = DeploymentStatus.FAILED
            self.target_deployment.error_message = str(e)
            self.db.commit()
            await self.logger.error(f"Rollback failed: {e}")
            raise RollbackError(f"Rollback failed: {e}") from e

    async def _deploy_to_servers(self, artifact_path: Path) -> None:
        """Deploy artifact to all servers in server groups.

        Args:
            artifact_path: Path to deployment artifact
        """
        server_groups = self.target_deployment.server_groups

        await self.logger.info(f"Deploying to {len(server_groups)} server group(s)")

        for group in server_groups:
            await self.logger.info(f"Deploying to server group: {group.name}")

            for server in group.servers:
                if not server.is_active:
                    await self.logger.warning(f"Skipping inactive server: {server.name}")
                    continue

                await self._deploy_to_server(server, artifact_path)

    async def _deploy_to_server(self, server: Server, artifact_path: Path) -> None:
        """Deploy artifact to a single server.

        Args:
            server: Server to deploy to
            artifact_path: Path to deployment artifact
        """
        await self.logger.info(f"Deploying to server: {server.name} ({server.host})")

        try:
            # Create SSH logger adapter
            ssh_logger = _RollbackSSHLoggerAdapter(self.logger)
            conn = create_ssh_connection(server, logger=ssh_logger)

            with conn:
                # Upload artifact
                await self.logger.info(f"Uploading artifact to {server.host}")
                remote_temp = f"/tmp/{artifact_path.name}"
                conn.upload_file(artifact_path, remote_temp)

                # Extract to deploy path
                await self.logger.info(f"Extracting to {server.deploy_path}")
                exit_code, stdout, stderr = conn.execute_command(
                    f"mkdir -p {server.deploy_path} && "
                    f"tar -xzf {remote_temp} -C {server.deploy_path} && "
                    f"rm {remote_temp}"
                )

                if exit_code != 0:
                    raise RollbackError(f"Failed to extract artifact: {stderr}")

                # Execute restart script
                if self.source_deployment.project.deploy_script_path:
                    await self.logger.info(
                        f"Executing restart script: {self.source_deployment.project.deploy_script_path}"
                    )
                    exit_code, stdout, stderr = conn.execute_command(
                        f"bash {self.source_deployment.project.deploy_script_path}"
                    )

                    if exit_code != 0:
                        await self.logger.warning(f"Restart script failed: {stderr}")
                    else:
                        await self.logger.info("Restart script executed successfully")

                await self.logger.info(f"Successfully rolled back on {server.name}")

        except Exception as e:
            raise RollbackError(f"Failed to deploy to {server.name}: {e}") from e


async def execute_rollback(
    target_deployment_id: int,
    source_deployment_id: int,
) -> None:
    """Execute a rollback (background task).

    This function creates its own database session to avoid issues with
    the parent request's session being closed after the HTTP response.

    Args:
        target_deployment_id: New deployment (rollback) ID
        source_deployment_id: Original deployment ID to rollback to
    """
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        target_deployment = (
            db.query(Deployment).filter(Deployment.id == target_deployment_id).first()
        )
        source_deployment = (
            db.query(Deployment).filter(Deployment.id == source_deployment_id).first()
        )

        if not target_deployment or not source_deployment:
            return

        service = RollbackService(target_deployment, source_deployment, db)
        await service.rollback()
    finally:
        db.close()

    # Clean up log buffer after rollback is complete
    from app.services.log_service import remove_log_buffer

    await remove_log_buffer(target_deployment_id)
