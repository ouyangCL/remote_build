"""SSH connection management."""
import asyncio
import io
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Generator

from paramiko import (
    AutoAddPolicy,
    SSHClient,
    SFTPClient,
)
from paramiko.ssh_exception import (
    AuthenticationException,
    SSHException,
)

from app.config import settings
from app.core.security import decrypt_data
from app.models.server import AuthType, Server


class SSHLogger:
    """Logger interface for SSH operations."""

    async def info(self, message: str) -> None:
        """Log info message."""
        pass

    async def error(self, message: str) -> None:
        """Log error message."""
        pass


class NoOpSSHLogger(SSHLogger):
    """No-op logger implementation when no logger is provided."""


def _run_async(coro) -> None:
    """Run async function in sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(coro)
        else:
            loop.run_until_complete(coro)
    except RuntimeError:
        asyncio.run(coro)


@dataclass
class SSHConfig:
    """SSH connection configuration."""

    host: str
    port: int
    username: str
    auth_type: AuthType
    auth_value: str  # Encrypted password or key

    def decrypt_auth(self) -> str:
        """Decrypt authentication value.

        Returns:
            Decrypted password or SSH key
        """
        return decrypt_data(self.auth_value)


class SSHConnectionError(Exception):
    """SSH connection error."""

    pass


class SSHConnection:
    """SSH connection wrapper with context management."""

    def __init__(self, config: SSHConfig, logger: SSHLogger | None = None) -> None:
        """Initialize SSH connection.

        Args:
            config: SSH configuration
            logger: Optional logger for SSH operations
        """
        self.config = config
        self.client: SSHClient | None = None
        self.sftp: SFTPClient | None = None
        self._logger = logger or NoOpSSHLogger()

    def connect(self) -> None:
        """Establish SSH connection."""
        # Log connection start
        _run_async(
            self._logger.info(
                f"正在连接到服务器 {self.config.host}:{self.config.port}，用户 {self.config.username}"
            )
        )

        self.client = SSHClient()
        self.client.set_missing_host_key_policy(AutoAddPolicy())

        auth_value = self.config.decrypt_auth()

        try:
            # Log authentication method (仅 detailed 模式)
            if settings.deployment_log_verbosity == "detailed":
                if self.config.auth_type == AuthType.PASSWORD:
                    _run_async(self._logger.info("使用 密码 认证"))
                else:  # SSH_KEY
                    _run_async(self._logger.info("使用 SSH密钥 认证"))

            if self.config.auth_type == AuthType.PASSWORD:
                self.client.connect(
                    hostname=self.config.host,
                    port=self.config.port,
                    username=self.config.username,
                    password=auth_value,
                    timeout=30,
                )
            else:  # SSH_KEY
                # Handle key-based authentication
                import tempfile

                key_file = None
                try:
                    # Write key to temp file
                    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
                        f.write(auth_value)
                        key_file = f.name

                    # Load key from file
                    self.client.connect(
                        hostname=self.config.host,
                        port=self.config.port,
                        username=self.config.username,
                        key_filename=key_file,
                        timeout=30,
                    )
                finally:
                    # Clean up temp key file
                    if key_file and Path(key_file).exists():
                        Path(key_file).unlink()

            # Log successful connection
            _run_async(self._logger.info(f"已连接到服务器 {self.config.host}"))

        except AuthenticationException as e:
            _run_async(self._logger.error(f"SSH 连接失败: 认证失败 - {e}"))
            raise SSHConnectionError(f"SSH authentication failed: {e}") from e
        except SSHException as e:
            _run_async(self._logger.error(f"SSH 连接失败: {e}"))
            raise SSHConnectionError(f"SSH connection error: {e}") from e
        except OSError as e:
            _run_async(self._logger.error(f"SSH 连接失败: 网络错误 - {e}"))
            raise SSHConnectionError(f"Network error: {e}") from e

    def execute_command(self, command: str) -> tuple[int, str, str]:
        """Execute a command on the remote server.

        Args:
            command: Command to execute

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        if not self.client:
            raise SSHConnectionError("Not connected to SSH server")

        stdin, stdout, stderr = self.client.exec_command(command, timeout=300)
        exit_code = stdout.channel.recv_exit_status()
        stdout_text = stdout.read().decode("utf-8", errors="replace")
        stderr_text = stderr.read().decode("utf-8", errors="replace")

        return exit_code, stdout_text, stderr_text

    def execute_command_streaming(
        self,
        command: str,
        on_stdout: Callable[[str], None] | None = None,
        on_stderr: Callable[[str], None] | None = None,
    ) -> tuple[int, str, str]:
        """Execute a command with streaming output callbacks.

        This method provides real-time output streaming for long-running commands.
        Callback functions are invoked for each line of output as it is received.

        Args:
            command: Command to execute
            on_stdout: Optional callback for stdout lines (receives line string)
            on_stderr: Optional callback for stderr lines (receives line string)

        Returns:
            Tuple of (exit_code, full_stdout, full_stderr)
        """
        if not self.client:
            raise SSHConnectionError("Not connected to SSH server")

        stdin, stdout, stderr = self.client.exec_command(command, timeout=300)

        # Collect full output for return value
        full_stdout = []
        full_stderr = []

        # Read stdout line by line with streaming callback
        while True:
            line = stdout.readline()
            if not line:
                break
            line_text = line.rstrip("\n\r")
            full_stdout.append(line_text)
            if on_stdout and line_text:
                on_stdout(line_text)

        # Read stderr line by line with streaming callback
        while True:
            line = stderr.readline()
            if not line:
                break
            line_text = line.rstrip("\n\r")
            full_stderr.append(line_text)
            if on_stderr and line_text:
                on_stderr(line_text)

        # Wait for command to finish and get exit code
        exit_code = stdout.channel.recv_exit_status()

        return exit_code, "\n".join(full_stdout), "\n".join(full_stderr)

    def upload_file(self, local_path: str | Path, remote_path: str | Path) -> None:
        """Upload a file to the remote server.

        Args:
            local_path: Local file path
            remote_path: Remote file path
        """
        if not self.client:
            raise SSHConnectionError("Not connected to SSH server")

        if not self.sftp:
            self.sftp = self.client.open_sftp()

        self.sftp.put(str(local_path), str(remote_path))

    def upload_file_with_progress(
        self,
        local_path: str | Path,
        remote_path: str | Path,
    ) -> None:
        """Upload a file to the remote server with progress tracking.

        Args:
            local_path: Local file path
            remote_path: Remote file path
        """
        if not self.client:
            raise SSHConnectionError("Not connected to SSH server")

        if not self.sftp:
            self.sftp = self.client.open_sftp()

        local_path = Path(local_path)
        filename = local_path.name
        file_size = local_path.stat().st_size
        size_mb = file_size / (1024 * 1024)

        # Log upload start
        _run_async(
            self._logger.info(f"开始上传 {filename} (文件大小: {size_mb:.2f} MB)")
        )

        start_time = time.time()

        # minimal 模式下不使用进度回调
        if settings.deployment_log_verbosity == "detailed":
            # Progress tracking
            last_progress = 0

            def progress_callback(transferred_size: int, total_size: int) -> None:
                nonlocal last_progress

                current_time = time.time()
                duration = current_time - start_time
                transferred_mb = transferred_size / (1024 * 1024)
                total_mb = total_size / (1024 * 1024)
                progress = int((transferred_size / total_size) * 100)

                # Log every 10% progress
                if progress >= last_progress + 10 or progress == 100:
                    _run_async(
                        self._logger.info(
                            f"上传进度: {progress}% ({transferred_mb:.2f}/{total_mb:.2f} MB)"
                        )
                    )
                    last_progress = progress

            try:
                # Use put with callback for progress tracking
                self.sftp.put(str(local_path), str(remote_path), callback=progress_callback)

                # Log upload complete
                duration = time.time() - start_time
                speed_mb = size_mb / duration if duration > 0 else 0
                _run_async(
                    self._logger.info(
                        f"上传完成 (耗时: {duration:.2f}秒, 速度: {speed_mb:.2f} MB/s)"
                    )
                )

            except Exception as e:
                # Log upload error
                duration = time.time() - start_time
                transferred_mb = (last_progress / 100) * size_mb
                _run_async(
                    self._logger.error(
                        f"上传失败: {e} (已传输: {transferred_mb:.2f} MB)"
                    )
                )
                raise
        else:
            # 简化模式：直接上传，无进度回调
            try:
                self.sftp.put(str(local_path), str(remote_path))

                # Log upload complete
                duration = time.time() - start_time
                _run_async(
                    self._logger.info(
                        f"上传完成 (耗时: {duration:.1f}秒)"
                    )
                )

            except Exception as e:
                # Log upload error
                _run_async(
                    self._logger.error(f"上传失败: {e}")
                )
                raise

    def upload_fileobj(self, fileobj: io.BytesIO, remote_path: str | Path) -> None:
        """Upload a file-like object to the remote server.

        Args:
            fileobj: File-like object to upload
            remote_path: Remote file path
        """
        if not self.client:
            raise SSHConnectionError("Not connected to SSH server")

        if not self.sftp:
            self.sftp = self.client.open_sftp()

        with self.sftp.file(str(remote_path), "wb") as remote_file:
            fileobj.seek(0)
            remote_file.write(fileobj.read())

    def download_file(self, remote_path: str | Path, local_path: str | Path) -> None:
        """Download a file from the remote server.

        Args:
            remote_path: Remote file path
            local_path: Local file path
        """
        if not self.client:
            raise SSHConnectionError("Not connected to SSH server")

        if not self.sftp:
            self.sftp = self.client.open_sftp()

        self.sftp.get(str(remote_path), str(local_path))

    def file_exists(self, remote_path: str | Path) -> bool:
        """Check if a file exists on the remote server.

        Args:
            remote_path: Remote file path

        Returns:
            True if file exists
        """
        if not self.client:
            raise SSHConnectionError("Not connected to SSH server")

        if not self.sftp:
            self.sftp = self.client.open_sftp()

        try:
            self.sftp.stat(str(remote_path))
            return True
        except IOError:
            return False

    def mkdir(self, remote_path: str | Path, mode: int = 0o755) -> None:
        """Create a directory on the remote server.

        Args:
            remote_path: Remote directory path
            mode: Directory permissions
        """
        if not self.client:
            raise SSHConnectionError("Not connected to SSH server")

        if not self.sftp:
            self.sftp = self.client.open_sftp()

        self.sftp.mkdir(str(remote_path), mode)

    def close(self) -> None:
        """Close SSH connection."""
        if self.sftp:
            self.sftp.close()
            self.sftp = None

        if self.client:
            self.client.close()
            self.client = None

    def __enter__(self) -> "SSHConnection":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        """Context manager exit."""
        self.close()


def create_ssh_connection(
    server: Server, logger: SSHLogger | None = None
) -> SSHConnection:
    """Create SSH connection from Server model.

    Args:
        server: Server model instance
        logger: Optional logger for SSH operations

    Returns:
        SSH connection instance
    """
    config = SSHConfig(
        host=server.host,
        port=server.port,
        username=server.username,
        auth_type=server.auth_type,
        auth_value=server.auth_value,
    )
    return SSHConnection(config, logger=logger)


@contextmanager
def ssh_connect(server: Server) -> Generator[SSHConnection, None, None]:
    """Context manager for SSH connection.

    Args:
        server: Server model instance

    Yields:
        SSH connection instance
    """
    conn = create_ssh_connection(server)
    try:
        conn.connect()
        yield conn
    finally:
        conn.close()


def test_ssh_connection(server: Server) -> bool:
    """Test SSH connection to a server.

    Args:
        server: Server model instance

    Returns:
        True if connection successful
    """
    try:
        with ssh_connect(server) as conn:
            # Execute a simple command
            exit_code, _, _ = conn.execute_command("echo 'connection test'")
            return exit_code == 0
    except SSHConnectionError:
        return False
