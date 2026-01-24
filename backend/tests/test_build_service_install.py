"""Test BuildService dependency installation."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from app.services.build_service import BuildService, BuildStatus


@pytest.fixture
def sample_source_dir(tmp_path):
    """Create a sample source directory."""
    source = tmp_path / "project"
    source.mkdir()
    return source


class TestDependencyInstallation:
    """Test automatic dependency installation."""

    def test_build_service_accepts_project_type(self, sample_source_dir):
        """Test BuildService accepts project_type parameter."""
        build_service = BuildService(
            source_dir=sample_source_dir,
            build_script="npm run build",
            output_dir="dist",
            project_type="frontend",
        )

        assert build_service.project_type == "frontend"

    def test_frontend_gets_npm_install_default(self, sample_source_dir):
        """Test frontend projects get 'npm install' as default."""
        build_service = BuildService(
            source_dir=sample_source_dir,
            build_script="npm run build",
            output_dir="dist",
            project_type="frontend",
            auto_install=True,
        )

        install_cmd = build_service._get_install_command()
        assert install_cmd == "npm install"

    def test_java_gets_maven_default(self, sample_source_dir):
        """Test Java projects get 'mvn dependency:resolve' as default."""
        build_service = BuildService(
            source_dir=sample_source_dir,
            build_script="mvn package",
            output_dir="target",
            project_type="java",
            auto_install=True,
        )

        install_cmd = build_service._get_install_command()
        assert install_cmd == "mvn dependency:resolve"

    def test_backend_no_default_install(self, sample_source_dir):
        """Test backend projects have no default install command."""
        build_service = BuildService(
            source_dir=sample_source_dir,
            build_script="python build.py",
            output_dir="build",
            project_type="backend",
            auto_install=True,
        )

        install_cmd = build_service._get_install_command()
        assert install_cmd is None

    def test_custom_install_script_overrides_default(self, sample_source_dir):
        """Test custom install_script overrides default."""
        build_service = BuildService(
            source_dir=sample_source_dir,
            build_script="npm run build",
            output_dir="dist",
            project_type="frontend",
            install_script="npm ci",
            auto_install=True,
        )

        install_cmd = build_service._get_install_command()
        assert install_cmd == "npm ci"

    def test_auto_install_false_skips_installation(self, sample_source_dir):
        """Test auto_install=False skips dependency installation."""
        build_service = BuildService(
            source_dir=sample_source_dir,
            build_script="npm run build",
            output_dir="dist",
            project_type="frontend",
            auto_install=False,
        )

        install_cmd = build_service._get_install_command()
        assert install_cmd is None
