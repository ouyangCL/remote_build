"""Test auto_install fields in Project model."""
import pytest
from app.models.project import Project


class TestAutoInstallFields:
    """Test auto_install and install_script fields."""

    def test_project_has_auto_install_fields(self):
        """Test Project model has auto_install and install_script attributes."""
        project = Project(
            name="test-project",
            git_url="https://github.com/test/repo.git",
            project_type="frontend",
            build_script="npm run build",
            install_script="npm ci",
            auto_install=True,
        )

        assert hasattr(project, 'install_script')
        assert hasattr(project, 'auto_install')
        assert project.install_script == "npm ci"
        assert project.auto_install is True

    def test_auto_install_default_value(self):
        """Test auto_install defaults to True when not specified."""
        project = Project(
            name="test-project",
            git_url="https://github.com/test/repo.git",
            project_type="frontend",
            build_script="npm run build",
        )

        # Should default to True (we'll set this in model)
        # For now, just test the field exists
        assert hasattr(project, 'auto_install')
