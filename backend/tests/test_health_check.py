"""Tests for health check service."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.deployment import DeploymentStatus
from app.models.project import HealthCheckType, ProjectType
from app.services.health_check_service import HealthCheckError, HealthCheckService


@pytest.fixture
def mock_project():
    """Create a mock project."""
    project = MagicMock()
    project.health_check_enabled = True
    project.health_check_type = HealthCheckType.HTTP
    project.health_check_url = "http://localhost:8080/health"
    project.health_check_port = 8080
    project.health_check_command = "curl -f http://localhost:8080/health || exit 1"
    project.health_check_timeout = 30
    project.health_check_retries = 3
    project.health_check_interval = 5
    return project


@pytest.fixture
def mock_server():
    """Create a mock server."""
    server = MagicMock()
    server.host = "192.168.1.100"
    server.deploy_path = "/opt/app"
    server.is_active = True
    return server


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    logger = AsyncMock()
    logger.info = AsyncMock()
    logger.warning = AsyncMock()
    logger.error = AsyncMock()
    return logger


class TestHealthCheckService:
    """Test health check service."""

    @pytest.mark.asyncio
    async def test_http_health_check_success(self, mock_project, mock_server, mock_logger):
        """Test successful HTTP health check."""
        with patch("httpx.AsyncClient") as mock_client_class:
            # Mock successful response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            service = HealthCheckService(mock_project, mock_server, mock_logger)
            result = await service.check()

            assert result is True
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_http_health_check_failure(self, mock_project, mock_server, mock_logger):
        """Test failed HTTP health check."""
        with patch("httpx.AsyncClient") as mock_client_class:
            # Mock failed response
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            service = HealthCheckService(mock_project, mock_server, mock_logger)
            result = await service.check()

            assert result is False
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_http_health_check_disabled(self, mock_project, mock_server, mock_logger):
        """Test health check when disabled."""
        mock_project.health_check_enabled = False

        service = HealthCheckService(mock_project, mock_server, mock_logger)
        result = await service.check()

        assert result is True
        mock_logger.info.assert_called_with("健康检查已禁用，跳过")

    @pytest.mark.asyncio
    async def test_http_health_check_missing_url(self, mock_project, mock_server, mock_logger):
        """Test HTTP health check without URL."""
        mock_project.health_check_url = None

        service = HealthCheckService(mock_project, mock_server, mock_logger)

        with pytest.raises(HealthCheckError, match="HTTP 健康检查需要配置 health_check_url"):
            await service.check()

    @pytest.mark.asyncio
    async def test_tcp_health_check_success(self, mock_project, mock_server, mock_logger):
        """Test successful TCP health check."""
        mock_project.health_check_type = HealthCheckType.TCP

        with patch("socket.socket") as mock_socket_class:
            # Mock successful connection
            mock_socket = MagicMock()
            mock_socket.connect_ex.return_value = 0  # Success
            mock_socket_class.return_value = mock_socket

            service = HealthCheckService(mock_project, mock_server, mock_logger)
            result = await service.check()

            assert result is True
            mock_socket.close.assert_called()

    @pytest.mark.asyncio
    async def test_tcp_health_check_failure(self, mock_project, mock_server, mock_logger):
        """Test failed TCP health check."""
        mock_project.health_check_type = HealthCheckType.TCP

        with patch("socket.socket") as mock_socket_class:
            # Mock failed connection
            mock_socket = MagicMock()
            mock_socket.connect_ex.return_value = 111  # Connection refused
            mock_socket_class.return_value = mock_socket

            service = HealthCheckService(mock_project, mock_server, mock_logger)
            result = await service.check()

            assert result is False
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_tcp_health_check_missing_port(self, mock_project, mock_server, mock_logger):
        """Test TCP health check without port."""
        mock_project.health_check_type = HealthCheckType.TCP
        mock_project.health_check_port = None

        service = HealthCheckService(mock_project, mock_server, mock_logger)

        with pytest.raises(HealthCheckError, match="TCP 健康检查需要配置 health_check_port"):
            await service.check()

    @pytest.mark.asyncio
    async def test_command_health_check_success(self, mock_project, mock_server, mock_logger):
        """Test successful command health check."""
        mock_project.health_check_type = HealthCheckType.COMMAND

        # Mock SSH connection
        mock_ssh = MagicMock()
        mock_ssh.execute_command_streaming.return_value = (0, "success", "")

        service = HealthCheckService(mock_project, mock_server, mock_logger, mock_ssh)
        result = await service.check()

        assert result is True
        mock_ssh.execute_command_streaming.assert_called_once()

    @pytest.mark.asyncio
    async def test_command_health_check_failure(self, mock_project, mock_server, mock_logger):
        """Test failed command health check."""
        mock_project.health_check_type = HealthCheckType.COMMAND

        # Mock SSH connection
        mock_ssh = MagicMock()
        mock_ssh.execute_command_streaming.return_value = (1, "", "error")

        service = HealthCheckService(mock_project, mock_server, mock_logger, mock_ssh)
        result = await service.check()

        assert result is False
        mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_command_health_check_missing_connection(self, mock_project, mock_server, mock_logger):
        """Test command health check without SSH connection."""
        mock_project.health_check_type = HealthCheckType.COMMAND

        service = HealthCheckService(mock_project, mock_server, mock_logger, None)

        with pytest.raises(HealthCheckError, match="命令健康检查需要 SSH 连接"):
            await service.check()

    @pytest.mark.asyncio
    async def test_command_health_check_missing_command(self, mock_project, mock_server, mock_logger):
        """Test command health check without command."""
        mock_project.health_check_type = HealthCheckType.COMMAND
        mock_project.health_check_command = None

        mock_ssh = MagicMock()

        service = HealthCheckService(mock_project, mock_server, mock_logger, mock_ssh)

        with pytest.raises(HealthCheckError, match="命令健康检查需要配置 health_check_command"):
            await service.check()
