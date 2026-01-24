"""Health check service for verifying deployment health."""
import asyncio
import socket
from typing import Callable

import httpx

from app.config import settings
from app.core.ssh import SSHConnection, SSHLogger, create_ssh_connection
from app.models.project import HealthCheckType, Project
from app.models.server import Server
from app.services.log_service import DeploymentLogger


class HealthCheckError(Exception):
    """Health check error."""

    pass


class _HealthCheckSSHLoggerAdapter(SSHLogger):
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


class HealthCheckService:
    """Service for performing health checks on deployed applications."""

    def __init__(
        self,
        project: Project,
        server: Server,
        deployment_logger: DeploymentLogger,
        ssh_connection: SSHConnection | None = None,
    ) -> None:
        """Initialize health check service.

        Args:
            project: Project model instance
            server: Server to check
            deployment_logger: Deployment logger instance
            ssh_connection: Optional SSH connection for command execution
        """
        self.project = project
        self.server = server
        self.logger = deployment_logger
        self.ssh_connection = ssh_connection

    async def check(self) -> bool:
        """Execute health check based on project configuration.

        Returns:
            True if health check passes, False otherwise

        Raises:
            HealthCheckError: If health check configuration is invalid
        """
        if not self.project.health_check_enabled:
            await self.logger.info("健康检查已禁用，跳过")
            return True

        # health_check_type from database is a string, not enum
        check_type_str = self.project.health_check_type if isinstance(self.project.health_check_type, str) else self.project.health_check_type.value

        await self.logger.info(
            f"开始健康检查 (类型: {check_type_str})"
        )

        try:
            if check_type_str == "http":
                result = await self._check_http()
            elif check_type_str == "tcp":
                result = await self._check_tcp()
            elif check_type_str == "command":
                result = await self._check_command()
            else:
                raise HealthCheckError(f"不支持的健康检查类型: {check_type_str}")

            if result:
                await self.logger.info("健康检查通过")
            else:
                await self.logger.error("健康检查失败")

            return result

        except Exception as e:
            await self.logger.error(f"健康检查异常: {e}")
            raise HealthCheckError(f"健康检查执行失败: {e}") from e

    async def _check_http(self) -> bool:
        """Perform HTTP health check with retry mechanism.

        Returns:
            True if check passes, False otherwise
        """
        if not self.project.health_check_url:
            raise HealthCheckError("HTTP 健康检查需要配置 health_check_url")

        url = self.project.health_check_url
        timeout = self.project.health_check_timeout
        retries = self.project.health_check_retries
        interval = self.project.health_check_interval

        # Replace localhost with server host if needed
        if "localhost" in url or "127.0.0.1" in url:
            url = url.replace("localhost", self.server.host).replace("127.0.0.1", self.server.host)
            if settings.deployment_log_verbosity == "detailed":
                await self.logger.info(f"替换为服务器地址: {url}")

        if settings.deployment_log_verbosity == "detailed":
            await self.logger.info(
                f"HTTP 健康检查: {url} (超时: {timeout}s, 重试: {retries}次, 间隔: {interval}s)"
            )
        else:
            await self.logger.info(f"HTTP 健康检查: {url}")

        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(1, retries + 1):
                try:
                    # 只在 detailed 模式下记录每次尝试
                    if settings.deployment_log_verbosity == "detailed":
                        await self.logger.info(f"HTTP 健康检查尝试 {attempt}/{retries}")

                    response = await client.get(url)
                    status_code = response.status_code

                    if 200 <= status_code < 400:
                        # minimal 模式下只记录最终成功一次
                        await self.logger.info("健康检查通过")
                        return True
                    else:
                        if settings.deployment_log_verbosity == "detailed":
                            await self.logger.warning(
                                f"HTTP 健康检查失败 (状态码: {status_code})"
                            )

                except httpx.TimeoutException:
                    if settings.deployment_log_verbosity == "detailed":
                        await self.logger.warning(f"HTTP 健康检查超时 (尝试 {attempt}/{retries})")
                except httpx.ConnectError as e:
                    if settings.deployment_log_verbosity == "detailed":
                        await self.logger.warning(f"HTTP 连接失败: {e}")
                except Exception as e:
                    if settings.deployment_log_verbosity == "detailed":
                        await self.logger.warning(f"HTTP 健康检查异常: {e}")

                # Wait before retry (except on last attempt)
                if attempt < retries:
                    if settings.deployment_log_verbosity == "detailed":
                        await self.logger.info(f"等待 {interval} 秒后重试...")
                    await asyncio.sleep(interval)

        await self.logger.error("健康检查失败")
        return False

    async def _check_tcp(self) -> bool:
        """Perform TCP port health check with retry mechanism.

        Returns:
            True if check passes, False otherwise
        """
        if not self.project.health_check_port:
            raise HealthCheckError("TCP 健康检查需要配置 health_check_port")

        host = self.server.host
        port = self.project.health_check_port
        timeout = self.project.health_check_timeout
        retries = self.project.health_check_retries
        interval = self.project.health_check_interval

        if settings.deployment_log_verbosity == "detailed":
            await self.logger.info(
                f"TCP 健康检查: {host}:{port} (超时: {timeout}s, 重试: {retries}次, 间隔: {interval}s)"
            )
        else:
            await self.logger.info(f"TCP 健康检查: {host}:{port}")

        for attempt in range(1, retries + 1):
            try:
                if settings.deployment_log_verbosity == "detailed":
                    await self.logger.info(f"TCP 健康检查尝试 {attempt}/{retries}")

                # Create socket and attempt connection
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)

                result = sock.connect_ex((host, port))
                sock.close()

                if result == 0:
                    await self.logger.info("健康检查通过")
                    return True
                else:
                    if settings.deployment_log_verbosity == "detailed":
                        await self.logger.warning(
                            f"TCP 端口 {port} 连接失败 (错误码: {result})"
                        )

            except socket.timeout:
                if settings.deployment_log_verbosity == "detailed":
                    await self.logger.warning(f"TCP 健康检查超时")
            except Exception as e:
                if settings.deployment_log_verbosity == "detailed":
                    await self.logger.warning(f"TCP 健康检查异常: {e}")

            # Wait before retry (except on last attempt)
            if attempt < retries:
                if settings.deployment_log_verbosity == "detailed":
                    await self.logger.info(f"等待 {interval} 秒后重试...")
                await asyncio.sleep(interval)

        await self.logger.error("健康检查失败")
        return False

    async def _check_command(self) -> bool:
        """Perform custom command health check with retry mechanism.

        Returns:
            True if check passes, False otherwise
        """
        if not self.project.health_check_command:
            raise HealthCheckError("命令健康检查需要配置 health_check_command")

        if not self.ssh_connection:
            raise HealthCheckError("命令健康检查需要 SSH 连接")

        command = self.project.health_check_command
        timeout = self.project.health_check_timeout
        retries = self.project.health_check_retries
        interval = self.project.health_check_interval

        if settings.deployment_log_verbosity == "detailed":
            await self.logger.info(
                f"命令健康检查: '{command}' (超时: {timeout}s, 重试: {retries}次, 间隔: {interval}s)"
            )
        else:
            await self.logger.info(f"命令健康检查")

        # Change to project's upload path before executing command
        upload_path = self.project.upload_path
        if not upload_path:
            raise HealthCheckError("项目未配置 upload_path，无法执行命令健康检查")

        full_command = f"cd {upload_path} && {command}"

        for attempt in range(1, retries + 1):
            try:
                if settings.deployment_log_verbosity == "detailed":
                    await self.logger.info(f"命令健康检查尝试 {attempt}/{retries}")

                # minimal 模式下不 streaming 输出
                if settings.deployment_log_verbosity == "minimal":
                    exit_code, stdout, stderr = self.ssh_connection.execute_command(full_command)
                    if exit_code == 0:
                        await self.logger.info("健康检查通过")
                        return True
                else:
                    # Execute command with streaming output
                    exit_code, stdout, stderr = self.ssh_connection.execute_command_streaming(
                        full_command,
                        on_stdout=lambda line: asyncio.create_task(
                            self.logger.info(f"[stdout] {line}")
                        ),
                        on_stderr=lambda line: asyncio.create_task(
                            self.logger.info(f"[stderr] {line}")
                        ),
                    )

                    await self.logger.info(f"命令退出码: {exit_code}")

                    if exit_code == 0:
                        await self.logger.info("命令健康检查成功")
                        return True
                    else:
                        await self.logger.warning(
                            f"命令健康检查失败 (退出码: {exit_code})"
                        )

            except Exception as e:
                if settings.deployment_log_verbosity == "detailed":
                    await self.logger.warning(f"命令健康检查异常: {e}")

            # Wait before retry (except on last attempt)
            if attempt < retries:
                if settings.deployment_log_verbosity == "detailed":
                    await self.logger.info(f"等待 {interval} 秒后重试...")
                await asyncio.sleep(interval)

        await self.logger.error("健康检查失败")
        return False


async def perform_health_check(
    project: Project,
    server: Server,
    deployment_logger: DeploymentLogger,
    ssh_connection: SSHConnection | None = None,
) -> bool:
    """Perform health check on a deployed application.

    This is a convenience function for creating and executing a health check.

    Args:
        project: Project model instance
        server: Server to check
        deployment_logger: Deployment logger instance
        ssh_connection: Optional SSH connection for command execution

    Returns:
        True if health check passes, False otherwise

    Raises:
        HealthCheckError: If health check configuration is invalid or execution fails
    """
    service = HealthCheckService(project, server, deployment_logger, ssh_connection)
    return await service.check()
