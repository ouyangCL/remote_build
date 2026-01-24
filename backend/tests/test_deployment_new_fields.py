"""Tests for new deployment fields and deployment flow.

This module tests the following changes:
1. Project model: new fields upload_path and restart_script_path
2. Server model: removed deploy_path field
3. Deployment flow: upload to upload_path, execute restart_script_path
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.deployment import DeploymentStatus
from app.models.project import ProjectType, HealthCheckType
from app.models.server import AuthType
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.services.deploy_service import DeploymentService, DeploymentError


@pytest.fixture
def mock_project_with_new_fields():
    """Create a mock project with new fields."""
    project = MagicMock()
    project.id = 1
    project.name = "test-project"
    project.description = "Test project with new fields"
    project.git_url = "https://github.com/test/repo.git"
    project.git_token = None
    project.git_ssh_key = None
    project.project_type = ProjectType.FRONTEND
    project.build_script = "npm run build"
    project.upload_path = "/opt/uploads"
    project.restart_script_path = "/opt/restart.sh"
    project.output_dir = "dist"
    project.environment = "development"
    project.health_check_enabled = True
    project.health_check_type = HealthCheckType.HTTP
    project.health_check_url = "http://localhost:8080/health"
    project.health_check_port = 8080
    project.health_check_command = "curl -f http://localhost:8080/health || exit 1"
    project.health_check_timeout = 30
    project.health_check_retries = 3
    project.health_check_interval = 5
    project.has_git_credentials = False
    return project


@pytest.fixture
def mock_server_without_deploy_path():
    """Create a mock server without deploy_path (as per new schema)."""
    server = MagicMock()
    server.id = 1
    server.name = "test-server"
    server.host = "192.168.1.100"
    server.port = 22
    server.username = "testuser"
    server.auth_type = AuthType.PASSWORD
    server.auth_value = "encrypted_password"
    server.is_active = True
    server.connection_status = "online"
    # Note: server.deploy_path should NOT be present in new schema
    # We can't assert this with MagicMock since it creates attributes on access
    # The actual model tests verify this properly
    return server


class TestProjectNewFields:
    """Test project model and schema with new fields."""

    def test_project_create_schema_with_new_fields(self):
        """Test ProjectCreate schema accepts new fields."""
        project_data = {
            "name": "test-project",
            "git_url": "https://github.com/test/repo.git",
            "project_type": "frontend",
            "build_script": "npm run build",
            "upload_path": "/opt/uploads",
            "restart_script_path": "/opt/restart.sh",
            "output_dir": "dist",
            "environment": "development",
        }

        project = ProjectCreate(**project_data)

        assert project.upload_path == "/opt/uploads"
        assert project.restart_script_path == "/opt/restart.sh"
        assert project.output_dir == "dist"

    def test_project_create_schema_default_values(self):
        """Test ProjectCreate schema uses correct default values."""
        project_data = {
            "name": "test-project",
            "git_url": "https://github.com/test/repo.git",
            "project_type": "frontend",
            "build_script": "npm run build",
        }

        project = ProjectCreate(**project_data)

        assert project.upload_path == ""  # Default is empty string
        assert project.restart_script_path == "/opt/restart.sh"  # Default value
        assert project.output_dir == "dist"  # Default value

    def test_project_update_schema_with_new_fields(self):
        """Test ProjectUpdate schema allows updating new fields."""
        update_data = {
            "upload_path": "/var/uploads",
            "restart_script_path": "/var/scripts/restart.sh",
        }

        project_update = ProjectUpdate(**update_data)

        assert project_update.upload_path == "/var/uploads"
        assert project_update.restart_script_path == "/var/scripts/restart.sh"

    def test_project_response_schema_includes_new_fields(self):
        """Test ProjectResponse schema includes new fields."""
        project_dict = {
            "id": 1,
            "name": "test-project",
            "description": "Test",
            "git_url": "https://github.com/test/repo.git",
            "git_token": None,
            "project_type": "frontend",
            "build_script": "npm run build",
            "upload_path": "/opt/uploads",
            "restart_script_path": "/opt/restart.sh",
            "output_dir": "dist",
            "environment": "development",
            "health_check_enabled": False,
            "health_check_type": "http",
            "health_check_url": None,
            "health_check_port": None,
            "health_check_command": None,
            "health_check_timeout": 30,
            "health_check_retries": 3,
            "health_check_interval": 5,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "has_git_credentials": False,
        }

        project = ProjectResponse(**project_dict)

        assert hasattr(project, 'upload_path')
        assert hasattr(project, 'restart_script_path')
        assert project.upload_path == "/opt/uploads"
        assert project.restart_script_path == "/opt/restart.sh"


class TestServerWithoutDeployPath:
    """Test server model no longer has deploy_path field."""

    def test_server_model_excludes_deploy_path(self):
        """Verify Server model does not have deploy_path field."""
        from app.models.server import Server

        # Check that deploy_path is not a column in Server model
        server_columns = [column.name for column in Server.__table__.columns]
        assert 'deploy_path' not in server_columns

    def test_server_response_schema_excludes_deploy_path(self):
        """Verify server response schema does not include deploy_path."""
        from app.schemas.server import ServerResponse

        server_data = {
            "id": 1,
            "name": "test-server",
            "host": "192.168.1.100",
            "port": 22,
            "username": "testuser",
            "auth_type": "password",
            "is_active": True,
            "connection_status": "online",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }

        server = ServerResponse(**server_data)

        # Verify deploy_path is not in the schema
        assert not hasattr(server, 'deploy_path')


class TestDeploymentFlowWithNewFields:
    """Test deployment flow uses new fields correctly."""

    @pytest.mark.asyncio
    async def test_deploy_to_server_uses_upload_path(
        self, mock_project_with_new_fields, mock_server_without_deploy_path
    ):
        """Test that deployment uploads to project's upload_path."""
        # Create a mock deployment
        deployment = MagicMock()
        deployment.id = 1
        deployment.project = mock_project_with_new_fields
        deployment.branch = "main"
        deployment.server_groups = []
        deployment.status = DeploymentStatus.PENDING

        # Create mock database session
        db = MagicMock()

        # Create deployment service
        service = DeploymentService(deployment, db)

        # Mock SSH connection
        mock_ssh_conn = MagicMock()
        mock_ssh_conn.__enter__ = MagicMock(return_value=mock_ssh_conn)
        mock_ssh_conn.__exit__ = MagicMock(return_value=False)
        mock_ssh_conn.execute_command = MagicMock(return_value=(0, "", ""))
        mock_ssh_conn.upload_file = MagicMock()

        with patch('app.services.deploy_service.create_ssh_connection', return_value=mock_ssh_conn):
            artifact_path = Path("/tmp/artifact.zip")

            # Deploy to server
            await service._deploy_to_server(mock_server_without_deploy_path, artifact_path)

            # Verify upload_file was called with correct remote path
            expected_remote_path = f"{mock_project_with_new_fields.upload_path}/{artifact_path.name}"
            mock_ssh_conn.upload_file.assert_called_once_with(artifact_path, expected_remote_path)

    @pytest.mark.asyncio
    async def test_deploy_executes_restart_script_path(
        self, mock_project_with_new_fields, mock_server_without_deploy_path
    ):
        """Test that deployment executes project's restart_script_path."""
        deployment = MagicMock()
        deployment.id = 1
        deployment.project = mock_project_with_new_fields
        deployment.branch = "main"
        deployment.server_groups = []
        deployment.status = DeploymentStatus.PENDING

        db = MagicMock()
        service = DeploymentService(deployment, db)

        # Mock SSH connection with streaming support
        mock_ssh_conn = MagicMock()
        mock_ssh_conn.__enter__ = MagicMock(return_value=mock_ssh_conn)
        mock_ssh_conn.__exit__ = MagicMock(return_value=False)
        mock_ssh_conn.execute_command = MagicMock(return_value=(0, "", ""))
        mock_ssh_conn.execute_command_streaming = MagicMock(return_value=(0, "success", ""))

        # Mock settings with proper object
        mock_settings = MagicMock()
        mock_settings.deployment_log_verbosity = 'detailed'

        with patch('app.services.deploy_service.create_ssh_connection', return_value=mock_ssh_conn):
            with patch('app.services.deploy_service.settings', mock_settings):
                artifact_path = Path("/tmp/artifact.zip")

                await service._deploy_to_server(mock_server_without_deploy_path, artifact_path)

                # Verify execute_command_streaming was called with restart script
                assert mock_ssh_conn.execute_command_streaming.called
                call_args = mock_ssh_conn.execute_command_streaming.call_args
                command = call_args[0][0]

                # Command should include the restart_script_path
                assert mock_project_with_new_fields.restart_script_path in command

    @pytest.mark.asyncio
    async def test_deploy_handles_empty_restart_script_path(
        self, mock_project_with_new_fields, mock_server_without_deploy_path
    ):
        """Test that deployment handles empty restart_script_path gracefully."""
        # Set restart_script_path to None
        mock_project_with_new_fields.restart_script_path = None

        deployment = MagicMock()
        deployment.id = 1
        deployment.project = mock_project_with_new_fields
        deployment.branch = "main"
        deployment.server_groups = []
        deployment.status = DeploymentStatus.PENDING

        db = MagicMock()
        service = DeploymentService(deployment, db)

        # Mock SSH connection
        mock_ssh_conn = MagicMock()
        mock_ssh_conn.__enter__ = MagicMock(return_value=mock_ssh_conn)
        mock_ssh_conn.__exit__ = MagicMock(return_value=False)
        mock_ssh_conn.execute_command = MagicMock(return_value=(0, "", ""))

        with patch('app.services.deploy_service.create_ssh_connection', return_value=mock_ssh_conn):
            artifact_path = Path("/tmp/artifact.zip")

            # Should not raise an error
            await service._deploy_to_server(mock_server_without_deploy_path, artifact_path)

            # Verify restart script was not executed
            # execute_command should be called twice: mkdir and unzip
            assert mock_ssh_conn.execute_command.call_count == 2

            # Verify mkdir command was called
            mkdir_calls = [call for call in mock_ssh_conn.execute_command.call_args_list
                          if 'mkdir' in call[0][0]]
            assert len(mkdir_calls) == 1
            assert mock_project_with_new_fields.upload_path in mkdir_calls[0][0][0]

            # Verify unzip command was called
            unzip_calls = [call for call in mock_ssh_conn.execute_command.call_args_list
                          if 'unzip' in call[0][0]]
            assert len(unzip_calls) == 1
            unzip_command = unzip_calls[0][0][0]
            assert 'unzip -o' in unzip_command
            assert mock_project_with_new_fields.upload_path in unzip_command

            # Verify execute_command_streaming was NOT called (no restart script)
            assert not mock_ssh_conn.execute_command_streaming.called

    @pytest.mark.asyncio
    async def test_deploy_creates_upload_directory(
        self, mock_project_with_new_fields, mock_server_without_deploy_path
    ):
        """Test that deployment creates upload directory before uploading."""
        deployment = MagicMock()
        deployment.id = 1
        deployment.project = mock_project_with_new_fields
        deployment.branch = "main"
        deployment.server_groups = []
        deployment.status = DeploymentStatus.PENDING

        db = MagicMock()
        service = DeploymentService(deployment, db)

        # Mock SSH connection
        mock_ssh_conn = MagicMock()
        mock_ssh_conn.__enter__ = MagicMock(return_value=mock_ssh_conn)
        mock_ssh_conn.__exit__ = MagicMock(return_value=False)
        mock_ssh_conn.execute_command = MagicMock(return_value=(0, "", ""))
        mock_ssh_conn.upload_file = MagicMock()

        with patch('app.services.deploy_service.create_ssh_connection', return_value=mock_ssh_conn):
            artifact_path = Path("/tmp/artifact.zip")

            await service._deploy_to_server(mock_server_without_deploy_path, artifact_path)

            # Verify mkdir command was called
            mkdir_calls = [call for call in mock_ssh_conn.execute_command.call_args_list
                          if 'mkdir' in call[0][0]]
            assert len(mkdir_calls) > 0

            # Verify mkdir uses upload_path
            mkdir_command = mkdir_calls[0][0][0]
            assert mock_project_with_new_fields.upload_path in mkdir_command


class TestDeploymentFlowEdgeCases:
    """Test edge cases in deployment flow."""

    @pytest.mark.asyncio
    async def test_deploy_with_inline_restart_command(
        self, mock_project_with_new_fields, mock_server_without_deploy_path
    ):
        """Test deployment with inline shell command as restart script."""
        # Set an inline command (contains shell operators)
        mock_project_with_new_fields.restart_script_path = "pm2 restart app && pm2 logs"

        deployment = MagicMock()
        deployment.id = 1
        deployment.project = mock_project_with_new_fields
        deployment.branch = "main"
        deployment.server_groups = []
        deployment.status = DeploymentStatus.PENDING

        db = MagicMock()
        service = DeploymentService(deployment, db)

        # Mock SSH connection
        mock_ssh_conn = MagicMock()
        mock_ssh_conn.__enter__ = MagicMock(return_value=mock_ssh_conn)
        mock_ssh_conn.__exit__ = MagicMock(return_value=False)
        mock_ssh_conn.execute_command = MagicMock(return_value=(0, "", ""))
        mock_ssh_conn.execute_command_streaming = MagicMock(return_value=(0, "", ""))

        # Mock settings with proper object
        mock_settings = MagicMock()
        mock_settings.deployment_log_verbosity = 'detailed'

        with patch('app.services.deploy_service.create_ssh_connection', return_value=mock_ssh_conn):
            with patch('app.services.deploy_service.settings', mock_settings):
                artifact_path = Path("/tmp/artifact.zip")

                await service._deploy_to_server(mock_server_without_deploy_path, artifact_path)

                # Verify command includes the inline script
                assert mock_ssh_conn.execute_command_streaming.called
                call_args = mock_ssh_conn.execute_command_streaming.call_args
                command = call_args[0][0]
                assert "pm2 restart app && pm2 logs" in command
