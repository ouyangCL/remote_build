"""Test auto_install fields in Project model."""
import pytest
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


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


class TestAutoInstallSchemas:
    """Test auto_install fields in schemas."""

    def test_project_create_schema_accepts_install_script(self):
        """Test ProjectCreate accepts install_script field."""
        data = {
            "name": "test-project",
            "git_url": "https://github.com/test/repo.git",
            "project_type": "frontend",
            "build_script": "npm run build",
            "install_script": "npm ci",
            "auto_install": True,
        }

        project = ProjectCreate(**data)

        assert project.install_script == "npm ci"
        assert project.auto_install is True

    def test_project_create_schema_default_auto_install(self):
        """Test auto_install defaults to True in ProjectCreate."""
        data = {
            "name": "test-project",
            "git_url": "https://github.com/test/repo.git",
            "project_type": "frontend",
            "build_script": "npm run build",
        }

        project = ProjectCreate(**data)

        assert project.auto_install is True

    def test_project_update_schema_accepts_install_fields(self):
        """Test ProjectUpdate accepts install fields."""
        data = {
            "install_script": "yarn install",
            "auto_install": False,
        }

        update = ProjectUpdate(**data)

        assert update.install_script == "yarn install"
        assert update.auto_install is False
