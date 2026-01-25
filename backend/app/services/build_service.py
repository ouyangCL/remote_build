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
        project_type: str = "frontend",
        install_script: str | None = None,
        auto_install: bool = True,
        project_id: int | None = None,
    ) -> None:
        """Initialize build service.

        Args:
            source_dir: Source code directory
            build_script: Build script to execute
            output_dir: Output directory relative to source_dir
            on_output: Callback for build output (deprecated, use logger instead)
            logger: DeploymentLogger for structured logging
            project_type: Project type (frontend/backend/java) for default install commands
            install_script: Custom dependency installation command
            auto_install: Whether to automatically install dependencies
            project_id: Project ID for artifact cleanup
        """
        self.source_dir = Path(source_dir)
        self.build_script = build_script
        self.output_dir = output_dir
        self.on_output = on_output or (lambda x: None)
        self.logger = logger
        self.project_type = project_type
        self.install_script = install_script
        self.auto_install = auto_install
        self.project_id = project_id
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

    def _get_install_command(self) -> str | None:
        """Get the dependency installation command.

        Returns:
            Install command string or None if no installation needed
        """
        # If auto_install is disabled, return None
        if not self.auto_install:
            return None

        # If custom install_script is provided, use it
        if self.install_script:
            return self.install_script

        # Otherwise, use default based on project type
        default_commands = {
            "frontend": "npm install",
            "java": "mvn dependency:resolve",
            "backend": None,  # No default for backend
        }

        return default_commands.get(self.project_type)

    def _install_dependencies(self) -> int:
        """Install project dependencies before build.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        install_cmd = self._get_install_command()

        if not install_cmd:
            self._log_info("跳过依赖安装（未配置或已禁用）")
            return 0

        self._log_info("=" * 50)
        self._log_info("开始安装依赖")
        if settings.deployment_log_verbosity == "detailed":
            self._log_info(f"项目类型: {self.project_type}")
            self._log_info(f"安装命令: {install_cmd}")
        self._log_info("=" * 50)

        import subprocess

        # Parse install command
        parts = install_cmd.split()
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
                # Simple mode: collect output
                stdout, _ = process.communicate()

                if process.returncode != 0:
                    self._log_error("依赖安装失败，输出:")
                    for line in stdout.splitlines():
                        self._log_error(f"  {line}")
                    return process.returncode
                else:
                    self._log_info("依赖安装完成")
            else:
                # Detailed mode: stream output
                self._log_info("安装输出:")

                for line in process.stdout or []:
                    line = line.rstrip()
                    if line:
                        self._log_info(f"  {line}")

                process.wait()

                if process.returncode != 0:
                    self._log_error(f"依赖安装失败，退出码: {process.returncode}")
                    return process.returncode

                self._log_info("=" * 50)
                self._log_info("依赖安装成功")
                self._log_info("=" * 50)

            return 0

        except FileNotFoundError:
            self._log_error(f"命令未找到: {command}")
            self._log_error(f"请确保 {command} 已安装并在 PATH 中")
            return 1
        except Exception as e:
            self._log_error(f"依赖安装时出错: {e}")
            return 1

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

        # Install dependencies if needed
        if self.auto_install or self.install_script:
            install_exit_code = self._install_dependencies()
            if install_exit_code != 0:
                self._log_warning(f"依赖安装失败（退出码: {install_exit_code}），将继续尝试构建")
                # Continue anyway - user might have pre-installed dependencies

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

        # Clean up old artifacts (keep only the latest one)
        try:
            cleanup_artifacts(
                project_id=self.project_id,
                keep_latest=True,
                logger=self.logger,
            )
        except Exception as e:
            # Cleanup failure should not affect the build process
            self._log_warning(f"清理旧 artifacts 时出错: {e}")

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


def cleanup_artifacts(
    project_id: int | None = None,
    max_size_mb: int | None = None,
    keep_latest: bool = True,
    logger: "DeploymentLogger | None" = None,
) -> None:
    """Clean up old artifacts.

    Args:
        project_id: Project ID to filter artifacts. If None, cleans all artifacts.
        max_size_mb: Maximum size in MB (deprecated, use keep_latest instead).
        keep_latest: If True, keeps only the latest artifact per project.
        logger: DeploymentLogger for logging cleanup actions.
    """
    artifacts_dir = Path(settings.artifacts_dir)
    if not artifacts_dir.exists():
        return

    # Get all artifacts with their stats
    artifacts = []
    for artifact_path in artifacts_dir.glob("artifact_*.zip"):
        try:
            stat = artifact_path.stat()
            artifacts.append({
                "path": artifact_path,
                "mtime": stat.st_mtime,
                "size": stat.st_size,
                "name": artifact_path.name,
            })
        except OSError:
            # Skip files that can't be accessed
            continue

    if not artifacts:
        return

    # Sort by modification time (newest first)
    artifacts.sort(key=lambda x: x["mtime"], reverse=True)

    # Group by project if project_id is specified
    if project_id is not None:
        # Filter artifacts belonging to this project
        # Note: Since artifacts are named by timestamp, we need to query the database
        # to find which artifacts belong to which project
        from app.db.session import SessionLocal
        from app.models.deployment import DeploymentArtifact

        db = SessionLocal()
        try:
            # Get all artifact file paths for this project
            project_artifacts = db.query(DeploymentArtifact).join(
                DeploymentArtifact.deployment
            ).filter(
                DeploymentArtifact.deployment.has(project_id=project_id)
            ).all()

            project_file_paths = {artifact.file_path for artifact in project_artifacts}

            # Filter artifacts to only those belonging to this project
            filtered_artifacts = [
                a for a in artifacts
                if str(a["path"]) in project_file_paths
            ]
            artifacts = filtered_artifacts
        finally:
            db.close()

    if not artifacts:
        return

    # Keep only the latest artifact
    if keep_latest and len(artifacts) > 1:
        artifacts_to_delete = artifacts[1:]  # Keep the first (newest) one
        total_deleted_size = 0
        deleted_count = 0
        deleted_names = []

        for artifact in artifacts_to_delete:
            try:
                total_deleted_size += artifact["size"]
                deleted_names.append(artifact["name"])
                artifact["path"].unlink()
                deleted_count += 1
            except OSError as e:
                _log_cleanup_warning(
                    logger,
                    f"删除 artifact 失败: {artifact['name']} - {e}"
                )

        # Log cleanup results
        if deleted_count > 0:
            # Format size for display
            if total_deleted_size < 1024:
                size_str = f"{total_deleted_size} B"
            elif total_deleted_size < 1024 * 1024:
                size_str = f"{total_deleted_size / 1024:.2f} KB"
            else:
                size_str = f"{total_deleted_size / (1024 * 1024):.2f} MB"

            _log_cleanup_info(
                logger,
                f"Artifact 清理完成：删除 {deleted_count} 个旧文件，"
                f"释放 {size_str} 磁盘空间"
            )

            if deleted_count <= 5:  # Only list names if not too many
                for name in deleted_names:
                    _log_cleanup_info(logger, f"  - 已删除: {name}")
            else:
                _log_cleanup_info(
                    logger,
                    f"  - 已删除: {deleted_names[0]}, {deleted_names[1]}, "
                    f"... (共 {deleted_count} 个文件)"
                )

    # Legacy: size-based cleanup (deprecated)
    elif max_size_mb is not None:
        total_size = sum(a["size"] for a in artifacts)
        total_size_mb = total_size / (1024 * 1024)

        if total_size_mb > max_size_mb:
            # Sort by modification time (oldest first)
            artifacts.sort(key=lambda x: x["mtime"])

            # Delete oldest artifacts until under limit
            deleted_count = 0
            for artifact in artifacts:
                artifact["path"].unlink()
                total_size -= artifact["size"]
                deleted_count += 1
                total_size_mb = total_size / (1024 * 1024)

                if total_size_mb <= max_size_mb:
                    break

            _log_cleanup_info(
                logger,
                f"基于大小的清理：删除 {deleted_count} 个旧 artifact"
            )


def _log_cleanup_info(logger: "DeploymentLogger | None", message: str) -> None:
    """Log info message during cleanup.

    Args:
        logger: DeploymentLogger instance
        message: Message to log
    """
    if logger:
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                asyncio.create_task(logger.info(message))
            else:
                loop.run_until_complete(logger.info(message))
        except Exception:
            pass


def _log_cleanup_warning(logger: "DeploymentLogger | None", message: str) -> None:
    """Log warning message during cleanup.

    Args:
        logger: DeploymentLogger instance
        message: Message to log
    """
    if logger:
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                asyncio.create_task(logger.warning(message))
            else:
                loop.run_until_complete(logger.warning(message))
        except Exception:
            pass
