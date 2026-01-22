"""Deployment service for orchestrating deployments."""
import asyncio
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

from app.config import settings
from app.core.ssh import SSHConnection, create_ssh_connection
from app.models.deployment import Deployment, DeploymentStatus
from app.models.server import Server, ServerGroup
from app.models.user import User
from app.services.build_service import BuildService, BuildError
from app.services.git_service import GitError, GitService, git_context
from app.services.log_service import DeploymentLogger, LogLevel


class DeploymentError(Exception):
    """Deployment error."""

    pass


class DeploymentService:
    """Service for orchestrating deployments."""

    def __init__(
        self,
        deployment: Deployment,
        db: Session,
        on_log: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize deployment service.

        Args:
            deployment: Deployment model instance
            db: Database session
            on_log: Callback for log messages
        """
        self.deployment = deployment
        self.db = db
        self.on_log = on_log or (lambda x: None)
        self.logger = DeploymentLogger(deployment.id, db)
        self._cancelled = False

    def cancel(self) -> None:
        """Cancel the deployment."""
        self._cancelled = True

    async def deploy(self) -> None:
        """Execute deployment process.

        Raises:
            DeploymentError: If deployment fails
        """
        try:
            project = self.deployment.project
            await self.logger.info(f"Starting deployment: {project.name} ({self.deployment.branch})")

            # Step 1: Clone repository
            await self._update_status(DeploymentStatus.CLONING)
            await self._clone_repo()

            if self._cancelled:
                await self._handle_cancel()
                return

            # Step 2: Build project
            await self._update_status(DeploymentStatus.BUILDING)
            artifact_info = await self._build_project()

            if self._cancelled:
                await self._handle_cancel()
                return

            # Step 3: Deploy to servers
            await self._update_status(DeploymentStatus.DEPLOYING)
            await self._deploy_to_servers(artifact_info["path"])

            # Step 4: Success
            await self._update_status(DeploymentStatus.SUCCESS)
            await self.logger.info("Deployment completed successfully")

        except Exception as e:
            await self._update_status(DeploymentStatus.FAILED, str(e))
            await self.logger.error(f"Deployment failed: {e}")
            raise DeploymentError(f"Deployment failed: {e}") from e

    async def _clone_repo(self) -> None:
        """Clone Git repository."""
        await self.logger.info(f"Cloning repository: {self.deployment.project.git_url}")

        try:
            with git_context(
                self.deployment.project.git_url,
                self.deployment.branch,
                ssh_key=self.deployment.project.git_ssh_key,
            ) as git_service:
                git_info = git_service.get_info()
                self.deployment.commit_hash = git_info.commit_hash
                self.deployment.commit_message = git_info.commit_message
                self.db.commit()

                await self.logger.info(f"Checked out branch: {git_info.branch}")
                await self.logger.info(f"Commit: {git_info.commit_hash}")
                await self.logger.info(f"Message: {git_info.commit_message}")

        except GitError as e:
            raise DeploymentError(f"Git operation failed: {e}") from e

    async def _build_project(self) -> dict:
        """Build project and create artifact.

        Returns:
            Dictionary with artifact info
        """
        await self.logger.info("Starting build process")

        # Create work directory for cloning
        work_dir = Path(settings.work_dir) / f"build_{self.deployment.id}"
        work_dir.mkdir(parents=True, exist_ok=True)

        # Clone repo for building
        git_service = GitService(
            self.deployment.project.git_url,
            ssh_key=self.deployment.project.git_ssh_key,
        )
        try:
            git_service.clone(work_dir)
            git_service.checkout_branch(self.deployment.branch)
        except GitError as e:
            raise DeploymentError(f"Failed to clone for build: {e}") from e

        try:
            # Create build service
            build_service = BuildService(
                source_dir=work_dir,
                build_script=self.deployment.project.build_script,
                output_dir=self.deployment.project.output_dir,
                on_output=lambda msg: asyncio.create_task(self.logger.info(msg)),
            )

            # Execute build
            result = build_service.build()

            if result.status.value == "failed":
                raise DeploymentError(f"Build failed: {result.error_message}")

            # Create artifact record
            from app.models.deployment import DeploymentArtifact

            artifact = DeploymentArtifact(
                deployment_id=self.deployment.id,
                file_path=str(result.artifact_path),
                file_size=result.artifact_size,
                checksum=result.checksum,
            )
            self.db.add(artifact)
            self.db.commit()

            return {"path": result.artifact_path, "size": result.artifact_size}

        finally:
            # Clean up
            git_service.cleanup()
            import shutil

            shutil.rmtree(work_dir, ignore_errors=True)

    async def _deploy_to_servers(self, artifact_path: Path) -> None:
        """Deploy artifact to all servers in server groups.

        Args:
            artifact_path: Path to deployment artifact
        """
        server_groups = self.deployment.server_groups

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
            conn = create_ssh_connection(server)

            with conn:
                # Upload artifact
                await self.logger.info(f"Uploading artifact to {server.host}")
                remote_temp = f"/tmp/{artifact_path.name}"
                conn.upload_file(artifact_path, remote_temp)

                # Extract to deploy path
                await self.logger.info(f"Extracting to {server.deploy_path}")
                exit_code, stdout, stderr = conn.execute_command(
                    f"mkdir -p {server.deploy_path} && "
                    f"unzip -o {remote_temp} -d {server.deploy_path} && "
                    f"rm {remote_temp}"
                )

                if exit_code != 0:
                    raise DeploymentError(f"Failed to extract artifact: {stderr}")

                # Execute restart script
                if self.deployment.project.deploy_script_path:
                    await self.logger.info(
                        f"Executing restart script: {self.deployment.project.deploy_script_path}"
                    )
                    exit_code, stdout, stderr = conn.execute_command(
                        f"bash {self.deployment.project.deploy_script_path}"
                    )

                    if exit_code != 0:
                        await self.logger.warning(f"Restart script failed: {stderr}")
                    else:
                        await self.logger.info("Restart script executed successfully")

                await self.logger.info(f"Successfully deployed to {server.name}")

        except Exception as e:
            raise DeploymentError(f"Failed to deploy to {server.name}: {e}") from e

    async def _update_status(
        self, status: DeploymentStatus, error_message: str | None = None
    ) -> None:
        """Update deployment status.

        Args:
            status: New status
            error_message: Error message if failed
        """
        self.deployment.status = status
        if error_message:
            self.deployment.error_message = error_message
        self.db.commit()

    async def _handle_cancel(self) -> None:
        """Handle deployment cancellation."""
        await self._update_status(DeploymentStatus.CANCELLED)
        await self.logger.warning("Deployment was cancelled")


async def execute_deployment(
    deployment_id: int,
    db: Session,
) -> None:
    """Execute a deployment (background task).

    Args:
        deployment_id: Deployment ID
        db: Database session
    """
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        return

    service = DeploymentService(deployment, db)
    await service.deploy()

    # Clean up log buffer after deployment is complete
    from app.services.log_service import remove_log_buffer

    await remove_log_buffer(deployment_id)
