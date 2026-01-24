"""Build service for building and packaging projects."""
import asyncio
import hashlib
import os
import shutil
import zipfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from app.config import settings

if TYPE_CHECKING:
    from app.services.log_service import DeploymentLogger


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
        logger: "DeploymentLogger | None" = None,
    ) -> None:
        """Initialize build service.

        Args:
            source_dir: Source code directory
            build_script: Build script to execute
            output_dir: Output directory relative to source_dir
            on_output: Callback for build output (deprecated, use logger instead)
            logger: DeploymentLogger for structured logging
        """
        self.source_dir = Path(source_dir)
        self.build_script = build_script
        self.output_dir = output_dir
        self.on_output = on_output or (lambda x: None)
        self.logger = logger
        self._cancelled = False

    def cancel(self) -> None:
        """Cancel the build."""
        self._cancelled = True
        self._log_info("构建已取消")

    def _log_info(self, message: str) -> None:
        """Log info message (synchronous wrapper for async logger).

        Args:
            message: Message to log
        """
        # Always call on_output for backward compatibility
        self.on_output(message)

        # Also use DeploymentLogger if available
        if self.logger:
            try:
                # Create new event loop if none exists
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        raise RuntimeError("Loop is closed")
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                # Run async logging in existing loop
                if loop.is_running():
                    # If loop is running, schedule the coroutine
                    asyncio.create_task(self.logger.info(message))
                else:
                    # If loop is not running, run the coroutine
                    loop.run_until_complete(self.logger.info(message))
            except Exception:
                # Silently fail if logging fails
                pass

    def _log_error(self, message: str) -> None:
        """Log error message (synchronous wrapper for async logger).

        Args:
            message: Message to log
        """
        # Always call on_output for backward compatibility
        self.on_output(f"ERROR: {message}")

        # Also use DeploymentLogger if available
        if self.logger:
            try:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        raise RuntimeError("Loop is closed")
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                if loop.is_running():
                    asyncio.create_task(self.logger.error(message))
                else:
                    loop.run_until_complete(self.logger.error(message))
            except Exception:
                pass

    def _log_warning(self, message: str) -> None:
        """Log warning message (synchronous wrapper for async logger).

        Args:
            message: Message to log
        """
        # Always call on_output for backward compatibility
        self.on_output(f"WARNING: {message}")

        # Also use DeploymentLogger if available
        if self.logger:
            try:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        raise RuntimeError("Loop is closed")
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                if loop.is_running():
                    asyncio.create_task(self.logger.warning(message))
                else:
                    loop.run_until_complete(self.logger.warning(message))
            except Exception:
                pass

    def build(self) -> BuildResult:
        """Execute build process.

        Returns:
            Build result

        Raises:
            BuildError: If build fails
        """
        # minimal 模式下移除过多的分隔线
        if settings.deployment_log_verbosity == "detailed":
            self._log_info("=" * 50)

        self._log_info("开始构建过程")

        if settings.deployment_log_verbosity == "detailed":
            self._log_info(f"源代码目录: {self.source_dir}")
            self._log_info(f"输出目录: {self.output_dir}")
            self._log_info(f"构建脚本: {self.build_script}")
            self._log_info("=" * 50)

        try:
            # Execute build script
            exit_code = self._execute_build_script()

            if self._cancelled:
                self._log_info("构建已取消")
                return BuildResult(status=BuildStatus.CANCELLED)

            if exit_code != 0:
                self._log_error(f"构建脚本执行失败，退出码: {exit_code}")
                return BuildResult(
                    status=BuildStatus.FAILED,
                    error_message=f"Build script failed with exit code {exit_code}",
                )

            # Check if output directory exists
            output_path = self.source_dir / self.output_dir
            if not output_path.exists():
                self._log_error(f"输出目录不存在: {self.output_dir}")
                return BuildResult(
                    status=BuildStatus.FAILED,
                    error_message=f"Output directory '{self.output_dir}' not found",
                )

            self._log_info(f"输出目录已找到: {output_path}")

            # Create artifact
            artifact_path = self._create_artifact(output_path)

            # Calculate checksum
            self._log_info("正在计算校验和...")
            checksum = self._calculate_checksum(artifact_path)
            file_size = artifact_path.stat().st_size

            # Format file size for display
            if file_size < 1024:
                size_str = f"{file_size} B"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.2f} KB"
            else:
                size_str = f"{file_size / (1024 * 1024):.2f} MB"

            if settings.deployment_log_verbosity == "detailed":
                self._log_info("=" * 50)
            self._log_info("构建完成！")
            if settings.deployment_log_verbosity == "detailed":
                self._log_info("=" * 50)
            self._log_info(f"产物路径: {artifact_path}")
            self._log_info(f"产物大小: {size_str}")
            if settings.deployment_log_verbosity == "detailed":
                self._log_info(f"SHA256 校验和: {checksum}")

            return BuildResult(
                status=BuildStatus.SUCCESS,
                artifact_path=artifact_path,
                artifact_size=file_size,
                checksum=checksum,
            )

        except Exception as e:
            self._log_error(f"构建过程出错: {e}")
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

        self._log_info("执行构建脚本")

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
            )

            if settings.deployment_log_verbosity == "minimal":
                # 简化模式：收集输出，只显示结果
                stdout, _ = process.communicate()

                if process.returncode != 0:
                    # 失败时显示完整输出
                    self._log_error("构建失败，输出:")
                    for line in stdout.splitlines():
                        self._log_error(f"  {line}")
                else:
                    self._log_info("构建完成")
            else:
                # 详细模式：streaming 输出
                self._log_info("-" * 50)
                self._log_info(f"命令: {self.build_script}")
                self._log_info(f"工作目录: {self.source_dir}")
                self._log_info("-" * 50)
                self._log_info("构建输出:")

                # Stream output
                line_count = 0
                for line in process.stdout or []:
                    line = line.rstrip()
                    if line:
                        self._log_info(f"  {line}")
                        line_count += 1

                self._log_info("-" * 50)
                self._log_info(f"构建脚本执行完成，共输出 {line_count} 行")

            process.wait()
            return process.returncode

        except FileNotFoundError:
            self._log_error(f"命令未找到: {command}")
            self._log_error(f"请确保 {command} 已安装并在 PATH 中")
            return 1
        except Exception as e:
            self._log_error(f"执行构建脚本时出错: {e}")
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

        if settings.deployment_log_verbosity == "detailed":
            self._log_info("-" * 50)
        self._log_info("创建部署产物")
        if settings.deployment_log_verbosity == "detailed":
            self._log_info("-" * 50)
            self._log_info(f"源目录: {source_path}")
            self._log_info(f"产物路径: {artifact_path}")

        # Count files before compression
        file_count = 0
        total_size = 0
        for root, dirs, files in os.walk(source_path):
            for file in files:
                file_count += 1
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)

        if settings.deployment_log_verbosity == "detailed":
            # Format total size for display
            if total_size < 1024:
                total_size_str = f"{total_size} B"
            elif total_size < 1024 * 1024:
                total_size_str = f"{total_size / 1024:.2f} KB"
            else:
                total_size_str = f"{total_size / (1024 * 1024):.2f} MB"

            self._log_info(f"打包文件数量: {file_count}")
            self._log_info(f"源文件总大小: {total_size_str}")
        self._log_info("正在压缩...")

        # Create zip archive
        with zipfile.ZipFile(artifact_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, source_path)
                    zipf.write(file_path, arcname)

        # Get compressed size
        compressed_size = artifact_path.stat().st_size
        if compressed_size < 1024:
            compressed_size_str = f"{compressed_size} B"
        elif compressed_size < 1024 * 1024:
            compressed_size_str = f"{compressed_size / 1024:.2f} KB"
        else:
            compressed_size_str = f"{compressed_size / (1024 * 1024):.2f} MB"

        if settings.deployment_log_verbosity == "detailed":
            compression_ratio = (1 - compressed_size / total_size) * 100 if total_size > 0 else 0
            self._log_info(f"压缩后大小: {compressed_size_str}")
            self._log_info(f"压缩率: {compression_ratio:.1f}%")
            self._log_info("-" * 50)
        else:
            self._log_info(f"压缩完成: {compressed_size_str}")

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
