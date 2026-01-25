"""Deployment service for orchestrating deployments."""
import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

from app.config import settings
from app.core.ssh import SSHConnection, SSHLogger, create_ssh_connection
from app.models.deployment import Deployment, DeploymentStatus, DeploymentType
from app.models.project import ProjectType
from app.models.server import Server, ServerGroup
from app.models.user import User
from app.services.build_service import BuildService, BuildError
from app.services.git_service import GitError, GitService, git_context
from app.services.health_check_service import HealthCheckError, perform_health_check
from app.services.log_service import DeploymentLogger, LogLevel
from app.utils.script_utils import get_script_execution_info


class DeploymentConcurrencyManager:
    """Manages deployment concurrency limits."""

    def __init__(self, max_concurrent: int = 3):
        """Initialize concurrency manager.

        Args:
            max_concurrent: Maximum number of concurrent deployments allowed
        """
        self.max_concurrent = max_concurrent
        self._running_deployments: set[int] = set()
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def acquire(self, deployment_id: int) -> bool:
        """Try to acquire a deployment slot.

        Args:
            deployment_id: Deployment ID

        Returns:
            True if slot acquired, False if max concurrent reached
        """
        async with self._lock:
            if len(self._running_deployments) >= self.max_concurrent:
                return False

            self._running_deployments.add(deployment_id)
            return True

    async def release(self, deployment_id: int) -> None:
        """Release a deployment slot.

        Args:
            deployment_id: Deployment ID
        """
        async with self._lock:
            self._running_deployments.discard(deployment_id)

    @property
    def running_count(self) -> int:
        """Get current number of running deployments.

        Returns:
            Number of running deployments
        """
        return len(self._running_deployments)

    @property
    def available_slots(self) -> int:
        """Get number of available deployment slots.

        Returns:
            Number of available slots
        """
        return self.max_concurrent - len(self._running_deployments)


# Global concurrency manager instance
_concurrency_manager = DeploymentConcurrencyManager(max_concurrent=3)


def get_concurrency_manager() -> DeploymentConcurrencyManager:
    """Get the global deployment concurrency manager.

    Returns:
        Concurrency manager instance
    """
    return _concurrency_manager


class DeploymentError(Exception):
    """Deployment error."""

    pass


class _DeploymentSSHLoggerAdapter(SSHLogger):
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

            if self.deployment.deployment_type == DeploymentType.RESTART_ONLY:
                await self._restart_only_deploy()
            else:
                await self._full_deploy()

        except Exception as e:
            await self._update_status(DeploymentStatus.FAILED, str(e))
            await self.logger.error(f"Deployment failed: {e}")
            raise DeploymentError(f"Deployment failed: {e}") from e

    async def _full_deploy(self) -> None:
        """Execute full deployment process (clone, build, deploy).

        Raises:
            DeploymentError: If deployment fails
        """
        project = self.deployment.project
        await self.logger.info(f"Starting full deployment: {project.name} ({self.deployment.branch})")

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

        if self._cancelled:
            await self._handle_cancel()
            return

        # Step 4: Health check (if enabled)
        if self.deployment.project.health_check_enabled:
            await self._update_status(DeploymentStatus.HEALTH_CHECKING)
            await self._perform_health_checks()

            if self._cancelled:
                await self._handle_cancel()
                return

        # Step 5: Success
        await self._update_status(DeploymentStatus.SUCCESS)
        await self.logger.info("Deployment completed successfully")

    async def _restart_only_deploy(self) -> None:
        """Execute restart-only deployment (no clone, no build).

        Raises:
            DeploymentError: If deployment fails
        """
        project = self.deployment.project
        await self.logger.info(f"Starting restart-only deployment: {project.name}")

        # Update status to restarting
        await self._update_status(DeploymentStatus.RESTARTING)

        if self._cancelled:
            await self._handle_cancel()
            return

        # Restart servers
        await self._restart_servers()

        if self._cancelled:
            await self._handle_cancel()
            return

        # Success
        await self._update_status(DeploymentStatus.SUCCESS)
        await self.logger.info("Restart-only deployment completed successfully")

    async def _clone_repo(self) -> None:
        """Clone Git repository."""
        await self.logger.info(f"Cloning repository: {self.deployment.project.git_url}")

        try:
            with git_context(
                self.deployment.project.git_url,
                self.deployment.branch,
                git_token=self.deployment.project.git_token,
                ssh_key=self.deployment.project.git_ssh_key,
                logger=self.logger,
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
            git_token=self.deployment.project.git_token,
            ssh_key=self.deployment.project.git_ssh_key,
            logger=self.logger,
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
                logger=self.logger,
                project_type=self.deployment.project.project_type,
                install_script=self.deployment.project.install_script,
                auto_install=self.deployment.project.auto_install,
                project_id=self.deployment.project.id,
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
        await self.logger.info(f"部署到服务器: {server.name}")

        try:
            # Create SSH logger adapter
            ssh_logger = _DeploymentSSHLoggerAdapter(self.logger)
            conn = create_ssh_connection(server, logger=ssh_logger)

            with conn:
                # Upload artifact to project's upload_path
                project = self.deployment.project
                upload_path = project.upload_path
                if not upload_path:
                    raise DeploymentError("项目未配置 upload_path，无法部署")

                # 路径安全验证：不允许部署到根目录
                if upload_path == "/":
                    raise DeploymentError("安全限制：不允许部署到根目录 /，请配置具体的上传路径")

                # 根据项目类型选择部署策略
                if project.project_type == ProjectType.FRONTEND:
                    await self._deploy_frontend_to_server(conn, server, upload_path, artifact_path)
                else:
                    await self._deploy_backend_to_server(conn, server, upload_path, artifact_path)

                # Execute restart script
                if project.restart_script_path:
                    # Get script execution info
                    exec_info = get_script_execution_info(project.restart_script_path)

                    await self.logger.info(f"工作目录: {exec_info['working_dir']}")
                    await self.logger.info(f"执行脚本: {exec_info['script_name']}")

                    # minimal 模式下不 streaming 输出
                    if settings.deployment_log_verbosity == "minimal":
                        exit_code, stdout, stderr = conn.execute_command(exec_info['command'])
                        if exit_code != 0:
                            # 失败时显示完整输出
                            await self.logger.error(f"重启脚本执行失败 (退出码: {exit_code})")
                            for line in stderr.splitlines():
                                await self.logger.error(f"  {line}")
                            raise DeploymentError(f"Restart script failed: {stderr}")
                        else:
                            await self.logger.info("重启脚本执行成功")
                    else:
                        # 详细模式：streaming 输出
                        await self.logger.info(f"执行命令: {exec_info['command']}")

                        exit_code, stdout, stderr = conn.execute_command_streaming(
                            exec_info['command'],
                            on_stdout=lambda line: asyncio.create_task(
                                self.logger.info(f"[stdout] {line}")
                            ),
                            on_stderr=lambda line: asyncio.create_task(
                                self.logger.info(f"[stderr] {line}")
                            ),
                        )

                        if exit_code != 0:
                            await self.logger.error(f"脚本执行完成，退出码: {exit_code}")
                            await self.logger.error(f"重启脚本执行失败")
                        else:
                            await self.logger.info(f"脚本执行完成，退出码: {exit_code}")
                            await self.logger.info("重启脚本执行成功")
                else:
                    await self.logger.warning("项目未配置重启脚本路径，跳过脚本执行")

                await self.logger.info(f"成功部署到 {server.name}")

        except Exception as e:
            raise DeploymentError(f"Failed to deploy to {server.name}: {e}") from e

    async def _deploy_backend_to_server(
        self,
        conn: SSHConnection,
        server: Server,
        upload_path: str,
        artifact_path: Path,
    ) -> None:
        """Deploy backend project to server (original deployment logic).

        Args:
            conn: SSH connection
            server: Target server
            upload_path: Remote upload path
            artifact_path: Local artifact path
        """
        remote_artifact = f"{upload_path}/{artifact_path.name}"

        await self.logger.info(f"上传部署产物到: {remote_artifact}")
        # Ensure upload directory exists
        mkdir_command = f"mkdir -p {upload_path}"
        exit_code, stdout, stderr = conn.execute_command(mkdir_command)
        if exit_code != 0:
            await self.logger.error(f"创建上传目录失败: {stderr}")
            raise DeploymentError(f"Failed to create upload directory: {stderr}")

        # Upload artifact
        conn.upload_file(artifact_path, remote_artifact)
        await self.logger.info(f"部署产物上传完成: {remote_artifact}")

        # 解压zip包到upload_path目录
        await self.logger.info(f"解压部署产物到: {upload_path}")
        unzip_command = f"unzip -o {remote_artifact} -d {upload_path}"
        exit_code, stdout, stderr = conn.execute_command(unzip_command)
        if exit_code != 0:
            await self.logger.error(f"解压失败: {stderr}")
            raise DeploymentError(f"Failed to unzip artifact: {stderr}")
        await self.logger.info("解压完成")

    async def _deploy_frontend_to_server(
        self,
        conn: SSHConnection,
        server: Server,
        upload_path: str,
        artifact_path: Path,
    ) -> None:
        """Deploy frontend project to server with backup mechanism.

        部署流程：
        1. 上传zip到父目录
        2. 备份现有目录（如果存在）
        3. 解压到配置路径
        4. 清理zip文件

        Args:
            conn: SSH connection
            server: Target server
            upload_path: Remote upload path (e.g., /application/web/admin)
            artifact_path: Local artifact path
        """
        # 计算父目录和备份路径
        parent_dir = os.path.dirname(upload_path)
        target_dir_name = os.path.basename(upload_path)
        timestamp = datetime.now().strftime("%m%d-%H%M%S")
        backup_dir_name = f"{target_dir_name}-{timestamp}"
        backup_path = os.path.join(parent_dir, backup_dir_name)

        await self.logger.info(f"前端项目部署模式")
        await self.logger.info(f"目标路径: {upload_path}")
        await self.logger.info(f"父目录: {parent_dir}")
        await self.logger.info(f"备份路径: {backup_path}")

        # 验证父目录不为空（防止upload_path是根目录）
        if not parent_dir or parent_dir == upload_path:
            raise DeploymentError(
                f"无效的配置路径: {upload_path}。前端项目需要配置具体的子目录路径，例如 /application/web/admin"
            )

        # 1. 创建父目录
        await self.logger.info(f"创建父目录: {parent_dir}")
        mkdir_command = f"mkdir -p {parent_dir}"
        exit_code, stdout, stderr = conn.execute_command(mkdir_command)
        if exit_code != 0:
            await self.logger.error(f"创建父目录失败: {stderr}")
            raise DeploymentError(f"Failed to create parent directory: {stderr}")

        # 2. 上传zip到父目录
        remote_artifact = f"{parent_dir}/{artifact_path.name}"
        await self.logger.info(f"上传部署产物到父目录: {remote_artifact}")
        conn.upload_file(artifact_path, remote_artifact)
        await self.logger.info("部署产物上传完成")

        # 3. 备份现有目录（如果存在）
        backup_command = f"""if [ -d "{upload_path}" ]; then mv "{upload_path}" "{backup_path}"; fi"""
        await self.logger.info(f"检查并备份现有目录: {upload_path}")

        if settings.deployment_log_verbosity == "detailed":
            await self.logger.info(f"执行备份命令: {backup_command}")

        exit_code, stdout, stderr = conn.execute_command(backup_command)
        if exit_code != 0:
            await self.logger.error(f"备份失败: {stderr}")
            # 清理已上传的zip文件
            await self.logger.warning("备份失败，清理已上传的文件")
            cleanup_command = f"rm -f {remote_artifact}"
            conn.execute_command(cleanup_command)
            raise DeploymentError(f"备份失败，已中止部署: {stderr}")

        # 检查是否真的执行了备份（通过检查备份目录是否存在）
        check_backup_command = f"[ -d \"{backup_path}\" ] && echo \"EXISTS\" || echo \"NOT_EXISTS\""
        exit_code, stdout, stderr = conn.execute_command(check_backup_command)
        backup_exists = stdout.strip() == "EXISTS"

        if backup_exists:
            await self.logger.info(f"已备份现有目录到: {backup_path}")
        else:
            await self.logger.info("未发现现有目录，跳过备份")

        # 4. 解压到配置路径
        await self.logger.info(f"解压部署产物到: {upload_path}")
        unzip_command = f"unzip -o {remote_artifact} -d {upload_path}"

        if settings.deployment_log_verbosity == "detailed":
            await self.logger.info(f"执行解压命令: {unzip_command}")

        exit_code, stdout, stderr = conn.execute_command(unzip_command)
        if exit_code != 0:
            await self.logger.error(f"解压失败: {stderr}")

            # 尝试恢复备份
            if backup_exists:
                await self.logger.warning(f"解压失败，尝试恢复备份: {backup_path} -> {upload_path}")
                restore_command = f"mv \"{backup_path}\" \"{upload_path}\""
                exit_code_restore, stdout_restore, stderr_restore = conn.execute_command(restore_command)
                if exit_code_restore == 0:
                    await self.logger.info("备份恢复成功")
                else:
                    await self.logger.error(f"备份恢复失败: {stderr_restore}")
                    await self.logger.error(f"手动恢复命令: mv \"{backup_path}\" \"{upload_path}\"")
            else:
                await self.logger.info("无备份可恢复")

            # 清理zip文件
            await self.logger.warning("清理已上传的zip文件")
            cleanup_command = f"rm -f {remote_artifact}"
            conn.execute_command(cleanup_command)

            raise DeploymentError(f"解压失败，已中止部署: {stderr}")

        await self.logger.info("解压完成")

        # 5. 清理zip文件
        await self.logger.info(f"清理zip文件: {remote_artifact}")
        cleanup_command = f"rm -f {remote_artifact}"
        exit_code, stdout, stderr = conn.execute_command(cleanup_command)
        if exit_code != 0:
            await self.logger.warning(f"清理zip文件失败（不影响部署）: {stderr}")
        else:
            await self.logger.info("zip文件清理完成")

    async def _restart_servers(self) -> None:
        """Restart services on all servers.

        Raises:
            DeploymentError: If restart fails
        """
        server_groups = self.deployment.server_groups

        await self.logger.info(f"Restarting on {len(server_groups)} server group(s)")

        failed_servers = []

        for group in server_groups:
            await self.logger.info(f"Restarting in server group: {group.name}")

            for server in group.servers:
                if not server.is_active:
                    await self.logger.warning(f"Skipping inactive server: {server.name}")
                    continue

                try:
                    await self._restart_server(server)
                except DeploymentError as e:
                    await self.logger.error(f"Failed to restart {server.name}: {e}")
                    failed_servers.append(server.name)

        if failed_servers:
            await self._update_status(
                DeploymentStatus.FAILED,
                f"Failed to restart servers: {', '.join(failed_servers)}"
            )
            raise DeploymentError(f"Failed to restart servers: {', '.join(failed_servers)}")

    async def _restart_server(self, server: Server) -> None:
        """Restart service on a single server.

        Args:
            server: Server to restart

        Raises:
            DeploymentError: If restart fails
        """
        await self.logger.info(f"Restarting on server: {server.name} ({server.host})")

        # Check if project has restart-only script configured
        if not self.deployment.project.restart_only_script_path:
            raise DeploymentError(
                f"项目 {self.deployment.project.name} 未配置仅重启脚本路径，无法执行仅重启部署"
            )

        try:
            # Get script execution info
            exec_info = get_script_execution_info(
                self.deployment.project.restart_only_script_path
            )

            await self.logger.info(f"工作目录: {exec_info['working_dir']}")
            await self.logger.info(f"执行脚本: {exec_info['script_name']}")

            conn = create_ssh_connection(server)

            with conn:
                await self.logger.info(f"执行命令: {exec_info['command']}")
                exit_code, stdout, stderr = conn.execute_command(exec_info['command'])

                if exit_code != 0:
                    raise DeploymentError(f"重启脚本执行失败: {stderr}")

                await self.logger.info("重启脚本执行成功")
                await self.logger.info(f"成功重启 {server.name}")

        except DeploymentError:
            raise
        except Exception as e:
            raise DeploymentError(f"重启失败 {server.name}: {e}") from e

    async def _perform_health_checks(self) -> None:
        """Perform health checks on all deployed servers.

        Raises:
            DeploymentError: If health check fails on any server
        """
        server_groups = self.deployment.server_groups

        await self.logger.info(f"开始对 {len(server_groups)} 个服务器组进行健康检查")

        all_passed = True

        for group in server_groups:
            await self.logger.info(f"对服务器组进行健康检查: {group.name}")

            for server in group.servers:
                if not server.is_active:
                    await self.logger.warning(
                        f"跳过非活动服务器: {server.name}"
                    )
                    continue

                try:
                    # Create SSH connection for command checks
                    ssh_logger = _DeploymentSSHLoggerAdapter(self.logger)
                    conn = create_ssh_connection(server, logger=ssh_logger)

                    with conn:
                        # Perform health check
                        passed = await perform_health_check(
                            project=self.deployment.project,
                            server=server,
                            deployment_logger=self.logger,
                            ssh_connection=conn,
                        )

                        if not passed:
                            all_passed = False
                            await self.logger.error(
                                f"服务器 {server.name} 健康检查失败"
                            )

                except HealthCheckError as e:
                    all_passed = False
                    await self.logger.error(
                        f"服务器 {server.name} 健康检查异常: {e}"
                    )

        if not all_passed:
            raise DeploymentError("一个或多个服务器健康检查失败")

    async def _update_status(
        self, status: DeploymentStatus, error_message: str | None = None
    ) -> None:
        """Update deployment status and progress.

        Args:
            status: New status
            error_message: Error message if failed
        """
        self.deployment.status = status
        self.deployment.current_step = status.value

        # Calculate progress based on status
        progress_map = {
            DeploymentStatus.PENDING: 0,
            DeploymentStatus.CLONING: 10,
            DeploymentStatus.BUILDING: 30,
            DeploymentStatus.UPLOADING: 60,
            DeploymentStatus.DEPLOYING: 80,
            DeploymentStatus.RESTARTING: 90,
            DeploymentStatus.HEALTH_CHECKING: 95,
            DeploymentStatus.SUCCESS: 100,
            DeploymentStatus.FAILED: 0,
            DeploymentStatus.CANCELLED: 0,
        }
        self.deployment.progress = progress_map.get(status, 0)

        if error_message:
            self.deployment.error_message = error_message
        self.db.commit()

    async def _handle_cancel(self) -> None:
        """Handle deployment cancellation."""
        await self._update_status(DeploymentStatus.CANCELLED)
        await self.logger.warning("Deployment was cancelled")


async def execute_deployment(
    deployment_id: int,
) -> None:
    """Execute a deployment (background task).

    This function creates its own database session to avoid issues with
    the parent request's session being closed after the HTTP response.

    Args:
        deployment_id: Deployment ID
    """
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
        if not deployment:
            # Release concurrency slot even if deployment not found
            await get_concurrency_manager().release(deployment_id)
            return

        service = DeploymentService(deployment, db)
        await service.deploy()

        # Clean up log buffer after deployment is complete
        from app.services.log_service import remove_log_buffer

        await remove_log_buffer(deployment_id)
    finally:
        # Always release the concurrency slot when deployment completes
        await get_concurrency_manager().release(deployment_id)
        db.close()
