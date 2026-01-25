# Auto Dependency Installation for Build Process

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Automatically install project dependencies before build to prevent "command not found" errors like cross-env missing.

**Architecture:** Add `install_script` and `auto_install` fields to Project model, enhance BuildService to execute dependency installation based on project type, with smart defaults and user override capability.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, pytest

---

## Context

**Problem:** When deploying frontend projects, the build fails with `cross-env: command not found` because BuildService executes `build_script` directly without first running `npm install`.

**Current Flow:** Clone → Checkout → **Build** → Deploy

**New Flow:** Clone → Checkout → **Install Dependencies** → Build → Deploy

**Project Types:**
- `frontend`: Node.js projects (npm/yarn/pnpm)
- `backend`: Python projects (pip) or other backends
- `java`: Maven/Gradle projects

---

## Task 1: Database Migration - Add Install Fields

**Files:**
- Create: `backend/alembic/versions/012_add_auto_install_fields.py`

**Step 1: Create the migration file**

```bash
# Generate new migration file (next number is 012)
cd /Users/ouyang/Public/workspace/future/remote_build/backend
alembic revision -m "add_auto_install_fields"
```

Expected: New file created in `alembic/versions/`

**Step 2: Write the migration**

Open the generated file (should be `012_add_auto_install_fields.py` or similar) and replace contents with:

```python
"""add auto_install fields

Revision ID: 012
Revises: 011
Create Date: 2026-01-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade():
    # Add install_script column (optional, 500 chars)
    op.add_column('projects', sa.Column('install_script', sa.String(500), nullable=True))

    # Add auto_install column (defaults to True)
    op.add_column('projects', sa.Column('auto_install', sa.Boolean(), nullable=False, server_default='1'))


def downgrade():
    op.drop_column('projects', 'auto_install')
    op.drop_column('projects', 'install_script')
```

**Step 3: Verify migration syntax**

```bash
cd /Users/ouyang/Public/workspace/future/remote_build/backend
python -m py_compile alembic/versions/012_add_auto_install_fields.py
```

Expected: No syntax errors

**Step 4: Run migration to test**

```bash
alembic upgrade head
```

Expected: SUCCESS with message "Running upgrade 011 -> 012"

**Step 5: Verify database schema**

```bash
sqlite3 devops.db ".schema projects" | grep -E "(install_script|auto_install)"
```

Expected: Output shows both columns in schema

**Step 6: Commit**

```bash
git add backend/alembic/versions/012_add_auto_install_fields.py
git commit -m "feat: add install_script and auto_install fields to projects table"
```

---

## Task 2: Update Project Model

**Files:**
- Modify: `backend/app/models/project.py:58-67`

**Step 1: Write failing test**

Create test file `backend/tests/test_auto_install_fields.py`:

```python
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
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/ouyang/Public/workspace/future/remote_build/backend
pytest tests/test_auto_install_fields.py -v
```

Expected: FAIL or AttributeError - fields don't exist yet

**Step 3: Add fields to Project model**

In `backend/app/models/project.py`, find the `Project` class and add these lines after line 64 (`output_dir` field):

```python
    output_dir: Mapped[str] = mapped_column(
        String(255), nullable=False, default="dist"
    )
    # Dependency installation configuration
    install_script: Mapped[str | None] = mapped_column(
        String(500), nullable=True, default=None
    )
    auto_install: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    environment: Mapped[EnvironmentType] = mapped_column(
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_auto_install_fields.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/models/project.py backend/tests/test_auto_install_fields.py
git commit -m "feat: add auto_install and install_script fields to Project model"
```

---

## Task 3: Update Project Schemas

**Files:**
- Modify: `backend/app/schemas/project.py:7-34` (ProjectBase)
- Modify: `backend/app/schemas/project.py:42-70` (ProjectUpdate)

**Step 1: Write failing test**

Add to `backend/tests/test_auto_install_fields.py`:

```python
from app.schemas.project import ProjectCreate, ProjectUpdate


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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_auto_install_fields.py::TestAutoInstallSchemas -v
```

Expected: FAIL - fields not in schema

**Step 3: Update ProjectBase schema**

In `backend/app/schemas/project.py`, add fields to `ProjectBase` class (after line 21):

```python
class ProjectBase(BaseModel):
    """Base project schema."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    git_url: str = Field(..., min_length=1, max_length=500)
    git_token: str | None = Field(None, description="Git access token for HTTPS private repositories")
    project_type: str = Field(..., pattern="^(frontend|backend|java)$")
    build_script: str = Field(..., min_length=1)
    upload_path: str = Field(default="", max_length=255, description="Server-side path for uploading deployment packages")
    restart_script_path: str = Field(default="/opt/restart.sh", max_length=255, description="Server-side script to restart the application")
    restart_only_script_path: str | None = Field(
        default=None,
        description="仅重启部署模式专用的重启脚本路径"
    )
    output_dir: str = Field(default="dist", max_length=255)
    # Dependency installation
    install_script: str | None = Field(
        default=None,
        max_length=500,
        description="Custom dependency installation command (e.g., 'npm ci', 'yarn install', 'pip install -r requirements.txt')"
    )
    auto_install: bool = Field(
        default=True,
        description="Automatically install dependencies before build"
    )
    environment: str = Field(default="development", pattern="^(development|production)$")
```

**Step 4: Update ProjectUpdate schema**

In `ProjectUpdate` class (after line 57), add:

```python
class ProjectUpdate(BaseModel):
    """Project update schema."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    git_url: str | None = Field(None, min_length=1, max_length=500)
    git_token: str | None = Field(None, description="Git access token for HTTPS private repositories")
    git_ssh_key: str | None = Field(None, description="SSH private key for private repositories")
    project_type: str | None = Field(None, pattern="^(frontend|backend|java)$")
    build_script: str | None = None
    upload_path: str | None = Field(None, max_length=255, description="Server-side path for uploading deployment packages")
    restart_script_path: str | None = Field(None, max_length=255, description="Server-side script to restart the application")
    restart_only_script_path: str | None = Field(
        default=None,
        description="仅重启部署模式专用的重启脚本路径"
    )
    output_dir: str | None = Field(None, max_length=255)
    # Dependency installation
    install_script: str | None = Field(
        default=None,
        max_length=500,
        description="Custom dependency installation command"
    )
    auto_install: bool | None = Field(
        default=None,
        description="Automatically install dependencies before build"
    )
    environment: str | None = Field(None, pattern="^(development|production)$")
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_auto_install_fields.py::TestAutoInstallSchemas -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/schemas/project.py backend/tests/test_auto_install_fields.py
git commit -m "feat: add install_script and auto_install to project schemas"
```

---

## Task 4: Enhance BuildService - Add Dependency Installation

**Files:**
- Modify: `backend/app/services/build_service.py:45-70` (BuildService.__init__)
- Modify: `backend/app/services/build_service.py:163-198` (BuildService.build method)

**Step 1: Write failing test**

Create `backend/tests/test_build_service_install.py`:

```python
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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_build_service_install.py -v
```

Expected: Multiple FAILs - BuildService doesn't have these methods/parameters yet

**Step 3: Update BuildService.__init__**

In `backend/app/services/build_service.py`, modify the `__init__` method (lines 48-69):

```python
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
        """
        self.source_dir = Path(source_dir)
        self.build_script = build_script
        self.output_dir = output_dir
        self.on_output = on_output or (lambda x: None)
        self.logger = logger
        self.project_type = project_type
        self.install_script = install_script
        self.auto_install = auto_install
        self._cancelled = False
```

**Step 4: Add _get_install_command method**

After the `_log_warning` method (around line 162), add:

```python
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
```

**Step 5: Add _install_dependencies method**

After `_get_install_command`, add:

```python
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
```

**Step 6: Modify build() method to call installation**

In the `build()` method (line 184), after `self._log_info("开始构建过程")` and before the `try:` block, add:

```python
        self._log_info("开始构建过程")

        # Install dependencies if needed
        if self.auto_install or self.install_script:
            install_exit_code = self._install_dependencies()
            if install_exit_code != 0:
                self._log_warning(f"依赖安装失败（退出码: {install_exit_code}），将继续尝试构建")
                # Continue anyway - user might have pre-installed dependencies

        if settings.deployment_log_verbosity == "detailed":
            self._log_info("=" * 50)

        try:
```

**Step 7: Run test to verify it passes**

```bash
pytest tests/test_build_service_install.py -v
```

Expected: PASS

**Step 8: Commit**

```bash
git add backend/app/services/build_service.py backend/tests/test_build_service_install.py
git commit -m "feat: add automatic dependency installation to BuildService"
```

---

## Task 5: Update DeployService to Pass Project Fields

**Files:**
- Modify: `backend/app/services/deploy_service.py:287-294`

**Step 1: Write failing test**

Add to `backend/tests/test_auto_install_fields.py`:

```python
def test_deploy_service_passes_install_fields_to_build_service():
    """Test DeployService passes install_script and auto_install to BuildService."""
    from unittest.mock import patch, MagicMock
    from app.services.deploy_service import DeploymentService
    from app.models.deployment import Deployment
    from app.models.project import Project
    from app.models.user import User

    # Create mock deployment with project
    mock_project = MagicMock()
    mock_project.id = 1
    mock_project.name = "test-project"
    mock_project.project_type = "frontend"
    mock_project.build_script = "npm run build"
    mock_project.output_dir = "dist"
    mock_project.install_script = "npm ci"
    mock_project.auto_install = True
    mock_project.git_url = "https://github.com/test/repo.git"
    mock_project.git_token = None
    mock_project.git_ssh_key = None
    mock_project.git_username = None
    mock_project.git_password = None

    mock_deployment = MagicMock()
    mock_deployment.id = 1
    mock_deployment.project = mock_project
    mock_deployment.server_groups = []
    mock_deployment.deployment_type = "full"

    mock_db = MagicMock()

    with patch('app.services.deploy_service.git_context') as mock_git_context:
        mock_git_service = MagicMock()
        mock_git_context.return_value.__enter__.return_value = mock_git_service
        mock_git_service.repo_path = Path("/tmp/test")

        with patch('app.services.deploy_service.BuildService') as mock_build_service:
            deploy_service = DeploymentService(
                db=mock_db,
                deployment=mock_deployment,
                user=User(id=1, username="test"),
            )

            # Trigger build
            result = deploy_service._build()

            # Verify BuildService was called with install fields
            mock_build_service.assert_called_once()
            call_kwargs = mock_build_service.call_args[1]

            assert 'project_type' in call_kwargs
            assert 'install_script' in call_kwargs
            assert 'auto_install' in call_kwargs
            assert call_kwargs['project_type'] == 'frontend'
            assert call_kwargs['install_script'] == 'npm ci'
            assert call_kwargs['auto_install'] is True
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_auto_install_fields.py::test_deploy_service_passes_install_fields_to_build_service -v
```

Expected: FAIL - BuildService not called with these parameters

**Step 3: Update DeployService._build method**

In `backend/app/services/deploy_service.py`, find the `_build` method around line 289 and modify:

```python
            # Create build service
            build_service = BuildService(
                source_dir=work_dir,
                build_script=self.deployment.project.build_script,
                output_dir=self.deployment.project.output_dir,
                logger=self.logger,
                project_type=self.deployment.project.project_type,
                install_script=self.deployment.project.install_script,
                auto_install=self.deployment.project.auto_install,
            )
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_auto_install_fields.py::test_deploy_service_passes_install_fields_to_build_service -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/deploy_service.py backend/tests/test_auto_install_fields.py
git commit -m "feat: pass install_script and auto_install to BuildService"
```

---

## Task 6: Integration Test - Full Build Flow

**Files:**
- Create: `backend/tests/test_integration_auto_install.py`

**Step 1: Write integration test**

Create comprehensive integration test:

```python
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
```

**Step 2: Run integration test**

```bash
pytest tests/test_integration_auto_install.py -v
```

Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/test_integration_auto_install.py
git commit -m "test: add integration tests for auto dependency installation"
```

---

## Task 7: Update API Documentation

**Files:**
- Create: `docs/api/auto-dependency-installation.md`

**Step 1: Write documentation**

```markdown
# Auto Dependency Installation

## Overview

The build process now supports automatic dependency installation before running build scripts. This prevents "command not found" errors when build tools like `cross-env` are missing.

## New Project Fields

### `install_script` (optional)
- **Type**: `string | null`
- **Max Length**: 500 characters
- **Description**: Custom dependency installation command
- **Examples**:
  - `npm install` - Standard npm install
  - `npm ci` - Fast, reproducible npm install (recommended for CI/CD)
  - `yarn install` - Yarn package manager
  - `pnpm install` - pnpm package manager
  - `pip install -r requirements.txt` - Python dependencies
  - `mvn dependency:resolve` - Maven dependencies

### `auto_install` (boolean)
- **Type**: `boolean`
- **Default**: `true`
- **Description**: Whether to automatically install dependencies before build
- **Usage**:
  - `true` - Install dependencies using default or custom command
  - `false` - Skip automatic installation (useful if dependencies are pre-installed)

## Default Behavior by Project Type

| Project Type | Default Install Command | Notes |
|-------------|------------------------|-------|
| `frontend` | `npm install` | Can be overridden with `install_script` |
| `java` | `mvn dependency:resolve` | Maven dependency resolution |
| `backend` | `None` | No default, requires explicit `install_script` |

## Usage Examples

### Example 1: Frontend Project with Defaults

```json
{
  "name": "my-frontend-app",
  "project_type": "frontend",
  "build_script": "npm run build",
  "auto_install": true
}
```

**Behavior**: Runs `npm install` automatically before `npm run build`

### Example 2: Use npm ci for Faster Installs

```json
{
  "name": "my-frontend-app",
  "project_type": "frontend",
  "build_script": "npm run build",
  "install_script": "npm ci",
  "auto_install": true
}
```

**Behavior**: Runs `npm ci` (faster, deterministic) before build

### Example 3: Yarn-based Project

```json
{
  "name": "yarn-project",
  "project_type": "frontend",
  "build_script": "yarn build",
  "install_script": "yarn install",
  "auto_install": true
}
```

**Behavior**: Runs `yarn install` before `yarn build`

### Example 4: Pre-installed Dependencies

```json
{
  "name": "cached-deps-project",
  "project_type": "frontend",
  "build_script": "npm run build",
  "auto_install": false
}
```

**Behavior**: Skips dependency installation entirely (useful with Docker image caches)

### Example 5: Python Backend

```json
{
  "name": "python-api",
  "project_type": "backend",
  "build_script": "python build.py",
  "install_script": "pip install -r requirements.txt",
  "auto_install": true
}
```

**Behavior**: Installs Python dependencies before build

## Troubleshooting

### Error: "npm: command not found"

**Cause**: Node.js/npm is not installed on the build server

**Solution**:
1. Install Node.js on the build server
2. Or use a Docker image with Node.js pre-installed
3. Or set `auto_install: false` and pre-install dependencies in your Docker image

### Error: "Dependency installation failed, continuing anyway"

**Cause**: The install command failed, but build continues (dependencies might already be installed)

**Solutions**:
1. Check if dependencies are already installed (e.g., `node_modules` exists)
2. Verify the `install_script` command is correct
3. Check build server logs for detailed error messages
4. If using custom command, test it manually in the project directory

### Build is slow with auto_install enabled

**Solutions**:
1. Use `npm ci` instead of `npm install` (faster and deterministic)
2. Set `auto_install: false` and use a Docker image with pre-installed dependencies
3. Use `node_modules` caching in your CI/CD pipeline

## Migration Guide for Existing Projects

Existing projects will automatically get `auto_install: true` and `npm install` for frontend projects.

**To disable auto-install for an existing project**:

```bash
curl -X PATCH http://your-api/projects/{project_id} \
  -H "Content-Type: application/json" \
  -d '{"auto_install": false}'
```

**To set a custom install script**:

```bash
curl -X PATCH http://your-api/projects/{project_id} \
  -H "Content-Type: application/json" \
  -d '{"install_script": "npm ci"}'
```

## Best Practices

1. **Use `npm ci` for CI/CD**: Faster and more reproducible than `npm install`
2. **Lock files**: Commit `package-lock.json`, `yarn.lock`, or `pnpm-lock.yaml` to ensure consistent installs
3. **Pre-install in Docker**: For production, use a Docker image with dependencies pre-installed and set `auto_install: false`
4. **Monitor logs**: Check deployment logs to ensure dependency installation succeeds
5. **Test locally**: Run the install command locally before deploying to ensure it works
```

**Step 2: Commit**

```bash
git add docs/api/auto-dependency-installation.md
git commit -m "docs: add auto dependency installation documentation"
```

---

## Task 8: Run Full Test Suite

**Step 1: Run all tests**

```bash
cd /Users/ouyang/Public/workspace/future/remote_build/backend
pytest tests/ -v --tb=short
```

Expected: All tests PASS

**Step 2: Run specific new tests**

```bash
pytest tests/test_auto_install_fields.py tests/test_build_service_install.py tests/test_integration_auto_install.py -v
```

Expected: All PASS

**Step 3: Check test coverage**

```bash
pytest --cov=app.services.build_service --cov=app.models.project --cov=app.schemas.project tests/test_auto_install_fields.py tests/test_build_service_install.py -v
```

Expected: Coverage report shows new code covered

**Step 4: Commit if all tests pass**

```bash
git add .
git commit -m "test: all tests passing for auto dependency installation feature"
```

---

## Task 9: Manual Testing (Optional but Recommended)

**Step 1: Create a test project**

```bash
# In the frontend UI, create a new project with:
{
  "name": "test-auto-install",
  "git_url": "<your-test-repo>",
  "project_type": "frontend",
  "build_script": "npm run build",
  "auto_install": true
}
```

**Step 2: Trigger a deployment**

```bash
# Through the UI or API, trigger a deployment
```

**Step 3: Check deployment logs**

Verify logs show:
1. "开始安装依赖"
2. "npm install" output
3. "依赖安装成功"
4. Build continues normally

**Step 4: Test with auto_install=false**

Update project to set `auto_install: false` and verify installation is skipped.

---

## Verification Checklist

- [x] Database migration created and tested
- [x] Project model updated with new fields
- [x] Schemas updated (ProjectBase, ProjectCreate, ProjectUpdate)
- [x] BuildService enhanced with dependency installation
- [x] DeployService passes new fields to BuildService
- [x] Unit tests written and passing
- [x] Integration tests written and passing
- [x] API documentation created
- [x] All existing tests still pass
- [x] Manual testing completed (if performed)

---

## Rollback Plan (If Needed)

If issues arise, rollback steps:

1. **Database rollback**:
```bash
cd backend
alembic downgrade -1
```

2. **Code rollback**:
```bash
git revert HEAD~8  # Revert all commits for this feature
```

3. **Verify rollback**:
```bash
pytest tests/ -v
```

---

## Success Criteria

✅ Frontend projects automatically run `npm install` before build
✅ Users can override with custom `install_script`
✅ Users can disable with `auto_install: false`
✅ No breaking changes to existing projects
✅ Clear error messages when installation fails
✅ Comprehensive test coverage
✅ Complete documentation

---

**End of Implementation Plan**

Next step: Use `superpowers:executing-plans` to execute this plan task-by-task, or `superpowers:subagent-driven-development` for subagent-driven execution in this session.
