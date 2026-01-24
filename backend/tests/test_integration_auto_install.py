"""Integration test for auto dependency installation."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from app.services.build_service import BuildService, BuildStatus


@pytest.fixture
def frontend_project_dir(tmp_path):
    """Create a mock frontend project with package.json."""
    project_dir = tmp_path / "frontend"
    project_dir.mkdir()

    # Create package.json
    package_json = project_dir / "package.json"
    package_json.write_text('''{
        "name": "test-project",
        "version": "1.0.0",
        "scripts": {
            "build": "webpack --mode production"
        },
        "devDependencies": {
            "webpack": "^5.0.0",
            "cross-env": "^7.0.0"
        }
    }''')

    # Create mock dist directory (simulating build output)
    dist_dir = project_dir / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text("<html></html>")

    return project_dir


class TestIntegrationAutoInstall:
    """Integration tests for auto dependency installation."""

    @patch('subprocess.Popen')
    def test_frontend_project_installs_before_build(self, mock_popen, frontend_project_dir):
        """Test frontend project runs npm install before build."""
        # Mock npm install process
        mock_install_process = MagicMock()
        mock_install_process.stdout = ["Installing dependencies...", "Done"]
        mock_install_process.returncode = 0
        mock_install_process.wait.return_value = 0

        # Mock build process
        mock_build_process = MagicMock()
        mock_build_process.stdout = ["Building...", "Built"]
        mock_build_process.returncode = 0
        mock_build_process.wait.return_value = 0

        mock_popen.side_effect = [mock_install_process, mock_build_process]

        build_service = BuildService(
            source_dir=frontend_project_dir,
            build_script="npm run build",
            output_dir="dist",
            project_type="frontend",
            auto_install=True,
        )

        result = build_service.build()

        assert result.status == BuildStatus.SUCCESS
        assert mock_popen.call_count == 2  # Once for install, once for build

        # Verify first call was npm install
        first_call = mock_popen.call_args_list[0]
        assert "npm" in first_call[0][0]
        assert "install" in first_call[0][0]

    def test_auto_install_disabled_skips_install(self, frontend_project_dir):
        """Test auto_install=False skips dependency installation."""
        with patch('subprocess.Popen') as mock_popen:
            mock_build_process = MagicMock()
            mock_build_process.stdout = ["Building..."]
            mock_build_process.returncode = 0
            mock_build_process.wait.return_value = 0

            mock_popen.return_value = mock_build_process

            build_service = BuildService(
                source_dir=frontend_project_dir,
                build_script="npm run build",
                output_dir="dist",
                project_type="frontend",
                auto_install=False,
            )

            result = build_service.build()

            assert result.status == BuildStatus.SUCCESS
            assert mock_popen.call_count == 1  # Only build, no install

    def test_custom_install_script_used(self, frontend_project_dir):
        """Test custom install_script overrides default."""
        with patch('subprocess.Popen') as mock_popen:
            mock_install_process = MagicMock()
            mock_install_process.stdout = ["Installing with yarn..."]
            mock_install_process.returncode = 0
            mock_install_process.wait.return_value = 0

            mock_build_process = MagicMock()
            mock_build_process.returncode = 0
            mock_build_process.wait.return_value = 0

            mock_popen.side_effect = [mock_install_process, mock_build_process]

            build_service = BuildService(
                source_dir=frontend_project_dir,
                build_script="npm run build",
                output_dir="dist",
                project_type="frontend",
                install_script="yarn install",
                auto_install=True,
            )

            result = build_service.build()

            assert result.status == BuildStatus.SUCCESS

            # Verify yarn install was used
            first_call = mock_popen.call_args_list[0]
            assert "yarn" in first_call[0][0]

    @patch('subprocess.Popen')
    def test_install_failure_continues_to_build(self, mock_popen, frontend_project_dir):
        """Test that install failure warns but continues to build."""
        # Mock failed npm install
        mock_install_process = MagicMock()
        mock_install_process.stdout = ["Error: npm not found"]
        mock_install_process.returncode = 1
        mock_install_process.wait.return_value = 1

        # Mock successful build (dependencies might be pre-installed)
        mock_build_process = MagicMock()
        mock_build_process.stdout = ["Building..."]
        mock_build_process.returncode = 0
        mock_build_process.wait.return_value = 0

        mock_popen.side_effect = [mock_install_process, mock_build_process]

        build_service = BuildService(
            source_dir=frontend_project_dir,
            build_script="npm run build",
            output_dir="dist",
            project_type="frontend",
            auto_install=True,
        )

        result = build_service.build()

        # Build should still succeed
        assert result.status == BuildStatus.SUCCESS
