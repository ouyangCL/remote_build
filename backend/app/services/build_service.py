"""Build service for building and packaging projects."""
import hashlib
import os
import shutil
import zipfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from app.config import settings


class BuildStatus(str, Enum):
    """Build status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BuildResult:
    """Build result."""

    status: BuildStatus
    artifact_path: Path | None = None
    artifact_size: int = 0
    checksum: str = ""
    error_message: str = ""


class BuildError(Exception):
    """Build operation error."""

    pass


class BuildService:
    """Service for building projects."""

    def __init__(
        self,
        source_dir: Path,
        build_script: str,
        output_dir: str = "dist",
        on_output: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize build service.

        Args:
            source_dir: Source code directory
            build_script: Build script to execute
            output_dir: Output directory relative to source_dir
            on_output: Callback for build output
        """
        self.source_dir = Path(source_dir)
        self.build_script = build_script
        self.output_dir = output_dir
        self.on_output = on_output or (lambda x: None)
        self._cancelled = False

    def cancel(self) -> None:
        """Cancel the build."""
        self._cancelled = True

    def build(self) -> BuildResult:
        """Execute build process.

        Returns:
            Build result

        Raises:
            BuildError: If build fails
        """
        self._log(f"Starting build in {self.source_dir}")
        self._log(f"Output directory: {self.output_dir}")

        try:
            # Execute build script
            exit_code = self._execute_build_script()

            if self._cancelled:
                return BuildResult(status=BuildStatus.CANCELLED)

            if exit_code != 0:
                return BuildResult(
                    status=BuildStatus.FAILED,
                    error_message=f"Build script failed with exit code {exit_code}",
                )

            # Check if output directory exists
            output_path = self.source_dir / self.output_dir
            if not output_path.exists():
                return BuildResult(
                    status=BuildStatus.FAILED,
                    error_message=f"Output directory '{self.output_dir}' not found",
                )

            # Create artifact
            artifact_path = self._create_artifact(output_path)

            # Calculate checksum
            checksum = self._calculate_checksum(artifact_path)
            file_size = artifact_path.stat().st_size

            self._log(f"Build completed successfully")
            self._log(f"Artifact: {artifact_path}")
            self._log(f"Size: {file_size} bytes")
            self._log(f"Checksum: {checksum}")

            return BuildResult(
                status=BuildStatus.SUCCESS,
                artifact_path=artifact_path,
                artifact_size=file_size,
                checksum=checksum,
            )

        except Exception as e:
            self._log(f"Build error: {e}")
            return BuildResult(
                status=BuildStatus.FAILED,
                error_message=str(e),
            )

    def _execute_build_script(self) -> int:
        """Execute build script.

        Returns:
            Exit code
        """
        import subprocess

        self._log(f"Executing: {self.build_script}")

        # Parse build script into command and arguments
        parts = self.build_script.split()
        command = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        try:
            process = subprocess.Popen(
                [command] + args,
                cwd=self.source_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered
            )

            # Stream output
            for line in process.stdout or []:
                line = line.rstrip()
                if line:
                    self._log(line)

            process.wait()
            return process.returncode

        except FileNotFoundError:
            self._log(f"Error: Command '{command}' not found")
            return 1
        except Exception as e:
            self._log(f"Error executing build script: {e}")
            return 1

    def _create_artifact(self, source_path: Path) -> Path:
        """Create a zip artifact from source directory.

        Args:
            source_path: Source directory to package

        Returns:
            Path to created artifact
        """
        # Create artifacts directory
        artifacts_dir = Path(settings.artifacts_dir)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Generate artifact filename
        import time

        timestamp = int(time.time())
        artifact_name = f"artifact_{timestamp}.zip"
        artifact_path = artifacts_dir / artifact_name

        self._log(f"Creating artifact: {artifact_path}")

        # Create zip archive
        with zipfile.ZipFile(artifact_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, source_path)
                    zipf.write(file_path, arcname)

        return artifact_path

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file.

        Args:
            file_path: File to checksum

        Returns:
            Hexadecimal checksum string
        """
        sha256 = hashlib.sha256()

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)

        return sha256.hexdigest()

    def _log(self, message: str) -> None:
        """Log a message.

        Args:
            message: Message to log
        """
        self.on_output(message)


def cleanup_artifacts(max_size_mb: int | None = None) -> None:
    """Clean up old artifacts if total size exceeds limit.

    Args:
        max_size_mb: Maximum size in MB
    """
    if max_size_mb is None:
        max_size_mb = settings.max_artifacts_size_mb

    artifacts_dir = Path(settings.artifacts_dir)
    if not artifacts_dir.exists():
        return

    # Get all artifacts with their stats
    artifacts = []
    total_size = 0

    for artifact in artifacts_dir.glob("artifact_*.zip"):
        size = artifact.stat().st_size
        total_size += size
        artifacts.append((artifact.stat().st_mtime, artifact, size))

    # Check if size limit exceeded
    total_size_mb = total_size / (1024 * 1024)
    if total_size_mb <= max_size_mb:
        return

    # Sort by modification time (oldest first)
    artifacts.sort(key=lambda x: x[0])

    # Delete oldest artifacts until under limit
    for mtime, artifact, size in artifacts:
        artifact.unlink()
        total_size -= size
        total_size_mb = total_size / (1024 * 1024)

        if total_size_mb <= max_size_mb:
            break
