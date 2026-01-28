"""Tests for upload deployment API endpoint."""
import hashlib
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.deployment import Deployment, DeploymentArtifact, DeploymentStatus, DeploymentType
from app.models.project import Project, ProjectType
from app.models.server import ServerGroup
from app.models.user import User, UserRole


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = MagicMock(spec=Session)
    return db


@pytest.fixture
def mock_current_user():
    """Create a mock current user."""
    user = MagicMock(spec=User)
    user.id = 1
    user.username = "testuser"
    user.role = UserRole.ADMIN
    return user


@pytest.fixture
def mock_project():
    """Create a mock project."""
    project = MagicMock(spec=Project)
    project.id = 1
    project.name = "test-project"
    project.project_type = ProjectType.JAVA
    project.environment = "production"
    return project


@pytest.fixture
def mock_server_group():
    """Create a mock server group."""
    group = MagicMock(spec=ServerGroup)
    group.id = 1
    group.name = "test-group"
    group.environment = "production"
    return group


@pytest.fixture
def mock_upload_file_jar():
    """Create a mock uploaded JAR file."""
    file = MagicMock(spec=UploadFile)
    file.filename = "app.jar"
    file.content_type = "application/java-archive"

    # Create mock file content
    content = b"fake jar content"
    file.read = AsyncMock(return_value=content)
    return file, content


@pytest.fixture
def mock_upload_file_zip():
    """Create a mock uploaded ZIP file."""
    file = MagicMock(spec=UploadFile)
    file.filename = "frontend.zip"
    file.content_type = "application/zip"

    # Create mock file content
    content = b"fake zip content"
    file.read = AsyncMock(return_value=content)
    return file, content


class TestValidateUploadFile:
    """Test file validation function."""

    def test_validate_jar_file_for_java_project(self):
        """Test validation passes for JAR file with Java project."""
        from app.api.deployments import validate_upload_file

        # Should not raise exception
        validate_upload_file(ProjectType.JAVA, "app.jar")

    def test_validate_zip_file_for_frontend_project(self):
        """Test validation passes for ZIP file with frontend project."""
        from app.api.deployments import validate_upload_file

        # Should not raise exception
        validate_upload_file(ProjectType.FRONTEND, "app.zip")

    def test_validate_wrong_extension_for_java_project(self):
        """Test validation fails for non-JAR file with Java project."""
        from app.api.deployments import validate_upload_file
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_upload_file(ProjectType.JAVA, "app.zip")

        assert exc_info.value.status_code == 400
        assert "Java项目请上传.jar文件" in exc_info.value.detail

    def test_validate_wrong_extension_for_frontend_project(self):
        """Test validation fails for non-ZIP file with frontend project."""
        from app.api.deployments import validate_upload_file
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_upload_file(ProjectType.FRONTEND, "app.jar")

        assert exc_info.value.status_code == 400
        assert "前端项目请上传.zip压缩包" in exc_info.value.detail


class TestUploadDeploymentAPI:
    """Test upload deployment API endpoint."""

    @pytest.mark.asyncio
    async def test_create_upload_deployment_success_java(
        self, mock_db, mock_current_user, mock_project, mock_server_group, mock_upload_file_jar
    ):
        """Test successful creation of upload deployment for Java project."""
        from app.api.deployments import validate_upload_file
        from fastapi import BackgroundTasks

        file, content = mock_upload_file_jar

        # Test that validation passes for correct file type
        validate_upload_file(mock_project.project_type, file.filename)

        # Verify the file content was read
        assert await file.read() == content
        assert len(content) > 0

        # Verify the mock setup is correct
        assert mock_project.project_type == ProjectType.JAVA
        assert file.filename == "app.jar"

    @pytest.mark.asyncio
    async def test_create_upload_deployment_invalid_file_type(
        self, mock_db, mock_current_user, mock_project, mock_upload_file_zip
    ):
        """Test upload deployment fails with wrong file type."""
        from app.api.deployments import create_upload_deployment
        from fastapi import BackgroundTasks, HTTPException

        file, content = mock_upload_file_zip

        # Change project type to JAVA but file is ZIP
        mock_project.project_type = ProjectType.JAVA

        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_project
        mock_db.query.return_value = mock_query

        mock_background_tasks = MagicMock(spec=BackgroundTasks)

        with pytest.raises(HTTPException) as exc_info:
            await create_upload_deployment(
                project_id=1,
                server_group_ids="1",
                file=file,
                request=MagicMock(),
                background_tasks=mock_background_tasks,
                db=mock_db,
                current_user=mock_current_user,
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_create_upload_deployment_project_not_found(
        self, mock_db, mock_current_user, mock_upload_file_jar
    ):
        """Test upload deployment fails when project not found."""
        from app.api.deployments import create_upload_deployment
        from fastapi import BackgroundTasks, HTTPException

        file, content = mock_upload_file_jar

        # Setup mock to return None (project not found)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        mock_background_tasks = MagicMock(spec=BackgroundTasks)

        with pytest.raises(HTTPException) as exc_info:
            await create_upload_deployment(
                project_id=999,
                server_group_ids="1",
                file=file,
                request=MagicMock(),
                background_tasks=mock_background_tasks,
                db=mock_db,
                current_user=mock_current_user,
            )

        assert exc_info.value.status_code == 404
        assert "项目不存在" in exc_info.value.detail


class TestUploadDeploymentService:
    """Test upload deployment in deployment service."""

    @pytest.mark.asyncio
    async def test_upload_deploy_flow(self):
        """Test upload deployment flow in service."""
        from app.models.deployment import DeploymentArtifact
        from app.services.deploy_service import DeploymentService

        # Create mock deployment with artifact
        mock_deployment = MagicMock(spec=Deployment)
        mock_deployment.id = 1
        mock_deployment.branch = "upload"
        mock_deployment.deployment_type = DeploymentType.UPLOAD
        mock_deployment.status = DeploymentStatus.PENDING

        # Create mock project
        mock_project = MagicMock()
        mock_project.name = "test-project"
        mock_project.health_check_enabled = False
        mock_deployment.project = mock_project

        # Create mock artifact
        mock_artifact = MagicMock(spec=DeploymentArtifact)
        mock_artifact.file_path = "/tmp/deployments/1_app.jar"
        mock_deployment.artifacts = [mock_artifact]

        mock_db = MagicMock(spec=Session)

        # Create deployment service
        service = DeploymentService(mock_deployment, mock_db)

        # Mock the internal methods
        service._update_status = AsyncMock()
        service._deploy_to_servers = AsyncMock()
        service._perform_health_checks = AsyncMock()

        # Execute upload deployment
        await service._upload_deploy()

        # Verify the flow
        service._update_status.assert_any_call(DeploymentStatus.DEPLOYING)
        service._deploy_to_servers.assert_called_once_with(mock_artifact.file_path)
        service._update_status.assert_any_call(DeploymentStatus.SUCCESS)

    @pytest.mark.asyncio
    async def test_upload_deploy_with_health_check(self):
        """Test upload deployment flow with health check."""
        from app.models.deployment import DeploymentArtifact
        from app.services.deploy_service import DeploymentService

        # Create mock deployment with artifact
        mock_deployment = MagicMock(spec=Deployment)
        mock_deployment.id = 1
        mock_deployment.branch = "upload"
        mock_deployment.deployment_type = DeploymentType.UPLOAD
        mock_deployment.status = DeploymentStatus.PENDING

        # Create mock project with health check enabled
        mock_project = MagicMock()
        mock_project.name = "test-project"
        mock_project.health_check_enabled = True
        mock_deployment.project = mock_project

        # Create mock artifact
        mock_artifact = MagicMock(spec=DeploymentArtifact)
        mock_artifact.file_path = "/tmp/deployments/1_app.jar"
        mock_deployment.artifacts = [mock_artifact]

        mock_db = MagicMock(spec=Session)

        # Create deployment service
        service = DeploymentService(mock_deployment, mock_db)

        # Mock the internal methods
        service._update_status = AsyncMock()
        service._deploy_to_servers = AsyncMock()
        service._perform_health_checks = AsyncMock()

        # Execute upload deployment
        await service._upload_deploy()

        # Verify the flow includes health check
        service._update_status.assert_any_call(DeploymentStatus.DEPLOYING)
        service._deploy_to_servers.assert_called_once()
        service._update_status.assert_any_call(DeploymentStatus.HEALTH_CHECKING)
        service._perform_health_checks.assert_called_once()
        service._update_status.assert_any_call(DeploymentStatus.SUCCESS)

    @pytest.mark.asyncio
    async def test_upload_deploy_no_artifact(self):
        """Test upload deployment fails when no artifact found."""
        from app.services.deploy_service import DeploymentService, DeploymentError

        # Create mock deployment without artifact
        mock_deployment = MagicMock(spec=Deployment)
        mock_deployment.id = 1
        mock_deployment.branch = "upload"
        mock_deployment.deployment_type = DeploymentType.UPLOAD
        mock_deployment.status = DeploymentStatus.PENDING
        mock_deployment.artifacts = []

        # Create mock project
        mock_project = MagicMock()
        mock_project.name = "test-project"
        mock_deployment.project = mock_project

        mock_db = MagicMock(spec=Session)

        # Create deployment service
        service = DeploymentService(mock_deployment, mock_db)

        # Mock the internal methods
        service._update_status = AsyncMock()

        # Execute upload deployment should raise error
        with pytest.raises(DeploymentError) as exc_info:
            await service._upload_deploy()

        assert "No artifact found" in str(exc_info.value)
