"""SSH connection management."""
import io
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

from paramiko import (
    AutoAddPolicy,
    SSHClient,
    SFTPClient,
)
from paramiko.ssh_exception import (
    AuthenticationException,
    SSHException,
)

from app.core.security import decrypt_data
from app.models.server import AuthType, Server


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

    def __init__(self, config: SSHConfig) -> None:
        """Initialize SSH connection.

        Args:
            config: SSH configuration
        """
        self.config = config
        self.client: SSHClient | None = None
        self.sftp: SFTPClient | None = None

    def connect(self) -> None:
        """Establish SSH connection."""
        self.client = SSHClient()
        self.client.set_missing_host_key_policy(AutoAddPolicy())

        auth_value = self.config.decrypt_auth()

        try:
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

        except AuthenticationException as e:
            raise SSHConnectionError(f"SSH authentication failed: {e}") from e
        except SSHException as e:
            raise SSHConnectionError(f"SSH connection error: {e}") from e
        except OSError as e:
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


def create_ssh_connection(server: Server) -> SSHConnection:
    """Create SSH connection from Server model.

    Args:
        server: Server model instance

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
    return SSHConnection(config)


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
