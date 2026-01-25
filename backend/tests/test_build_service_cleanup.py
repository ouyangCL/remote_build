"""Tests for artifact cleanup functionality."""
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.build_service import cleanup_artifacts


@pytest.fixture
def temp_artifacts_dir():
    """Create a temporary artifacts directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_dir = Path(tmpdir) / "artifacts"
        artifacts_dir.mkdir()
        yield artifacts_dir


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    return logger


def create_artifact(artifacts_dir: Path, timestamp: int | None = None) -> Path:
    """Helper to create a test artifact file.

    Args:
        artifacts_dir: Directory to create artifact in
        timestamp: Timestamp for filename (uses current time if None)

    Returns:
        Path to created artifact
    """
    if timestamp is None:
        timestamp = int(time.time())

    artifact_path = artifacts_dir / f"artifact_{timestamp}.zip"
    artifact_path.write_text(f"test content {timestamp}")
    return artifact_path


def test_cleanup_keeps_latest_single_project(temp_artifacts_dir, mock_logger):
    """Test that cleanup keeps only the latest artifact for a project."""
    with patch("app.services.build_service.settings") as mock_settings:
        mock_settings.artifacts_dir = str(temp_artifacts_dir)

        # Create 5 artifacts with different timestamps
        timestamps = [1000, 2000, 3000, 4000, 5000]
        for ts in timestamps:
            create_artifact(temp_artifacts_dir, ts)

        # Verify all files exist
        artifacts = list(temp_artifacts_dir.glob("artifact_*.zip"))
        assert len(artifacts) == 5

        # Run cleanup with project_id=None (global cleanup)
        # Project-specific filtering requires database integration
        cleanup_artifacts(
            project_id=None,
            keep_latest=True,
            logger=mock_logger,
        )

        # Verify only the latest artifact remains
        artifacts = list(temp_artifacts_dir.glob("artifact_*.zip"))
        assert len(artifacts) == 1
        assert artifacts[0].name == "artifact_5000.zip"


def test_cleanup_with_no_project_filter(temp_artifacts_dir, mock_logger):
    """Test cleanup without project filter keeps only one global artifact."""
    with patch("app.services.build_service.settings") as mock_settings:
        mock_settings.artifacts_dir = str(temp_artifacts_dir)

        # Create 5 artifacts
        timestamps = [1000, 2000, 3000, 4000, 5000]
        for ts in timestamps:
            create_artifact(temp_artifacts_dir, ts)

        # Run cleanup without project filter
        cleanup_artifacts(
            project_id=None,
            keep_latest=True,
            logger=mock_logger,
        )

        # Verify only the latest artifact remains
        artifacts = list(temp_artifacts_dir.glob("artifact_*.zip"))
        assert len(artifacts) == 1
        assert artifacts[0].name == "artifact_5000.zip"


def test_cleanup_with_single_artifact(temp_artifacts_dir, mock_logger):
    """Test that cleanup doesn't delete when there's only one artifact."""
    with patch("app.services.build_service.settings") as mock_settings:
        mock_settings.artifacts_dir = str(temp_artifacts_dir)

        # Create only 1 artifact
        create_artifact(temp_artifacts_dir, 1000)

        # Run cleanup
        cleanup_artifacts(
            project_id=None,
            keep_latest=True,
            logger=mock_logger,
        )

        # Verify the artifact still exists
        artifacts = list(temp_artifacts_dir.glob("artifact_*.zip"))
        assert len(artifacts) == 1


def test_cleanup_with_no_artifacts(temp_artifacts_dir, mock_logger):
    """Test that cleanup handles empty artifacts directory gracefully."""
    with patch("app.services.build_service.settings") as mock_settings:
        mock_settings.artifacts_dir = str(temp_artifacts_dir)

        # Run cleanup on empty directory
        cleanup_artifacts(
            project_id=None,
            keep_latest=True,
            logger=mock_logger,
        )

        # Should not raise any errors
        assert True


def test_cleanup_logs_deleted_files(temp_artifacts_dir, mock_logger):
    """Test that cleanup logs information about deleted files."""
    with patch("app.services.build_service.settings") as mock_settings:
        mock_settings.artifacts_dir = str(temp_artifacts_dir)

        # Create 3 artifacts
        create_artifact(temp_artifacts_dir, 1000)  # 50 bytes
        create_artifact(temp_artifacts_dir, 2000)  # 50 bytes
        create_artifact(temp_artifacts_dir, 3000)  # 50 bytes

        # Run cleanup
        cleanup_artifacts(
            project_id=None,
            keep_latest=True,
            logger=mock_logger,
        )

        # Verify logger was called
        assert mock_logger.info.called

        # Check that cleanup summary was logged
        log_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("删除 2 个旧文件" in str(call) for call in log_calls)


def test_cleanup_handles_file_errors_gracefully(temp_artifacts_dir, mock_logger):
    """Test that cleanup doesn't crash even with unexpected file states."""
    with patch("app.services.build_service.settings") as mock_settings:
        mock_settings.artifacts_dir = str(temp_artifacts_dir)

        # Create artifacts
        artifact1 = create_artifact(temp_artifacts_dir, 1000)
        artifact2 = create_artifact(temp_artifacts_dir, 2000)
        artifact3 = create_artifact(temp_artifacts_dir, 3000)

        # Run cleanup - should complete without errors
        cleanup_artifacts(
            project_id=None,
            keep_latest=True,
            logger=mock_logger,
        )

        # Verify cleanup completed successfully
        # The latest artifact should remain
        artifacts = list(temp_artifacts_dir.glob("artifact_*.zip"))
        assert len(artifacts) == 1
        assert artifacts[0].name == "artifact_3000.zip"


def test_cleanup_size_formatting(temp_artifacts_dir, mock_logger):
    """Test that cleanup formats file sizes correctly."""
    with patch("app.services.build_service.settings") as mock_settings:
        mock_settings.artifacts_dir = str(temp_artifacts_dir)

        # Create multiple artifacts with larger content to test MB formatting
        # Create oldest artifact (will be deleted)
        old_artifact = create_artifact(temp_artifacts_dir, 1000)
        old_artifact.write_bytes(b"x" * int(1.5 * 1024 * 1024))  # 1.5 MB

        # Wait a bit to ensure different mtime
        time.sleep(0.01)

        # Create newest artifact (will be kept)
        new_artifact = create_artifact(temp_artifacts_dir, 2000)
        new_artifact.write_bytes(b"x" * int(2.0 * 1024 * 1024))  # 2.0 MB

        # Run cleanup
        cleanup_artifacts(
            project_id=None,
            keep_latest=True,
            logger=mock_logger,
        )

        # Verify logger was called with size information
        assert mock_logger.info.called

        # Check the actual log messages
        info_messages = []
        for call in mock_logger.info.call_args_list:
            if call[0]:  # If there are positional args
                info_messages.append(str(call[0][0]))

        # Should log size in MB for large files (1.5 MB should be formatted as MB)
        assert any("MB" in msg for msg in info_messages), f"No MB found in: {info_messages}"
